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
from ..tools import ALL_TOOL_SCHEMAS

logger = logging.getLogger(__name__)


class GeminiLiveClient:
    """
    Client for Gemini 2.5 Flash Native Audio via Live API.
    Provides sub-800ms response times for natural conversation.
    """

    def __init__(self, system_prompt: str | None = None):
        """
        Initialize the Gemini Live client.

        Args:
            system_prompt: Optional custom system prompt. If not provided,
                           uses the default SYSTEM_PROMPT from prompts.py.
        """
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        # Using -09-2025 version due to 1008 policy violation bug in -12-2025
        # See: https://discuss.ai.google.dev/t/gemini-live-api-websocket-error-1008-operation-is-not-implemented-or-supported-or-enabled/114644
        self.model = "gemini-2.5-flash-native-audio-preview-09-2025"
        self.session = None
        self._session_context = None
        self._on_audio_callback: Callable | None = None
        self._on_tool_call_callback: Callable | None = None
        self._system_prompt = system_prompt or SYSTEM_PROMPT

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
            "system_instruction": self._system_prompt,
            "tools": [{"function_declarations": ALL_TOOL_SCHEMAS}],
            # Enable transcriptions for logging
            "input_audio_transcription": {},
            "output_audio_transcription": {},
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

        logger.debug(f"Sending audio to Gemini: {len(audio_chunk)} bytes")

        # Send audio as realtime input with proper MIME type
        # Gemini expects 16kHz, 16-bit PCM, little-endian
        await self.session.send_realtime_input(
            media=types.Blob(
                data=audio_chunk,
                mime_type="audio/pcm;rate=16000"
            )
        )

    async def send_text(self, text: str) -> None:
        """
        Send a text message to Gemini to prompt a response.
        Useful for triggering the initial greeting.
        """
        if self.session is None:
            logger.warning("Cannot send text: session not connected")
            return

        logger.info(f"Sending text prompt: {text}")
        await self.session.send_client_content(
            turns=[{"role": "user", "parts": [{"text": text}]}],
            turn_complete=True
        )

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """
        Receive audio responses from Gemini.
        Yields 24kHz LPCM16 audio chunks (Gemini's native output format).

        Also handles tool calls by invoking the registered callback.

        IMPORTANT: session.receive() returns a single turn. After turn_complete,
        we must call receive() again to get the next turn. This loop runs
        continuously until the session is closed.
        """
        if self.session is None:
            logger.warning("Cannot receive audio: session not connected")
            return

        try:
            # Continuously receive turns from Gemini
            # Each call to session.receive() returns one turn's worth of responses
            while True:
                if self.session is None:
                    logger.info("Session closed, stopping receive loop")
                    break

                logger.debug("Waiting for next turn from Gemini...")
                turn = self.session.receive()

                async for response in turn:
                    # Log the full response structure for debugging
                    logger.debug(f"Gemini response type: {type(response)}")
                    logger.debug(f"Has tool_call: {bool(response.tool_call)}")
                    logger.debug(f"Has server_content: {bool(response.server_content)}")

                    # Handle tool calls
                    if response.tool_call:
                        logger.info(f"Received tool call: {response.tool_call}")
                        for fc in response.tool_call.function_calls:
                            if self._on_tool_call_callback:
                                self._on_tool_call_callback(fc.name, fc.id, fc.args)

                    # Log any transcripts from user input
                    if response.server_content:
                        sc = response.server_content
                        # Log key fields
                        if sc.turn_complete:
                            logger.info(f"Turn complete. interrupted={sc.interrupted}")
                        if sc.input_transcription:
                            logger.info(f"[USER SAID]: {sc.input_transcription}")
                        if sc.interrupted:
                            logger.info(f"Gemini was interrupted by user")

                        # Check for output transcription (what AI said)
                        if hasattr(response.server_content, 'output_transcription') and response.server_content.output_transcription:
                            logger.info(f"[AI SAID]: {response.server_content.output_transcription}")

                    # Handle audio responses
                    if response.server_content and response.server_content.model_turn:
                        logger.debug(f"model_turn parts: {len(response.server_content.model_turn.parts)}")
                        for part in response.server_content.model_turn.parts:
                            logger.debug(f"Part type: {type(part)}, has inline_data: {hasattr(part, 'inline_data')}")
                            if hasattr(part, 'inline_data') and part.inline_data:
                                logger.debug(f"inline_data type: {type(part.inline_data.data)}, len: {len(part.inline_data.data) if part.inline_data.data else 0}")
                            if part.inline_data and isinstance(part.inline_data.data, bytes):
                                logger.info(f"Yielding audio chunk: {len(part.inline_data.data)} bytes")
                                yield part.inline_data.data

                logger.debug("Turn completed, waiting for next turn...")

        except Exception as e:
            logger.error(f"Error receiving audio: {e}")
            raise

    async def interrupt(self) -> None:
        """
        Handle barge-in: clear pending audio and interrupt Gemini.
        Called when user starts speaking while AI is responding.

        Note: With automatic activity detection enabled (default),
        Gemini handles barge-in automatically. We just clear the
        local audio queue - no need to send explicit ActivityStart.
        """
        if self.session is None:
            logger.warning("Cannot interrupt: session not connected")
            return

        # With automatic activity detection, Gemini handles interruption
        # automatically when it detects user speech. We just log it.
        logger.info("Barge-in detected - Gemini will handle automatically")

    def on_audio(self, callback: Callable[[bytes], None]) -> None:
        """Register callback for audio output."""
        self._on_audio_callback = callback

    def on_tool_call(self, callback: Callable[[str, str, dict], None]) -> None:
        """Register callback for function/tool calls. Callback receives (name, id, args)."""
        self._on_tool_call_callback = callback

    async def send_tool_response(self, function_call_id: str, tool_name: str, result: dict) -> None:
        """
        Send the result of a tool call back to Gemini.
        This allows Gemini to continue the conversation after a tool is executed.

        Args:
            function_call_id: The ID of the function call from Gemini
            tool_name: The name of the tool that was called
            result: The result dictionary to send back
        """
        if self.session is None:
            logger.warning("Cannot send tool response: session not connected")
            return

        logger.info(f"Sending tool response for {tool_name} ({function_call_id}): {result}")

        from google.genai import types

        await self.session.send_tool_response(
            function_responses=[
                types.FunctionResponse(
                    id=function_call_id,
                    name=tool_name,
                    response=result
                )
            ]
        )

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
