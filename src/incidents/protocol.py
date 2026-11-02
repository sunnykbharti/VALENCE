"""Service protocol for incident management in Phase 2."""

from __future__ import annotations

from typing import Optional, Protocol, Sequence
from contracts import Evidence
from src.incidents.schema import Incident


class IncidentServiceProtocol(Protocol):
    """Protocol for incident lifecycle and status management."""

    def create_incident(
        self,
        title: str,
        symptom: str,
        equipment_model: Optional[str] = None,
        equipment_confirmed: bool = False,
        observations: Optional[Sequence[str]] = None,
        evidence: Optional[Sequence[Evidence]] = None,
    ) -> Incident:
        """Creates a new incident record.

        Raises:
            ValueError: If title, symptom, or validation constraints fail.
        """
        ...

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieves an incident by its unique ID, or None if not found."""
        ...

    def list_incidents(self) -> list[Incident]:
        """Lists all existing incidents, typically ordered by update time descending."""
        ...

    def update_status(self, incident_id: str, new_status: str) -> Incident:
        """Updates the operational status of an incident.

        Raises:
            KeyError: If incident_id does not exist.
            ValueError: If new_status is invalid or forbidden by transition rules.
        """
        ...

    def confirm_equipment(self, incident_id: str, equipment_model: str) -> Incident:
        """Marks the equipment model as confirmed by operator.

        Raises:
            KeyError: If incident_id does not exist.
            ValueError: If equipment_model is empty or whitespace.
        """
        ...

    def add_observations(self, incident_id: str, observations: Sequence[str]) -> Incident:
        """Appends tentative visual observations to the incident record.

        Observations remain distinctly labeled as tentative and do not confirm equipment identity.

        Raises:
            KeyError: If incident_id does not exist.
        """
        ...

    def attach_evidence(self, incident_id: str, evidence: Sequence[Evidence]) -> Incident:
        """Attaches verified documentary evidence to the incident record.

        Raises:
            KeyError: If incident_id does not exist.
        """
        ...

    def add_technician_findings(self, incident_id: str, findings: Sequence[str]) -> Incident:
        """Appends human-verified physical inspection findings to the incident record.

        Findings represent physical inspection results carried out by human technicians.

        Raises:
            KeyError: If incident_id does not exist.
        """
        ...

