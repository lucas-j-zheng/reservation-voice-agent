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
from src.tools import save_booking, report_no_availability, end_call, CallContext
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

    def __init__(
        self,
        websocket: WebSocket,
        db: PostgresClient | None = None,
        request_id: str | None = None,
        restaurant_id: str | None = None,
        restaurant_name: str | None = None,
        user_id: str | None = None,
    ):
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
        self._gemini: GeminiLiveClient | None = None  # Reference for tool responses

        # Context for tool calls (populated from UI/orchestration)
        self._request_id = request_id
        self._restaurant_id = restaurant_id
        self._restaurant_name = restaurant_name
        self._user_id = user_id

    async def handle_stream(self, gemini: GeminiLiveClient) -> None:
        """
        Main loop for handling Twilio media stream.
        Processes incoming audio and routes to Gemini.
        """
        await gemini.connect()
        self._running = True
        self._gemini = gemini  # Store reference for tool responses

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
            call_data = {
                "twilio_sid": self.call_sid,
                "status": "ongoing",
            }

            # Add optional context fields
            if self._request_id:
                call_data["request_id"] = self._request_id
            if self._restaurant_id:
                call_data["restaurant_id"] = self._restaurant_id

            result = self._db.table("calls").insert(call_data).execute()

            if result.data:
                self.call_id = result.data[0]["id"]
                logger.info(f"Created call record: {self.call_id} for twilio_sid: {self.call_sid}")

                # If part of a request, update request status to in_progress
                if self._request_id:
                    self._db.table("reservation_requests").update(
                        {"status": "in_progress"}
                    ).eq("id", self._request_id).execute()
            else:
                logger.error("Failed to create call record - no data returned")

        except Exception as e:
            logger.error(f"Error creating call record: {e}")

    def _get_call_context(self) -> CallContext:
        """Build the call context for tool execution."""
        return CallContext(
            call_id=self.call_id,
            request_id=self._request_id,
            restaurant_id=self._restaurant_id,
            restaurant_name=self._restaurant_name,
            user_id=self._user_id,
        )

    def _handle_tool_call(self, tool_name: str, tool_id: str, tool_args: dict) -> None:
        """
        Handle tool calls from Gemini.
        Called when Gemini invokes a registered tool.
        """
        logger.info(f"Tool call received: {tool_name} (id={tool_id}) with args: {tool_args}")

        if tool_name == "save_booking":
            asyncio.create_task(self._execute_save_booking(tool_id, tool_args))
        elif tool_name == "report_no_availability":
            asyncio.create_task(self._execute_report_no_availability(tool_id, tool_args))
        elif tool_name == "end_call":
            asyncio.create_task(self._execute_end_call(tool_id, tool_args))
        else:
            logger.warning(f"Unknown tool call: {tool_name}")

    async def _execute_save_booking(self, tool_id: str, booking_args: dict) -> None:
        """Execute save_booking asynchronously and send response to Gemini."""
        if not self.call_id:
            logger.error("Cannot save booking: no call_id available")
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "save_booking", {
                    "success": False,
                    "error": "No call_id available",
                })
            return

        try:
            context = self._get_call_context()
            result = await save_booking(context, booking_args)
            self._booking_saved = True
            logger.info(f"Booking saved successfully: {result}")

            # Send tool response back to Gemini so it can confirm to the user
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "save_booking", result)
        except Exception as e:
            logger.error(f"Error saving booking: {e}")
            # Send error response to Gemini
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "save_booking", {
                    "success": False,
                    "error": str(e),
                })

    async def _execute_report_no_availability(self, tool_id: str, args: dict) -> None:
        """Execute report_no_availability asynchronously and send response to Gemini."""
        if not self.call_id:
            logger.error("Cannot report no availability: no call_id available")
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "report_no_availability", {
                    "success": False,
                    "error": "No call_id available",
                })
            return

        try:
            context = self._get_call_context()
            result = await report_no_availability(context, args)
            logger.info(f"No availability reported: {result}")

            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "report_no_availability", result)
        except Exception as e:
            logger.error(f"Error reporting no availability: {e}")
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "report_no_availability", {
                    "success": False,
                    "error": str(e),
                })

    async def _execute_end_call(self, tool_id: str, args: dict) -> None:
        """Execute end_call asynchronously and send response to Gemini."""
        if not self.call_id:
            logger.error("Cannot end call: no call_id available")
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "end_call", {
                    "success": False,
                    "error": "No call_id available",
                })
            return

        try:
            context = self._get_call_context()
            result = await end_call(context, args)
            logger.info(f"Call ended: {result}")

            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "end_call", result)
        except Exception as e:
            logger.error(f"Error ending call: {e}")
            if self._gemini:
                await self._gemini.send_tool_response(tool_id, "end_call", {
                    "success": False,
                    "error": str(e),
                })

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
