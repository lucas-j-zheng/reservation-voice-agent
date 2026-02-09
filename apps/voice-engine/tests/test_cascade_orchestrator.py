"""
Tests for the cascade orchestrator state machine, controls, and event flow.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ============================================================================
# Helpers
# ============================================================================


def make_request(db, **overrides) -> dict:
    """Insert a request + reservation_details and return merged record."""
    request_id = overrides.pop("id", str(uuid.uuid4()))
    user_id = overrides.pop("user_id", str(uuid.uuid4()))

    # Fields that live in reservation_details
    detail_fields = {
        "party_size", "requested_date", "time_range_start",
        "time_range_end", "contact_phone", "special_requests",
    }
    detail_overrides = {k: overrides.pop(k) for k in list(overrides) if k in detail_fields}

    # Insert into requests table
    request_data = {
        "id": request_id,
        "user_id": user_id,
        "type": "reservation",
        "status": overrides.pop("status", "pending"),
        "cascade_status": overrides.pop("cascade_status", "idle"),
        "current_restaurant_idx": overrides.pop("current_restaurant_idx", 0),
        **overrides,
    }
    result = db.table("requests").insert(request_data).execute()
    req = result.data[0]

    # Insert into reservation_details table
    details_data = {
        "request_id": request_id,
        "party_size": detail_overrides.get("party_size", 4),
        "requested_date": detail_overrides.get("requested_date", "2025-02-15"),
        "time_range_start": detail_overrides.get("time_range_start", "18:00"),
        "time_range_end": detail_overrides.get("time_range_end", "20:00"),
        "contact_phone": detail_overrides.get("contact_phone", "+15551234567"),
    }
    if "special_requests" in detail_overrides:
        details_data["special_requests"] = detail_overrides["special_requests"]
    db.table("reservation_details").insert(details_data).execute()

    # Return merged dict (matches what _load_request() returns)
    req.update(details_data)
    return req


def make_restaurant(db, name: str, phone: str = "+15559990000") -> dict:
    data = {
        "id": str(uuid.uuid4()),
        "name": name,
        "phone": phone,
    }
    result = db.table("restaurants").insert(data).execute()
    return result.data[0]


def link_restaurant(db, request_id: str, restaurant_id: str, priority: int) -> dict:
    data = {
        "id": str(uuid.uuid4()),
        "request_id": request_id,
        "restaurant_id": restaurant_id,
        "priority": priority,
        "attempt_status": "pending",
        "attempt_count": 0,
    }
    result = db.table("request_restaurants").insert(data).execute()
    return result.data[0]


# ============================================================================
# State Machine Tests
# ============================================================================


class TestCascadeStateMachine:
    """Test cascade status transitions."""

    def test_initial_status_is_idle(self, mock_db):
        req = make_request(mock_db)
        assert req["cascade_status"] == "idle"

    @pytest.mark.asyncio
    async def test_start_sets_running(self, mock_db):
        from src.orchestrator.cascade import CascadeOrchestrator

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A")
        link_restaurant(mock_db, req["id"], r1["id"], 1)

        orch = CascadeOrchestrator(mock_db, req["id"])

        # Mock _place_call to avoid Twilio
        with patch.object(orch, "_place_call", new_callable=AsyncMock, return_value=None):
            with patch("src.orchestrator.events.get_redis_client", return_value=None):
                await orch._run_cascade()

        # Request should have been updated to running, then exhausted (since _place_call returns None)
        req_data = mock_db.get_data("requests")
        assert len(req_data) == 1
        # Final state after all restaurants fail should be exhausted
        assert req_data[0]["cascade_status"] == "exhausted"

    @pytest.mark.asyncio
    async def test_cancel_sets_cancelled(self, mock_db):
        from src.orchestrator.cascade import CascadeOrchestrator

        req = make_request(mock_db)
        orch = CascadeOrchestrator(mock_db, req["id"])

        with patch("src.orchestrator.events.get_redis_client", return_value=None):
            await orch.cancel()

        req_data = mock_db.get_data("requests")
        assert req_data[0]["cascade_status"] == "cancelled"
        assert req_data[0]["status"] == "cancelled"


# ============================================================================
# Restaurant Ordering Tests
# ============================================================================


class TestRestaurantOrdering:
    """Test restaurants are tried in priority order."""

    def test_restaurants_loaded_by_priority(self, mock_db):
        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A")
        r2 = make_restaurant(mock_db, "Restaurant B")
        r3 = make_restaurant(mock_db, "Restaurant C")

        link_restaurant(mock_db, req["id"], r2["id"], 2)
        link_restaurant(mock_db, req["id"], r1["id"], 1)
        link_restaurant(mock_db, req["id"], r3["id"], 3)

        # Query with ordering
        result = mock_db.table("request_restaurants").select("*").eq(
            "request_id", req["id"]
        ).order("priority", ascending=True).execute()

        assert len(result.data) == 3
        assert result.data[0]["restaurant_id"] == r1["id"]
        assert result.data[1]["restaurant_id"] == r2["id"]
        assert result.data[2]["restaurant_id"] == r3["id"]

    @pytest.mark.asyncio
    async def test_reorder_updates_priorities(self, mock_db):
        from src.orchestrator.cascade import CascadeOrchestrator

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A")
        r2 = make_restaurant(mock_db, "Restaurant B")
        r3 = make_restaurant(mock_db, "Restaurant C")

        link_restaurant(mock_db, req["id"], r1["id"], 1)
        link_restaurant(mock_db, req["id"], r2["id"], 2)
        link_restaurant(mock_db, req["id"], r3["id"], 3)

        orch = CascadeOrchestrator(mock_db, req["id"])

        # Reorder: C first, then A, then B
        await orch.reorder([r3["id"], r1["id"], r2["id"]])

        # Check updated priorities
        rr_data = mock_db.get_data("request_restaurants")
        r3_entry = next(r for r in rr_data if r["restaurant_id"] == r3["id"])
        r1_entry = next(r for r in rr_data if r["restaurant_id"] == r1["id"])
        r2_entry = next(r for r in rr_data if r["restaurant_id"] == r2["id"])

        assert r3_entry["priority"] == 1
        assert r1_entry["priority"] == 2
        assert r2_entry["priority"] == 3


# ============================================================================
# Event Bus Tests
# ============================================================================


class TestEventBus:
    """Test cascade event persistence and Redis publishing."""

    @pytest.mark.asyncio
    async def test_event_persisted_to_db(self, mock_db):
        from src.orchestrator.events import EventBus

        bus = EventBus(mock_db)

        with patch("src.orchestrator.events.get_redis_client", return_value=None):
            row = await bus.emit(
                request_id="req-123",
                event_type="cascade_started",
                data={"restaurant_count": 3},
            )

        events = mock_db.get_data("cascade_events")
        assert len(events) == 1
        assert events[0]["event_type"] == "cascade_started"
        assert events[0]["request_id"] == "req-123"

    @pytest.mark.asyncio
    async def test_event_published_to_redis(self, mock_db):
        from src.orchestrator.events import EventBus

        bus = EventBus(mock_db)

        mock_redis = AsyncMock()
        with patch("src.orchestrator.events.get_redis_client", return_value=mock_redis):
            await bus.emit(
                request_id="req-456",
                event_type="restaurant_calling",
                restaurant_id="rest-789",
                restaurant_name="Test Restaurant",
            )

        mock_redis.publish.assert_called_once()
        channel, payload = mock_redis.publish.call_args.args
        assert channel == "cascade_events:req-456"
        data = json.loads(payload)
        assert data["event_type"] == "restaurant_calling"
        assert data["request_type"] == "reservation"
        assert data["restaurant_name"] == "Test Restaurant"


# ============================================================================
# Cascade Integration Tests
# ============================================================================


class TestCascadeIntegration:
    """Integration tests for the full cascade flow."""

    @pytest.mark.asyncio
    async def test_cascade_exhausted_when_all_fail(self, mock_db):
        """All restaurants fail → cascade_status = exhausted."""
        from src.orchestrator.cascade import CascadeOrchestrator

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A", "+15551111111")
        r2 = make_restaurant(mock_db, "Restaurant B", "+15552222222")
        r3 = make_restaurant(mock_db, "Restaurant C", "+15553333333")

        link_restaurant(mock_db, req["id"], r1["id"], 1)
        link_restaurant(mock_db, req["id"], r2["id"], 2)
        link_restaurant(mock_db, req["id"], r3["id"], 3)

        orch = CascadeOrchestrator(mock_db, req["id"])

        # Mock _place_call to always fail (return None)
        with patch.object(orch, "_place_call", new_callable=AsyncMock, return_value=None):
            with patch("src.orchestrator.events.get_redis_client", return_value=None):
                with patch("src.orchestrator.notifications.os.getenv", return_value=None):
                    await orch._run_cascade()

        req_data = mock_db.get_data("requests")
        assert req_data[0]["cascade_status"] == "exhausted"
        assert req_data[0]["status"] == "failed"

        # All restaurants should be marked as failed
        rr_data = mock_db.get_data("request_restaurants")
        for rr in rr_data:
            assert rr["attempt_status"] == "failed"

    @pytest.mark.asyncio
    async def test_cascade_stops_on_first_success(self, mock_db):
        """First restaurant succeeds → cascade_status = completed, second not called."""
        from src.orchestrator.cascade import CascadeOrchestrator
        from src.orchestrator.state import CallOutcome

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A", "+15551111111")
        r2 = make_restaurant(mock_db, "Restaurant B", "+15552222222")

        link_restaurant(mock_db, req["id"], r1["id"], 1)
        link_restaurant(mock_db, req["id"], r2["id"], 2)

        orch = CascadeOrchestrator(mock_db, req["id"])

        call_count = 0

        async def mock_place_call(req_data, restaurant, attempt_number):
            nonlocal call_count
            call_count += 1
            return f"CA{call_count}"

        async def mock_wait_outcome(call_id, call_sid):
            # First call succeeds
            return CallOutcome.SUCCEEDED

        with patch.object(orch, "_place_call", side_effect=mock_place_call):
            with patch.object(orch, "_wait_for_outcome", side_effect=mock_wait_outcome):
                with patch("src.orchestrator.events.get_redis_client", return_value=None):
                    with patch("src.orchestrator.notifications.os.getenv", return_value=None):
                        await orch._run_cascade()

        # Only one call should have been made
        assert call_count == 1

        req_data = mock_db.get_data("requests")
        assert req_data[0]["cascade_status"] == "completed"
        assert req_data[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_cascade_first_fails_second_succeeds(self, mock_db):
        """First restaurant fails, second succeeds."""
        from src.orchestrator.cascade import CascadeOrchestrator
        from src.orchestrator.state import CallOutcome

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A", "+15551111111")
        r2 = make_restaurant(mock_db, "Restaurant B", "+15552222222")
        r3 = make_restaurant(mock_db, "Restaurant C", "+15553333333")

        link_restaurant(mock_db, req["id"], r1["id"], 1)
        link_restaurant(mock_db, req["id"], r2["id"], 2)
        link_restaurant(mock_db, req["id"], r3["id"], 3)

        orch = CascadeOrchestrator(mock_db, req["id"])

        call_count = 0

        async def mock_place_call(req_data, restaurant, attempt_number):
            nonlocal call_count
            call_count += 1
            return f"CA{call_count}"

        outcomes = [CallOutcome.NO_AVAILABILITY, CallOutcome.SUCCEEDED]
        outcome_idx = 0

        async def mock_wait_outcome(call_id, call_sid):
            nonlocal outcome_idx
            result = outcomes[outcome_idx]
            outcome_idx += 1
            return result

        with patch.object(orch, "_place_call", side_effect=mock_place_call):
            with patch.object(orch, "_wait_for_outcome", side_effect=mock_wait_outcome):
                with patch("src.orchestrator.events.get_redis_client", return_value=None):
                    with patch("src.orchestrator.notifications.os.getenv", return_value=None):
                        await orch._run_cascade()

        assert call_count == 2

        req_data = mock_db.get_data("requests")
        assert req_data[0]["cascade_status"] == "completed"

        # First restaurant should be failed, second succeeded
        rr_data = mock_db.get_data("request_restaurants")
        rr_sorted = sorted(rr_data, key=lambda r: r["priority"])
        assert rr_sorted[0]["attempt_status"] == "failed"
        assert rr_sorted[1]["attempt_status"] == "succeeded"
        # Third shouldn't have been attempted
        assert rr_sorted[2]["attempt_status"] == "pending"


# ============================================================================
# Pause / Resume / Skip / Cancel Tests
# ============================================================================


class TestCascadeControls:
    """Test cascade control operations."""

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, mock_db):
        from src.orchestrator.cascade import CascadeOrchestrator

        req = make_request(mock_db)
        orch = CascadeOrchestrator(mock_db, req["id"])

        with patch("src.orchestrator.events.get_redis_client", return_value=None):
            # Pause
            await orch.pause()
            req_data = mock_db.get_data("requests")
            assert req_data[0]["cascade_status"] == "paused"

            # Resume
            await orch.resume()
            req_data = mock_db.get_data("requests")
            assert req_data[0]["cascade_status"] == "running"

    @pytest.mark.asyncio
    async def test_cancel_stops_cascade(self, mock_db):
        from src.orchestrator.cascade import CascadeOrchestrator

        req = make_request(mock_db)
        orch = CascadeOrchestrator(mock_db, req["id"])

        with patch("src.orchestrator.events.get_redis_client", return_value=None):
            with patch("src.orchestrator.notifications.os.getenv", return_value=None):
                await orch.cancel()

        req_data = mock_db.get_data("requests")
        assert req_data[0]["cascade_status"] == "cancelled"
        assert req_data[0]["status"] == "cancelled"

        # Cancel event should be recorded
        events = mock_db.get_data("cascade_events")
        event_types = [e["event_type"] for e in events]
        assert "cascade_cancelled" in event_types

    @pytest.mark.asyncio
    async def test_skip_moves_to_next(self, mock_db):
        """Skip advances past the current restaurant."""
        from src.orchestrator.cascade import CascadeOrchestrator
        from src.orchestrator.state import CallOutcome

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A", "+15551111111")
        r2 = make_restaurant(mock_db, "Restaurant B", "+15552222222")

        link_restaurant(mock_db, req["id"], r1["id"], 1)
        link_restaurant(mock_db, req["id"], r2["id"], 2)

        orch = CascadeOrchestrator(mock_db, req["id"])

        call_count = 0

        async def mock_place_call(req_data, restaurant, attempt_number):
            nonlocal call_count
            call_count += 1
            # When first call is placed, trigger skip
            if call_count == 1:
                orch._skip_current = True
            return f"CA{call_count}"

        async def mock_wait_outcome(call_id, call_sid):
            # First call: skip flag triggers FAILED return
            # Second call: succeed
            if call_count <= 1:
                return CallOutcome.FAILED  # Will be overridden by skip
            return CallOutcome.SUCCEEDED

        with patch.object(orch, "_place_call", side_effect=mock_place_call):
            with patch.object(orch, "_wait_for_outcome", side_effect=mock_wait_outcome):
                with patch("src.orchestrator.events.get_redis_client", return_value=None):
                    with patch("src.orchestrator.notifications.os.getenv", return_value=None):
                        await orch._run_cascade()

        assert call_count == 2

        rr_data = mock_db.get_data("request_restaurants")
        rr_sorted = sorted(rr_data, key=lambda r: r["priority"])
        assert rr_sorted[0]["attempt_status"] == "skipped"
        assert rr_sorted[1]["attempt_status"] == "succeeded"


# ============================================================================
# No-Answer Handling Test
# ============================================================================


class TestNoAnswer:
    """Test no-answer retry behavior."""

    @pytest.mark.asyncio
    async def test_no_answer_marked_correctly(self, mock_db):
        from src.orchestrator.cascade import CascadeOrchestrator
        from src.orchestrator.state import CallOutcome

        req = make_request(mock_db)
        r1 = make_restaurant(mock_db, "Restaurant A", "+15551111111")
        link_restaurant(mock_db, req["id"], r1["id"], 1)

        orch = CascadeOrchestrator(mock_db, req["id"])

        async def mock_place_call(req_data, restaurant, attempt_number):
            return "CA001"

        async def mock_wait_outcome(call_id, call_sid):
            return CallOutcome.NO_ANSWER

        with patch.object(orch, "_place_call", side_effect=mock_place_call):
            with patch.object(orch, "_wait_for_outcome", side_effect=mock_wait_outcome):
                with patch("src.orchestrator.events.get_redis_client", return_value=None):
                    with patch("src.orchestrator.notifications.os.getenv", return_value=None):
                        await orch._run_cascade()

        rr_data = mock_db.get_data("request_restaurants")
        assert rr_data[0]["attempt_status"] == "no_answer"
        assert rr_data[0]["failure_reason"] == "No answer"


# ============================================================================
# Notification Tests
# ============================================================================


class TestNotifications:
    """Test SMS notification recording."""

    @pytest.mark.asyncio
    async def test_notification_recorded_in_db(self, mock_db):
        from src.orchestrator.notifications import NotificationService

        svc = NotificationService(mock_db)

        with patch("src.orchestrator.notifications.os.getenv", return_value=None):
            result = await svc.send_sms(
                request_id="req-1",
                user_id="user-1",
                to_phone="+15551234567",
                notification_type="cascade_started",
                message="Testing notification",
            )

        # SMS won't send (no Twilio), but notification should be recorded
        assert result is False  # No Twilio client

        notifs = mock_db.get_data("notifications")
        assert len(notifs) == 1
        assert notifs[0]["notification_type"] == "cascade_started"
        assert notifs[0]["message"] == "Testing notification"
        assert notifs[0]["status"] == "pending"


# ============================================================================
# SSE Event Schema Tests
# ============================================================================


class TestSSEEvents:
    """Test SSE event format includes request_type."""

    @pytest.mark.asyncio
    async def test_sse_event_includes_request_type(self, mock_db):
        from src.orchestrator.events import EventBus

        bus = EventBus(mock_db)

        mock_redis = AsyncMock()
        published_data = None

        async def capture_publish(channel, data):
            nonlocal published_data
            published_data = json.loads(data)

        mock_redis.publish = capture_publish

        with patch("src.orchestrator.events.get_redis_client", return_value=mock_redis):
            await bus.emit(
                request_id="req-sse",
                event_type="restaurant_calling",
                restaurant_name="SSE Test Restaurant",
            )

        assert published_data is not None
        assert published_data["request_type"] == "reservation"
        assert published_data["event_type"] == "restaurant_calling"
        assert published_data["restaurant_name"] == "SSE Test Restaurant"
        assert "timestamp" in published_data


# ============================================================================
# DB Client Tests
# ============================================================================


class TestDBClientExtensions:
    """Test the select() and order() extensions to PostgresClient."""

    def test_select_returns_rows(self, mock_db):
        mock_db.table("restaurants").insert({"id": "1", "name": "A", "priority": 1}).execute()
        mock_db.table("restaurants").insert({"id": "2", "name": "B", "priority": 2}).execute()

        result = mock_db.table("restaurants").select("*").execute()
        assert len(result.data) == 2

    def test_select_with_filter(self, mock_db):
        mock_db.table("restaurants").insert({"id": "1", "name": "A"}).execute()
        mock_db.table("restaurants").insert({"id": "2", "name": "B"}).execute()

        result = mock_db.table("restaurants").select("*").eq("id", "1").execute()
        assert len(result.data) == 1
        assert result.data[0]["name"] == "A"

    def test_select_with_order(self, mock_db):
        mock_db.table("items").insert({"id": "1", "priority": 3}).execute()
        mock_db.table("items").insert({"id": "2", "priority": 1}).execute()
        mock_db.table("items").insert({"id": "3", "priority": 2}).execute()

        result = mock_db.table("items").select("*").order("priority", ascending=True).execute()
        priorities = [r["priority"] for r in result.data]
        assert priorities == [1, 2, 3]

    def test_select_with_order_descending(self, mock_db):
        mock_db.table("items").insert({"id": "1", "priority": 1}).execute()
        mock_db.table("items").insert({"id": "2", "priority": 3}).execute()
        mock_db.table("items").insert({"id": "3", "priority": 2}).execute()

        result = mock_db.table("items").select("*").order("priority", ascending=False).execute()
        priorities = [r["priority"] for r in result.data]
        assert priorities == [3, 2, 1]
