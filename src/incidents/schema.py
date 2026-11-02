"""Incident schema and data models for Phase 2 incident-oriented assistant.

Defines the minimum shared incident schema agreed upon between Member A and Member B.
Invariants:
- incident_id and symptom must be non-empty and non-whitespace.
- status must be one of: "open", "investigating", "mitigated", "resolved", "closed".
- If equipment_model is None or empty, equipment_confirmed cannot be True.
- observations represents tentative visual or sensory findings, kept strictly
  separate from confirmed equipment_model and documentary evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Sequence

from contracts import Evidence


VALID_INCIDENT_STATUSES = ("open", "investigating", "mitigated", "resolved", "closed")


@dataclass
class Incident:
    """Represents an industrial operational incident or troubleshooting session.

    Attributes:
        incident_id: Unique identifier (e.g. 'INC-2026-001').
        title: Short descriptive title of the incident.
        symptom: Detailed description of the observed malfunction or alarm.
        equipment_model: Specific equipment model identifier if identified, otherwise None.
        equipment_confirmed: True if equipment model is verified by operator/documentation;
                             False if tentative, unconfirmed, or unknown.
        status: Current workflow status ('open', 'investigating', 'mitigated', 'resolved', 'closed').
        observations: Tentative visual or sensory observations (e.g., from inspection images).
        evidence: Verified documentary evidence references retrieved from manuals and SOPs.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last update timestamp.
    """
    incident_id: str
    title: str
    symptom: str
    equipment_model: Optional[str] = None
    equipment_confirmed: bool = False
    status: str = "open"
    observations: list[str] = field(default_factory=list)
    interpretations: list[str] = field(default_factory=list)
    technician_findings: list[str] = field(default_factory=list)
    hardware_revision: Optional[str] = None
    firmware_revision: Optional[str] = None
    reviewed_by_engineer: Optional[str] = None
    engineer_signoff: bool = False
    evidence: list[Evidence] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.incident_id or not self.incident_id.strip():
            raise ValueError("incident_id must be non-empty and non-whitespace")
        if not self.title or not self.title.strip():
            raise ValueError("title must be non-empty and non-whitespace")
        if not self.symptom or not self.symptom.strip():
            raise ValueError("symptom must not be empty or whitespace-only")
        
        status_lower = self.status.lower()
        if status_lower not in VALID_INCIDENT_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of: {', '.join(VALID_INCIDENT_STATUSES)}"
            )
        self.status = status_lower

        if self.equipment_confirmed and (not self.equipment_model or not self.equipment_model.strip()):
            raise ValueError("Cannot mark equipment as confirmed when equipment_model is None or empty")

