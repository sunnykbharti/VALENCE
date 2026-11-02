"""Data contracts and event schemas for the bounded orchestrator (Phase 2 Milestone 2B)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from contracts import Evidence
from backend.applicability import EscalationDecision


ALLOWED_ACTIONS = frozenset({
    "search_documents",
    "lookup_equipment",
    "inspect_image",
    "ask_user",
    "finish",
    "escalate",
})


@dataclass(frozen=True)
class ActionSelection:
    """Action selected by the local model or deterministic guard.

    Attributes:
        action: Name of the action (must be in ALLOWED_ACTIONS).
        parameters: Dictionary of arguments for the action.
        rationale: Model explanation for selecting this action.
    """
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.action or not self.action.strip():
            raise ValueError("action must be non-empty")
        act = self.action.strip()
        if act not in ALLOWED_ACTIONS:
            raise ValueError(
                f"Action '{act}' is not in the explicit tool allowlist: {sorted(list(ALLOWED_ACTIONS))}"
            )


@dataclass(frozen=True)
class OrchestratorEvent:
    """Structured activity event emitted by the orchestrator for UI and auditing.

    Attributes:
        step: 1-based step counter.
        event_type: Category ('action_selected', 'tool_result', 'clarification_request', 'escalation', 'completion').
        action: Action name involved in the event.
        payload: Event data and parameters.
        timestamp: ISO 8601 UTC timestamp.
    """
    step: int
    event_type: str
    action: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class OrchestratorResult:
    """Final result of a bounded orchestration session.

    Attributes:
        status: Execution status ('COMPLETED', 'PAUSED_FOR_USER', 'ESCALATED', 'MAX_STEPS_EXCEEDED', 'REPEATED_ACTION_ABORT', 'PARSE_ERROR').
        final_answer: Supported technical guidance synthesized from evidence, if completed.
        events: Full timeline of structured events emitted during execution.
        escalation: Applicable escalation decision if escalated.
        steps_executed: Total number of loop iterations executed.
        evidence: List of documentary evidence retrieved across all steps.
        observations: List of tentative visual observations gathered across steps.
    """
    status: str
    final_answer: Optional[str] = None
    events: list[OrchestratorEvent] = field(default_factory=list)
    escalation: Optional[EscalationDecision] = None
    steps_executed: int = 0
    evidence: list[Evidence] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    handover: Optional[Any] = None


