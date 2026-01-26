"""
End Call Tool
Function calling tool for Gemini to gracefully end a call without a booking.
"""

import logging
from typing import TypedDict

from src.db import get_db_client

logger = logging.getLogger(__name__)


class EndCallDetails(TypedDict, total=False):
    """Details about ending the call from Gemini function call."""

    reason: str
    call_summary: str | None


class CallContext(TypedDict, total=False):
    """Context passed from the call handler."""

    call_id: str
    request_id: str | None
    restaurant_id: str | None


# Schema for Gemini function calling
END_CALL_SCHEMA = {
    "name": "end_call",
    "description": "Gracefully end the call without making a reservation. Call this when: the conversation is complete but no booking was made, the restaurant declined, the user (via the AI) decided not to proceed, or any other situation where the call should end without a confirmed reservation.",
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "The reason for ending the call (e.g., 'user declined alternative', 'restaurant closed', 'will call back later', 'wrong number')",
            },
            "call_summary": {
                "type": "string",
                "description": "A brief summary of what happened during the call for record-keeping",
            },
        },
        "required": ["reason"],
    },
}


async def end_call(context: CallContext, details: EndCallDetails) -> dict:
    """
    End a call gracefully without a booking.

    Args:
        context: Call context containing call_id, request_id, restaurant_id
        details: Details about why the call is ending

    Returns:
        Dict with success status and recorded information
    """
    client = get_db_client()
    if not client:
        raise ValueError("Database client not available")

    call_id = context.get("call_id")
    if not call_id:
        raise ValueError("call_id is required in context")

    reason = details.get("reason", "Call ended")
    call_summary = details.get("call_summary")

    logger.info(f"Ending call {call_id}: {reason}")

    # Update call record
    update_data = {
        "status": "failed",  # No booking made
        "failure_reason": reason,
    }

    if call_summary:
        update_data["transcript_summary"] = call_summary

    client.table("calls").update(update_data).eq("id", call_id).execute()

    # If this call is part of a request, the orchestration layer will decide
    # whether to try the next restaurant or mark the request as failed
    if context.get("request_id"):
        logger.info(f"Request {context['request_id']} call ended without booking")

    logger.info(f"Call {call_id} ended: {reason}")

    return {
        "success": True,
        "reason": reason,
        "call_summary": call_summary,
    }
