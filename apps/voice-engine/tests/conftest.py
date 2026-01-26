"""
Test fixtures and configuration for voice-engine tests.
"""

import os
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Generator, AsyncGenerator

# Set test environment variables before importing app
os.environ.setdefault("GEMINI_API_KEY", "test-api-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest123")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15551234567")

from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from main import app, _call_context_store


# Sample test data
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


class MockQueryResult:
    """Mock database query result."""
    def __init__(self, data: list | None = None):
        self.data = data or []


class MockTableQuery:
    """Mock fluent query builder."""
    def __init__(self, data: list | None = None):
        self._data = data or []
        self._filters = {}

    def select(self, columns: str = "*"):
        return self

    def insert(self, data: dict):
        self._insert_data = data
        return self

    def update(self, data: dict):
        self._update_data = data
        return self

    def eq(self, column: str, value):
        self._filters[column] = value
        return self

    def execute(self):
        return MockQueryResult(self._data)


class MockDbClient:
    """Mock database client for testing."""

    def __init__(self):
        self._tables = {
            "users": [SAMPLE_USER],
            "restaurants": [SAMPLE_RESTAURANT],
            "reservation_requests": [SAMPLE_RESERVATION_REQUEST],
            "calls": [],
        }

    def table(self, name: str) -> MockTableQuery:
        data = self._tables.get(name, [])
        return MockTableQuery(data)

    def close(self):
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


@pytest.fixture
def mock_db():
    """Provide a mock database client."""
    return MockDbClient()


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    return MockRedisClient()


@pytest.fixture
def mock_twilio_client(mocker):
    """Mock Twilio client for outbound calls."""
    mock_call = Mock()
    mock_call.sid = "CA_test_call_sid_123"

    mock_client = Mock()
    mock_client.calls.create.return_value = mock_call

    mocker.patch("main.TwilioClient", return_value=mock_client)
    return mock_client


@pytest.fixture
def app_with_mocks(mock_db, mock_redis):
    """Configure app with mock dependencies."""
    app.state.db = mock_db
    app.state.redis = mock_redis
    # Clear in-memory context store
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
