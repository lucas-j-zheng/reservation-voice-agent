"""
Save Booking Tool
Function calling tool for Gemini to save confirmed reservations.
"""

import logging
from datetime import datetime
from typing import TypedDict

from src.db import get_db_client

logger = logging.getLogger(__name__)


class BookingDetails(TypedDict, total=False):
    """Booking details from Gemini function call."""

    confirmed_date: str  # YYYY-MM-DD format
    confirmed_time: str  # HH:MM format
    party_size: int
    confirmation_code: str | None
    notes: str | None


class CallContext(TypedDict, total=False):
    """Context passed from the call handler."""

    call_id: str
    request_id: str | None
    restaurant_id: str | None
    restaurant_name: str | None
    user_id: str | None


# Schema for Gemini function calling
SAVE_BOOKING_SCHEMA = {
    "name": "save_booking",
    "description": "Save a confirmed restaurant reservation to the database. Call this when the restaurant confirms the booking with a specific date and time.",
    "parameters": {
        "type": "object",
        "properties": {
            "confirmed_date": {
                "type": "string",
                "description": "Confirmed reservation date in YYYY-MM-DD format (e.g., '2025-01-20')",
            },
            "confirmed_time": {
                "type": "string",
                "description": "Confirmed reservation time in HH:MM format, 24-hour (e.g., '19:30' for 7:30 PM)",
            },
            "party_size": {
                "type": "integer",
                "description": "Number of people in the party",
            },
            "confirmation_code": {
                "type": "string",
                "description": "Confirmation code or reference number provided by the restaurant, if any",
            },
            "notes": {
                "type": "string",
                "description": "Any additional notes about the reservation (special requests, table preferences, etc.)",
            },
        },
        "required": ["confirmed_date", "confirmed_time", "party_size"],
    },
}


async def save_booking(context: CallContext, booking: BookingDetails) -> dict:
    """
    Save a confirmed reservation to the database.

    Args:
        context: Call context containing call_id, request_id, restaurant_id, etc.
        booking: Booking details from Gemini

    Returns:
        Dict with success status and reservation details
    """
    client = get_db_client()
    if not client:
        raise ValueError("Database client not available")

    call_id = context.get("call_id")
    if not call_id:
        raise ValueError("call_id is required in context")

    # Validate date and time formats
    try:
        confirmed_date = booking["confirmed_date"]
        confirmed_time = booking["confirmed_time"]
        # Validate date format
        datetime.strptime(confirmed_date, "%Y-%m-%d")
        # Validate time format
        datetime.strptime(confirmed_time, "%H:%M")
    except (KeyError, ValueError) as e:
        raise ValueError(f"Invalid date/time format: {e}")

    # Get restaurant name from context or fetch from DB
    restaurant_name = context.get("restaurant_name")
    restaurant_id = context.get("restaurant_id")

    if not restaurant_name and restaurant_id:
        # Fetch restaurant name from database
        result = client.table("restaurants").select("name").eq("id", restaurant_id).execute()
        if result.data:
            restaurant_name = result.data[0]["name"]

    if not restaurant_name:
        restaurant_name = "Unknown Restaurant"
        logger.warning(f"No restaurant name available for call {call_id}")

    # Build reservation record
    reservation = {
        "call_id": call_id,
        "restaurant_name": restaurant_name,
        "party_size": booking["party_size"],
        "confirmed_date": confirmed_date,
        "confirmed_time": confirmed_time,
        "confirmation_code": booking.get("confirmation_code"),
        "notes": booking.get("notes"),
        "status": "confirmed",
    }

    # Add optional context fields
    if context.get("request_id"):
        reservation["request_id"] = context["request_id"]
    if context.get("restaurant_id"):
        reservation["restaurant_id"] = context["restaurant_id"]
    if context.get("user_id"):
        reservation["user_id"] = context["user_id"]

    logger.info(f"Saving reservation: {reservation}")

    result = client.table("reservations").insert(reservation).execute()

    # Update call status to completed
    client.table("calls").update({"status": "completed"}).eq("id", call_id).execute()

    # If this call is part of a request, update request status
    if context.get("request_id"):
        client.table("reservation_requests").update(
            {"status": "completed"}
        ).eq("id", context["request_id"]).execute()

    reservation_data = result.data[0] if result.data else {}
    logger.info(f"Reservation saved successfully: {reservation_data.get('id')}")

    return {
        "success": True,
        "reservation_id": reservation_data.get("id"),
        "message": f"Reservation confirmed for {booking['party_size']} people on {confirmed_date} at {confirmed_time}",
    }
