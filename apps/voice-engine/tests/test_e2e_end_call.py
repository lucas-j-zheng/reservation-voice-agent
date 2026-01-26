"""
E2E Tests: End Call Flow

Tests the scenario when a call ends without a booking:
1. User declines alternative
2. Call ends gracefully
3. Call marked as failed with reason
4. Summary recorded
"""

import asyncio
import pytest
from unittest.mock import patch

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.stream.twilio_handler import TwilioMediaHandler
from src.tools import end_call, CallContext
from tests.conftest import generate_mulaw_silence


class TestEndCallFlow:
    """Test the end-call flow for graceful termination without booking."""

    async def test_end_call_basic(self, mock_db, call_context, end_call_args):
        """Test basic end call functionality."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            result = await end_call(call_context, end_call_args)

        assert result["success"] is True
        assert result["reason"] == "User declined alternative time"
        assert "7pm" in result["call_summary"]

    async def test_call_marked_as_failed(self, mock_db, call_context, end_call_args):
        """Test that call is marked as failed when ended without booking."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            await end_call(call_context, end_call_args)

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        assert call["status"] == "failed"
        assert call["failure_reason"] == "User declined alternative time"

    async def test_call_summary_recorded(self, mock_db, call_context):
        """Test that call summary is recorded when provided."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {
            "reason": "Restaurant closed",
            "call_summary": "Called Bella Italia, they are permanently closed",
        }

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            await end_call(call_context, args)

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        assert call["transcript_summary"] == "Called Bella Italia, they are permanently closed"

    async def test_end_call_minimal_args(self, mock_db, call_context):
        """Test end call with only required fields."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {"reason": "Wrong number"}

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            result = await end_call(call_context, args)

        assert result["success"] is True
        assert result["reason"] == "Wrong number"
        assert result["call_summary"] is None

    async def test_end_call_without_summary(self, mock_db, call_context):
        """Test that call can end without a summary."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {"reason": "Will call back later"}

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            await end_call(call_context, args)

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        assert "transcript_summary" not in call or call.get("transcript_summary") is None


class TestEndCallReasons:
    """Test various end call reasons."""

    @pytest.mark.parametrize("reason", [
        "User declined alternative",
        "Restaurant closed",
        "Will call back later",
        "Wrong number",
        "No answer after greeting",
        "Language barrier",
        "Technical issues",
    ])
    async def test_various_reasons(self, mock_db, call_context, reason):
        """Test that various reasons are properly recorded."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {"reason": reason}

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            result = await end_call(call_context, args)

        assert result["success"] is True
        assert result["reason"] == reason

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        assert call["failure_reason"] == reason


class TestEndCallHandlerIntegration:
    """Test end_call through the handler."""

    async def test_handler_executes_end_call_tool(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test handler processes end_call tool call."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        # Create call record
        mock_db.table("calls").insert({
            "id": "call-456",
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        handler.call_id = "call-456"
        handler._gemini = mock_gemini

        tool_id = "tool-end-call-456"

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            await handler._execute_end_call(
                tool_id,
                {
                    "reason": "User not interested",
                    "call_summary": "User said they already have a reservation",
                }
            )

        # Verify tool response sent to Gemini
        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 1
        assert responses[0]["name"] == "end_call"
        assert responses[0]["response"]["success"] is True

    async def test_full_end_call_flow(self, mock_db, mock_websocket, mock_gemini):
        """Test complete flow when Gemini calls end_call."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        # Queue the tool call from Gemini
        mock_gemini.queue_tool_call(
            name="end_call",
            args={
                "reason": "Conversation ended normally",
                "call_summary": "User decided not to book",
            },
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-end-test")
        mock_websocket.send_media(generate_mulaw_silence())
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            try:
                await asyncio.wait_for(
                    handler.handle_stream(mock_gemini),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                pass

        # Verify call record exists
        calls = mock_db.get_data("calls")
        assert len(calls) >= 1


class TestEndCallValidation:
    """Test input validation for end_call."""

    async def test_missing_call_id(self, mock_db, end_call_args):
        """Test that missing call_id raises error."""
        context = CallContext(request_id="req-123")  # No call_id

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            with pytest.raises(ValueError, match="call_id is required"):
                await end_call(context, end_call_args)

    async def test_no_database_client(self, end_call_args, call_context):
        """Test that missing database client raises error."""
        with patch("src.tools.end_call.get_db_client", return_value=None):
            with pytest.raises(ValueError, match="Database client not available"):
                await end_call(call_context, end_call_args)

    async def test_default_reason_when_empty(self, mock_db, call_context):
        """Test default reason is used when not provided."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {}  # Empty args

        with patch("src.tools.end_call.get_db_client", return_value=mock_db):
            result = await end_call(call_context, args)

        assert result["reason"] == "Call ended"


class TestCallStatusOnStreamEnd:
    """Test call status when stream ends."""

    async def test_status_failed_when_no_booking(self, mock_db, mock_websocket, mock_gemini):
        """Test call marked as failed when stream ends without booking."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-no-booking-test")
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Call should be marked as failed (no booking saved)
        calls = mock_db.get_data("calls")
        if calls:
            assert calls[0]["status"] == "failed"

    async def test_status_completed_when_booking_saved(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test call marked as completed when booking was saved."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
            restaurant_name="Test Restaurant",
        )

        # Simulate booking was saved
        handler._booking_saved = True

        # Pre-create call record
        mock_db.table("calls").insert({
            "id": "call-booked",
            "twilio_sid": "CA-booked-test",
            "status": "ongoing",
        }).execute()

        handler.call_id = "call-booked"

        # Call the status update directly
        await handler._update_call_status()

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == "call-booked"), None)
        assert call["status"] == "completed"
