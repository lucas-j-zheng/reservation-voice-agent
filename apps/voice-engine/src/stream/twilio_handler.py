"""
Twilio Media Stream Handler
Manages WebSocket connection with Twilio for real-time audio.
"""

import asyncio
import json
import base64
import logging
from typing import Literal
from fastapi import WebSocket
from pydantic import BaseModel, ValidationError

import sys
from pathlib import Path

# Add libs to path for local development
libs_path = Path(__file__).parent.parent.parent.parent.parent / "libs"
sys.path.insert(0, str(libs_path))

from audio_utils import transcode_mulaw_to_pcm, transcode_pcm_24k_to_mulaw
from src.brain.gemini_client import GeminiLiveClient
from src.tools.save_booking import save_booking
from src.db import get_db_client, PostgresClient

logger = logging.getLogger(__name__)


# Pydantic models for Twilio WebSocket message validation
class TwilioStartData(BaseModel):
    """Data payload for 'start' event."""
    streamSid: str
    callSid: str


class TwilioMediaData(BaseModel):
    """Data payload for 'media' event."""
    payload: str  # Base64 encoded audio


class TwilioStartMessage(BaseModel):
    """Twilio 'start' event message."""
    event: Literal["start"]
    start: TwilioStartData


class TwilioMediaMessage(BaseModel):
    """Twilio 'media' event message."""
    event: Literal["media"]
    media: TwilioMediaData


class TwilioConnectedMessage(BaseModel):
    """Twilio 'connected' event message."""
    event: Literal["connected"]


class TwilioStopMessage(BaseModel):
    """Twilio 'stop' event message."""
    event: Literal["stop"]


class TwilioBaseMessage(BaseModel):
    """Base message to extract event type."""
    event: str


def get_database_client() -> PostgresClient | None:
    """Get database client instance."""
    return get_db_client()


class TwilioMediaHandler:
    """
    Handles Twilio Media Stream WebSocket protocol.

    Twilio sends 8kHz μ-law audio, we transcode to 16kHz LPCM16 for Gemini.
    Gemini responds with 24kHz LPCM16, we transcode back to 8kHz μ-law for Twilio.
    """

    def __init__(self, websocket: WebSocket, db: PostgresClient | None = None):
        self.websocket = websocket
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.call_id: str | None = None  # Database record ID
        self._db = db or get_database_client()
        self._outbound_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._is_speaking = False
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._booking_saved = False  # Track if booking was saved

    async def handle_stream(self, gemini: GeminiLiveClient) -> None:
        """
        Main loop for handling Twilio media stream.
        Processes incoming audio and routes to Gemini.
        """
        await gemini.connect()
        self._running = True

        # Register tool callback to handle save_booking calls from Gemini
        gemini.on_tool_call(self._handle_tool_call)

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._gemini_receive_loop(gemini)),
            asyncio.create_task(self._outbound_audio_loop()),
        ]

        try:
            async for message in self.websocket.iter_text():
                await self._process_message(message, gemini)
        finally:
            self._running = False
            # Cancel background tasks
            for task in self._tasks:
                task.cancel()
            # Wait for tasks to complete
            await asyncio.gather(*self._tasks, return_exceptions=True)
            await gemini.close()

    async def _process_message(self, message: str, gemini: GeminiLiveClient) -> None:
        """Process a single Twilio WebSocket message with validation."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WebSocket message: {e}")
            return

        # Extract event type first
        try:
            base_msg = TwilioBaseMessage.model_validate(data)
            event = base_msg.event
        except ValidationError as e:
            logger.error(f"Invalid message format (missing event): {e}")
            return

        if event == "connected":
            # Connection established
            try:
                TwilioConnectedMessage.model_validate(data)
                logger.info("Twilio WebSocket connected")
            except ValidationError as e:
                logger.warning(f"Connected event validation warning: {e}")

        elif event == "start":
            # Stream started - capture metadata
            try:
                msg = TwilioStartMessage.model_validate(data)
                self.stream_sid = msg.start.streamSid
                self.call_sid = msg.start.callSid
                logger.info(f"Stream started: {self.stream_sid}, call: {self.call_sid}")

                # Create call record in database
                await self._create_call_record()

                # Send initial prompt to trigger Gemini's greeting
                await gemini.send_text("The call has connected. Please introduce yourself and ask how you can help.")
            except ValidationError as e:
                logger.error(f"Invalid start message: {e}")
                return

        elif event == "media":
            # Incoming audio from caller
            try:
                msg = TwilioMediaMessage.model_validate(data)
                mulaw_audio = base64.b64decode(msg.media.payload)
            except ValidationError as e:
                logger.error(f"Invalid media message: {e}")
                return
            except Exception as e:
                logger.error(f"Error decoding audio payload: {e}")
                return

            # Note: Barge-in is handled automatically by Gemini's
            # voice activity detection. We just forward all audio.

            # Transcode and send to Gemini
            pcm_audio = transcode_mulaw_to_pcm(mulaw_audio)
            logger.debug(f"Sending {len(pcm_audio)} bytes to Gemini (from {len(mulaw_audio)} mulaw)")
            await gemini.send_audio(pcm_audio)

        elif event == "stop":
            # Stream ended - update call status
            try:
                TwilioStopMessage.model_validate(data)
                logger.info("Stream stopped")
                await self._update_call_status()
            except ValidationError as e:
                logger.warning(f"Stop event validation warning: {e}")
                await self._update_call_status()

        else:
            logger.debug(f"Ignoring unknown event type: {event}")

    async def _create_call_record(self) -> None:
        """Create a call record in the database."""
        if not self._db:
            logger.warning("Database not available - skipping call record creation")
            return

        if not self.call_sid:
            logger.warning("No call_sid available - skipping call record creation")
            return

        try:
            result = self._db.table("calls").insert({
                "twilio_sid": self.call_sid,
                "status": "ongoing",
            }).execute()

            if result.data:
                self.call_id = result.data[0]["id"]
                logger.info(f"Created call record: {self.call_id} for twilio_sid: {self.call_sid}")
            else:
                logger.error("Failed to create call record - no data returned")

        except Exception as e:
            logger.error(f"Error creating call record: {e}")

    def _handle_tool_call(self, tool_name: str, tool_args: dict) -> None:
        """
        Handle tool calls from Gemini.
        Called when Gemini invokes a registered tool (e.g., save_booking).
        """
        logger.info(f"Tool call received: {tool_name} with args: {tool_args}")

        if tool_name == "save_booking":
            # Run async save_booking in background
            asyncio.create_task(self._save_booking_async(tool_args))
        else:
            logger.warning(f"Unknown tool call: {tool_name}")

    async def _save_booking_async(self, booking_args: dict) -> None:
        """Execute save_booking asynchronously."""
        if not self.call_id:
            logger.error("Cannot save booking: no call_id available")
            return

        try:
            result = await save_booking(self.call_id, booking_args)
            self._booking_saved = True
            logger.info(f"Booking saved successfully: {result}")
        except Exception as e:
            logger.error(f"Error saving booking: {e}")

    async def _update_call_status(self) -> None:
        """Update call status when stream ends."""
        if not self._db:
            logger.warning("Database not available - skipping status update")
            return

        if not self.call_id:
            logger.warning("No call_id available - skipping status update")
            return

        # Determine final status based on whether booking was saved
        final_status = "completed" if self._booking_saved else "failed"

        try:
            self._db.table("calls").update({
                "status": final_status,
            }).eq("id", self.call_id).execute()
            logger.info(f"Updated call {self.call_id} status to: {final_status}")
        except Exception as e:
            logger.error(f"Error updating call status: {e}")

    async def _handle_barge_in(self, gemini: GeminiLiveClient) -> None:
        """Handle user interruption (barge-in)."""
        # Clear the outbound queue
        while not self._outbound_queue.empty():
            try:
                self._outbound_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self._is_speaking = False
        await gemini.interrupt()
        # Send clear message to Twilio to stop playback
        await self._send_clear()
        logger.info("Barge-in handled: cleared queue and interrupted Gemini")

    async def _gemini_receive_loop(self, gemini: GeminiLiveClient) -> None:
        """Background task to receive audio from Gemini and queue for Twilio."""
        logger.info("Starting Gemini receive loop")
        try:
            async for pcm_audio in gemini.receive_audio():
                if not self._running:
                    break

                # Transcode 24kHz PCM to 8kHz μ-law for Twilio
                mulaw_audio = transcode_pcm_24k_to_mulaw(pcm_audio)

                # Queue for sending to Twilio
                await self._outbound_queue.put(mulaw_audio)
                self._is_speaking = True

        except asyncio.CancelledError:
            logger.info("Gemini receive loop cancelled")
        except Exception as e:
            logger.error(f"Error in Gemini receive loop: {e}")

    async def _outbound_audio_loop(self) -> None:
        """Background task to send queued audio to Twilio."""
        logger.info("Starting outbound audio loop")
        try:
            while self._running:
                try:
                    # Wait for audio with timeout to allow checking _running
                    audio = await asyncio.wait_for(
                        self._outbound_queue.get(),
                        timeout=0.1
                    )
                    await self.send_audio(audio)
                except asyncio.TimeoutError:
                    continue

            # Drain any remaining audio in queue
            while not self._outbound_queue.empty():
                try:
                    audio = self._outbound_queue.get_nowait()
                    await self.send_audio(audio)
                except asyncio.QueueEmpty:
                    break

        except asyncio.CancelledError:
            logger.info("Outbound audio loop cancelled")
        except Exception as e:
            logger.error(f"Error in outbound audio loop: {e}")
        finally:
            self._is_speaking = False

    async def send_audio(self, audio: bytes) -> None:
        """Send audio chunk to Twilio."""
        if not self.stream_sid:
            return

        payload = base64.b64encode(audio).decode("utf-8")
        message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": payload},
        }
        await self.websocket.send_json(message)

    async def _send_clear(self) -> None:
        """Send clear message to stop Twilio's audio playback."""
        if not self.stream_sid:
            return

        message = {
            "event": "clear",
            "streamSid": self.stream_sid,
        }
        await self.websocket.send_json(message)
