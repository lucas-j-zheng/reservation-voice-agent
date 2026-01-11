"""
Voice Engine Entry Point
FastAPI application for handling Twilio WebSocket connections and Gemini Live API.
"""

import os
import logging
from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager

import redis.asyncio as redis
from supabase import create_client, Client

from src.brain.gemini_client import GeminiLiveClient
from src.stream.twilio_handler import TwilioMediaHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_supabase_client() -> Client | None:
    """Initialize Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_SERVICE_KEY not set - database disabled")
        return None
    return create_client(url, key)


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

    # Initialize Supabase client
    app.state.db = get_supabase_client()
    if app.state.db:
        logger.info("Supabase client initialized")

    # Initialize Redis connection pool
    app.state.redis = await get_redis_client()

    yield

    # Cleanup resources
    logger.info("Shutting down Voice Engine...")
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


@app.websocket("/ws/twilio")
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
