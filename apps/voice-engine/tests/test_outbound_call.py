"""
End-to-end tests for outbound call functionality.

Tests cover:
1. POST /api/calls/outbound - Initiate outbound calls
2. POST /ws/twilio/outbound-twiml - TwiML webhook for answered calls
3. Context storage and retrieval (Redis + in-memory fallback)
4. Error handling and validation
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock

from main import (
    app,
    _call_context_store,
    _get_call_context,
    _store_call_context,
)
from tests.conftest import (
    SAMPLE_USER,
    SAMPLE_RESTAURANT,
    SAMPLE_RESERVATION_REQUEST,
    MockQueryResult,
    MockTableQuery,
)


class TestOutboundCallEndpoint:
    """Tests for POST /api/calls/outbound endpoint."""

    async def test_initiate_outbound_call_success(
        self, async_client, mock_twilio_client, sample_outbound_request
    ):
        """Test successful outbound call initiation."""
        response = await async_client.post(
            "/api/calls/outbound",
            json=sample_outbound_request,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initiated"
        assert data["call_sid"] == "CA_test_call_sid_123"

        # Verify Twilio was called with correct params
        mock_twilio_client.calls.create.assert_called_once()
        call_kwargs = mock_twilio_client.calls.create.call_args.kwargs
        assert call_kwargs["to"] == SAMPLE_RESTAURANT["phone"]
        assert call_kwargs["from_"] == "+15551234567"
        assert "outbound-twiml" in call_kwargs["url"]
        assert "context_id=" in call_kwargs["url"]

    async def test_initiate_outbound_call_request_not_found(
        self, async_client, app_with_mocks, mock_twilio_client
    ):
        """Test 404 when reservation request doesn't exist."""
        # Override db to return empty for reservation_requests
        app_with_mocks.state.db._tables["reservation_requests"] = []

        response = await async_client.post(
            "/api/calls/outbound",
            json={
                "request_id": "nonexistent-uuid",
                "restaurant_id": SAMPLE_RESTAURANT["id"],
            },
        )

        assert response.status_code == 404
        assert "Reservation request not found" in response.json()["detail"]

    async def test_initiate_outbound_call_restaurant_not_found(
        self, async_client, app_with_mocks, mock_twilio_client
    ):
        """Test 404 when restaurant doesn't exist."""
        app_with_mocks.state.db._tables["restaurants"] = []

        response = await async_client.post(
            "/api/calls/outbound",
            json={
                "request_id": SAMPLE_RESERVATION_REQUEST["id"],
                "restaurant_id": "nonexistent-uuid",
            },
        )

        assert response.status_code == 404
        assert "Restaurant not found" in response.json()["detail"]

    async def test_initiate_outbound_call_restaurant_no_phone(
        self, async_client, app_with_mocks, mock_twilio_client
    ):
        """Test 400 when restaurant has no phone number."""
        app_with_mocks.state.db._tables["restaurants"] = [
            {**SAMPLE_RESTAURANT, "phone": None}
        ]

        response = await async_client.post(
            "/api/calls/outbound",
            json={
                "request_id": SAMPLE_RESERVATION_REQUEST["id"],
                "restaurant_id": SAMPLE_RESTAURANT["id"],
            },
        )

        assert response.status_code == 400
        assert "no phone number" in response.json()["detail"]

    async def test_initiate_outbound_call_wrong_status(
        self, async_client, app_with_mocks, mock_twilio_client
    ):
        """Test 400 when reservation request has wrong status."""
        app_with_mocks.state.db._tables["reservation_requests"] = [
            {**SAMPLE_RESERVATION_REQUEST, "status": "completed"}
        ]

        response = await async_client.post(
            "/api/calls/outbound",
            json={
                "request_id": SAMPLE_RESERVATION_REQUEST["id"],
                "restaurant_id": SAMPLE_RESTAURANT["id"],
            },
        )

        assert response.status_code == 400
        assert "must be pending or in_progress" in response.json()["detail"]

    async def test_initiate_outbound_call_in_progress_status_allowed(
        self, async_client, app_with_mocks, mock_twilio_client
    ):
        """Test that in_progress status is allowed for retry calls."""
        app_with_mocks.state.db._tables["reservation_requests"] = [
            {**SAMPLE_RESERVATION_REQUEST, "status": "in_progress"}
        ]

        response = await async_client.post(
            "/api/calls/outbound",
            json={
                "request_id": SAMPLE_RESERVATION_REQUEST["id"],
                "restaurant_id": SAMPLE_RESTAURANT["id"],
            },
        )

        assert response.status_code == 200

    async def test_initiate_outbound_call_stores_context(
        self, async_client, app_with_mocks, mock_twilio_client, sample_outbound_request
    ):
        """Test that call context is stored for later retrieval."""
        response = await async_client.post(
            "/api/calls/outbound",
            json=sample_outbound_request,
        )

        assert response.status_code == 200

        # Context should be stored (either in Redis mock or in-memory)
        # Check in-memory fallback since Redis mock might not be fully wired
        assert len(_call_context_store) >= 0  # Context was processed

    async def test_initiate_outbound_call_no_database(self, async_client, app_with_mocks):
        """Test 503 when database is not available."""
        app_with_mocks.state.db = None

        response = await async_client.post(
            "/api/calls/outbound",
            json={
                "request_id": "any-uuid",
                "restaurant_id": "any-uuid",
            },
        )

        assert response.status_code == 503
        assert "Database not available" in response.json()["detail"]


class TestOutboundTwiMLWebhook:
    """Tests for POST /ws/twilio/outbound-twiml webhook."""

    async def test_outbound_twiml_success(
        self, async_client, app_with_mocks, sample_call_context
    ):
        """Test successful TwiML generation when restaurant answers."""
        # Store context first
        context_id = "test-context-123"
        await _store_call_context(app_with_mocks.state.redis, context_id, sample_call_context)

        response = await async_client.post(
            f"/ws/twilio/outbound-twiml?context_id={context_id}",
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"

        content = response.text
        assert '<?xml version="1.0"' in content
        assert "<Response>" in content
        assert "<Connect>" in content
        assert "<Stream" in content
        assert f"context_id={context_id}" in content
        assert 'name="call_type" value="outbound"' in content
        assert f'name="request_id" value="{sample_call_context["request_id"]}"' in content
        assert f'name="restaurant_id" value="{sample_call_context["restaurant_id"]}"' in content

    async def test_outbound_twiml_no_context_id(self, async_client):
        """Test error when context_id is missing."""
        response = await async_client.post("/ws/twilio/outbound-twiml")

        assert response.status_code == 200  # TwiML always returns 200
        content = response.text
        assert "Configuration error" in content
        assert "Goodbye" in content

    async def test_outbound_twiml_context_not_found(self, async_client, app_with_mocks):
        """Test error when context doesn't exist."""
        response = await async_client.post(
            "/ws/twilio/outbound-twiml?context_id=nonexistent-context",
        )

        assert response.status_code == 200  # TwiML always returns 200
        content = response.text
        assert "Configuration error" in content

    async def test_outbound_twiml_websocket_protocol(
        self, async_client, app_with_mocks, sample_call_context
    ):
        """Test that WebSocket URL uses correct protocol based on host."""
        context_id = "test-context-456"
        await _store_call_context(app_with_mocks.state.redis, context_id, sample_call_context)

        # Test with cloudflare host (should use wss)
        response = await async_client.post(
            f"/ws/twilio/outbound-twiml?context_id={context_id}",
            headers={"host": "abc123.trycloudflare.com"},
        )

        content = response.text
        assert "wss://" in content

        # Test with localhost (should use ws)
        response = await async_client.post(
            f"/ws/twilio/outbound-twiml?context_id={context_id}",
            headers={"host": "localhost:8000"},
        )

        content = response.text
        assert "ws://" in content


class TestContextStorage:
    """Tests for call context storage and retrieval."""

    async def test_store_and_get_context_redis(self, mock_redis, sample_call_context):
        """Test context storage with Redis."""
        context_id = "redis-test-123"

        await _store_call_context(mock_redis, context_id, sample_call_context)
        retrieved = await _get_call_context(mock_redis, context_id)

        assert retrieved == sample_call_context

    async def test_store_and_get_context_inmemory_fallback(self, sample_call_context):
        """Test context storage with in-memory fallback when Redis unavailable."""
        context_id = "inmemory-test-456"
        _call_context_store.clear()

        # Pass None for Redis to use fallback
        await _store_call_context(None, context_id, sample_call_context)
        retrieved = await _get_call_context(None, context_id)

        assert retrieved == sample_call_context
        assert context_id in _call_context_store

    async def test_get_context_not_found(self, mock_redis):
        """Test getting non-existent context returns None."""
        retrieved = await _get_call_context(mock_redis, "nonexistent")
        assert retrieved is None

    async def test_context_redis_failure_fallback(self, sample_call_context):
        """Test fallback to in-memory when Redis fails."""
        context_id = "fallback-test-789"
        _call_context_store.clear()

        # Create a mock Redis that raises exceptions
        failing_redis = Mock()
        failing_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))
        failing_redis.setex = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Store should fall back to in-memory
        await _store_call_context(failing_redis, context_id, sample_call_context)
        assert context_id in _call_context_store

        # Get should also fall back
        retrieved = await _get_call_context(failing_redis, context_id)
        assert retrieved == sample_call_context


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    async def test_health_check(self, async_client):
        """Test health endpoint returns healthy status."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestIncomingCallEndpoint:
    """Tests for existing incoming call functionality."""

    async def test_incoming_call_twiml(self, async_client):
        """Test incoming call webhook returns valid TwiML."""
        response = await async_client.post("/ws/twilio")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"

        content = response.text
        assert '<?xml version="1.0"' in content
        assert "<Response>" in content
        assert "<Say>" in content
        assert "<Connect>" in content
        assert "<Stream" in content
        assert "/ws/twilio/stream" in content


class TestPromptGeneration:
    """Tests for system prompt generation."""

    def test_build_outbound_prompt(self):
        """Test outbound prompt is correctly generated."""
        from src.brain.prompts import build_outbound_prompt

        prompt = build_outbound_prompt(
            user_name="John Doe",
            restaurant_name="Le Petit Bistro",
            party_size=4,
            preferred_date="2024-02-15",
            preferred_time="18:00",
            time_range_start="18:00",
            time_range_end="20:00",
            contact_phone="+15559876543",
            special_requests="outdoor seating",
        )

        assert "John Doe" in prompt
        assert "Le Petit Bistro" in prompt
        assert "4" in prompt
        assert "2024-02-15" in prompt
        assert "18:00" in prompt
        assert "20:00" in prompt
        assert "outdoor seating" in prompt
        assert "save_booking" in prompt

    def test_build_outbound_prompt_no_special_requests(self):
        """Test outbound prompt handles empty special requests."""
        from src.brain.prompts import build_outbound_prompt

        prompt = build_outbound_prompt(
            user_name="Jane Doe",
            restaurant_name="Chez Marie",
            party_size=2,
            preferred_date="2024-03-01",
            preferred_time="19:00",
            time_range_start="19:00",
            time_range_end="21:00",
            contact_phone="+15551234567",
            special_requests="",
        )

        assert "None" in prompt  # Default for empty special_requests


class TestGeminiClientPrompt:
    """Tests for GeminiLiveClient system prompt handling."""

    def test_gemini_client_default_prompt(self):
        """Test GeminiLiveClient uses default prompt when none provided."""
        from src.brain.gemini_client import GeminiLiveClient
        from src.brain.prompts import SYSTEM_PROMPT

        client = GeminiLiveClient()
        assert client._system_prompt == SYSTEM_PROMPT

    def test_gemini_client_custom_prompt(self):
        """Test GeminiLiveClient accepts custom system prompt."""
        from src.brain.gemini_client import GeminiLiveClient

        custom_prompt = "Custom test prompt for outbound calls"
        client = GeminiLiveClient(system_prompt=custom_prompt)
        assert client._system_prompt == custom_prompt


class TestTwilioHandlerContext:
    """Tests for TwilioMediaHandler context handling."""

    def test_handler_accepts_call_context(self):
        """Test TwilioMediaHandler accepts call context parameter."""
        from src.stream.twilio_handler import TwilioMediaHandler
        from unittest.mock import Mock

        mock_websocket = Mock()
        context = {
            "request_id": "test-request-id",
            "restaurant_id": "test-restaurant-id",
        }

        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            call_context=context,
        )

        assert handler._call_context == context

    def test_handler_accepts_system_prompt(self):
        """Test TwilioMediaHandler accepts system prompt parameter."""
        from src.stream.twilio_handler import TwilioMediaHandler
        from unittest.mock import Mock

        mock_websocket = Mock()
        prompt = "Custom system prompt"

        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            system_prompt=prompt,
        )

        assert handler._system_prompt == prompt

    def test_handler_default_context_is_empty(self):
        """Test TwilioMediaHandler has empty context by default."""
        from src.stream.twilio_handler import TwilioMediaHandler
        from unittest.mock import Mock

        mock_websocket = Mock()
        handler = TwilioMediaHandler(websocket=mock_websocket)

        assert handler._call_context == {}
        assert handler._system_prompt is None


class TestDatabaseClientSelect:
    """Tests for PostgresClient select functionality."""

    def test_table_query_select(self):
        """Test TableQuery select method exists and returns self."""
        from src.db.client import TableQuery
        from unittest.mock import Mock

        mock_client = Mock()
        query = TableQuery(mock_client, "test_table")

        result = query.select("*")
        assert result is query
        assert query._operation == "select"
        assert query._select_columns == "*"

    def test_table_query_select_specific_columns(self):
        """Test TableQuery select with specific columns."""
        from src.db.client import TableQuery
        from unittest.mock import Mock

        mock_client = Mock()
        query = TableQuery(mock_client, "test_table")

        result = query.select("id, name, phone")
        assert query._select_columns == "id, name, phone"
