"""Agent execution and activity tracking schemas for Phase 2 Milestone 2A.

Defines structured models for real tool events, clarification requests,
and agent execution lifecycle states.
Invariants:
- Private chain-of-thought is strictly forbidden in event models;
  only structured actions, concise purposes, and user-facing outcomes are captured.
- States are restricted to: 'running', 'waiting', 'completed', 'failed', 'cancelled', 'escalated'.
- Clarification requests must target an existing incident and require non-empty questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from contracts import Answer
    from backend.applicability import EscalationDecision

VALID_EXECUTION_STATES = (
    "running",
    "waiting",
    "completed",
    "failed",
    "cancelled",
    "escalated",
)

VALID_EVENT_STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "waiting",
    "cancelled",
    "escalated",
)


@dataclass
class ToolEvent:
    """Represents a discrete, auditable tool invocation by the agent.

    Attributes:
        event_id: Unique deterministic or sequential event ID (e.g. 'EVT-01').
        tool_name: Machine-readable tool identifier (e.g. 'retrieve_evidence', 'validate_applicability').
        short_purpose: Brief, concise human-readable explanation of why this tool was invoked.
        outcome: Concise user-facing outcome or result of the tool invocation.
        status: Current status of this event ('pending', 'running', 'completed', 'failed', 'waiting', 'cancelled', 'escalated').
        timestamp: ISO 8601 UTC timestamp of creation.
        details: Optional structured metadata dictionary (never private chain-of-thought).
    """
    event_id: str
    tool_name: str
    short_purpose: str
    outcome: Optional[str] = None
    status: str = "pending"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_id.strip():
            raise ValueError("event_id must be non-empty and non-whitespace")
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("tool_name must be non-empty and non-whitespace")
        if not self.short_purpose or not self.short_purpose.strip():
            raise ValueError("short_purpose must be non-empty and non-whitespace")

        status_lower = self.status.lower()
        if status_lower not in VALID_EVENT_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of: {', '.join(VALID_EVENT_STATUSES)}"
            )
        self.status = status_lower


@dataclass
class ClarificationRequest:
    """Represents an explicit request from the agent for operator clarification.

    Attributes:
        clarification_id: Unique identifier for the question (e.g. 'CLR-01').
        incident_id: ID of the incident to which this clarification belongs.
        question: Concise question directed to the human operator.
        parameter: Specific parameter requiring resolution (e.g. 'equipment_model', 'firmware_revision').
        options: Optional list of proposed choices for operator convenience.
        response: Operator-supplied response once answered; None while pending.
        status: Status ('pending', 'answered', 'cancelled').
        created_at: ISO 8601 UTC timestamp of request.
        answered_at: ISO 8601 UTC timestamp of operator submission.
    """
    clarification_id: str
    incident_id: str
    question: str
    parameter: str
    options: list[str] = field(default_factory=list)
    response: Optional[str] = None
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    answered_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.clarification_id or not self.clarification_id.strip():
            raise ValueError("clarification_id must be non-empty and non-whitespace")
        if not self.incident_id or not self.incident_id.strip():
            raise ValueError("incident_id must be non-empty and non-whitespace")
        if not self.question or not self.question.strip():
            raise ValueError("question must be non-empty and non-whitespace")
        if not self.parameter or not self.parameter.strip():
            raise ValueError("parameter must be non-empty and non-whitespace")
        if self.status not in ("pending", "answered", "cancelled"):
            raise ValueError(f"Invalid clarification status '{self.status}'")


@dataclass
class AgentExecution:
    """Encapsulates the lifecycle, state, and tool events of an incident troubleshooting execution.

    Attributes:
        execution_id: Unique execution identifier (e.g. 'EXEC-101').
        incident_id: Associated incident identifier.
        query: Specific troubleshooting prompt or symptom investigated.
        state: Overall execution state ('running', 'waiting', 'completed', 'failed', 'cancelled', 'escalated').
        events: Chronological sequence of real tool events supplied by the backend.
        clarification: Active or historical clarification request, if triggered.
        answer: Grounded final Answer if successfully completed.
        escalation: EscalationDecision if an applicability or safety rule triggered escalation.
        error_message: Technical failure explanation if execution failed.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last update timestamp.
    """
    execution_id: str
    incident_id: str
    query: str
    state: str = "running"
    events: list[ToolEvent] = field(default_factory=list)
    clarification: Optional[ClarificationRequest] = None
    answer: Optional[Answer] = None
    escalation: Optional[EscalationDecision] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("execution_id must be non-empty and non-whitespace")
        if not self.incident_id or not self.incident_id.strip():
            raise ValueError("incident_id must be non-empty and non-whitespace")

        state_lower = self.state.lower()
        if state_lower not in VALID_EXECUTION_STATES:
            raise ValueError(
                f"Invalid state '{self.state}'. Must be one of: {', '.join(VALID_EXECUTION_STATES)}"
            )
        self.state = state_lower

    def add_event(self, event: ToolEvent) -> None:
        """Appends a real tool event and updates execution timestamp."""
        self.events.append(event)
        self.updated_at = datetime.now(timezone.utc).isoformat()
