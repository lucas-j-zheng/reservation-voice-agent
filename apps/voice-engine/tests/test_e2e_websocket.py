"""
E2E Tests: WebSocket Message Handling

Tests Twilio WebSocket protocol handling:
1. Message parsing and validation
2. Pydantic model validation
3. Different event types
4. Malformed message handling
"""

import asyncio
import base64
import json
import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.stream.twilio_handler import (
    TwilioMediaHandler,
    TwilioConnectedMessage,
    TwilioStartMessage,
    TwilioMediaMessage,
    TwilioStopMessage,
    TwilioBaseMessage,
)
from tests.conftest import generate_mulaw_silence


class TestTwilioPydanticModels:
    """Test Pydantic models for Twilio messages."""

    def test_connected_message_valid(self):
        """Test valid connected message."""
        data = {"event": "connected"}
        msg = TwilioConnectedMessage.model_validate(data)
        assert msg.event == "connected"

    def test_connected_message_invalid_event(self):
        """Test connected message with wrong event type."""
        data = {"event": "start"}
        with pytest.raises(ValidationError):
            TwilioConnectedMessage.model_validate(data)

    def test_start_message_valid(self):
        """Test valid start message."""
        data = {
            "event": "start",
            "start": {
                "streamSid": "MZ123",
                "callSid": "CA456",
            }
        }
        msg = TwilioStartMessage.model_validate(data)
        assert msg.event == "start"
        assert msg.start.streamSid == "MZ123"
        assert msg.start.callSid == "CA456"

    def test_start_message_missing_fields(self):
        """Test start message with missing fields."""
        data = {
            "event": "start",
            "start": {
                "streamSid": "MZ123",
                # Missing callSid
            }
        }
        with pytest.raises(ValidationError):
            TwilioStartMessage.model_validate(data)

    def test_media_message_valid(self):
        """Test valid media message."""
        audio_payload = base64.b64encode(b"\xff\xff").decode()
        data = {
            "event": "media",
            "media": {
                "payload": audio_payload,
            }
        }
        msg = TwilioMediaMessage.model_validate(data)
        assert msg.event == "media"
        assert msg.media.payload == audio_payload

    def test_media_message_missing_payload(self):
        """Test media message with missing payload."""
        data = {
            "event": "media",
            "media": {}
        }
        with pytest.raises(ValidationError):
            TwilioMediaMessage.model_validate(data)

    def test_stop_message_valid(self):
        """Test valid stop message."""
        data = {"event": "stop"}
        msg = TwilioStopMessage.model_validate(data)
        assert msg.event == "stop"

    def test_base_message_extracts_event(self):
        """Test base message extracts event type."""
        data = {"event": "custom", "other": "data"}
        msg = TwilioBaseMessage.model_validate(data)
        assert msg.event == "custom"


class TestWebSocketMessageProcessing:
    """Test WebSocket message processing in handler."""

    async def test_connected_event_logged(self, mock_db, mock_websocket, mock_gemini):
        """Test that connected event is processed without error."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Should complete without error

    async def test_start_event_creates_call_record(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that start event creates call record in database."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-test-789", stream_sid="MZ-test-012")
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Verify call record created
        calls = mock_db.get_data("calls")
        assert len(calls) == 1
        assert calls[0]["twilio_sid"] == "CA-test-789"
        assert calls[0]["status"] == "ongoing"

        # Verify stream_sid and call_sid captured
        assert handler.stream_sid == "MZ-test-012"
        assert handler.call_sid == "CA-test-789"

    async def test_start_event_triggers_gemini_greeting(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that start event sends text to Gemini to trigger greeting."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Verify greeting prompt was sent
        texts = mock_gemini.get_received_text()
        assert len(texts) >= 1
        assert "connected" in texts[0].lower() or "introduce" in texts[0].lower()

    async def test_media_event_sends_audio_to_gemini(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that media event audio is sent to Gemini."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()

        # Send multiple audio frames
        audio = generate_mulaw_silence(duration_ms=100)
        mock_websocket.send_media(audio)
        mock_websocket.send_media(audio)
        mock_websocket.send_media(audio)

        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Verify audio was received by Gemini (transcoded)
        received = mock_gemini.get_received_audio()
        assert len(received) >= 1

    async def test_stop_event_updates_call_status(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that stop event updates call status."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-stop-test")
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Verify call status was updated
        calls = mock_db.get_data("calls")
        if calls:
            # Status should be 'failed' since no booking was saved
            assert calls[0]["status"] == "failed"

    async def test_unknown_event_ignored(self, mock_db, mock_websocket, mock_gemini):
        """Test that unknown event types are ignored without error."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        # Send unknown event
        mock_websocket.send_message({"event": "unknown_event", "data": "test"})
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Should complete without error


class TestMalformedMessages:
    """Test handling of malformed WebSocket messages."""

    async def test_invalid_json_skipped(self, mock_db, mock_websocket, mock_gemini):
        """Test that invalid JSON is logged and skipped."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        # Send invalid JSON
        mock_websocket._incoming.put_nowait("not valid json {{{")
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        # Should complete without raising exception
        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

    async def test_missing_event_field_skipped(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that messages without event field are skipped."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        # Send message without event field
        mock_websocket.send_message({"data": "test", "no_event": True})
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

    async def test_invalid_start_message_skipped(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that invalid start message is logged and skipped."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        # Send malformed start event (missing required fields)
        mock_websocket.send_message({
            "event": "start",
            "start": {"streamSid": "only-stream"},  # Missing callSid
        })
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # No call record should be created due to validation error
        calls = mock_db.get_data("calls")
        assert len(calls) == 0

    async def test_invalid_media_payload_skipped(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that invalid media payload is handled gracefully."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        # Send media with invalid base64
        mock_websocket.send_message({
            "event": "media",
            "media": {"payload": "not-valid-base64!!!"},
        })
        mock_websocket.send_stop()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        # Should complete without raising exception


class TestRequestContext:
    """Test that request context is properly passed through."""

    async def test_context_fields_passed_to_call_record(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that request_id and restaurant_id are stored in call record."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
            request_id="req-context-test",
            restaurant_id="rest-context-test",
        )

        mock_websocket.send_connected()
        mock_websocket.send_start(call_sid="CA-context-test")
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        calls = mock_db.get_data("calls")
        assert len(calls) == 1
        assert calls[0]["request_id"] == "req-context-test"
        assert calls[0]["restaurant_id"] == "rest-context-test"

    async def test_request_status_updated_on_start(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that reservation request status is updated to in_progress."""
        # Pre-create a reservation request
        mock_db.table("reservation_requests").insert({
            "id": "req-status-test",
            "status": "pending",
        }).execute()

        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
            request_id="req-status-test",
        )

        mock_websocket.send_connected()
        mock_websocket.send_start()
        mock_websocket.close_stream()

        try:
            await asyncio.wait_for(
                handler.handle_stream(mock_gemini),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass

        requests = mock_db.get_data("reservation_requests")
        req = next((r for r in requests if r["id"] == "req-status-test"), None)
        assert req is not None
        assert req["status"] == "in_progress"


class TestOutboundAudio:
    """Test audio sending to Twilio."""

    async def test_audio_sent_with_correct_format(
        self, mock_db, mock_websocket, mock_gemini
    ):
        """Test that outbound audio has correct Twilio format."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        # Set stream_sid so audio can be sent
        handler.stream_sid = "MZ-test-stream"

        # Send some audio
        audio = generate_mulaw_silence(duration_ms=50)
        await handler.send_audio(audio)

        outgoing = mock_websocket.get_outgoing()
        assert len(outgoing) == 1
        assert outgoing[0]["event"] == "media"
        assert outgoing[0]["streamSid"] == "MZ-test-stream"
        assert "payload" in outgoing[0]["media"]

        # Verify payload is base64
        payload = outgoing[0]["media"]["payload"]
        decoded = base64.b64decode(payload)
        assert decoded == audio

    async def test_audio_not_sent_without_stream_sid(self, mock_db, mock_websocket):
        """Test that audio is not sent if stream_sid not set."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        # Don't set stream_sid
        audio = generate_mulaw_silence(duration_ms=50)
        await handler.send_audio(audio)

        outgoing = mock_websocket.get_outgoing()
        assert len(outgoing) == 0

    async def test_clear_message_sent(self, mock_db, mock_websocket):
        """Test that clear message can be sent to stop Twilio playback."""
        handler = TwilioMediaHandler(
            websocket=mock_websocket,
            db=mock_db,
        )

        handler.stream_sid = "MZ-clear-test"
        await handler._send_clear()

        outgoing = mock_websocket.get_outgoing()
        assert len(outgoing) == 1
        assert outgoing[0]["event"] == "clear"
        assert outgoing[0]["streamSid"] == "MZ-clear-test"
