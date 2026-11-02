"""Mock incident management service for Phase 2 development and testing.

Provides in-memory incident tracking with synthetic industrial sample incidents.
Clearly labeled as [MOCK INCIDENT SERVICE] for development and offline testing.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional, Sequence

from contracts import Evidence
from src.incidents.schema import Incident, VALID_INCIDENT_STATUSES
from src.incidents.protocol import IncidentServiceProtocol

logger = logging.getLogger(__name__)


class MockIncidentService(IncidentServiceProtocol):
    """In-memory mock incident service conforming to IncidentServiceProtocol."""

    def __init__(self, populate_defaults: bool = True) -> None:
        self._incidents: dict[str, Incident] = {}
        self._counter: int = 100
        if populate_defaults:
            self._seed_default_incidents()

    def _seed_default_incidents(self) -> None:
        """Seeds initial synthetic incidents for testing and UI demonstration."""
        inc_1 = Incident(
            incident_id="INC-2026-001",
            title="Overheating Warning on S7-1200 CPU Module",
            symptom="PLC rack temperature sensor reads 68°C (threshold: 60°C). CPU DIAG LED is blinking amber.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            status="investigating",
            observations=[
                "[MOCK OBSERVATION] Amber DIAG indicator flashing at 2 Hz on front panel.",
                "[MOCK OBSERVATION] Cabinet ventilation fan appears stationary.",
            ],
            evidence=[],
        )
        inc_2 = Incident(
            incident_id="INC-2026-002",
            title="Hydraulic Infeed Pressure Drop",
            symptom="Line pressure dropped to 35 bar during secondary clamp cycle. Low pressure interlock tripped.",
            equipment_model=None,
            equipment_confirmed=False,
            status="open",
            observations=[
                "[MOCK OBSERVATION] Possible fluid pooling under manifold valve B3.",
                "[MOCK OBSERVATION] Pressure gauge dial reads 35 bar (nominal: 70 bar).",
            ],
            evidence=[],
        )
        self._incidents[inc_1.incident_id] = inc_1
        self._incidents[inc_2.incident_id] = inc_2

    def create_incident(
        self,
        title: str,
        symptom: str,
        equipment_model: Optional[str] = None,
        equipment_confirmed: bool = False,
        observations: Optional[Sequence[str]] = None,
        evidence: Optional[Sequence[Evidence]] = None,
    ) -> Incident:
        """Creates a new incident record in-memory."""
        self._counter += 1
        incident_id = f"INC-2026-{self._counter:03d}"
        now = datetime.now(timezone.utc).isoformat()
        
        inc = Incident(
            incident_id=incident_id,
            title=title.strip(),
            symptom=symptom.strip(),
            equipment_model=equipment_model.strip() if equipment_model and equipment_model.strip() else None,
            equipment_confirmed=equipment_confirmed,
            status="open",
            observations=list(observations or []),
            evidence=list(evidence or []),
            created_at=now,
            updated_at=now,
        )
        self._incidents[incident_id] = inc
        logger.info("[MOCK INCIDENT SERVICE] Created incident %s: %s", incident_id, title)
        return inc

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieves an incident by its unique ID."""
        return self._incidents.get(incident_id)

    def list_incidents(self) -> list[Incident]:
        """Lists all existing incidents sorted by creation / ID."""
        return list(self._incidents.values())

    def update_status(self, incident_id: str, new_status: str) -> Incident:
        """Updates the operational status of an incident."""
        if incident_id not in self._incidents:
            raise KeyError(f"Incident with ID '{incident_id}' not found")
        
        status_clean = new_status.strip().lower()
        if status_clean not in VALID_INCIDENT_STATUSES:
            raise ValueError(
                f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_INCIDENT_STATUSES)}"
            )

        inc = self._incidents[incident_id]
        inc.status = status_clean
        inc.updated_at = datetime.now(timezone.utc).isoformat()
        return inc

    def confirm_equipment(self, incident_id: str, equipment_model: str) -> Incident:
        """Marks the equipment model as confirmed by operator."""
        if incident_id not in self._incidents:
            raise KeyError(f"Incident with ID '{incident_id}' not found")
        if not equipment_model or not equipment_model.strip():
            raise ValueError("Equipment model must not be empty when confirming")

        inc = self._incidents[incident_id]
        inc.equipment_model = equipment_model.strip()
        inc.equipment_confirmed = True
        inc.updated_at = datetime.now(timezone.utc).isoformat()
        return inc

    def add_observations(self, incident_id: str, observations: Sequence[str]) -> Incident:
        """Appends tentative visual observations to the incident record."""
        if incident_id not in self._incidents:
            raise KeyError(f"Incident with ID '{incident_id}' not found")

        inc = self._incidents[incident_id]
        for obs in observations:
            cleaned = obs.strip()
            if cleaned and cleaned not in inc.observations:
                inc.observations.append(cleaned)
        inc.updated_at = datetime.now(timezone.utc).isoformat()
        return inc

    def attach_evidence(self, incident_id: str, evidence: Sequence[Evidence]) -> Incident:
        """Attaches verified documentary evidence to the incident record."""
        if incident_id not in self._incidents:
            raise KeyError(f"Incident with ID '{incident_id}' not found")

        inc = self._incidents[incident_id]
        existing_sources = {e.source_id for e in inc.evidence}
        for ev in evidence:
            if ev.source_id not in existing_sources:
                inc.evidence.append(ev)
                existing_sources.add(ev.source_id)
        inc.updated_at = datetime.now(timezone.utc).isoformat()
        return inc

    def add_technician_findings(self, incident_id: str, findings: Sequence[str]) -> Incident:
        """Appends verified technician findings to the incident record."""
        if incident_id not in self._incidents:
            raise KeyError(f"Incident with ID '{incident_id}' not found")

        inc = self._incidents[incident_id]
        for f in findings:
            cleaned = f.strip()
            if cleaned and cleaned not in inc.technician_findings:
                inc.technician_findings.append(cleaned)
        inc.updated_at = datetime.now(timezone.utc).isoformat()
        return inc

