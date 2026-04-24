from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


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


class TicketInput(BaseModel):
    ticket_id: str
    subject: str
    body: str
    requestor_email: str
    requestor_name: str
    requestor_title: Optional[str] = None
    channel: str = "email"  # email | slack | chat | web


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
