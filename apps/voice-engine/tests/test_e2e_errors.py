"""
E2E Tests: Error Scenarios

Tests error handling throughout the system:
1. Database unavailability
2. Gemini connection errors
3. Tool execution failures
4. Invalid inputs
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.stream.twilio_handler import TwilioMediaHandler
from src.tools import save_booking, report_no_availability, end_call, CallContext
from tests.conftest import generate_mulaw_silence


class TestDatabaseErrors:
    """Test handling of database errors."""

    async def test_handler_continues_without_db(self, mock_websocket, mock_gemini):
        """Test handler continues even if database is unavailable."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=None,  # No database
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        mock_websocket.send_media(generate_mulaw_silence())
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        # Should complete without error even without database
        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

    async def test_call_record_creation_error_handled(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that database errors during call creation are handled."""
        # Make insert raise an exception
        original_table = mock_db.table

        def failing_table(name):
            builder = original_table(name)
            if name == "calls":
                original_execute = builder.insert

                def failing_insert(*args, **kwargs):
                    raise Exception("Database connection lost")

                builder.insert = failing_insert
            return builder

        mock_db.table = failing_table

        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        # Should handle error gracefully
        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

    async def test_status_update_error_handled(self, mock_db, mock_websocket, mock_gemini):
        """Test that database errors during status update are handled."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-error-test")

        # Make update fail
        original_table = mock_db.table

        def failing_on_update(name):
            builder = original_table(name)
            if name == "calls":

                def failing_update(*args, **kwargs):
                    raise Exception("Update failed")

                builder.update = failing_update
            return builder

        mock_db.table = failing_on_update

        mock_websocket.send_stop()
        mock_websocket.close_stream()

        # Should handle error gracefully
        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass


class TestToolExecutionErrors:
    """Test handling of tool execution errors."""

    async def test_save_booking_error_sent_to_gemini(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that tool errors are sent back to Gemini."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        handler.call_id = "call-error-test"
        handler._gemini = mock_gemini

        # Force save_booking to fail
        with patch(
            "src.tools.save_booking.get_db_client",
            return_value=None  # This will cause ValueError
        ):
            await handler._execute_save_booking(
                "tool-error-123",
                {
                    "confirmed_date": "2025-01-25",
                    "confirmed_time": "19:30",
                    "party_size": 4,
                }
            )

        # Verify error response was sent to Gemini
        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 1
        assert responses[0]["response"]["success"] is False
        assert "error" in responses[0]["response"]

    async def test_save_booking_without_call_id(self, mock_db, mock_websocket, mock_gemini):
        """Test save_booking fails gracefully without call_id."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        # Don't set call_id
        handler._gemini = mock_gemini

        await handler._execute_save_booking(
            "tool-no-call-id",
            {
                "confirmed_date": "2025-01-25",
                "confirmed_time": "19:30",
                "party_size": 4,
            }
        )

        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 1
        assert responses[0]["response"]["success"] is False
        assert "call_id" in responses[0]["response"]["error"].lower()

    async def test_report_no_availability_error_handled(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that report_no_availability errors are handled."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        handler.call_id = None  # No call_id
        handler._gemini = mock_gemini

        await handler._execute_report_no_availability(
            "tool-error-456",
            {"reason": "Test reason"}
        )

        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 1
        assert responses[0]["response"]["success"] is False

    async def test_end_call_error_handled(self, mock_db, mock_websocket, mock_gemini):
        """Test that end_call errors are handled."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        handler.call_id = None  # No call_id
        handler._gemini = mock_gemini

        await handler._execute_end_call(
            "tool-error-789",
            {"reason": "Test reason"}
        )

        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 1
        assert responses[0]["response"]["success"] is False

    async def test_unknown_tool_logged(self, mock_db, mock_websocket, mock_gemini):
        """Test that unknown tool calls are logged but don't crash."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        handler.call_id = "call-test"
        handler._gemini = mock_gemini

        # Call with unknown tool name
        handler._handle_tool_call("unknown_tool", "tool-unknown-123", {"arg": "value"})

        # Should not crash, just log warning
        # No response should be sent for unknown tools
        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 0


class TestInputValidationErrors:
    """Test input validation error handling."""

    async def test_booking_missing_required_fields(self, mock_db, call_context):
        """Test booking with missing required fields."""
        mock_db.table("calls").insert({
            "id": call_context["call_id"],
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        with patch("src.tools.save_booking.get_db_client", return_value=mock_db):
            # Missing party_size
            with pytest.raises(KeyError):
                await save_booking(
                    call_context,
                    {
                        "confirmed_date": "2025-01-25",
                        "confirmed_time": "19:30",
                        # Missing party_size
                    }
                )

    async def test_booking_invalid_date(self, mock_db, call_context):
        """Test booking with invalid date format."""
        mock_db.table("calls").insert({
            "id": call_context["call_id"],
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        with patch("src.tools.save_booking.get_db_client", return_value=mock_db):
            with pytest.raises(ValueError, match="Invalid date/time format"):
                await save_booking(
                    call_context,
                    {
                        "confirmed_date": "invalid-date",
                        "confirmed_time": "19:30",
                        "party_size": 4,
                    }
                )

    async def test_booking_invalid_time(self, mock_db, call_context):
        """Test booking with invalid time format."""
        mock_db.table("calls").insert({
            "id": call_context["call_id"],
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        with patch("src.tools.save_booking.get_db_client", return_value=mock_db):
            with pytest.raises(ValueError, match="Invalid date/time format"):
                await save_booking(
                    call_context,
                    {
                        "confirmed_date": "2025-01-25",
                        "confirmed_time": "25:99",  # Invalid time
                        "party_size": 4,
                    }
                )


class TestGeminiConnectionErrors:
    """Test handling of Gemini connection issues."""

    async def test_handler_handles_gemini_close(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test handler handles Gemini connection closing."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Gemini should be closed after handler exits
        assert mock_gemini._connected is False

    async def test_background_tasks_cancelled_on_exit(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that background tasks are cancelled when stream ends."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        mock_websocket.send_media(generate_mulaw_silence())
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Handler should have cleaned up
        assert handler._running is False


class TestConcurrencyErrors:
    """Test handling of concurrent operations."""

    async def test_multiple_tool_calls_handled(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test handling multiple tool calls in sequence."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
            restaurant_name="Test Restaurant",
        )

        # Create call record
        mock_db.table("calls").insert({
            "id": "call-multi-tool",
            "twilio_sid": "CA-multi",
            "status": "ongoing",
        }).execute()

        handler.call_id = "call-multi-tool"
        handler._gemini = mock_gemini

        # Execute multiple tools
        with patch("src.tools.save_booking.get_db_client", return_value=mock_db):
            with patch("src.tools.end_call.get_db_client", return_value=mock_db):
                # First report no availability
                await handler._execute_report_no_availability(
                    "tool-1",
                    {"reason": "Fully booked", "should_try_alternative": True}
                )

                # Then save booking
                await handler._execute_save_booking(
                    "tool-2",
                    {
                        "confirmed_date": "2025-01-25",
                        "confirmed_time": "20:30",
                        "party_size": 4,
                    }
                )

        # Both responses should be sent
        responses = mock_gemini.get_tool_responses()
        assert len(responses) == 2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_empty_audio_ignored(self, mock_db, mock_websocket, mock_gemini):
        """Test that empty audio chunks are ignored."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        # Send empty audio
        mock_websocket.send_media(b"")
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

    async def test_handler_with_all_context_fields(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test handler with all context fields populated."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
            request_id="req-full",
            restaurant_id="rest-full",
            restaurant_name="Full Context Restaurant",
            user_id="user-full",
        )

        context = handler._get_call_context()
        assert context.get("request_id") == "req-full"
        assert context.get("restaurant_id") == "rest-full"
        assert context.get("restaurant_name") == "Full Context Restaurant"
        assert context.get("user_id") == "user-full"

    async def test_booking_fetches_restaurant_name(self, mock_db, call_context):
        """Test that booking fetches restaurant name if not in context."""
        call_id = call_context["call_id"]
        restaurant_id = call_context["restaurant_id"]

        # Create call and restaurant records
        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        mock_db.table("restaurants").insert({
            "id": restaurant_id,
            "name": "Fetched Restaurant Name",
        }).execute()

        # Context without restaurant_name but with restaurant_id
        context_without_name = CallContext(
            call_id=call_id,
            restaurant_id=restaurant_id,
        )

        booking_args = {
            "confirmed_date": "2025-01-25",
            "confirmed_time": "19:30",
            "party_size": 4,
        }

        with patch("src.tools.save_booking.get_db_client", return_value=mock_db):
            await save_booking(context_without_name, booking_args)

        reservations = mock_db.get_data("reservations")
        assert len(reservations) == 1
        assert reservations[0]["restaurant_name"] == "Fetched Restaurant Name"

    async def test_booking_uses_default_restaurant_name(self, mock_db, call_context):
        """Test that booking uses default name if none available."""
        call_id = call_context["call_id"]

        mock_db.table("calls").insert({
            "id": call_id,
            "twilio_sid": "CA-test",
            "status": "ongoing",
        }).execute()

        # Context without restaurant_name or restaurant_id
        context_minimal = CallContext(call_id=call_id)

        booking_args = {
            "confirmed_date": "2025-01-25",
            "confirmed_time": "19:30",
            "party_size": 4,
        }

        with patch("src.tools.save_booking.get_db_client", return_value=mock_db):
            await save_booking(context_minimal, booking_args)

        reservations = mock_db.get_data("reservations")
        assert len(reservations) == 1
        assert reservations[0]["restaurant_name"] == "Unknown Restaurant"
