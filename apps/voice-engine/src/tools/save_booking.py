"""
Save Booking Tool
Function calling tool for Gemini to save confirmed reservations.
"""

import os
from datetime import datetime
from typing import TypedDict

from supabase import create_client, Client


class BookingDetails(TypedDict):
    """Booking details from Gemini function call."""

    call_id: str
    restaurant_name: str
    party_size: int
    confirmed_time: str  # ISO format
    confirmation_code: str | None


# Schema for Gemini function calling
SAVE_BOOKING_SCHEMA = {
    "name": "save_booking",
    "description": "Save a confirmed restaurant reservation to the database. Call this when the restaurant confirms the booking.",
    "parameters": {
        "type": "object",
        "properties": {
            "restaurant_name": {
                "type": "string",
                "description": "Name of the restaurant",
            },
            "party_size": {
                "type": "integer",
                "description": "Number of people in the party",
            },
            "confirmed_time": {
                "type": "string",
                "description": "Confirmed reservation time in ISO 8601 format",
            },
            "confirmation_code": {
                "type": "string",
                "description": "Confirmation code provided by the restaurant, if any",
            },
        },
        "required": ["restaurant_name", "party_size", "confirmed_time"],
    },
}


def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, key)


async def save_booking(call_id: str, booking: BookingDetails) -> dict:
    """
    Save a confirmed reservation to the database.

    Args:
        call_id: The UUID of the current call record
        booking: Booking details from Gemini

    Returns:
        The created reservation record
    """
    client = get_supabase_client()

    # Parse the confirmed time
    confirmed_time = datetime.fromisoformat(booking["confirmed_time"])

    # Insert reservation
    reservation = {
        "call_id": call_id,
        "restaurant_name": booking["restaurant_name"],
        "party_size": booking["party_size"],
        "confirmed_time": confirmed_time.isoformat(),
        "confirmation_code": booking.get("confirmation_code"),
    }

    result = client.table("reservations").insert(reservation).execute()

    # Update call status
    client.table("calls").update({"status": "completed"}).eq("id", call_id).execute()

    return result.data[0] if result.data else {}
