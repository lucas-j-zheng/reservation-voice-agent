"""
Voice Engine Entry Point
FastAPI application for handling Twilio WebSocket connections and Gemini Live API.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
from contextlib import asynccontextmanager

import redis.asyncio as redis

from src.brain.gemini_client import GeminiLiveClient
from src.stream.twilio_handler import TwilioMediaHandler
from src.db import get_db_client, PostgresClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
    """
    await websocket.accept()

    # Use shared db client from app.state
    handler = TwilioMediaHandler(websocket, db=app.state.db)
    gemini = GeminiLiveClient()

    try:
        await handler.handle_stream(gemini)
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
