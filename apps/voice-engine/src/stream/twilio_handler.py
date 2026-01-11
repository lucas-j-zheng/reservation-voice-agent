"""
Twilio Media Stream Handler
Manages WebSocket connection with Twilio for real-time audio.
"""

import json
import base64
from fastapi import WebSocket

import sys
from pathlib import Path

# Add libs to path for local development
libs_path = Path(__file__).parent.parent.parent.parent.parent / "libs"
sys.path.insert(0, str(libs_path))

from audio_utils import transcode_mulaw_to_pcm, transcode_pcm_to_mulaw
from src.brain.gemini_client import GeminiLiveClient


class TwilioMediaHandler:
    """
    Handles Twilio Media Stream WebSocket protocol.

    Twilio sends 8kHz μ-law audio, we transcode to 16kHz LPCM16 for Gemini.
    Gemini responds with 16kHz LPCM16, we transcode back to 8kHz μ-law for Twilio.
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self._outbound_buffer: list[bytes] = []
        self._is_speaking = False

    async def handle_stream(self, gemini: GeminiLiveClient) -> None:
        """
        Main loop for handling Twilio media stream.
        Processes incoming audio and routes to Gemini.
        """
        await gemini.connect()

        # Register callbacks
        gemini.on_audio(self._queue_outbound_audio)

        try:
            async for message in self.websocket.iter_text():
                await self._process_message(message, gemini)
        finally:
            await gemini.close()

    async def _process_message(self, message: str, gemini: GeminiLiveClient) -> None:
        """Process a single Twilio WebSocket message."""
        data = json.loads(message)
        event = data.get("event")

        if event == "connected":
            # Connection established
            pass

        elif event == "start":
            # Stream started - capture metadata
            self.stream_sid = data["start"]["streamSid"]
            self.call_sid = data["start"]["callSid"]

        elif event == "media":
            # Incoming audio from caller
            payload = data["media"]["payload"]
            mulaw_audio = base64.b64decode(payload)

            # Check for barge-in
            if self._is_speaking:
                await self._handle_barge_in(gemini)

            # Transcode and send to Gemini
            pcm_audio = transcode_mulaw_to_pcm(mulaw_audio)
            await gemini.send_audio(pcm_audio)

        elif event == "stop":
            # Stream ended
            pass

    async def _handle_barge_in(self, gemini: GeminiLiveClient) -> None:
        """Handle user interruption (barge-in)."""
        self._outbound_buffer.clear()
        self._is_speaking = False
        await gemini.interrupt()
        # Send clear message to Twilio
        await self._send_clear()

    def _queue_outbound_audio(self, pcm_audio: bytes) -> None:
        """Queue audio for sending to Twilio."""
        mulaw_audio = transcode_pcm_to_mulaw(pcm_audio)
        self._outbound_buffer.append(mulaw_audio)
        self._is_speaking = True

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
