import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Queue(str, Enum):
    ACCOUNTS = "accounts"
    NETWORKING = "networking"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"


_VALID_CHANNELS = {"email", "slack", "chat", "web"}
_TICKET_ID_RE = re.compile(r'^[A-Za-z0-9\-_]{1,64}$')


class TicketInput(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=32_000)
    requestor_email: EmailStr
    requestor_name: str = Field(min_length=1, max_length=200)
    requestor_title: Optional[str] = Field(default=None, max_length=200)
    channel: str = Field(default="email", max_length=20)

    @field_validator("ticket_id")
    @classmethod
    def validate_ticket_id(cls, v: str) -> str:
        if not _TICKET_ID_RE.match(v):
            raise ValueError("ticket_id must be alphanumeric with hyphens/underscores only")
        return v

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        if v not in _VALID_CHANNELS:
            raise ValueError(f"channel must be one of {sorted(_VALID_CHANNELS)}")
        return v

    @field_validator("requestor_name", "requestor_title", mode="before")
    @classmethod
    def strip_control_chars(cls, v):
        if v is None:
            return v
        # Strip newlines and other control characters that could break prompt structure
        return re.sub(r'[\x00-\x1f\x7f]', ' ', str(v)).strip()


class TriageResult(BaseModel):
    ticket_id: str
    queue: Queue
    priority: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    suggested_actions: list[str] = Field(default_factory=list)
    retry_count: int = 0


class EscalationDecision(BaseModel):
    ticket_id: str
    should_escalate: bool
    reason: str
    escalation_triggers: list[str] = Field(default_factory=list)


class ResolutionResult(BaseModel):
    ticket_id: str
    resolved: bool
    resolution_steps: list[str] = Field(default_factory=list)
    cannot_auto_resolve_reason: Optional[str] = None


class CoordinatorOutput(BaseModel):
    ticket_id: str
    triage: TriageResult
    escalation: EscalationDecision
    resolution: Optional[ResolutionResult] = None
    total_retry_count: int = 0
