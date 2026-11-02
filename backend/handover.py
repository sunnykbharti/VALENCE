"""Shift Handover and Knowledge Promotion Governance for VALENCE (Phase 2 Milestone 3B).

Generates auditable handover summaries from persisted incident facts:
1. Keeps tentative observations, diagnostic interpretations, and verified technician findings strictly distinct.
2. Identifies incomplete handovers when mandatory operational fields are absent.
3. Enforces the Authoritative Knowledge Promotion Guard:
   Never converts an unreviewed incident or an unresolved escalation into authoritative knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Sequence

from contracts import Chunk
from src.incidents.schema import Incident
from backend.applicability import EscalationDecision


@dataclass(frozen=True)
class HandoverReport:
    """Structured report generated at shift change or incident handoff.

    Attributes:
        incident_id: Associated incident identifier.
        title: Incident title.
        status: Incident workflow status.
        timestamp: Generation timestamp in UTC.
        is_complete: True if all required operational fields are present; False if incomplete.
        missing_fields: List of mandatory fields that are absent or unresolved.
        tentative_observations: Visual or sensory cues ([TENTATIVE OBSERVATION]).
        system_interpretations: Diagnostic hypotheses ([SYSTEM INTERPRETATION - NOT AUTHORITATIVE]).
        technician_findings: Human-verified physical inspection results ([VERIFIED TECHNICIAN FINDING]).
        escalation: Applicable escalation decision, if evaluated.
        authoritative_knowledge_eligible: True ONLY if reviewed and signed off by engineer; False otherwise.
        knowledge_guard_reason: Explanation of why knowledge promotion is permitted or blocked.
        markdown_text: Human-readable markdown handover document.
    """
    incident_id: str
    title: str
    status: str
    timestamp: str
    is_complete: bool
    missing_fields: list[str]
    tentative_observations: list[str]
    system_interpretations: list[str]
    technician_findings: list[str]
    escalation: Optional[EscalationDecision]
    authoritative_knowledge_eligible: bool
    knowledge_guard_reason: str
    markdown_text: str


def generate_handover(
    incident: Incident,
    escalation: Optional[EscalationDecision] = None,
) -> HandoverReport:
    """Generates an auditable handover report from persisted incident facts."""
    now = datetime.now(timezone.utc).isoformat()
    missing_fields: list[str] = []

    # 1. Completeness Validation
    if not incident.symptom or not incident.symptom.strip():
        missing_fields.append("symptom")

    # If incident is advanced beyond 'open', technician findings are mandatory
    if incident.status in ("mitigated", "resolved", "closed"):
        if not incident.technician_findings:
            missing_fields.append("technician_findings")
        if not incident.equipment_confirmed:
            missing_fields.append("confirmed_equipment_model")

    # If escalation is active and unresolved
    if escalation and escalation.escalate:
        missing_fields.append(f"unresolved_escalation_{escalation.reason.lower()}")

    is_complete = len(missing_fields) == 0

    # 2. Distinct Classification of Findings
    labeled_observations = [f"[TENTATIVE OBSERVATION] {obs}" for obs in incident.observations]
    labeled_interpretations = [f"[SYSTEM INTERPRETATION - NOT AUTHORITATIVE] {interp}" for interp in incident.interpretations]
    labeled_findings = [f"[VERIFIED TECHNICIAN FINDING] {finding}" for finding in incident.technician_findings]

    # 3. Knowledge Promotion Guard (Task 10)
    eligible = False
    guard_reason = ""

    if not incident.engineer_signoff:
        guard_reason = "PROMOTION BLOCKED: Incident lacks certified engineer sign-off (engineer_signoff=False)."
    elif not incident.reviewed_by_engineer or not incident.reviewed_by_engineer.strip():
        guard_reason = "PROMOTION BLOCKED: Reviewing engineer name is absent (reviewed_by_engineer is None)."
    elif incident.status not in ("resolved", "closed"):
        guard_reason = f"PROMOTION BLOCKED: Incident status is '{incident.status}' (must be 'resolved' or 'closed')."
    elif escalation and escalation.escalate:
        guard_reason = f"PROMOTION BLOCKED: Active escalation '{escalation.reason}' remains unresolved."
    elif not is_complete:
        guard_reason = f"PROMOTION BLOCKED: Handover is incomplete. Missing: {missing_fields}"
    else:
        eligible = True
        guard_reason = f"PROMOTION APPROVED: Reviewed and signed off by {incident.reviewed_by_engineer}."

    # 4. Generate Markdown text
    lines = [
        f"# Shift Handover Report: {incident.incident_id}",
        f"**Title**: {incident.title}",
        f"**Status**: `{incident.status.upper()}` | **Handover Time**: `{now[:19]} UTC`",
        f"**Completeness**: {'✅ COMPLETE' if is_complete else '⚠️ INCOMPLETE'}",
    ]
    if missing_fields:
        lines.append(f"> ⚠️ **Missing Information**: {', '.join(missing_fields)}")

    lines.extend([
        "",
        "## 1. Equipment & Symptom",
        f"- **Reported Symptom**: {incident.symptom}",
        f"- **Equipment Model**: `{incident.equipment_model or 'Unidentified (None)'}`",
        f"- **Confirmation State**: {'✅ Confirmed' if incident.equipment_confirmed else '⚠️ Unconfirmed / Tentative'}",
        f"- **Hardware/Firmware**: HW `{incident.hardware_revision or 'N/A'}` | FW `{incident.firmware_revision or 'N/A'}`",
        "",
        "## 2. Categorized Findings (Separation Enforced)",
        "### A. Tentative Observations (Visual / Sensory)",
    ])
    if labeled_observations:
        for obs in labeled_observations:
            lines.append(f"- {obs}")
    else:
        lines.append("- *No visual observations recorded.*")

    lines.append("\n### B. Diagnostic Interpretations (System Hypotheses)")
    if labeled_interpretations:
        for interp in labeled_interpretations:
            lines.append(f"- {interp}")
    else:
        lines.append("- *No system interpretations logged.*")

    lines.append("\n### C. Verified Technician Findings (Physical Inspection)")
    if labeled_findings:
        for finding in labeled_findings:
            lines.append(f"- {finding}")
    else:
        lines.append("- *No physical technician findings recorded.*")

    lines.append("\n## 3. Applicability & Escalation State")
    if escalation:
        lines.append(f"- **Decision**: {'🚨 ESCALATE' if escalation.escalate else '✅ CONFIRMED APPLICABLE'}")
        lines.append(f"- **Reason**: `{escalation.reason}`")
        lines.append(f"- **Details**: {escalation.details}")
        if escalation.action_required:
            lines.append(f"- **Action Required**: {escalation.action_required}")
    else:
        lines.append("- *Applicability check not executed.*")

    lines.extend([
        "",
        "## 4. Knowledge Base Promotion Guard",
        f"- **Status**: {'🟢 ELIGIBLE FOR SOP PROMOTION' if eligible else '🛑 PROMOTION FORBIDDEN'}",
        f"- **Policy Rule**: {guard_reason}",
        f"- **Engineer Review**: `{incident.reviewed_by_engineer or 'None'}` (Sign-off: {incident.engineer_signoff})",
    ])

    markdown_text = "\n".join(lines)

    return HandoverReport(
        incident_id=incident.incident_id,
        title=incident.title,
        status=incident.status,
        timestamp=now,
        is_complete=is_complete,
        missing_fields=missing_fields,
        tentative_observations=labeled_observations,
        system_interpretations=labeled_interpretations,
        technician_findings=labeled_findings,
        escalation=escalation,
        authoritative_knowledge_eligible=eligible,
        knowledge_guard_reason=guard_reason,
        markdown_text=markdown_text,
    )


def promote_incident_to_knowledge_chunk(incident: Incident, handover: HandoverReport) -> Chunk:
    """Converts a verified and signed-off incident into an authoritative knowledge chunk.

    Raises:
        PermissionError: If incident is unreviewed or escalation is unresolved.
    """
    if not handover.authoritative_knowledge_eligible:
        raise PermissionError(
            f"Cannot convert incident {incident.incident_id} to authoritative knowledge: {handover.knowledge_guard_reason}"
        )

    # Format synthesized authoritative resolution chunk
    findings_str = "\n".join(f"- {f}" for f in incident.technician_findings)
    text_content = (
        f"AUTHORITATIVE RESOLUTION NOTE: {incident.title}\n"
        f"Equipment: {incident.equipment_model}\n"
        f"Symptom: {incident.symptom}\n"
        f"Verified Findings & Fix:\n{findings_str}\n"
        f"Approved By: {incident.reviewed_by_engineer} on {handover.timestamp[:10]}"
    )

    return Chunk(
        chunk_id=f"chunk_incident_{incident.incident_id.lower().replace('-', '_')}",
        document_id=f"doc_incident_{incident.incident_id.lower().replace('-', '_')}",
        filename=f"incident_{incident.incident_id}.txt",
        page=1,
        text=text_content,
        equipment_model=incident.equipment_model,
        synthetic=False,
    )

