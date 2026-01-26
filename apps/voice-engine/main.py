"""
Voice Engine Entry Point
FastAPI application for handling Twilio WebSocket connections and Gemini Live API.
"""

import os
import json
import uuid
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import Response
from contextlib import asynccontextmanager
from pydantic import BaseModel

import redis.asyncio as redis
from twilio.rest import Client as TwilioClient

from src.brain.gemini_client import GeminiLiveClient
from src.brain.prompts import build_outbound_prompt
from src.stream.twilio_handler import TwilioMediaHandler
from src.db import get_db_client, PostgresClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Pydantic models for outbound call API
class InitiateOutboundCallRequest(BaseModel):
    """Request to start an outbound call."""
    request_id: str  # UUID of existing reservation_request
    restaurant_id: str  # UUID of restaurant to call


class InitiateOutboundCallResponse(BaseModel):
    """Response from outbound call initiation."""
    call_sid: str
    status: str


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


@app.post("/api/calls/outbound", response_model=InitiateOutboundCallResponse)
async def initiate_outbound_call(request: Request, body: InitiateOutboundCallRequest):
    """
    Initiate an outbound call for a reservation request.

    1. Validates request_id exists and is pending/in_progress
    2. Validates restaurant_id exists and has phone number
    3. Stores call context in Redis
    4. Initiates Twilio call
    5. Returns call_sid for tracking
    """
    db = app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Validate and fetch reservation request
    request_result = db.table("reservation_requests").select("*").eq("id", body.request_id).execute()
    if not request_result.data:
        raise HTTPException(status_code=404, detail="Reservation request not found")

    reservation_request = request_result.data[0]
    if reservation_request.get("status") not in ("pending", "in_progress"):
        raise HTTPException(
            status_code=400,
            detail=f"Request status is '{reservation_request.get('status')}', must be pending or in_progress"
        )

    # Validate and fetch restaurant
    restaurant_result = db.table("restaurants").select("*").eq("id", body.restaurant_id).execute()
    if not restaurant_result.data:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    restaurant = restaurant_result.data[0]
    if not restaurant.get("phone"):
        raise HTTPException(status_code=400, detail="Restaurant has no phone number")

    # Fetch user for name
    user_result = db.table("users").select("*").eq("id", reservation_request.get("user_id")).execute()
    user_name = "the customer"
    contact_phone = ""
    if user_result.data:
        user = user_result.data[0]
        user_name = user.get("name", "the customer")
        contact_phone = user.get("phone", "")

    # Generate context ID and store context
    context_id = str(uuid.uuid4())

    # Convert date/time objects to strings for JSON serialization
    requested_date = reservation_request.get("requested_date", "")
    time_range_start = reservation_request.get("time_range_start", "")
    time_range_end = reservation_request.get("time_range_end", "")

    if hasattr(requested_date, 'isoformat'):
        requested_date = requested_date.isoformat()
    if hasattr(time_range_start, 'isoformat'):
        time_range_start = time_range_start.isoformat()
    if hasattr(time_range_end, 'isoformat'):
        time_range_end = time_range_end.isoformat()

    call_context = {
        "call_type": "outbound",
        "request_id": body.request_id,
        "restaurant_id": body.restaurant_id,
        "restaurant_name": restaurant.get("name", "the restaurant"),
        "user_name": user_name,
        "party_size": reservation_request.get("party_size", 2),
        "requested_date": str(requested_date) if requested_date else "",
        "time_range_start": str(time_range_start) if time_range_start else "",
        "time_range_end": str(time_range_end) if time_range_end else "",
        "special_requests": reservation_request.get("special_requests", ""),
        "contact_phone": contact_phone,
    }

    await _store_call_context(app.state.redis, context_id, call_context)
    logger.info(f"Stored call context: {context_id}")

    # Get host for TwiML webhook URL
    host = request.headers.get("host", "localhost:8000")
    protocol = "https" if "trycloudflare.com" in host else "http"

    # Initialize Twilio client
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not all([twilio_account_sid, twilio_auth_token, twilio_phone_number]):
        raise HTTPException(status_code=503, detail="Twilio credentials not configured")

    twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)

    try:
        # Create the outbound call
        call = twilio_client.calls.create(
            to=restaurant.get("phone"),
            from_=twilio_phone_number,
            url=f"{protocol}://{host}/ws/twilio/outbound-twiml?context_id={context_id}",
        )

        logger.info(f"Initiated outbound call: {call.sid} to {restaurant.get('phone')}")

        # Update reservation request status
        db.table("reservation_requests").update({
            "status": "in_progress"
        }).eq("id", body.request_id).execute()

        return InitiateOutboundCallResponse(
            call_sid=call.sid,
            status="initiated"
        )

    except Exception as e:
        logger.error(f"Failed to initiate outbound call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call: {str(e)}")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
