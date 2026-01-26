"""
E2E Tests: No Availability Flow

Tests the scenario when a restaurant cannot accommodate the reservation:
1. Twilio connects WebSocket
2. Conversation happens
3. Gemini triggers report_no_availability tool
4. Call updated with failure reason
5. Call marked as failed (unless trying alternative)
"""

import asyncio
import pytest
from unittest.mock import patch

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.stream.twilio_handler import TwilioMediaHandler
from src.tools import report_no_availability, CallContext
from tests.conftest import generate_mulaw_silence


class TestNoAvailabilityFlow:
    """Test the no-availability flow when restaurant can't accommodate."""

    async def test_report_no_availability_basic(self, mock_db, call_context, no_availability_args):
        """Test basic no-availability reporting."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            result = await report_no_availability(call_context, no_availability_args)

        assert result["success"] is True
        assert result["reason"] == "Fully booked for the requested time"
        assert result["alternative_offered"] == "8:30 PM available"
        assert result["should_try_alternative"] is True

    async def test_call_not_failed_when_trying_alternative(self, mock_db, call_context):
        """Test call stays ongoing when should_try_alternative is True."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {
            "reason": "Fully booked at 7pm",
            "alternative_offered": "8:30 PM available",
            "should_try_alternative": True,
        }

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            await report_no_availability(call_context, args)

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        # Status should NOT be failed since we're trying alternative
        assert call["status"] == "ongoing"
        assert "Fully booked" in call["failure_reason"]
        assert "8:30 PM" in call["failure_reason"]

    async def test_call_failed_when_not_trying_alternative(self, mock_db, call_context):
        """Test call marked as failed when should_try_alternative is False."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {
            "reason": "Restaurant closed on Mondays",
            "should_try_alternative": False,
        }

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            await report_no_availability(call_context, args)

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        assert call["status"] == "failed"
        assert "closed on Mondays" in call["failure_reason"]

    async def test_failure_reason_recorded(self, mock_db, call_context):
        """Test that failure reason is properly recorded."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {
            "reason": "Party size too large",
            "alternative_offered": "Can accommodate up to 8 people",
            "should_try_alternative": False,
        }

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            await report_no_availability(call_context, args)

        calls = mock_db.get_data("calls")
        call = next((c for c in calls if c["id"] == call_id), None)
        assert "Party size too large" in call["failure_reason"]
        assert "Can accommodate up to 8" in call["failure_reason"]

    async def test_minimal_no_availability(self, mock_db, call_context):
        """Test no-availability with only required fields."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {"reason": "No tables available"}

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            result = await report_no_availability(call_context, args)

        assert result["success"] is True
        assert result["reason"] == "No tables available"
        assert result["alternative_offered"] is None
        assert result["should_try_alternative"] is False


class TestNoAvailabilityHandlerIntegration:
    """Test no-availability through the handler."""

    async def test_handler_executes_no_availability_tool(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test handler processes report_no_availability tool call."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
            restaurant_name="Test Restaurant",
        )

        # Create call record
        mock_db.table("calls").insert({
            "id": "call-123",
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        handler.call_id = "call-123"
        handler._gemini = mock_gemini

        tool_id = "tool-no-avail-123"

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            await handler._execute_report_no_availability(
                tool_id,
                {
                    "reason": "Fully booked",
                    "should_try_alternative": False,
                }
            )

        # Verify tool response sent to Gemini
        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 1
        assert responses[0]["name"] == "report_no_availability"
        assert responses[0]["response"]["success"] is True

    async def test_full_no_availability_flow(self, mock_db, mock_websocket, mock_gemini):
        """Test complete flow when Gemini calls report_no_availability."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        # Queue the tool call from Gemini
        mock_gemini.queue_tool_call(
            name="report_no_availability",
            args={
                "reason": "Restaurant fully booked",
                "should_try_alternative": False,
            },
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-no-avail-test")
        mock_websocket.send_media(generate_mulaw_silence())
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
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


class TestNoAvailabilityValidation:
    """Test input validation for no-availability reporting."""

    async def test_missing_call_id(self, mock_db, no_availability_args):
        """Test that missing call_id raises error."""
        context = CallContext(request_id="req-123")  # No call_id

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            with pytest.raises(ValueError, match="call_id is required"):
                await report_no_availability(context, no_availability_args)

    async def test_no_database_client(self, no_availability_args, call_context):
        """Test that missing database client raises error."""
        with patch("src.tools.report_no_availability.get_db_client", return_value=None):
            with pytest.raises(ValueError, match="Database client not available"):
                await report_no_availability(call_context, no_availability_args)

    async def test_default_reason_when_empty(self, mock_db, call_context):
        """Test default reason is used when not provided."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        args = {}  # Empty args

        with patch("src.tools.report_no_availability.get_db_client", return_value=mock_db):
            result = await report_no_availability(call_context, args)

        assert result["reason"] == "Unknown reason"
