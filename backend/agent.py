"""Incident troubleshooting agent execution engine for VALENCE (Phase 2 Milestone 2A).

Coordinates real backend tool invocations:
1. 'retrieve_evidence': Query local vector store for grounded manuals and SOP excerpts.
2. 'validate_applicability': Validate equipment model compatibility, revision metadata, and detect contradictions.
3. 'request_clarification': Prompt human operator when critical parameters (e.g. equipment model) are unconfirmed.
4. 'apply_clarification': Resume the SAME incident with operator-provided facts without duplicated execution.
5. 'synthesize_guidance': Synthesize grounded maintenance guidance strictly referencing verified evidence.
6. 'cancel_investigation': Pause or cancel execution per backend-supported controls.

Invariants:
- Events rendered are supplied by real tool execution, never invented.
- Private chain-of-thought is excluded; only structured actions and concise explanations are produced.
- Concurrency guard prevents duplicate submissions while execution is actively running.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import uuid4

from contracts import Answer, Evidence
from backend.applicability import (
    EscalationDecision,
    evaluate_incident_applicability,
)
from src.incidents.schema import Incident
from src.incidents.protocol import IncidentServiceProtocol
from src.incidents.agent_schema import (
    AgentExecution,
    ClarificationRequest,
    ToolEvent,
    VALID_EXECUTION_STATES,
)

logger = logging.getLogger("valence.agent")


class AgentExecutor:
    """Orchestrates multi-step agent investigation workflows over industrial incidents."""

    def __init__(self, backend, incident_service: IncidentServiceProtocol) -> None:
        self.backend = backend
        self.incident_service = incident_service
        # Map of execution_id -> AgentExecution
        self._executions: dict[str, AgentExecution] = {}
        # Concurrency guard: incident_id -> active execution_id
        self._running_incidents: dict[str, str] = {}

    def get_execution(self, execution_id: str) -> Optional[AgentExecution]:
        """Retrieves an execution by ID."""
        return self._executions.get(execution_id)

    def list_executions_for_incident(self, incident_id: str) -> list[AgentExecution]:
        """Returns all executions associated with a specific incident ID."""
        return [
            e for e in self._executions.values() if e.incident_id == incident_id
        ]

    def start_investigation(
        self,
        incident_id: str,
        query: Optional[str] = None,
    ) -> AgentExecution:
        """Initiates an automated agent investigation workflow for an incident.

        Enforces duplicate prevention: if an execution is already running for this incident,
        it raises RuntimeError rather than duplicating execution.
        """
        # Concurrency & duplicate prevention check
        if incident_id in self._running_incidents:
            active_exec_id = self._running_incidents[incident_id]
            existing = self._executions.get(active_exec_id)
            if existing and existing.state in ("running", "waiting"):
                raise RuntimeError(
                    f"Execution '{active_exec_id}' is already active for incident '{incident_id}'. "
                    f"Duplicate execution blocked."
                )

        incident = self.incident_service.get_incident(incident_id)
        if incident is None:
            raise KeyError(f"Incident '{incident_id}' not found.")

        search_query = (query or incident.symptom or incident.title).strip()
        if not search_query:
            raise ValueError("Investigation query or incident symptom must be non-empty.")

        exec_id = f"EXEC-{uuid4().hex[:8].upper()}"
        execution = AgentExecution(
            execution_id=exec_id,
            incident_id=incident_id,
            query=search_query,
            state="running",
        )
        self._executions[exec_id] = execution
        self._running_incidents[incident_id] = exec_id

        # ── Step 1: Tool 'retrieve_evidence' ──────────────────────────────────
        evt_retrieval_id = f"EVT-{len(execution.events) + 1:02d}"
        retrieval_event = ToolEvent(
            event_id=evt_retrieval_id,
            tool_name="retrieve_evidence",
            short_purpose="Query local vector store for diagnostic procedures matching reported symptom",
            status="running",
        )
        execution.add_event(retrieval_event)

        evidence: list[Evidence] = list(incident.evidence) if incident.evidence else []
        if not evidence:
            try:
                evidence = self.backend.retrieve(
                    question=search_query,
                    top_k=5,
                )
            except Exception as e:
                retrieval_event.status = "failed"
                retrieval_event.outcome = f"Retrieval failed with error: {e}"
                execution.state = "failed"
                execution.error_message = str(e)
                self._cleanup_running_guard(incident_id)
                return execution

            if not evidence:
                retrieval_event.status = "failed"
                retrieval_event.outcome = "No documentary evidence found in indexed technical documentation."
                execution.state = "escalated"
                execution.escalation = EscalationDecision(
                    escalate=True,
                    reason="ABSENT_EVIDENCE",
                    details="No documentary evidence found in knowledge base for the observed symptom.",
                    action_required="Escalate to senior systems engineering for manual diagnostic review.",
                )
                self._cleanup_running_guard(incident_id)
                return execution

            # Attach evidence to the same incident
            self.incident_service.attach_evidence(incident_id, evidence)
            retrieval_event.status = "completed"
            retrieval_event.outcome = (
                f"Successfully retrieved {len(evidence)} verified document excerpt(s) "
                f"from '{evidence[0].chunk.filename}'."
            )
        else:
            retrieval_event.status = "completed"
            retrieval_event.outcome = (
                f"Utilizing {len(evidence)} verified document excerpt(s) already attached to incident."
            )

        # ── Step 2: Tool 'validate_applicability' ──────────────────────────────
        evt_app_id = f"EVT-{len(execution.events) + 1:02d}"
        app_event = ToolEvent(
            event_id=evt_app_id,
            tool_name="validate_applicability",
            short_purpose="Verify equipment identity, firmware compatibility, and absence of contradictions",
            status="running",
        )
        execution.add_event(app_event)

        # Re-fetch incident with attached evidence
        incident = self.incident_service.get_incident(incident_id)

        # Check for unconfirmed equipment identity -> requires operator clarification
        if not incident.equipment_model or not incident.equipment_confirmed:
            app_event.status = "waiting"
            app_event.outcome = (
                "Equipment model is unconfirmed. Operator clarification required before proceeding."
            )
            suggested_options = []
            for ev in evidence:
                if ev.chunk.equipment_model and ev.chunk.equipment_model not in suggested_options:
                    suggested_options.append(ev.chunk.equipment_model)

            clarification = ClarificationRequest(
                clarification_id=f"CLR-{uuid4().hex[:6].upper()}",
                incident_id=incident_id,
                question=(
                    f"Equipment model for incident '{incident.title}' is unconfirmed. "
                    "Please confirm the exact equipment model identifier (e.g. S7-1200 CPU 1214C) "
                    "to ensure safe and applicable troubleshooting."
                ),
                parameter="equipment_model",
                options=suggested_options,
            )
            execution.clarification = clarification
            execution.state = "waiting"
            # Keep in _running_incidents so duplicate runs are blocked while waiting
            return execution

        # Perform full applicability evaluation
        decision = evaluate_incident_applicability(incident)
        if decision.escalate:
            app_event.status = "escalated"
            app_event.outcome = f"Escalation triggered [{decision.reason}]: {decision.details}"
            execution.state = "escalated"
            execution.escalation = decision
            self._cleanup_running_guard(incident_id)
            return execution

        app_event.status = "completed"
        app_event.outcome = f"Applicability certified for verified equipment '{incident.equipment_model}'."

        # ── Step 3: Tool 'synthesize_guidance' ─────────────────────────────────
        self._run_synthesis(execution, incident, search_query)
        self._cleanup_running_guard(incident_id)
        return execution

    def resume_investigation(
        self,
        execution_id: str,
        user_response: str,
    ) -> AgentExecution:
        """Resumes an existing execution paused in 'waiting' state.

        Applies the operator response to the SAME incident, records the tool event,
        and proceeds with subsequent validation and synthesis steps.
        Enforces strict validation against duplicate resumption.
        """
        execution = self._executions.get(execution_id)
        if execution is None:
            raise KeyError(f"Execution '{execution_id}' not found.")

        if execution.state != "waiting" or execution.clarification is None:
            raise ValueError(
                f"Execution '{execution_id}' is not awaiting clarification (current state: {execution.state}). "
                f"Duplicate resumption blocked."
            )

        if execution.clarification.status != "pending":
            raise ValueError("Clarification request has already been answered.")

        clean_resp = (user_response or "").strip()
        if not clean_resp:
            raise ValueError("Clarification response cannot be empty or whitespace-only.")

        incident_id = execution.incident_id
        incident = self.incident_service.get_incident(incident_id)
        if incident is None:
            raise KeyError(f"Incident '{incident_id}' not found.")

        # Mark execution as running
        execution.state = "running"
        now_iso = datetime.now(timezone.utc).isoformat()
        execution.clarification.response = clean_resp
        execution.clarification.status = "answered"
        execution.clarification.answered_at = now_iso

        # ── Step: Tool 'apply_clarification' ──────────────────────────────────
        evt_clarif_id = f"EVT-{len(execution.events) + 1:02d}"
        clarif_event = ToolEvent(
            event_id=evt_clarif_id,
            tool_name="apply_clarification",
            short_purpose=f"Apply operator clarification for '{execution.clarification.parameter}'",
            status="completed",
            outcome=f"Confirmed '{execution.clarification.parameter}' as '{clean_resp}' for incident {incident_id}.",
        )
        execution.add_event(clarif_event)

        # Update the SAME incident record with operator's confirmed facts
        if execution.clarification.parameter == "equipment_model":
            self.incident_service.confirm_equipment(incident_id, clean_resp)
        elif execution.clarification.parameter == "firmware_revision":
            incident.firmware_revision = clean_resp
        elif execution.clarification.parameter == "hardware_revision":
            incident.hardware_revision = clean_resp
        else:
            self.incident_service.add_observations(
                incident_id, [f"[OPERATOR CLARIFICATION]: {clean_resp}"]
            )

        # Re-fetch the same updated incident
        incident = self.incident_service.get_incident(incident_id)

        # ── Step: Re-evaluate applicability with confirmed facts ──────────────
        evt_reapp_id = f"EVT-{len(execution.events) + 1:02d}"
        reapp_event = ToolEvent(
            event_id=evt_reapp_id,
            tool_name="validate_applicability",
            short_purpose="Re-evaluate applicability rules with confirmed operator details",
            status="running",
        )
        execution.add_event(reapp_event)

        decision = evaluate_incident_applicability(incident)
        if decision.escalate:
            reapp_event.status = "escalated"
            reapp_event.outcome = f"Escalation required [{decision.reason}]: {decision.details}"
            execution.state = "escalated"
            execution.escalation = decision
            self._cleanup_running_guard(incident_id)
            return execution

        reapp_event.status = "completed"
        reapp_event.outcome = f"Applicability confirmed for equipment '{incident.equipment_model}'."

        # ── Step: Tool 'synthesize_guidance' ─────────────────────────────────
        self._run_synthesis(execution, incident, execution.query)
        self._cleanup_running_guard(incident_id)
        return execution

    def cancel_execution(self, execution_id: str) -> AgentExecution:
        """Cancels or pauses an active execution using backend-supported controls."""
        execution = self._executions.get(execution_id)
        if execution is None:
            raise KeyError(f"Execution '{execution_id}' not found.")

        if execution.state in ("completed", "failed", "cancelled"):
            return execution

        execution.state = "cancelled"
        # Update any currently active/waiting event to cancelled
        for ev in execution.events:
            if ev.status in ("running", "waiting", "pending"):
                ev.status = "cancelled"
                ev.outcome = "Operation cancelled by operator."

        if execution.clarification and execution.clarification.status == "pending":
            execution.clarification.status = "cancelled"

        evt_cancel_id = f"EVT-{len(execution.events) + 1:02d}"
        cancel_event = ToolEvent(
            event_id=evt_cancel_id,
            tool_name="cancel_investigation",
            short_purpose="Halt active agent execution by operator request",
            outcome="Execution cancelled. No further automated actions taken.",
            status="cancelled",
        )
        execution.add_event(cancel_event)
        self._cleanup_running_guard(execution.incident_id)
        return execution

    def _run_synthesis(
        self,
        execution: AgentExecution,
        incident: Incident,
        query: str,
    ) -> None:
        """Executes the synthesis tool step."""
        evt_synth_id = f"EVT-{len(execution.events) + 1:02d}"
        synth_event = ToolEvent(
            event_id=evt_synth_id,
            tool_name="synthesize_guidance",
            short_purpose="Synthesize grounded diagnostic recommendation referencing verified citations",
            status="running",
        )
        execution.add_event(synth_event)

        try:
            effective_model = incident.equipment_model if incident.equipment_confirmed else None
            answer = self.backend.answer_question(
                question=query,
                equipment_model=effective_model,
            )
            synth_event.status = "completed"
            citation_count = len(answer.evidence)
            synth_event.outcome = (
                f"Generated grounded troubleshooting guidance referencing {citation_count} document citation(s)."
            )
            execution.answer = answer
            execution.state = "completed"
        except Exception as e:
            synth_event.status = "failed"
            synth_event.outcome = f"Synthesis failed with error: {e}"
            execution.state = "failed"
            execution.error_message = str(e)

    def _cleanup_running_guard(self, incident_id: str) -> None:
        """Removes incident from active running guard."""
        if incident_id in self._running_incidents:
            del self._running_incidents[incident_id]
