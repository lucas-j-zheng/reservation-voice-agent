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
# GENERALIZED REQUEST SCHEMAS
# ============================================


RequestType = Literal["reservation", "info_query", "event_inquiry", "cancellation"]
RequestStatus = Literal["pending", "in_progress", "completed", "failed", "cancelled"]


class RequestCreate(BaseModel):
    """Schema for creating a base request."""

    user_id: UUID | None = None
    type: RequestType


class Request(BaseModel):
    """Schema for a request record."""

    id: UUID
    user_id: UUID | None = None
    type: RequestType
    status: RequestStatus = "pending"
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
# TYPE-SPECIFIC DETAIL SCHEMAS
# ============================================


QueryCategory = Literal[
    "hours", "wait_times", "menu", "pricing", "dietary", "allergens", "facilities"
]

FacilityCategory = Literal[
    "outdoor", "private_rooms", "wheelchair", "high_chairs", "pet_friendly", "parking"
]

EventTypeEnum = Literal[
    "birthday", "anniversary", "large_party", "catering", "event_space"
]


class ReservationDetailsCreate(BaseModel):
    """Schema for reservation-specific details."""

    request_id: UUID
    party_size: int = Field(..., ge=1, le=20)
    requested_date: date
    time_range_start: time
    time_range_end: time
    special_requests: str | None = None
    contact_phone: str | None = None


class ReservationDetails(BaseModel):
    """Schema for reservation detail record."""

    id: UUID
    request_id: UUID
    party_size: int
    requested_date: date
    time_range_start: time
    time_range_end: time
    special_requests: str | None = None
    contact_phone: str | None = None


class InfoQueryDetailsCreate(BaseModel):
    """Schema for info query-specific details."""

    request_id: UUID
    query_categories: list[QueryCategory]
    specific_questions: str | None = None
    facility_categories: list[FacilityCategory] | None = None


class InfoQueryDetails(BaseModel):
    """Schema for info query detail record."""

    id: UUID
    request_id: UUID
    query_categories: list[str]
    specific_questions: str | None = None
    facility_categories: list[str] | None = None


class EventInquiryDetailsCreate(BaseModel):
    """Schema for event inquiry-specific details."""

    request_id: UUID
    event_type: EventTypeEnum
    party_size: int | None = Field(default=None, ge=1)
    preferred_date: date | None = None
    budget_range: str | None = None
    details: str | None = None


class EventInquiryDetails(BaseModel):
    """Schema for event inquiry detail record."""

    id: UUID
    request_id: UUID
    event_type: str
    party_size: int | None = None
    preferred_date: date | None = None
    budget_range: str | None = None
    details: str | None = None


class CancellationDetailsCreate(BaseModel):
    """Schema for cancellation-specific details."""

    request_id: UUID
    reservation_id: UUID
    reason: str | None = None


class CancellationDetails(BaseModel):
    """Schema for cancellation detail record."""

    id: UUID
    request_id: UUID
    reservation_id: UUID | None = None
    reason: str | None = None


# ============================================
# CALL SCHEMAS
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
# RESERVATION SCHEMAS (outcome of type='reservation')
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
    confirmed_date: date
    confirmed_time: time
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
# TYPE-SPECIFIC RESULT SCHEMAS
# ============================================


class InfoResultCreate(BaseModel):
    """Schema for creating an info query result."""

    call_id: UUID
    request_id: UUID
    restaurant_id: UUID
    operating_hours: str | None = None
    wait_time_minutes: int | None = None
    menu_highlights: str | None = None
    pricing_info: str | None = None
    dietary_options: dict[str, bool] | None = None
    allergen_info: str | None = None
    facilities: dict[str, bool] | None = None
    raw_notes: str | None = None


class InfoResult(BaseModel):
    """Schema for an info query result record."""

    id: UUID
    call_id: UUID
    request_id: UUID
    restaurant_id: UUID
    operating_hours: str | None = None
    wait_time_minutes: int | None = None
    menu_highlights: str | None = None
    pricing_info: str | None = None
    dietary_options: dict[str, bool] | None = None
    allergen_info: str | None = None
    facilities: dict[str, bool] | None = None
    raw_notes: str | None = None
    created_at: datetime


class EventInquiryResultCreate(BaseModel):
    """Schema for creating an event inquiry result."""

    call_id: UUID
    request_id: UUID
    restaurant_id: UUID
    available: bool
    quoted_price: str | None = None
    capacity: int | None = None
    details: str | None = None
    contact_name: str | None = None
    contact_info: str | None = None


class EventInquiryResult(BaseModel):
    """Schema for an event inquiry result record."""

    id: UUID
    call_id: UUID
    request_id: UUID
    restaurant_id: UUID
    available: bool
    quoted_price: str | None = None
    capacity: int | None = None
    details: str | None = None
    contact_name: str | None = None
    contact_info: str | None = None
    created_at: datetime


class CancellationResultCreate(BaseModel):
    """Schema for creating a cancellation result."""

    call_id: UUID
    request_id: UUID
    reservation_id: UUID
    confirmed: bool
    cancellation_code: str | None = None
    notes: str | None = None


class CancellationResult(BaseModel):
    """Schema for a cancellation result record."""

    id: UUID
    call_id: UUID
    request_id: UUID
    reservation_id: UUID | None = None
    confirmed: bool
    cancellation_code: str | None = None
    notes: str | None = None
    created_at: datetime


# ============================================
# CASCADE SCHEMAS
# ============================================


CascadeStatusType = Literal[
    "idle", "running", "paused", "completed", "exhausted", "cancelled"
]

AttemptStatusType = Literal[
    "pending", "calling", "succeeded", "failed", "skipped", "no_answer"
]


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
