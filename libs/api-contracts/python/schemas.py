"""
Shared Pydantic schemas for API contracts.
These schemas ensure data consistency between voice-engine and database.
"""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# CORE ENTITY SCHEMAS
# ============================================


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    email: str | None = None
    name: str
    phone: str | None = None


class User(BaseModel):
    """Schema for a user record."""

    id: UUID
    email: str | None = None
    name: str
    phone: str | None = None
    created_at: datetime


class RestaurantCreate(BaseModel):
    """Schema for creating a new restaurant."""

    name: str
    phone: str
    address: str | None = None
    cuisine_type: str | None = None
    notes: str | None = None


class Restaurant(BaseModel):
    """Schema for a restaurant record."""

    id: UUID
    name: str
    phone: str
    address: str | None = None
    cuisine_type: str | None = None
    notes: str | None = None
    created_at: datetime


# ============================================
# RESERVATION REQUEST SCHEMAS (UI Intent)
# ============================================


ReservationRequestStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


class ReservationRequestCreate(BaseModel):
    """Schema for creating a reservation request from UI."""

    user_id: UUID | None = None
    party_size: int = Field(..., ge=1, le=20)
    requested_date: date = Field(..., description="Date in YYYY-MM-DD format")
    time_range_start: time = Field(..., description="Start of time range (HH:MM)")
    time_range_end: time = Field(..., description="End of time range (HH:MM)")
    special_requests: str | None = None
    contact_phone: str | None = None


class ReservationRequest(BaseModel):
    """Schema for a reservation request record."""

    id: UUID
    user_id: UUID | None = None
    party_size: int
    requested_date: date
    time_range_start: time
    time_range_end: time
    special_requests: str | None = None
    contact_phone: str | None = None
    status: ReservationRequestStatus = "pending"
    created_at: datetime


class RequestRestaurantCreate(BaseModel):
    """Schema for adding a restaurant to a request."""

    request_id: UUID
    restaurant_id: UUID
    priority: int = Field(default=1, ge=1)


class RequestRestaurant(BaseModel):
    """Schema for request-restaurant junction."""

    id: UUID
    request_id: UUID
    restaurant_id: UUID
    priority: int


# ============================================
# CALL SCHEMAS (Enhanced with context)
# ============================================


CallStatus = Literal["ongoing", "completed", "failed"]


class CallCreate(BaseModel):
    """Schema for creating a new call record."""

    twilio_sid: str = Field(..., description="Twilio Call SID")
    request_id: UUID | None = None
    restaurant_id: UUID | None = None


class Call(BaseModel):
    """Schema for a call record."""

    id: UUID
    twilio_sid: str
    request_id: UUID | None = None
    restaurant_id: UUID | None = None
    status: CallStatus
    failure_reason: str | None = None
    duration_seconds: int | None = None
    transcript_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class CallUpdate(BaseModel):
    """Schema for updating a call record."""

    status: CallStatus | None = None
    failure_reason: str | None = None
    duration_seconds: int | None = None
    transcript_summary: str | None = None


# ============================================
# RESERVATION SCHEMAS (Enhanced with context)
# ============================================


ReservationStatus = Literal["confirmed", "cancelled", "completed", "no_show"]


class ReservationCreate(BaseModel):
    """Schema for creating a reservation."""

    call_id: UUID
    request_id: UUID | None = None
    restaurant_id: UUID | None = None
    user_id: UUID | None = None
    restaurant_name: str
    party_size: int = Field(..., ge=1, le=20)
    confirmed_date: date = Field(..., description="Confirmed date (YYYY-MM-DD)")
    confirmed_time: time = Field(..., description="Confirmed time (HH:MM)")
    confirmation_code: str | None = None
    status: ReservationStatus = "confirmed"
    notes: str | None = None


class Reservation(BaseModel):
    """Schema for a reservation record."""

    id: UUID
    call_id: UUID
    request_id: UUID | None = None
    restaurant_id: UUID | None = None
    user_id: UUID | None = None
    restaurant_name: str
    party_size: int
    confirmed_date: date
    confirmed_time: time
    confirmation_code: str | None = None
    status: ReservationStatus = "confirmed"
    notes: str | None = None
    created_at: datetime


class ReservationWithDetails(BaseModel):
    """Schema for reservation with joined restaurant details (for UI)."""

    id: UUID
    call_id: UUID
    request_id: UUID | None = None
    restaurant_id: UUID | None = None
    user_id: UUID | None = None
    restaurant_name: str
    restaurant_phone: str | None = None
    restaurant_address: str | None = None
    party_size: int
    confirmed_date: date
    confirmed_time: time
    confirmation_code: str | None = None
    status: ReservationStatus = "confirmed"
    notes: str | None = None
    created_at: datetime


# ============================================
# TOOL RESPONSE SCHEMAS
# ============================================


class SaveBookingResponse(BaseModel):
    """Response from save_booking tool."""

    success: bool
    reservation_id: str | None = None
    message: str | None = None
    error: str | None = None


class NoAvailabilityResponse(BaseModel):
    """Response from report_no_availability tool."""

    success: bool
    reason: str
    alternative_offered: str | None = None
    should_try_alternative: bool = False


class EndCallResponse(BaseModel):
    """Response from end_call tool."""

    success: bool
    reason: str
    call_summary: str | None = None


# ============================================
# LEGACY SUPPORT (for backward compatibility)
# ============================================


class LegacyReservationRequest(BaseModel):
    """Legacy schema for initiating a reservation call (deprecated)."""

    user_name: str
    restaurant_phone: str
    party_size: int = Field(..., ge=1, le=20)
    preferred_date: str = Field(..., description="Date in YYYY-MM-DD format")
    preferred_time: str = Field(..., description="Time in HH:MM format")
    contact_phone: str
