"""
Voice Engine Entry Point
FastAPI application for handling Twilio WebSocket connections and Gemini Live API.
"""

import asyncio
import json
import os
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)
from fastapi import FastAPI, WebSocket, Request, Form, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from starlette.websockets import WebSocketState
from contextlib import asynccontextmanager

import redis.asyncio as redis
from src.brain.gemini_client import GeminiLiveClient
from src.brain.prompts import build_outbound_prompt
from src.stream.twilio_handler import TwilioMediaHandler
from src.db import get_db_client, PostgresClient
from src.redis_client import set_redis_client, get_redis_client as get_module_redis
from src.orchestrator import CascadeOrchestrator
from src.orchestrator.events import CASCADE_EVENTS_CHANNEL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# In-memory fallback for call context when Redis is unavailable
_call_context_store: dict[str, dict] = {}


def get_database_client() -> PostgresClient | None:
    """Initialize database client from environment variables."""
    return get_db_client()


async def get_redis_client() -> redis.Redis | None:
    """Initialize Redis client from environment variables."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        logger.info(f"Connected to Redis at {redis_url}")
        return client
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - Redis disabled")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    logger.info("Starting Voice Engine...")

    # Initialize database client
    app.state.db = get_database_client()
    if app.state.db:
        logger.info("Database client initialized")

    # Initialize Redis connection pool
    app.state.redis = await get_redis_client()
    set_redis_client(app.state.redis)

    yield

    # Cleanup resources
    logger.info("Shutting down Voice Engine...")
    if app.state.db:
        app.state.db.close()
        logger.info("Database connection closed")
    if app.state.redis:
        await app.state.redis.close()
        logger.info("Redis connection closed")


app = FastAPI(
    title="Sam Voice Engine",
    description="AI Voice Agent for Restaurant Reservations",
    lifespan=lifespan,
)

# Active cascade orchestrators keyed by request_id
_active_cascades: dict[str, CascadeOrchestrator] = {}


# ============================================
# Pydantic models for cascade API
# ============================================

class CascadeStartBody(BaseModel):
    request_id: str

class CascadeRequestBody(BaseModel):
    request_id: str

class CascadeReorderBody(BaseModel):
    request_id: str
    restaurant_order: list[str]


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}


@app.post("/ws/twilio")
async def twilio_incoming_call(request: Request):
    """
    Handle incoming Twilio call webhook.
    Returns TwiML to connect the call to our WebSocket stream.
    """
    # Get the host from the request to build WebSocket URL
    host = request.headers.get("host", "localhost:8000")

    # Use wss:// for production (https), ws:// for local
    protocol = "wss" if "trycloudflare.com" in host or "https" in str(request.url) else "ws"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Please wait while we connect you.</Say>
    <Connect>
        <Stream url="{protocol}://{host}/ws/twilio/stream" />
    </Connect>
</Response>"""

    logger.info(f"Incoming call - connecting to {protocol}://{host}/ws/twilio/stream")
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws/twilio/stream")
async def twilio_websocket(websocket: WebSocket):
    """
    Twilio Media Stream WebSocket endpoint.
    Receives 8kHz μ-law audio, transcodes to 16kHz LPCM16, streams to Gemini.
    Supports both inbound and outbound calls via context_id query param.
    """
    await websocket.accept()

    # Check for outbound call context via query params
    context_id = websocket.query_params.get("context_id")
    call_context = None
    system_prompt = None

    if context_id:
        # Outbound call - retrieve context
        call_context = await _get_call_context(app.state.redis, context_id)
        if call_context:
            logger.info(f"Outbound call with context: {context_id}")
            # Build system prompt from context
            system_prompt = build_outbound_prompt(
                user_name=call_context.get("user_name", "the customer"),
                restaurant_name=call_context.get("restaurant_name", "the restaurant"),
                party_size=call_context.get("party_size", 2),
                preferred_date=call_context.get("requested_date", ""),
                preferred_time=call_context.get("time_range_start", ""),
                time_range_start=call_context.get("time_range_start", ""),
                time_range_end=call_context.get("time_range_end", ""),
                contact_phone=call_context.get("contact_phone", ""),
                special_requests=call_context.get("special_requests", ""),
            )

    # Use shared db client from app.state
    handler = TwilioMediaHandler(
        websocket,
        db=app.state.db,
        call_context=call_context,
        system_prompt=system_prompt,
    )
    gemini = GeminiLiveClient(system_prompt=system_prompt)

    try:
        await handler.handle_stream(gemini)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()


async def _get_call_context(redis_client: redis.Redis | None, context_id: str) -> dict | None:
    """Retrieve call context from Redis or in-memory fallback."""
    if redis_client:
        try:
            data = await redis_client.get(f"call_context:{context_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get context from Redis: {e}")

    # Fallback to in-memory store
    return _call_context_store.get(context_id)


async def _store_call_context(redis_client: redis.Redis | None, context_id: str, context: dict) -> None:
    """Store call context in Redis or in-memory fallback."""
    if redis_client:
        try:
            await redis_client.setex(
                f"call_context:{context_id}",
                300,  # 5 minute TTL
                json.dumps(context)
            )
            return
        except Exception as e:
            logger.warning(f"Failed to store context in Redis: {e}")

    # Fallback to in-memory store
    _call_context_store[context_id] = context


@app.post("/ws/twilio/outbound-twiml")
async def twilio_outbound_twiml(request: Request):
    """
    TwiML webhook for outbound calls.
    Called by Twilio when the restaurant answers.
    Returns TwiML to connect the call to our WebSocket stream with context params.
    """
    context_id = request.query_params.get("context_id")
    if not context_id:
        logger.error("Outbound TwiML called without context_id")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Configuration error. Goodbye.</Say></Response>',
            media_type="application/xml"
        )

    # Get the host from the request to build WebSocket URL
    host = request.headers.get("host", "localhost:8000")
    protocol = "wss" if "trycloudflare.com" in host or "https" in str(request.url) else "ws"

    # Retrieve context to include params in stream
    call_context = await _get_call_context(app.state.redis, context_id)
    if not call_context:
        logger.error(f"No context found for context_id: {context_id}")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Configuration error. Goodbye.</Say></Response>',
            media_type="application/xml"
        )

    # Build TwiML with custom parameters
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{protocol}://{host}/ws/twilio/stream?context_id={context_id}">
            <Parameter name="call_type" value="outbound" />
            <Parameter name="request_id" value="{call_context.get('request_id', '')}" />
            <Parameter name="restaurant_id" value="{call_context.get('restaurant_id', '')}" />
            <Parameter name="context_id" value="{context_id}" />
        </Stream>
    </Connect>
</Response>"""

    logger.info(f"Outbound call answered - connecting to stream with context: {context_id}")
    return Response(content=twiml, media_type="application/xml")


# ============================================
# CASCADE API ENDPOINTS
# ============================================


@app.post("/api/cascade/start")
async def cascade_start(body: CascadeStartBody):
    """Start a cascade for a reservation request."""
    if not app.state.db:
        raise HTTPException(status_code=503, detail="Database unavailable")

    request_id = body.request_id

    if request_id in _active_cascades:
        raise HTTPException(status_code=409, detail="Cascade already active for this request")

    orchestrator = CascadeOrchestrator(app.state.db, request_id)
    _active_cascades[request_id] = orchestrator
    await orchestrator.start()

    return {"status": "started", "request_id": request_id}


@app.post("/api/cascade/pause")
async def cascade_pause(body: CascadeRequestBody):
    """Pause an active cascade."""
    orchestrator = _active_cascades.get(body.request_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="No active cascade for this request")
    await orchestrator.pause()
    return {"status": "paused", "request_id": body.request_id}


@app.post("/api/cascade/resume")
async def cascade_resume(body: CascadeRequestBody):
    """Resume a paused cascade."""
    orchestrator = _active_cascades.get(body.request_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="No active cascade for this request")
    await orchestrator.resume()
    return {"status": "resumed", "request_id": body.request_id}


@app.post("/api/cascade/skip")
async def cascade_skip(body: CascadeRequestBody):
    """Skip the current restaurant in the cascade."""
    orchestrator = _active_cascades.get(body.request_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="No active cascade for this request")
    await orchestrator.skip()
    return {"status": "skipping", "request_id": body.request_id}


@app.post("/api/cascade/reorder")
async def cascade_reorder(body: CascadeReorderBody):
    """Reorder restaurants in the cascade."""
    orchestrator = _active_cascades.get(body.request_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="No active cascade for this request")
    await orchestrator.reorder(body.restaurant_order)
    return {"status": "reordered", "request_id": body.request_id}


@app.post("/api/cascade/cancel")
async def cascade_cancel(body: CascadeRequestBody):
    """Cancel a cascade."""
    orchestrator = _active_cascades.get(body.request_id)
    if not orchestrator:
        raise HTTPException(status_code=404, detail="No active cascade for this request")
    await orchestrator.cancel()
    _active_cascades.pop(body.request_id, None)
    return {"status": "cancelled", "request_id": body.request_id}


@app.get("/api/cascade/status/{request_id}")
async def cascade_status(request_id: str):
    """Get cascade status for a request."""
    if not app.state.db:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Load request
    req_result = app.state.db.table("requests").select("*").eq(
        "id", request_id
    ).execute()
    if not req_result.data:
        raise HTTPException(status_code=404, detail="Request not found")
    req = req_result.data[0]

    # Load restaurants
    restaurants = app.state.db.table("request_restaurants").select("*").eq(
        "request_id", request_id
    ).order("priority", ascending=True).execute()

    # Load recent events
    events = app.state.db.table("cascade_events").select("*").eq(
        "request_id", request_id
    ).order("created_at", ascending=False).execute()

    return {
        "request_id": request_id,
        "cascade_status": req.get("cascade_status", "idle"),
        "current_restaurant_idx": req.get("current_restaurant_idx", 0),
        "restaurants": restaurants.data,
        "recent_events": events.data[:20],  # Last 20 events
    }


@app.get("/api/cascade/events/{request_id}")
async def cascade_events_sse(request_id: str):
    """SSE stream of cascade events for a request."""
    redis_client = app.state.redis
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis unavailable for SSE")

    async def event_generator():
        pubsub = redis_client.pubsub()
        channel = CASCADE_EVENTS_CHANNEL.format(request_id=request_id)
        await pubsub.subscribe(channel)

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue

                if msg is None:
                    yield ": keepalive\n\n"
                    continue

                if msg["type"] != "message":
                    continue

                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()

                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/calls/status-callback")
async def twilio_status_callback(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str | None = Form(None),
):
    """
    Twilio status callback endpoint.
    Receives lifecycle events (initiated, ringing, answered, completed, busy, no-answer, failed).
    Publishes to Redis so the cascade orchestrator can react.
    """
    logger.info(f"Twilio status callback: sid={CallSid} status={CallStatus} duration={CallDuration}")

    # Update call record in database
    if app.state.db:
        try:
            update_data: dict = {"twilio_status": CallStatus}
            if CallDuration:
                update_data["duration_seconds"] = int(CallDuration)
            app.state.db.table("calls").update(update_data).eq("twilio_sid", CallSid).execute()
        except Exception as e:
            logger.error(f"Failed to update call status in DB: {e}")

    # Publish to Redis for orchestrator
    redis = app.state.redis
    if redis:
        import json
        message = json.dumps({
            "call_sid": CallSid,
            "status": CallStatus,
            "duration": CallDuration,
        })
        try:
            await redis.publish(f"call_status:{CallSid}", message)
        except Exception as e:
            logger.error(f"Failed to publish call status to Redis: {e}")

    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
