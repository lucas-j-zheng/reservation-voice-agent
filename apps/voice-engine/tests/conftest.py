"""
Test fixtures and mocks for voice-engine tests.
"""

import asyncio
import base64
import json
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Callable, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio
from fastapi import WebSocket
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

import sys
from pathlib import Path

# Add libs to path for local development
libs_path = Path(__file__).parent.parent.parent.parent / "libs"
sys.path.insert(0, str(libs_path))

# Set test environment variables before importing app
os.environ.setdefault("GEMINI_API_KEY", "test-api-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest123")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15551234567")


# ============================================================================
# Sample Test Data
# ============================================================================

SAMPLE_USER = {
    "id": "user-uuid-123",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+15559876543",
}

SAMPLE_RESTAURANT = {
    "id": "restaurant-uuid-456",
    "name": "Le Petit Bistro",
    "phone": "+15551112222",
    "address": "123 Main St",
}

SAMPLE_RESERVATION_REQUEST = {
    "id": "request-uuid-789",
    "user_id": "user-uuid-123",
    "status": "pending",
    "party_size": 4,
    "requested_date": "2024-02-15",
    "time_range_start": "18:00",
    "time_range_end": "20:00",
    "special_requests": "outdoor seating preferred",
}


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

    def __init__(self, preload_data: bool = False):
        self._data_store: dict[str, list] = {}
        if preload_data:
            self._data_store = {
                "users": [SAMPLE_USER],
                "restaurants": [SAMPLE_RESTAURANT],
                "reservation_requests": [SAMPLE_RESERVATION_REQUEST],
                "calls": [],
            }

    @property
    def _tables(self) -> dict[str, list]:
        """Alias for backward compatibility with tests."""
        return self._data_store

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


class MockRedisClient:
    """Mock Redis client for testing."""

    def __init__(self):
        self._store = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


# Aliases for backward compatibility
MockQueryResult = MagicMock  # Used by test_outbound_call.py
MockTableQuery = MockQueryBuilder  # Used by test_outbound_call.py


@pytest.fixture
def mock_db():
    """Provide a fresh mock database for each test."""
    return MockDatabaseClient()


@pytest.fixture
def mock_db_with_data():
    """Provide a mock database preloaded with sample data."""
    return MockDatabaseClient(preload_data=True)


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    return MockRedisClient()


# ============================================================================
# Twilio Mocks
# ============================================================================


@pytest.fixture
def mock_twilio_client(mocker):
    """Mock Twilio client for outbound calls."""
    mock_call = Mock()
    mock_call.sid = "CA_test_call_sid_123"

    mock_client = Mock()
    mock_client.calls.create.return_value = mock_call

    mocker.patch("main.TwilioClient", return_value=mock_client)
    return mock_client


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
        self.session = self._mock_session
        self._on_tool_call_callback: Callable | None = None
        self._connected = False
        self._tool_responses: list[dict] = []

    async def connect(self):
        """Mock connect."""
        self.session = self._mock_session
        self._connected = True

    async def send_audio(self, audio_chunk: bytes):
        """Mock send_audio."""
        if self.session:
            await self.session.send_realtime_input(MagicMock(data=audio_chunk))

    async def send_text(self, text: str):
        """Mock send_text."""
        if self.session:
            await self.session.send_client_content(
                turns=[{"role": "user", "parts": [{"text": text}]}],
                turn_complete=True
            )

    async def receive_audio(self) -> AsyncGenerator[bytes, None]:
        """Mock receive_audio."""
        if not self.session:
            return

        async for response in self.session._mock_receive():
            if response.tool_call and self._on_tool_call_callback:
                for fc in response.tool_call.function_calls:
                    self._on_tool_call_callback(fc.name, fc.id, fc.args)

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
        """Mock send_tool_response."""
        self._tool_responses.append({
            "id": function_call_id,
            "name": tool_name,
            "response": result,
        })
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

    def queue_audio_response(self, audio: bytes):
        """Queue audio to be returned."""
        self._mock_session.queue_audio(audio)

    def queue_tool_call(self, name: str, args: dict, tool_id: str | None = None):
        """Queue a tool call to be triggered."""
        if tool_id is None:
            tool_id = str(uuid.uuid4())
        self._mock_session.queue_tool_call(name, tool_id, args)


@pytest.fixture
def mock_gemini():
    """Provide a fresh mock Gemini client."""
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
        pass

    async def close(self):
        self._closed = True

    async def send_json(self, data: dict):
        self._outgoing.append(data)

    async def receive_text(self) -> str:
        return await self._incoming.get()

    async def iter_text(self):
        while True:
            msg = await self._incoming.get()
            if msg is None:
                break
            yield msg

    def send_message(self, data: dict):
        self._incoming.put_nowait(json.dumps(data))

    def send_connected(self):
        self.send_message({"event": "connected"})

    def send_start(self, call_sid: str = "CA123", stream_sid: str = "MZ456"):
        self.send_message({
            "event": "start",
            "start": {"streamSid": stream_sid, "callSid": call_sid}
        })

    def send_media(self, audio: bytes):
        payload = base64.b64encode(audio).decode("utf-8")
        self.send_message({"event": "media", "media": {"payload": payload}})

    def send_stop(self):
        self.send_message({"event": "stop"})

    def close_stream(self):
        self._incoming.put_nowait(None)

    def get_outgoing(self) -> list[dict]:
        return self._outgoing


@pytest.fixture
def mock_websocket():
    """Provide a fresh mock WebSocket."""
    return MockWebSocket()


# ============================================================================
# Audio Test Data
# ============================================================================


def generate_mulaw_silence(duration_ms: int = 100, sample_rate: int = 8000) -> bytes:
    """Generate silent μ-law audio."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return bytes([0xFF] * num_samples)


def generate_pcm_silence(duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Generate silent 16-bit PCM audio."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return bytes(num_samples * 2)


@pytest.fixture
def mulaw_silence():
    return generate_mulaw_silence()


@pytest.fixture
def pcm_audio():
    return generate_pcm_silence()


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
def sample_outbound_request():
    """Sample outbound call request body."""
    return {
        "request_id": SAMPLE_RESERVATION_REQUEST["id"],
        "restaurant_id": SAMPLE_RESTAURANT["id"],
    }


@pytest.fixture
def sample_call_context():
    """Sample call context as stored in Redis."""
    return {
        "call_type": "outbound",
        "request_id": SAMPLE_RESERVATION_REQUEST["id"],
        "restaurant_id": SAMPLE_RESTAURANT["id"],
        "restaurant_name": SAMPLE_RESTAURANT["name"],
        "user_name": SAMPLE_USER["name"],
        "party_size": SAMPLE_RESERVATION_REQUEST["party_size"],
        "requested_date": SAMPLE_RESERVATION_REQUEST["requested_date"],
        "time_range_start": SAMPLE_RESERVATION_REQUEST["time_range_start"],
        "time_range_end": SAMPLE_RESERVATION_REQUEST["time_range_end"],
        "special_requests": SAMPLE_RESERVATION_REQUEST["special_requests"],
        "contact_phone": SAMPLE_USER["phone"],
    }


# ============================================================================
# Application Fixtures
# ============================================================================


@pytest.fixture
def app_with_mocks(mock_db_with_data, mock_redis):
    """Configure app with mock dependencies."""
    from main import app, _call_context_store

    app.state.db = mock_db_with_data
    app.state.redis = mock_redis
    _call_context_store.clear()
    return app


@pytest.fixture
async def async_client(app_with_mocks) -> AsyncGenerator[AsyncClient, None]:
    """Provide async HTTP client for testing."""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sync_client(app_with_mocks) -> Generator[TestClient, None, None]:
    """Provide sync HTTP client for testing."""
    with TestClient(app_with_mocks) as client:
        yield client


# ============================================================================
# Pytest Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


def pytest_configure(config):
    """Configure pytest-asyncio."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
