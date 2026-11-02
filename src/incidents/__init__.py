"""Incident management module for Phase 2."""

from src.incidents.schema import Incident, VALID_INCIDENT_STATUSES
from src.incidents.protocol import IncidentServiceProtocol
from src.incidents.mock_service import MockIncidentService
from src.incidents.sqlite_service import SQLiteIncidentService

__all__ = [
    "Incident",
    "VALID_INCIDENT_STATUSES",
    "IncidentServiceProtocol",
    "MockIncidentService",
    "SQLiteIncidentService",
]

