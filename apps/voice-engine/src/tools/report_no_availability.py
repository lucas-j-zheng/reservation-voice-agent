"""
Report No Availability Tool
Function calling tool for Gemini to report when a restaurant cannot accommodate.
"""

import logging
from typing import TypedDict

from src.db import get_db_client

logger = logging.getLogger(__name__)


class NoAvailabilityDetails(TypedDict, total=False):
    """Details about unavailability from Gemini function call."""

    reason: str
    alternative_offered: str | None
    should_try_alternative: bool


class CallContext(TypedDict, total=False):
    """Context passed from the call handler."""

    call_id: str
    request_id: str | None
    restaurant_id: str | None


# Schema for Gemini function calling
REPORT_NO_AVAILABILITY_SCHEMA = {
    "name": "report_no_availability",
    "description": "Report that the restaurant cannot accommodate the reservation request. Call this when the restaurant says they are fully booked, closed, or otherwise cannot fulfill the request.",
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "The reason for unavailability (e.g., 'fully booked', 'closed on that day', 'party size too large')",
            },
            "alternative_offered": {
                "type": "string",
                "description": "Any alternative the restaurant offered (e.g., 'different time available at 8:30 PM', 'available next day')",
            },
            "should_try_alternative": {
                "type": "boolean",
                "description": "Whether the user should consider trying the alternative offered. True if the alternative seems reasonable.",
            },
        },
        "required": ["reason"],
    },
}


async def report_no_availability(context: CallContext, details: NoAvailabilityDetails) -> dict:
    """
    Report that a restaurant cannot accommodate the reservation.

    Args:
        context: Call context containing call_id, request_id, restaurant_id
        details: Details about the unavailability

    Returns:
        Dict with success status and recorded information
    """
    client = get_db_client()
    if not client:
        raise ValueError("Database client not available")

    call_id = context.get("call_id")
    if not call_id:
        raise ValueError("call_id is required in context")

    reason = details.get("reason", "Unknown reason")
    alternative_offered = details.get("alternative_offered")
    should_try_alternative = details.get("should_try_alternative", False)

    # Build failure reason string
    failure_reason = f"No availability: {reason}"
    if alternative_offered:
        failure_reason += f". Alternative offered: {alternative_offered}"

    logger.info(f"Reporting no availability for call {call_id}: {failure_reason}")

    # Update call with failure reason (but don't mark as failed yet - call might continue)
    update_data = {
        "failure_reason": failure_reason,
    }

    # Only mark as failed if we're not trying an alternative
    if not should_try_alternative:
        update_data["status"] = "failed"

    client.table("calls").update(update_data).eq("id", call_id).execute()

    # If this call is part of a request and we're not trying alternative, mark request as failed
    # (unless there are other restaurants to try - handled by orchestration logic)
    if context.get("request_id") and not should_try_alternative:
        # Don't automatically fail the request - let the orchestration decide
        # Just log for now
        logger.info(f"Request {context['request_id']} may need to try next restaurant")

    logger.info(f"No availability recorded for call {call_id}")

    return {
        "success": True,
        "reason": reason,
        "alternative_offered": alternative_offered,
        "should_try_alternative": should_try_alternative,
    }
