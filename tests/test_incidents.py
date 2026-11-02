"""Unit tests for Phase 2 Milestone 1A: Incident schema, service, and state transitions."""

import unittest
from contracts import Chunk, Evidence
from src.incidents.schema import Incident, VALID_INCIDENT_STATUSES
from src.incidents.mock_service import MockIncidentService


class TestIncidentSchema(unittest.TestCase):
    """Tests for Incident dataclass invariants and validation."""

    def test_valid_incident_instantiation(self):
        inc = Incident(
            incident_id="INC-101",
            title="Drive Overcurrent",
            symptom="Inverter trips with fault code F0001 under load.",
            equipment_model="Micromaster 440",
            equipment_confirmed=True,
            status="open",
        )
        self.assertEqual(inc.incident_id, "INC-101")
        self.assertEqual(inc.title, "Drive Overcurrent")
        self.assertEqual(inc.status, "open")
        self.assertTrue(inc.equipment_confirmed)
        self.assertEqual(inc.equipment_model, "Micromaster 440")
        self.assertEqual(len(inc.observations), 0)
        self.assertEqual(len(inc.evidence), 0)

    def test_empty_incident_id_raises_value_error(self):
        with self.assertRaises(ValueError):
            Incident(
                incident_id="   ",
                title="Fault",
                symptom="Overheat",
            )

    def test_empty_title_raises_value_error(self):
        with self.assertRaises(ValueError):
            Incident(
                incident_id="INC-102",
                title="",
                symptom="Overheat",
            )

    def test_empty_symptom_raises_value_error(self):
        with self.assertRaises(ValueError):
            Incident(
                incident_id="INC-103",
                title="Drive Failure",
                symptom="    ",
            )

    def test_invalid_status_raises_value_error(self):
        with self.assertRaises(ValueError):
            Incident(
                incident_id="INC-104",
                title="Drive Failure",
                symptom="Error code 12",
                status="unknown_status",
            )

    def test_confirm_without_equipment_model_raises_value_error(self):
        """Invariant: Cannot confirm equipment model if equipment_model is None or empty."""
        with self.assertRaises(ValueError):
            Incident(
                incident_id="INC-105",
                title="Unknown Sensor Failure",
                symptom="Sensor wire broken",
                equipment_model=None,
                equipment_confirmed=True,
            )

        with self.assertRaises(ValueError):
            Incident(
                incident_id="INC-106",
                title="Unknown Sensor Failure",
                symptom="Sensor wire broken",
                equipment_model="   ",
                equipment_confirmed=True,
            )


class TestMockIncidentService(unittest.TestCase):
    """Tests for MockIncidentService operations, state transitions, and observation isolation."""

    def setUp(self):
        self.service = MockIncidentService(populate_defaults=True)

    def test_default_seeded_incidents_present(self):
        incidents = self.service.list_incidents()
        self.assertGreaterEqual(len(incidents), 2)
        inc1 = self.service.get_incident("INC-2026-001")
        self.assertIsNotNone(inc1)
        self.assertEqual(inc1.equipment_model, "S7-1200 CPU 1214C")
        self.assertTrue(inc1.equipment_confirmed)
        self.assertEqual(inc1.status, "investigating")

    def test_create_incident_generates_unique_id_and_open_status(self):
        inc = self.service.create_incident(
            title="Conveyor Bearing Noise",
            symptom="High-frequency squeal from drive-end bearing.",
            equipment_model="SKF 6205-2RSH",
            equipment_confirmed=False,
            observations=["Grease leakage observed around seal."],
        )
        self.assertTrue(inc.incident_id.startswith("INC-2026-"))
        self.assertEqual(inc.status, "open")
        self.assertFalse(inc.equipment_confirmed)
        self.assertEqual(len(inc.observations), 1)
        self.assertIn("Grease leakage", inc.observations[0])

        # Verify retrieval
        fetched = self.service.get_incident(inc.incident_id)
        self.assertEqual(fetched, inc)

    def test_status_transitions(self):
        inc = self.service.create_incident(
            title="Pneumatic Valve Leak",
            symptom="Air hissing heard near cylinder manifold.",
        )
        self.assertEqual(inc.status, "open")

        for next_status in ["investigating", "mitigated", "resolved", "closed"]:
            updated = self.service.update_status(inc.incident_id, next_status)
            self.assertEqual(updated.status, next_status)
            self.assertEqual(self.service.get_incident(inc.incident_id).status, next_status)

    def test_invalid_status_transition_rejected(self):
        inc = self.service.create_incident(
            title="Test Incident",
            symptom="Test Symptom",
        )
        with self.assertRaises(ValueError):
            self.service.update_status(inc.incident_id, "invalid_workflow_step")

    def test_nonexistent_incident_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.service.update_status("NONEXISTENT-INC", "resolved")
        with self.assertRaises(KeyError):
            self.service.confirm_equipment("NONEXISTENT-INC", "Model-X")
        with self.assertRaises(KeyError):
            self.service.add_observations("NONEXISTENT-INC", ["obs"])
        with self.assertRaises(KeyError):
            self.service.attach_evidence("NONEXISTENT-INC", [])

    def test_equipment_confirmation_transition(self):
        """Operator physically confirms equipment identity."""
        inc = self.service.create_incident(
            title="Unidentified Pump Vibration",
            symptom="Vibration monitor alarm at 4.2 mm/s RMS.",
            equipment_model=None,
            equipment_confirmed=False,
        )
        self.assertFalse(inc.equipment_confirmed)
        self.assertIsNone(inc.equipment_model)

        updated = self.service.confirm_equipment(inc.incident_id, "Grundfos CR 15-4")
        self.assertTrue(updated.equipment_confirmed)
        self.assertEqual(updated.equipment_model, "Grundfos CR 15-4")

        # Verify empty confirmation string rejected
        with self.assertRaises(ValueError):
            self.service.confirm_equipment(inc.incident_id, "   ")

    def test_tentative_observations_kept_separate_from_confirmation(self):
        """Visual observations must remain tentative and never alter confirmation state."""
        inc = self.service.create_incident(
            title="Visual Smoke Inspection",
            symptom="Smoke reported near junction box JB-4.",
            equipment_model="JB-4 Enclosure",
            equipment_confirmed=False,
        )
        self.assertFalse(inc.equipment_confirmed)
        self.assertEqual(len(inc.observations), 0)

        # Append tentative observations
        updated = self.service.add_observations(
            inc.incident_id,
            ["[MOCK] Scorched terminal block TB-2.", "[MOCK] Black soot on enclosure lid."],
        )
        self.assertEqual(len(updated.observations), 2)
        # Confirmation state MUST still remain False
        self.assertFalse(updated.equipment_confirmed)
        self.assertEqual(updated.equipment_model, "JB-4 Enclosure")

    def test_attach_document_evidence_without_duplicates(self):
        inc = self.service.create_incident(
            title="Overheating Relay",
            symptom="Thermal relay tripping after 10 mins.",
        )
        chunk = Chunk(
            chunk_id="chunk_1",
            document_id="doc_sop_01",
            filename="sop_relay.pdf",
            page=4,
            text="Thermal overload relay trip curve specifications.",
        )
        ev1 = Evidence(source_id="doc_sop_01#p4#c0", chunk=chunk)
        ev2 = Evidence(source_id="doc_sop_01#p4#c0", chunk=chunk)  # duplicate source_id

        self.service.attach_evidence(inc.incident_id, [ev1, ev2])
        fetched = self.service.get_incident(inc.incident_id)
        # Should deduplicate source_id
        self.assertEqual(len(fetched.evidence), 1)
        self.assertEqual(fetched.evidence[0].source_id, "doc_sop_01#p4#c0")


if __name__ == "__main__":
    unittest.main()

