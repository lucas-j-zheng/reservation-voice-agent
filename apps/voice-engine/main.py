"""
Voice Engine Entry Point
FastAPI application for handling Twilio WebSocket connections and Gemini Live API.
"""

from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager

from src.brain.gemini_client import GeminiLiveClient
from src.stream.twilio_handler import TwilioMediaHandler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    # TODO: Initialize Redis connection pool
    # TODO: Initialize database connection
    yield
    # Cleanup resources


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

    handler = TwilioMediaHandler(websocket)
    gemini = GeminiLiveClient()

    try:
        await handler.handle_stream(gemini)
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
