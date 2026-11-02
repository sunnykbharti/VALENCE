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
        sources: List of attached documentary evidence source citations.
        unresolved_questions: List of open items, unresolved escalations, or uncertainties.
        symptom: Reported incident symptom.
        equipment_model: Target equipment model if specified.
        equipment_confirmed: Whether equipment model is confirmed by operator.
        is_synthetic: True if incident or evidence contains synthetic benchmark test data.
        is_reviewed: True if formally reviewed; False otherwise.
        review_disclaimer: Explicit notification regarding absence of authentication/authorization.
        user_review_notes: Optional human review notes added prior to saving or exporting.
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
    sources: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    symptom: str = ""
    equipment_model: Optional[str] = None
    equipment_confirmed: bool = False
    is_synthetic: bool = False
    is_reviewed: bool = False
    review_disclaimer: str = (
        "Authentication/authorization is not implemented in this offline runtime. "
        "Reviewer approval cannot be certified; outcomes remain strictly unreviewed."
    )
    user_review_notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Serializes handover report into structured JSON dictionary."""
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "status": self.status,
            "timestamp": self.timestamp,
            "is_complete": self.is_complete,
            "is_synthetic": self.is_synthetic,
            "is_reviewed": self.is_reviewed,
            "review_disclaimer": self.review_disclaimer,
            "symptom": self.symptom,
            "equipment_model": self.equipment_model,
            "equipment_confirmed": self.equipment_confirmed,
            "sources": self.sources,
            "tentative_observations": self.tentative_observations,
            "system_interpretations": self.system_interpretations,
            "technician_findings": self.technician_findings,
            "unresolved_questions": self.unresolved_questions,
            "missing_fields": self.missing_fields,
            "escalation": {
                "escalate": self.escalation.escalate,
                "reason": self.escalation.reason,
                "details": self.escalation.details,
                "action_required": self.escalation.action_required,
                "blocking_sources": self.escalation.blocking_sources,
            } if self.escalation else None,
            "authoritative_knowledge_eligible": self.authoritative_knowledge_eligible,
            "knowledge_guard_reason": self.knowledge_guard_reason,
            "user_review_notes": self.user_review_notes,
        }


def generate_handover(
    incident: Incident,
    escalation: Optional[EscalationDecision] = None,
    user_review_notes: Optional[str] = None,
) -> HandoverReport:
    """Generates an auditable handover report from persisted incident facts."""
    now = datetime.now(timezone.utc).isoformat()
    missing_fields: list[str] = []
    unresolved_questions: list[str] = []

    # 1. Completeness Validation
    if not incident.symptom or not incident.symptom.strip():
        missing_fields.append("symptom")
        unresolved_questions.append("Reported symptom is empty or unspecified.")

    if not incident.equipment_confirmed:
        unresolved_questions.append(
            "Equipment model is unconfirmed. Target identity requires verification via physical nameplate."
        )

    if not incident.evidence:
        unresolved_questions.append(
            "No documentary evidence or equipment manuals attached to substantiate procedure."
        )

    # If incident is advanced beyond 'open', technician findings are mandatory
    if incident.status in ("mitigated", "resolved", "closed"):
        if not incident.technician_findings:
            missing_fields.append("technician_findings")
            unresolved_questions.append(
                f"Incident status is '{incident.status}' but no verified physical technician findings are recorded."
            )
        if not incident.equipment_confirmed:
            missing_fields.append("confirmed_equipment_model")

    # If escalation is active and unresolved
    if escalation and escalation.escalate:
        missing_fields.append(f"unresolved_escalation_{escalation.reason.lower()}")
        unresolved_questions.append(
            f"Active escalation [{escalation.reason}]: {escalation.details} (Action: {escalation.action_required})"
        )

    is_complete = len(missing_fields) == 0

    # 2. Attached Documentary Sources
    sources = [
        f"{e.source_id} (Manual: {e.chunk.filename}, p. {e.chunk.page})"
        for e in incident.evidence
    ]

    # 3. Distinct Classification of Findings
    labeled_observations = [f"[TENTATIVE OBSERVATION] {obs}" for obs in incident.observations]
    labeled_interpretations = [f"[SYSTEM INTERPRETATION - NOT AUTHORITATIVE] {interp}" for interp in incident.interpretations]
    labeled_findings = [f"[VERIFIED TECHNICIAN FINDING] {finding}" for finding in incident.technician_findings]

    # 4. Check for Synthetic Benchmark Data
    is_synth = any(getattr(e.chunk, "synthetic", False) for e in incident.evidence)
    if "synthetic" in incident.title.lower() or "test" in incident.title.lower():
        is_synth = True

    # 5. Knowledge Promotion Guard & Review State
    # Note: Do not imply reviewer approval if authentication/authorization has not been implemented
    is_reviewed = bool(incident.engineer_signoff and incident.reviewed_by_engineer and incident.reviewed_by_engineer.strip())

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

    # 6. Generate Markdown text
    lines = [
        f"# Shift Handover Report: {incident.incident_id}",
        "> 🤖 **[GENERATED SUMMARY - REQUIRES HUMAN REVIEW]**",
    ]
    if is_synth:
        lines.append("> 🔶 **[SYNTHETIC TEST BENCHMARK DATA - NOT FOR PRODUCTION DISPATCH]**")

    if not is_reviewed:
        lines.append(
            "> ⚠️ **[UNREVIEWED OUTCOME - NO AUTHORIZED SIGN-OFF]** — "
            "Authentication/authorization is not implemented; reviewer approval cannot be verified."
        )

    lines.extend([
        "",
        f"**Title**: {incident.title}",
        f"**Status**: `{incident.status.upper()}` | **Handover Time**: `{now[:19]} UTC`",
        f"**Completeness**: {'✅ COMPLETE' if is_complete else '⚠️ INCOMPLETE'}",
    ])
    if missing_fields:
        lines.append(f"> ⚠️ **Missing Information**: {', '.join(missing_fields)}")

    lines.extend([
        "",
        "## 1. Equipment & Symptom",
        f"- **Reported Symptom**: {incident.symptom}",
        f"- **Equipment Model**: `{incident.equipment_model or 'Unidentified (None)'}`",
        f"- **Confirmation State**: {'✅ Confirmed by Operator' if incident.equipment_confirmed else '⚠️ Unconfirmed / Tentative'}",
        f"- **Hardware/Firmware**: HW `{incident.hardware_revision or 'N/A'}` | FW `{incident.firmware_revision or 'N/A'}`",
        "",
        "## 2. Attached Documentary Sources",
    ])
    if sources:
        for src in sources:
            lines.append(f"- `{src}`")
    else:
        lines.append("- *No documentary evidence attached to this incident.*")

    lines.extend([
        "",
        "## 3. Categorized Findings (Separation Enforced)",
        "### A. Tentative Observations (Visual / Sensory Cues)",
    ])
    if labeled_observations:
        for obs in labeled_observations:
            lines.append(f"- {obs}")
    else:
        lines.append("- *No visual observations recorded.*")

    lines.append("\n### B. Verified Technician Findings (Human Physical Inspection)")
    lines.append("*Recorded by human technician; not automated by system:*")
    if labeled_findings:
        for finding in labeled_findings:
            lines.append(f"- {finding}")
    else:
        lines.append("- *No physical technician findings recorded.*")

    lines.append("\n### C. Diagnostic Interpretations (System Hypotheses - Unreviewed)")
    if labeled_interpretations:
        for interp in labeled_interpretations:
            lines.append(f"- {interp}")
    else:
        lines.append("- *No system interpretations logged.*")

    lines.extend([
        "",
        "## 4. Unresolved Items & Uncertainty",
    ])
    if unresolved_questions:
        for uq in unresolved_questions:
            lines.append(f"- ❓ {uq}")
    else:
        lines.append("- *No unresolved questions or uncertainties outstanding.*")

    lines.append("\n## 5. Applicability & Escalation State")
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
        "## 6. Knowledge Base Promotion Guard & Governance",
        f"- **Promotion Status**: {'🟢 ELIGIBLE FOR SOP PROMOTION' if eligible else '🛑 PROMOTION FORBIDDEN'}",
        f"- **Policy Rule**: {guard_reason}",
        f"- **Engineer Review**: `{incident.reviewed_by_engineer or 'None'}` (Sign-off: {incident.engineer_signoff})",
        "- **Authorization Disclaimer**: Local air-gapped system does not enforce cryptographic identity; no reviewer approval is implied.",
    ])

    if user_review_notes and user_review_notes.strip():
        lines.extend([
            "",
            "## 7. Shift Reviewer Addendum",
            f"> {user_review_notes.strip()}",
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
        sources=sources,
        unresolved_questions=unresolved_questions,
        symptom=incident.symptom,
        equipment_model=incident.equipment_model,
        equipment_confirmed=incident.equipment_confirmed,
        is_synthetic=is_synth,
        is_reviewed=is_reviewed,
        user_review_notes=user_review_notes,
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

