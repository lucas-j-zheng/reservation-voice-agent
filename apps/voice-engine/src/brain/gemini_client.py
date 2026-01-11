"""
Gemini Live API Client
Handles real-time audio streaming with gemini-2.5-flash-native-audio.
"""

import os
import logging
from typing import AsyncGenerator, Callable

from google import genai
from google.genai import types

from .prompts import SYSTEM_PROMPT
from ..tools.save_booking import SAVE_BOOKING_SCHEMA

logger = logging.getLogger(__name__)


class GeminiLiveClient:
    """
    Client for Gemini 2.5 Flash Native Audio via Live API.
    Provides sub-800ms response times for natural conversation.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        self.model = "gemini-2.5-flash-native-audio-preview-12-2025"
        self.session = None
        self._session_context = None
        self._on_audio_callback: Callable | None = None
        self._on_tool_call_callback: Callable | None = None

        # Initialize the genai client
        self._client = genai.Client(api_key=self.api_key)

    async def connect(self) -> None:
        """
        Establish connection to Gemini Live API.
        Configure for audio response modality.
        """
        if self.session is not None:
            logger.warning("Session already connected, closing existing session")
            await self.close()

        # Configure the Live API session
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": SYSTEM_PROMPT,
            "tools": [{"function_declarations": [SAVE_BOOKING_SCHEMA]}],
        }

        logger.info(f"Connecting to Gemini Live API with model: {self.model}")

        # Create the async session context manager
        self._session_context = self._client.aio.live.connect(
            model=self.model,
            config=config
        )

        # Enter the context to establish connection
        self.session = await self._session_context.__aenter__()

        logger.info("Successfully connected to Gemini Live API")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """
        Stream audio chunk to Gemini.
        Audio should be 16kHz LPCM16 format.
        """
        if self.session is None:
            logger.warning("Cannot send audio: session not connected")
            return

        if not audio_chunk:
            return

        # Send audio as realtime input with proper MIME type
        # Gemini expects 16kHz, 16-bit PCM, little-endian
        await self.session.send_realtime_input(
            media=types.Blob(
                data=audio_chunk,
                mime_type="audio/pcm;rate=16000"
            )
        )

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """
        Receive audio responses from Gemini.
        Yields 24kHz LPCM16 audio chunks (Gemini's native output format).

        Also handles tool calls by invoking the registered callback.
        """
        if self.session is None:
            logger.warning("Cannot receive audio: session not connected")
            return

        try:
            async for response in self.session.receive():
                # Handle tool calls
                if response.tool_call:
                    logger.info(f"Received tool call: {response.tool_call}")
                    for fc in response.tool_call.function_calls:
                        if self._on_tool_call_callback:
                            self._on_tool_call_callback(fc.name, fc.args)

                # Handle audio responses
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and isinstance(part.inline_data.data, bytes):
                            yield part.inline_data.data

        except Exception as e:
            logger.error(f"Error receiving audio: {e}")
            raise

    async def interrupt(self) -> None:
        """
        Handle barge-in: clear pending audio and interrupt Gemini.
        Called when user starts speaking while AI is responding.

        Sends ActivityStart to signal user speech, which triggers
        Gemini to stop any ongoing audio generation.
        """
        if self.session is None:
            logger.warning("Cannot interrupt: session not connected")
            return

        try:
            # Send ActivityStart to signal user is speaking
            # This interrupts any ongoing model generation
            await self.session.send_realtime_input(
                activity_start=types.ActivityStart()
            )
            logger.info("Sent interrupt signal (ActivityStart)")
        except Exception as e:
            logger.error(f"Error sending interrupt: {e}")

    def on_audio(self, callback: Callable[[bytes], None]) -> None:
        """Register callback for audio output."""
        self._on_audio_callback = callback

    def on_tool_call(self, callback: Callable[[str, dict], None]) -> None:
        """Register callback for function/tool calls."""
        self._on_tool_call_callback = callback

    async def close(self) -> None:
        """Close the Live API session."""
        if self._session_context is not None:
            try:
                await self._session_context.__aexit__(None, None, None)
                logger.info("Gemini Live API session closed")
            except Exception as e:
                logger.error(f"Error closing Gemini session: {e}")
            finally:
                self.session = None
                self._session_context = None
