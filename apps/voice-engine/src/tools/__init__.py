from .save_booking import save_booking, SAVE_BOOKING_SCHEMA, CallContext
from .report_no_availability import report_no_availability, REPORT_NO_AVAILABILITY_SCHEMA
from .end_call import end_call, END_CALL_SCHEMA

# All tool schemas for Gemini registration
ALL_TOOL_SCHEMAS = [
    SAVE_BOOKING_SCHEMA,
    REPORT_NO_AVAILABILITY_SCHEMA,
    END_CALL_SCHEMA,
]

__all__ = [
    # Functions
    "save_booking",
    "report_no_availability",
    "end_call",
    # Schemas
    "SAVE_BOOKING_SCHEMA",
    "REPORT_NO_AVAILABILITY_SCHEMA",
    "END_CALL_SCHEMA",
    "ALL_TOOL_SCHEMAS",
    # Types
    "CallContext",
]
