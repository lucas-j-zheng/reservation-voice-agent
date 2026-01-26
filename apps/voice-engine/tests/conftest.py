"""
Test fixtures and mocks for voice-engine E2E tests.
"""

import asyncio
import base64
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import WebSocket
from fastapi.testclient import TestClient

import sys
from pathlib import Path

# Add libs to path for local development
libs_path = Path(__file__).parent.parent.parent.parent / "libs"
sys.path.insert(0, str(libs_path))


# ============================================================================
# Database Mocks
# ============================================================================


class MockQueryBuilder:
    """Mock Supabase query builder for chaining."""

    def __init__(self, table_name: str, data_store: dict):
        self._table = table_name
        self._store = data_store
        self._filters = {}
        self._data = None
        self._select_fields = "*"

    def select(self, fields: str = "*"):
        self._select_fields = fields
        return self

    def insert(self, data: dict):
        self._data = data
        return self

    def update(self, data: dict):
        self._data = data
        return self

    def eq(self, field: str, value):
        self._filters[field] = value
        return self

    def execute(self):
        """Execute the query and return mock response."""
        result = MagicMock()

        if self._data and not self._filters:
            # INSERT operation
            record = {**self._data}
            if "id" not in record:
                record["id"] = str(uuid.uuid4())
            record["created_at"] = datetime.now(timezone.utc).isoformat()
            self._store.setdefault(self._table, []).append(record)
            result.data = [record]

        elif self._data and self._filters:
            # UPDATE operation
            table_data = self._store.get(self._table, [])
            updated = []
            for row in table_data:
                if all(row.get(k) == v for k, v in self._filters.items()):
                    row.update(self._data)
                    row["updated_at"] = datetime.now(timezone.utc).isoformat()
                    updated.append(row)
            result.data = updated

        else:
            # SELECT operation
            table_data = self._store.get(self._table, [])
            if self._filters:
                filtered = [
                    row for row in table_data
                    if all(row.get(k) == v for k, v in self._filters.items())
                ]
                result.data = filtered
            else:
                result.data = table_data

        return result


class MockDatabaseClient:
    """Mock database client that stores data in memory."""

    def __init__(self):
        self._data_store: dict[str, list] = {}

    def table(self, name: str) -> MockQueryBuilder:
        return MockQueryBuilder(name, self._data_store)

    def get_data(self, table: str) -> list:
        """Helper to inspect stored data in tests."""
        return self._data_store.get(table, [])

    def clear(self):
        """Clear all stored data."""
        self._data_store.clear()

    def close(self):
        """Mock close method."""
        pass


@pytest.fixture
def mock_db():
    """Provide a fresh mock database for each test."""
    return MockDatabaseClient()


# ============================================================================
# Gemini Mocks
# ============================================================================


class MockGeminiSession:
    """Mock Gemini Live API session."""

    def __init__(self):
        self._audio_responses: list[bytes] = []
        self._tool_calls: list[tuple[str, str, dict]] = []
        self._received_audio: list[bytes] = []
        self._received_text: list[str] = []
        self._tool_responses: list[dict] = []

    async def send_realtime_input(self, media):
        """Record audio sent to Gemini."""
        self._received_audio.append(media.data)

    async def send_client_content(self, turns, turn_complete):
        """Record text sent to Gemini."""
        for turn in turns:
            for part in turn.get("parts", []):
                if "text" in part:
                    self._received_text.append(part["text"])

    async def send_tool_response(self, function_responses):
        """Record tool responses sent to Gemini."""
        for resp in function_responses:
            self._tool_responses.append({
                "id": resp.id,
                "name": resp.name,
                "response": resp.response,
            })

    def receive(self):
        """Return async generator for mock responses."""
        return self._mock_receive()

    async def _mock_receive(self):
        """Generate mock responses including audio and tool calls."""
        # First yield any pending tool calls
        for name, tool_id, args in self._tool_calls:
            response = MagicMock()
            response.tool_call = MagicMock()
            fc = MagicMock()
            fc.name = name
            fc.id = tool_id
            fc.args = args
            response.tool_call.function_calls = [fc]
            response.server_content = None
            yield response

        # Then yield audio responses
        for audio in self._audio_responses:
            response = MagicMock()
            response.tool_call = None
            response.server_content = MagicMock()
            response.server_content.model_turn = MagicMock()
            response.server_content.turn_complete = False
            response.server_content.interrupted = False
            response.server_content.input_transcription = None

            part = MagicMock()
            part.inline_data = MagicMock()
            part.inline_data.data = audio
            response.server_content.model_turn.parts = [part]

            yield response

        # Final turn complete
        response = MagicMock()
        response.tool_call = None
        response.server_content = MagicMock()
        response.server_content.model_turn = None
        response.server_content.turn_complete = True
        response.server_content.interrupted = False
        response.server_content.input_transcription = None
        yield response

    def queue_audio(self, audio: bytes):
        """Queue audio to be returned by receive()."""
        self._audio_responses.append(audio)

    def queue_tool_call(self, name: str, tool_id: str, args: dict):
        """Queue a tool call to be returned by receive()."""
        self._tool_calls.append((name, tool_id, args))


class MockGeminiClient:
    """Mock GeminiLiveClient for testing."""

    def __init__(self):
        self._mock_session = MockGeminiSession()
        self.session = self._mock_session  # Always have session for simpler testing
        self._on_tool_call_callback: Callable | None = None
        self._connected = False
        self._tool_responses: list[dict] = []  # Track tool responses directly

    async def connect(self):
        """Mock connect - sets up session."""
        self.session = self._mock_session
        self._connected = True

    async def send_audio(self, audio_chunk: bytes):
        """Mock send_audio."""
        if self.session:
            await self.session.send_realtime_input(
                MagicMock(data=audio_chunk)
            )

    async def send_text(self, text: str):
        """Mock send_text."""
        if self.session:
            await self.session.send_client_content(
                turns=[{"role": "user", "parts": [{"text": text}]}],
                turn_complete=True
            )

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """Mock receive_audio - yields queued audio and handles tool calls."""
        if not self.session:
            return

        async for response in self.session._mock_receive():
            # Handle tool calls
            if response.tool_call and self._on_tool_call_callback:
                for fc in response.tool_call.function_calls:
                    self._on_tool_call_callback(fc.name, fc.id, fc.args)

            # Yield audio
            if response.server_content and response.server_content.model_turn:
                for part in response.server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        yield part.inline_data.data

    async def interrupt(self):
        """Mock interrupt."""
        pass

    def on_tool_call(self, callback: Callable):
        """Register tool call callback."""
        self._on_tool_call_callback = callback

    async def send_tool_response(self, function_call_id: str, tool_name: str, result: dict):
        """Mock send_tool_response - always tracks responses."""
        # Track directly on client for easier test assertions
        self._tool_responses.append({
            "id": function_call_id,
            "name": tool_name,
            "response": result,
        })
        # Also track on session if available
        if self.session:
            resp = MagicMock()
            resp.id = function_call_id
            resp.name = tool_name
            resp.response = result
            await self.session.send_tool_response([resp])

    async def close(self):
        """Mock close."""
        self.session = None
        self._connected = False

    # Test helpers
    def queue_audio_response(self, audio: bytes):
        """Queue audio to be returned."""
        self._mock_session.queue_audio(audio)

    def queue_tool_call(self, name: str, args: dict, tool_id: str | None = None):
        """Queue a tool call to be triggered."""
        if tool_id is None:
            tool_id = str(uuid.uuid4())
        self._mock_session.queue_tool_call(name, tool_id, args)

    def get_received_audio(self) -> list[bytes]:
        """Get all audio sent to Gemini."""
        return self._mock_session._received_audio

    def get_received_text(self) -> list[str]:
        """Get all text sent to Gemini."""
        return self._mock_session._received_text

    def get_tool_responses(self) -> list[dict]:
        """Get all tool responses sent back to Gemini."""
        return self._tool_responses


@pytest.fixture
def mock_gemini():
    """Provide a fresh mock Gemini client for each test."""
    return MockGeminiClient()


# ============================================================================
# WebSocket Mocks
# ============================================================================


class MockWebSocket:
    """Mock FastAPI WebSocket for testing."""

    def __init__(self):
        self._incoming: asyncio.Queue = asyncio.Queue()
        self._outgoing: list[dict] = []
        self._closed = False

    async def accept(self):
        """Mock accept."""
        pass

    async def close(self):
        """Mock close."""
        self._closed = True

    async def send_json(self, data: dict):
        """Record outgoing messages."""
        self._outgoing.append(data)

    async def receive_text(self) -> str:
        """Get next incoming message."""
        return await self._incoming.get()

    async def iter_text(self):
        """Iterate over incoming messages until None is received."""
        while True:
            msg = await self._incoming.get()
            if msg is None:
                break
            yield msg

    # Test helpers
    def send_message(self, data: dict):
        """Queue a message to be received by the handler."""
        self._incoming.put_nowait(json.dumps(data))

    def send_connected(self):
        """Send Twilio 'connected' event."""
        self.send_message({"event": "connected"})

    def send_start(self, call_sid: str = "CA123", stream_sid: str = "MZ456"):
        """Send Twilio 'start' event."""
        self.send_message({
            "event": "start",
            "start": {
                "streamSid": stream_sid,
                "callSid": call_sid,
            }
        })

    def send_media(self, audio: bytes):
        """Send Twilio 'media' event with audio."""
        payload = base64.b64encode(audio).decode("utf-8")
        self.send_message({
            "event": "media",
            "media": {"payload": payload}
        })

    def send_stop(self):
        """Send Twilio 'stop' event."""
        self.send_message({"event": "stop"})

    def close_stream(self):
        """Signal end of WebSocket stream."""
        self._incoming.put_nowait(None)

    def get_outgoing(self) -> list[dict]:
        """Get all messages sent by the handler."""
        return self._outgoing

    def get_audio_sent(self) -> list[bytes]:
        """Get all audio chunks sent to Twilio."""
        audio = []
        for msg in self._outgoing:
            if msg.get("event") == "media":
                payload = msg.get("media", {}).get("payload", "")
                audio.append(base64.b64decode(payload))
        return audio


@pytest.fixture
def mock_websocket():
    """Provide a fresh mock WebSocket for each test."""
    return MockWebSocket()


# ============================================================================
# Audio Test Data
# ============================================================================


def generate_mulaw_silence(duration_ms: int = 100, sample_rate: int = 8000) -> bytes:
    """Generate silent μ-law audio (0xFF is silence in μ-law)."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return bytes([0xFF] * num_samples)


def generate_pcm_silence(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Generate silent 16-bit PCM audio (zeros)."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return bytes(num_samples * 2)  # 2 bytes per sample


def generate_pcm_tone(
    frequency: int = 440,
    duration_ms: int = 100,
    sample_rate: int = 16000,
    amplitude: int = 16000,
) -> bytes:
    """Generate a simple sine wave tone as 16-bit PCM."""
    import math

    num_samples = int(sample_rate * duration_ms / 1000)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        value = int(amplitude * math.sin(2 * math.pi * frequency * t))
        # Convert to little-endian 16-bit signed
        samples.append(value & 0xFF)
        samples.append((value >> 8) & 0xFF)

    return bytes(samples)


@pytest.fixture
def mulaw_silence():
    """Provide silent μ-law audio data."""
    return generate_mulaw_silence()


@pytest.fixture
def pcm_audio():
    """Provide sample PCM audio data."""
    return generate_pcm_tone()


# ============================================================================
# Call Context Fixtures
# ============================================================================


@pytest.fixture
def call_context():
    """Provide a sample call context."""
    return {
        "call_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "restaurant_id": str(uuid.uuid4()),
        "restaurant_name": "Test Restaurant",
        "user_id": str(uuid.uuid4()),
    }


@pytest.fixture
def booking_args():
    """Provide sample booking arguments."""
    return {
        "confirmed_date": "2025-01-25",
        "confirmed_time": "19:30",
        "party_size": 4,
        "confirmation_code": "CONF123",
        "notes": "Window seat requested",
    }


@pytest.fixture
def no_availability_args():
    """Provide sample no-availability arguments."""
    return {
        "reason": "Fully booked for the requested time",
        "alternative_offered": "8:30 PM available",
        "should_try_alternative": True,
    }


@pytest.fixture
def end_call_args():
    """Provide sample end-call arguments."""
    return {
        "reason": "User declined alternative time",
        "call_summary": "Called to book 7pm, fully booked, declined 8:30pm alternative",
    }


# ============================================================================
# Application Fixtures
# ============================================================================


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def app_with_mocks(mock_db, mock_env):
    """Provide FastAPI app with mocked dependencies."""
    from main import app

    # Override app.state with mocks
    app.state.db = mock_db
    app.state.redis = None  # Skip Redis for tests

    yield app

    # Cleanup
    app.state.db = None


# ============================================================================
# Pytest Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


def pytest_configure(config):
    """Configure pytest-asyncio."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
