"""Applicability and Escalation Governance Engine for VALENCE (Phase 2 Milestone 3B).

Enforces strict verification of documentation against industrial equipment metadata:
1. Validates explicit equipment model and revision metadata against document metadata.
2. Handles unknown identity, mismatch, and missing revision information distinctly.
3. Detects and flags contradictory instructions across retrieved documents without
   silently resolving them.
4. Restricts proposed technical checks to retrieved documentation and ensures all
   referenced evidence IDs belong to the active incident.
5. Produces enforceable escalation decisions when applicability cannot be certified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

from contracts import Evidence
from src.incidents.schema import Incident


@dataclass(frozen=True)
class ProposedCheck:
    """A single technical check or maintenance action grounded in evidence.

    Attributes:
        check_id: Identifier for the check (e.g. 'CHK-01').
        step_number: 1-based sequential execution step.
        instruction: Concrete diagnostic or maintenance action.
        evidence_ids: List of source_ids from incident evidence substantiating this check.
        target_component: Specific component or assembly being inspected.
        safety_precaution: Any mandatory PPE or isolation requirements before checking.
    """
    check_id: str
    step_number: int
    instruction: str
    evidence_ids: list[str]
    target_component: Optional[str] = None
    safety_precaution: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.check_id or not self.check_id.strip():
            raise ValueError("check_id must be non-empty")
        if self.step_number < 1:
            raise ValueError("step_number must be >= 1")
        if not self.instruction or not self.instruction.strip():
            raise ValueError("instruction must not be empty")
        if not self.evidence_ids:
            raise ValueError("ProposedCheck must reference at least one evidence_id")


@dataclass(frozen=True)
class EscalationDecision:
    """Explicit decision on whether a procedure can proceed or must escalate.

    Attributes:
        escalate: True if procedure cannot proceed safely; False if confirmed applicable.
        reason: Machine-readable escalation category:
                'CONFIRMED_APPLICABLE', 'ABSENT_EVIDENCE', 'UNKNOWN_EQUIPMENT',
                'EQUIPMENT_MISMATCH', 'MISSING_REVISION', 'CONTRADICTORY_INSTRUCTIONS',
                'INVALID_EVIDENCE_REFERENCE', 'UNRESOLVED_APPLICABILITY'.
        details: Human-readable diagnostic description of the failure or approval.
        blocking_sources: Source IDs of chunks causing the escalation or conflict.
        action_required: Prescribed corrective action for the technician or engineer.
    """
    escalate: bool
    reason: str
    details: str
    blocking_sources: list[str] = field(default_factory=list)
    action_required: str = ""


def _normalize_model_name(name: Optional[str]) -> str:
    """Normalizes equipment model string for robust matching."""
    if not name:
        return ""
    # Remove punctuation, collapse spaces, lowercase
    return re.sub(r"[\s\-_]+", "", name.lower())


def validate_equipment_applicability(
    target_equipment: Optional[str],
    target_revision: Optional[str],
    evidence: Sequence[Evidence],
) -> tuple[bool, str, str, list[str]]:
    """Validates target equipment metadata against retrieved documentary evidence.

    Returns:
        (is_applicable, reason_code, details, blocking_source_ids)
    """
    if not evidence:
        return (
            False,
            "ABSENT_EVIDENCE",
            "No documentary evidence retrieved to substantiate procedure.",
            [],
        )

    if not target_equipment or not target_equipment.strip():
        return (
            False,
            "UNKNOWN_EQUIPMENT",
            "Target equipment identity is unknown (None). Procedure cannot be certified as applicable.",
            [e.source_id for e in evidence],
        )

    norm_target = _normalize_model_name(target_equipment)

    # Check for equipment model mismatch across evidence
    mismatched_sources: list[str] = []
    has_matching_chunk = False

    for ev in evidence:
        chunk_model = ev.chunk.equipment_model
        if chunk_model:
            norm_chunk = _normalize_model_name(chunk_model)
            if norm_target in norm_chunk or norm_chunk in norm_target:
                has_matching_chunk = True
            else:
                mismatched_sources.append(ev.source_id)

    if mismatched_sources and not has_matching_chunk:
        return (
            False,
            "EQUIPMENT_MISMATCH",
            f"Target equipment '{target_equipment}' does not match retrieved document equipment model. "
            f"Sources apply to incompatible models: {mismatched_sources}",
            mismatched_sources,
        )

    # Check for revision requirements in document text
    # e.g., patterns like "FW 4.0 or higher", "Firmware v3.x", "Rev B only"
    for ev in evidence:
        txt = ev.chunk.text
        rev_match = re.search(r"(?:firmware|fw|rev|revision)\s*(?:v|version)?\s*([0-9]+(?:\.[0-9]+)*[a-zA-Z]?)", txt, re.IGNORECASE)
        if rev_match:
            doc_rev = rev_match.group(1)
            if not target_revision or not target_revision.strip():
                return (
                    False,
                    "MISSING_REVISION",
                    f"Retrieved document ({ev.source_id}) specifies revision requirement '{doc_rev}', "
                    f"but target equipment has no revision specified.",
                    [ev.source_id],
                )
            norm_target_rev = target_revision.strip().lower().lstrip("v")
            norm_doc_rev = doc_rev.strip().lower().lstrip("v")
            if not (norm_target_rev.startswith(norm_doc_rev) or norm_doc_rev.startswith(norm_target_rev)):
                return (
                    False,
                    "MISSING_REVISION",
                    f"Revision mismatch: Document ({ev.source_id}) requires '{doc_rev}' but target is '{target_revision}'.",
                    [ev.source_id],
                )

    return (True, "CONFIRMED_APPLICABLE", "Equipment model and revision match retrieved documentation.", [])


def detect_contradictions(evidence: Sequence[Evidence]) -> list[dict[str, str]]:
    """Detects conflicting procedures, values, or specifications across evidence chunks.

    Returns:
        List of contradiction reports with conflicting source IDs and details.
    """
    contradictions: list[dict[str, str]] = []
    
    # 1. Torque value conflicts (e.g., "torque flange bolts to 45 Nm" vs "torque to 65 Nm")
    torque_pattern = re.compile(
        r"(?:torque|tighten)(?:[^\.\n]*?)\b(\d+(?:\.\d+)?)\s*(?:n[·\-\s]?m|newton[- ]meters)",
        re.IGNORECASE,
    )
    # 2. Pressure setpoint conflicts (e.g., "set pressure to 35 bar")
    pressure_pattern = re.compile(
        r"(?:pressure|setpoint)(?:[^\.\n]*?)\b(\d+(?:\.\d+)?)\s*bar\b",
        re.IGNORECASE,
    )
    # 3. Voltage conflicts (e.g. "supply voltage 24 V")
    voltage_pattern = re.compile(
        r"(?:voltage|supply)(?:[^\.\n]*?)\b(\d+(?:\.\d+)?)\s*v(?:dc|ac)?\b",
        re.IGNORECASE,
    )

    patterns = [
        ("Torque specification", torque_pattern),
        ("Pressure setpoint", pressure_pattern),
        ("Supply voltage", voltage_pattern),
    ]

    for label, pat in patterns:
        found_values: dict[str, tuple[str, str]] = {}  # value_str -> (source_id, full_text_snippet)
        for ev in evidence:
            match = pat.search(ev.chunk.text)
            if match:
                val = match.group(1)
                if found_values and val not in found_values:
                    # Contradiction detected!
                    first_val, (first_src, _) = next(iter(found_values.items()))
                    contradictions.append({
                        "type": label,
                        "source_1": first_src,
                        "value_1": first_val,
                        "source_2": ev.source_id,
                        "value_2": val,
                        "description": (
                            f"Contradictory {label} detected: {first_src} specifies {first_val} "
                            f"whereas {ev.source_id} specifies {val}."
                        ),
                    })
                else:
                    found_values[val] = (ev.source_id, match.group(0))

    # 4. Direct opposing operational directives (e.g., clockwise vs counter-clockwise)
    cw_pattern = re.compile(r"\b(?:turn|rotate|spin)(?:\s+\w+){0,3}\s+clockwise\b", re.IGNORECASE)
    ccw_pattern = re.compile(r"\b(?:turn|rotate|spin)(?:\s+\w+){0,3}\s+counter[- ]clockwise\b", re.IGNORECASE)

    cw_sources = [ev.source_id for ev in evidence if cw_pattern.search(ev.chunk.text)]
    ccw_sources = [ev.source_id for ev in evidence if ccw_pattern.search(ev.chunk.text)]
    if cw_sources and ccw_sources:
        contradictions.append({
            "type": "Rotational direction directive",
            "source_1": cw_sources[0],
            "value_1": "clockwise",
            "source_2": ccw_sources[0],
            "value_2": "counter-clockwise",
            "description": f"Contradictory rotation directive between {cw_sources[0]} and {ccw_sources[0]}.",
        })

    return contradictions


def validate_proposed_checks(
    checks: Sequence[ProposedCheck],
    incident_evidence: Sequence[Evidence],
) -> tuple[bool, list[str]]:
    """Validates that all proposed checks cite evidence items that exist in the incident.

    Returns:
        (is_valid, invalid_source_ids)
    """
    valid_source_ids = {e.source_id for e in incident_evidence}
    invalid_ids: list[str] = []

    for chk in checks:
        for ref_id in chk.evidence_ids:
            if ref_id not in valid_source_ids:
                invalid_ids.append(ref_id)

    return (len(invalid_ids) == 0, invalid_ids)


def evaluate_incident_applicability(
    incident: Incident,
    proposed_checks: Optional[Sequence[ProposedCheck]] = None,
) -> EscalationDecision:
    """Evaluates comprehensive applicability and escalation rules for an incident.

    Enforces:
    1. Validation of equipment metadata against retrieved evidence.
    2. Explicit handling of unknown identity, mismatch, and missing revisions.
    3. Detection of contradictory instructions without silent resolution.
    4. Association of checks with valid evidence belonging strictly to this incident.
    """
    # Rule 1: Check if equipment identity is unknown or unconfirmed
    if not incident.equipment_model or not incident.equipment_model.strip():
        return EscalationDecision(
            escalate=True,
            reason="UNKNOWN_EQUIPMENT",
            details="Target equipment identity is unknown (None). Procedure cannot be certified as applicable.",
            blocking_sources=[],
            action_required="Identify target equipment model from physical nameplate before applying procedure.",
        )
    if not incident.equipment_confirmed:
        return EscalationDecision(
            escalate=True,
            reason="UNKNOWN_EQUIPMENT",
            details=f"Equipment model '{incident.equipment_model}' is tentative and unconfirmed by operator.",
            blocking_sources=[],
            action_required="Confirm equipment model identifier before proceeding with maintenance actions.",
        )

    # Rule 2: Check for absent evidence
    if not incident.evidence:
        return EscalationDecision(
            escalate=True,
            reason="ABSENT_EVIDENCE",
            details="No documentary evidence attached to this incident. Cannot formulate verified actions.",
            blocking_sources=[],
            action_required="Perform grounded document retrieval or index relevant equipment SOPs.",
        )

    # Rule 3: Check equipment applicability & revision
    is_app, reason_code, details, blocking_srcs = validate_equipment_applicability(
        target_equipment=incident.equipment_model,
        target_revision=incident.firmware_revision or incident.hardware_revision,
        evidence=incident.evidence,
    )
    if not is_app:
        actions = {
            "UNKNOWN_EQUIPMENT": "Identify target equipment model from physical nameplate before applying procedure.",
            "EQUIPMENT_MISMATCH": "Retrieve manual matching target equipment model or escalate to lead engineer.",
            "MISSING_REVISION": "Verify physical firmware/hardware revision and match against manual revision matrix.",
        }
        return EscalationDecision(
            escalate=True,
            reason=reason_code,
            details=details,
            blocking_sources=blocking_srcs,
            action_required=actions.get(reason_code, "Escalate to plant maintenance supervisor."),
        )

    # Rule 3: Contradiction Detection
    contradictions = detect_contradictions(incident.evidence)
    if contradictions:
        c = contradictions[0]
        blocking = [c["source_1"], c["source_2"]]
        return EscalationDecision(
            escalate=True,
            reason="CONTRADICTORY_INSTRUCTIONS",
            details=f"Conflicting documentary instructions detected: {c['description']} Silent resolution is prohibited.",
            blocking_sources=blocking,
            action_required="Escalate to plant safety officer / lead controls engineer to reconcile conflicting SOP versions.",
        )

    # Rule 4: Validate proposed checks against incident evidence
    if proposed_checks:
        is_valid_checks, invalid_ids = validate_proposed_checks(proposed_checks, incident.evidence)
        if not is_valid_checks:
            return EscalationDecision(
                escalate=True,
                reason="INVALID_EVIDENCE_REFERENCE",
                details=f"Proposed checks reference evidence identifiers not attached to this incident: {invalid_ids}",
                blocking_sources=invalid_ids,
                action_required="Re-link proposed steps strictly to retrieved evidence belonging to the current incident.",
            )

    return EscalationDecision(
        escalate=False,
        reason="CONFIRMED_APPLICABLE",
        details="Grounded evidence confirmed applicable to target equipment without contradictions.",
        blocking_sources=[],
        action_required="Proceed with authored troubleshooting checklist following documented safety precautions.",
    )
