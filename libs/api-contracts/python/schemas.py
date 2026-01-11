"""
Shared Pydantic schemas for API contracts.
These schemas ensure data consistency between voice-engine and database.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CallCreate(BaseModel):
    """Schema for creating a new call record."""

    twilio_sid: str = Field(..., description="Twilio Call SID")


class Call(BaseModel):
    """Schema for a call record."""

    id: UUID
    twilio_sid: str
    status: Literal["ongoing", "completed", "failed"]
    transcript_summary: str | None = None


class ReservationCreate(BaseModel):
    """Schema for creating a reservation."""

    call_id: UUID
    restaurant_name: str
    party_size: int = Field(..., ge=1, le=20)
    confirmed_time: datetime
    confirmation_code: str | None = None


class Reservation(BaseModel):
    """Schema for a reservation record."""

    id: UUID
    call_id: UUID
    restaurant_name: str
    party_size: int
    confirmed_time: datetime
    confirmation_code: str | None = None


class ReservationRequest(BaseModel):
    """Schema for initiating a reservation call."""

    user_name: str
    restaurant_phone: str
    party_size: int = Field(..., ge=1, le=20)
    preferred_date: str = Field(..., description="Date in YYYY-MM-DD format")
    preferred_time: str = Field(..., description="Time in HH:MM format")
    contact_phone: str
