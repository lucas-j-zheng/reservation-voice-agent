"""
Cascade orchestrator state enums and models.
"""

from enum import Enum


class CascadeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"


class AttemptStatus(str, Enum):
    PENDING = "pending"
    CALLING = "calling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    NO_ANSWER = "no_answer"


class CallOutcome(str, Enum):
    """Outcomes published via Redis from tool completion signals."""
    SUCCEEDED = "succeeded"
    NO_AVAILABILITY = "no_availability"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
