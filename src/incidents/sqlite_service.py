"""SQLite-backed persistent incident management service for Phase 2 Milestone 1B.

Provides disk-persistent, air-gapped storage for industrial incidents using Python's
built-in sqlite3 database. Conforms strictly to IncidentServiceProtocol and supports
create, load, update, and resume operations across application restarts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Chunk, Evidence
from src.incidents.schema import Incident, VALID_INCIDENT_STATUSES
from src.incidents.protocol import IncidentServiceProtocol

logger = logging.getLogger(__name__)


def _serialize_evidence(evidence: Sequence[Evidence]) -> str:
    """Serializes a sequence of Evidence objects into JSON string."""
    data = []
    for ev in evidence:
        data.append({
            "source_id": ev.source_id,
            "chunk": {
                "chunk_id": ev.chunk.chunk_id,
                "document_id": ev.chunk.document_id,
                "filename": ev.chunk.filename,
                "page": ev.chunk.page,
                "text": ev.chunk.text,
                "equipment_model": ev.chunk.equipment_model,
                "synthetic": ev.chunk.synthetic,
            },
        })
    return json.dumps(data)


def _deserialize_evidence(raw_json: str) -> list[Evidence]:
    """Deserializes JSON string into a list of Evidence objects."""
    if not raw_json or raw_json.strip() == "":
        return []
    try:
        items = json.loads(raw_json)
        res = []
        for item in items:
            c = item["chunk"]
            chunk = Chunk(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                filename=c["filename"],
                page=c["page"],
                text=c["text"],
                equipment_model=c.get("equipment_model"),
                synthetic=c.get("synthetic", False),
            )
            res.append(Evidence(source_id=item["source_id"], chunk=chunk))
        return res
    except Exception as e:
        logger.warning("Failed to deserialize evidence JSON: %s", e)
        return []


class SQLiteIncidentService(IncidentServiceProtocol):
    """Local SQLite-backed persistent incident service."""

    def __init__(self, db_path: Union[str, Path] = "data/incidents.db", populate_defaults: bool = False) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        if populate_defaults:
            self._seed_default_incidents_if_empty()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    symptom TEXT NOT NULL,
                    equipment_model TEXT,
                    equipment_confirmed INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'open',
                    observations TEXT NOT NULL DEFAULT '[]',
                    interpretations TEXT NOT NULL DEFAULT '[]',
                    technician_findings TEXT NOT NULL DEFAULT '[]',
                    hardware_revision TEXT,
                    firmware_revision TEXT,
                    reviewed_by_engineer TEXT,
                    engineer_signoff INTEGER NOT NULL DEFAULT 0,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def _seed_default_incidents_if_empty(self) -> None:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM incidents")
            count = cur.fetchone()[0]
            if count == 0:
                self.create_incident(
                    title="Overheating Warning on S7-1200 CPU Module",
                    symptom="PLC rack temperature sensor reads 68°C (threshold: 60°C). CPU DIAG LED is blinking amber.",
                    equipment_model="S7-1200 CPU 1214C",
                    equipment_confirmed=True,
                    observations=[
                        "[MOCK OBSERVATION] Amber DIAG indicator flashing at 2 Hz on front panel.",
                        "[MOCK OBSERVATION] Cabinet ventilation fan appears stationary.",
                    ],
                )
                self.create_incident(
                    title="Hydraulic Infeed Pressure Drop",
                    symptom="Line pressure dropped to 35 bar during secondary clamp cycle. Low pressure interlock tripped.",
                    equipment_model=None,
                    equipment_confirmed=False,
                    observations=[
                        "[MOCK OBSERVATION] Possible fluid pooling under manifold valve B3.",
                        "[MOCK OBSERVATION] Pressure gauge dial reads 35 bar (nominal: 70 bar).",
                    ],
                )

    def _row_to_incident(self, row: sqlite3.Row) -> Incident:
        return Incident(
            incident_id=row["incident_id"],
            title=row["title"],
            symptom=row["symptom"],
            equipment_model=row["equipment_model"],
            equipment_confirmed=bool(row["equipment_confirmed"]),
            status=row["status"],
            observations=json.loads(row["observations"]),
            interpretations=json.loads(row["interpretations"]),
            technician_findings=json.loads(row["technician_findings"]),
            hardware_revision=row["hardware_revision"],
            firmware_revision=row["firmware_revision"],
            reviewed_by_engineer=row["reviewed_by_engineer"],
            engineer_signoff=bool(row["engineer_signoff"]),
            evidence=_deserialize_evidence(row["evidence_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_incident(
        self,
        title: str,
        symptom: str,
        equipment_model: Optional[str] = None,
        equipment_confirmed: bool = False,
        observations: Optional[Sequence[str]] = None,
        evidence: Optional[Sequence[Evidence]] = None,
    ) -> Incident:
        """Creates a new incident record in persistent storage."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM incidents")
            count = cur.fetchone()[0]
            incident_id = f"INC-2026-{count + 1:03d}"

            # Validate via Incident dataclass first
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

            conn.execute(
                """
                INSERT INTO incidents (
                    incident_id, title, symptom, equipment_model, equipment_confirmed,
                    status, observations, interpretations, technician_findings,
                    hardware_revision, firmware_revision, reviewed_by_engineer,
                    engineer_signoff, evidence_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    inc.incident_id,
                    inc.title,
                    inc.symptom,
                    inc.equipment_model,
                    1 if inc.equipment_confirmed else 0,
                    inc.status,
                    json.dumps(inc.observations),
                    json.dumps(inc.interpretations),
                    json.dumps(inc.technician_findings),
                    inc.hardware_revision,
                    inc.firmware_revision,
                    inc.reviewed_by_engineer,
                    1 if inc.engineer_signoff else 0,
                    _serialize_evidence(inc.evidence),
                    inc.created_at,
                    inc.updated_at,
                ),
            )
            conn.commit()
            return inc

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Loads an incident from persistent storage by ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_incident(row)

    def load_incident(self, incident_id: str) -> Optional[Incident]:
        """Alias for get_incident to satisfy load contract."""
        return self.get_incident(incident_id)

    def list_incidents(self) -> list[Incident]:
        """Lists all existing incidents ordered by creation time."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM incidents ORDER BY created_at ASC")
            rows = cur.fetchall()
            return [self._row_to_incident(r) for r in rows]

    def update_status(self, incident_id: str, new_status: str) -> Incident:
        """Updates the operational status of an incident."""
        status_clean = new_status.strip().lower()
        if status_clean not in VALID_INCIDENT_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_INCIDENT_STATUSES)}")

        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
            if not cur.fetchone():
                raise KeyError(f"Incident with ID '{incident_id}' not found")

            conn.execute(
                "UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ?",
                (status_clean, now, incident_id),
            )
            conn.commit()
            return self.get_incident(incident_id)

    def confirm_equipment(self, incident_id: str, equipment_model: str) -> Incident:
        """Marks the equipment model as confirmed by operator."""
        if not equipment_model or not equipment_model.strip():
            raise ValueError("Equipment model must not be empty when confirming")

        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
            if not cur.fetchone():
                raise KeyError(f"Incident with ID '{incident_id}' not found")

            conn.execute(
                "UPDATE incidents SET equipment_model = ?, equipment_confirmed = 1, updated_at = ? WHERE incident_id = ?",
                (equipment_model.strip(), now, incident_id),
            )
            conn.commit()
            return self.get_incident(incident_id)

    def add_observations(self, incident_id: str, observations: Sequence[str]) -> Incident:
        """Appends tentative visual observations to the incident record."""
        inc = self.get_incident(incident_id)
        if not inc:
            raise KeyError(f"Incident with ID '{incident_id}' not found")

        current_obs = list(inc.observations)
        for obs in observations:
            cleaned = obs.strip()
            if cleaned and cleaned not in current_obs:
                current_obs.append(cleaned)

        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE incidents SET observations = ?, updated_at = ? WHERE incident_id = ?",
                (json.dumps(current_obs), now, incident_id),
            )
            conn.commit()
            return self.get_incident(incident_id)

    def attach_evidence(self, incident_id: str, evidence: Sequence[Evidence]) -> Incident:
        """Attaches verified documentary evidence to the incident record."""
        inc = self.get_incident(incident_id)
        if not inc:
            raise KeyError(f"Incident with ID '{incident_id}' not found")

        existing_sources = {e.source_id for e in inc.evidence}
        current_ev = list(inc.evidence)
        for ev in evidence:
            if ev.source_id not in existing_sources:
                current_ev.append(ev)
                existing_sources.add(ev.source_id)

        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE incidents SET evidence_json = ?, updated_at = ? WHERE incident_id = ?",
                (_serialize_evidence(current_ev), now, incident_id),
            )
            conn.commit()
            return self.get_incident(incident_id)

    def update_incident(self, incident: Incident) -> Incident:
        """Updates full incident state in persistent storage."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident.incident_id,))
            if not cur.fetchone():
                raise KeyError(f"Incident with ID '{incident.incident_id}' not found")

            conn.execute(
                """
                UPDATE incidents SET
                    title = ?,
                    symptom = ?,
                    equipment_model = ?,
                    equipment_confirmed = ?,
                    status = ?,
                    observations = ?,
                    interpretations = ?,
                    technician_findings = ?,
                    hardware_revision = ?,
                    firmware_revision = ?,
                    reviewed_by_engineer = ?,
                    engineer_signoff = ?,
                    evidence_json = ?,
                    updated_at = ?
                WHERE incident_id = ?;
                """,
                (
                    incident.title,
                    incident.symptom,
                    incident.equipment_model,
                    1 if incident.equipment_confirmed else 0,
                    incident.status,
                    json.dumps(incident.observations),
                    json.dumps(incident.interpretations),
                    json.dumps(incident.technician_findings),
                    incident.hardware_revision,
                    incident.firmware_revision,
                    incident.reviewed_by_engineer,
                    1 if incident.engineer_signoff else 0,
                    _serialize_evidence(incident.evidence),
                    now,
                    incident.incident_id,
                ),
            )
            conn.commit()
            return self.get_incident(incident.incident_id)

    def resume_incident(self, incident_id: str) -> Incident:
        """Resumes an existing incident, advancing status to 'investigating' if open."""
        inc = self.get_incident(incident_id)
        if not inc:
            raise KeyError(f"Incident with ID '{incident_id}' not found")

        if inc.status == "open":
            return self.update_status(incident_id, "investigating")
        return inc

