"""
Gemini Live API Client
Handles real-time audio streaming with gemini-2.5-flash-native-audio.
"""

import os
from typing import AsyncGenerator, Callable

from .prompts import SYSTEM_PROMPT


class GeminiLiveClient:
    """
    Client for Gemini 2.5 Flash Native Audio via Live API.
    Provides sub-800ms response times for natural conversation.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = "gemini-2.5-flash-preview-native-audio-dialog"
        self.session = None
        self._on_audio_callback: Callable | None = None
        self._on_tool_call_callback: Callable | None = None

    async def connect(self) -> None:
        """
        Establish connection to Gemini Live API.
        Configure for audio response modality.
        """
        # TODO: Initialize google.genai Live API session
        # Config: response_modality=AUDIO, system_instruction=SYSTEM_PROMPT
        pass

    async def send_audio(self, audio_chunk: bytes) -> None:
        """
        Stream audio chunk to Gemini.
        Audio should be 16kHz LPCM16 format.
        """
        # TODO: Send audio to active session
        pass

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """
        Receive audio responses from Gemini.
        Yields 16kHz LPCM16 audio chunks.
        """
        # TODO: Yield audio from session response stream
        yield b""

    async def interrupt(self) -> None:
        """
        Handle barge-in: clear pending audio and interrupt Gemini.
        Called when user starts speaking while AI is responding.
        """
        # TODO: Send interrupt signal to session
        pass

    def on_audio(self, callback: Callable[[bytes], None]) -> None:
        """Register callback for audio output."""
        self._on_audio_callback = callback

    def on_tool_call(self, callback: Callable[[str, dict], None]) -> None:
        """Register callback for function/tool calls."""
        self._on_tool_call_callback = callback

    async def close(self) -> None:
        """Close the Live API session."""
        if self.session:
            # TODO: Close session
            pass
