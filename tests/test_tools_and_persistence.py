"""Unit tests for Phase 2 Milestone 1B: Incident SQLite Persistence and Validated Tool Layer."""

import tempfile
import unittest
from pathlib import Path

from contracts import Chunk, Evidence
from src.incidents.schema import Incident
from src.incidents.sqlite_service import SQLiteIncidentService
from backend.tools.base import ToolResult, validate_safe_filesystem_path
from backend.tools.inspect_image import InspectImageTool
from backend.tools.lookup_equipment import LookupEquipmentTool
from backend.tools.search_documents import SearchDocumentsTool
from backend.tools.ask_user import AskUserTool
from backend.tools.read_manual_page import ReadManualPageTool
from backend.tools.registry import ToolRegistry
from backend.mock_backend import MockBackend


class TestSQLiteIncidentPersistence(unittest.TestCase):
    """Tests for SQLite persistence, create, load, update, and resume operations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_incidents.db"
        self.service = SQLiteIncidentService(db_path=self.db_path, populate_defaults=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_load_incident(self):
        chunk = Chunk(
            chunk_id="chunk_1",
            document_id="doc_sop_01",
            filename="sop_motor.pdf",
            page=2,
            text="Motor isolation procedure step 2.",
            equipment_model="Siemens 1LE1",
        )
        ev = Evidence(source_id="doc_sop_01#p2#c0", chunk=chunk)

        inc = self.service.create_incident(
            title="Motor Winding Resistance High",
            symptom="Phase to phase resistance exceeds 12 ohms.",
            equipment_model="Siemens 1LE1",
            equipment_confirmed=True,
            observations=["Phase U-V reads 14.2 ohms."],
            evidence=[ev],
        )
        self.assertTrue(inc.incident_id.startswith("INC-2026-"))
        self.assertEqual(inc.status, "open")
        self.assertEqual(len(inc.evidence), 1)

        # Load back
        loaded = self.service.load_incident(inc.incident_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "Motor Winding Resistance High")
        self.assertEqual(loaded.symptom, "Phase to phase resistance exceeds 12 ohms.")
        self.assertEqual(loaded.equipment_model, "Siemens 1LE1")
        self.assertTrue(loaded.equipment_confirmed)
        self.assertEqual(len(loaded.evidence), 1)
        self.assertEqual(loaded.evidence[0].source_id, "doc_sop_01#p2#c0")
        self.assertEqual(loaded.evidence[0].chunk.text, "Motor isolation procedure step 2.")

    def test_persistence_across_service_restarts(self):
        """Verify data survives SQLite service restart / separate connection."""
        inc = self.service.create_incident(
            title="Pressure Relief Stuck",
            symptom="Pressure relief valve failing to crack at 100 bar.",
            equipment_model="Rexroth DBDS",
            equipment_confirmed=False,
            observations=["Gauge reads 115 bar."],
        )

        # Simulate service restart with new service instance on same file
        restarted_service = SQLiteIncidentService(db_path=self.db_path, populate_defaults=False)
        fetched = restarted_service.get_incident(inc.incident_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.incident_id, inc.incident_id)
        self.assertEqual(fetched.title, "Pressure Relief Stuck")
        self.assertEqual(fetched.observations, ["Gauge reads 115 bar."])

    def test_update_status_and_confirm_equipment(self):
        inc = self.service.create_incident(
            title="Conveyor Jam",
            symptom="Belt stopped with motor stalled.",
        )
        self.assertEqual(inc.status, "open")
        self.assertFalse(inc.equipment_confirmed)

        # Update status
        updated = self.service.update_status(inc.incident_id, "investigating")
        self.assertEqual(updated.status, "investigating")

        # Confirm equipment
        confirmed = self.service.confirm_equipment(inc.incident_id, "Dorner 2200")
        self.assertEqual(confirmed.equipment_model, "Dorner 2200")
        self.assertTrue(confirmed.equipment_confirmed)

    def test_resume_incident_advances_open_to_investigating(self):
        """Resuming an open incident automatically moves status to investigating."""
        inc = self.service.create_incident(
            title="Bearing Temperature Alarm",
            symptom="Bearing RTD reads 85C.",
        )
        self.assertEqual(inc.status, "open")

        resumed = self.service.resume_incident(inc.incident_id)
        self.assertEqual(resumed.status, "investigating")

        # Resuming already investigating incident keeps investigating
        resumed_again = self.service.resume_incident(inc.incident_id)
        self.assertEqual(resumed_again.status, "investigating")

    def test_update_incident_full_payload(self):
        inc = self.service.create_incident(
            title="Original Title",
            symptom="Original Symptom",
        )
        inc.interpretations.append("Possible bearing grease breakdown.")
        inc.technician_findings.append("Inspected grease nipple; dry.")
        inc.reviewed_by_engineer = "Engineer Dave"
        inc.engineer_signoff = True
        inc.status = "resolved"

        saved = self.service.update_incident(inc)
        self.assertEqual(saved.reviewed_by_engineer, "Engineer Dave")
        self.assertTrue(saved.engineer_signoff)
        self.assertEqual(saved.technician_findings, ["Inspected grease nipple; dry."])
        self.assertEqual(saved.status, "resolved")


class TestToolSecurityAndPathValidation(unittest.TestCase):
    """Tests for path sandboxing and security boundary enforcement."""

    def setUp(self):
        self.fixture_image = Path("tests/fixtures/synthetic_plc_leds_normal.png")

    def test_authorized_workspace_path_accepted(self):
        resolved = validate_safe_filesystem_path(self.fixture_image)
        self.assertEqual(resolved.resolve(), self.fixture_image.resolve())

    def test_path_traversal_token_rejected(self):
        with self.assertRaises(PermissionError):
            validate_safe_filesystem_path("../../etc/passwd")

    def test_path_outside_allowed_roots_rejected(self):
        with self.assertRaises(PermissionError):
            validate_safe_filesystem_path("/var/log/system.log")

    def test_nonexistent_path_in_allowed_dir_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            validate_safe_filesystem_path("data/nonexistent_image_12345.png")


class TestToolsExecution(unittest.TestCase):
    """Direct execution tests for wrapped local tools."""

    def setUp(self):
        self.backend = MockBackend()
        # Seed backend with test chunks
        chunk = Chunk(
            chunk_id="chunk_test_01",
            document_id="doc_pump_sop",
            filename="pump_manual.pdf",
            page=1,
            text="Hydraulic pump startup sequence and pressure check guidelines.",
            equipment_model="Hydraulic Pump P-100",
        )
        self.backend.index_chunks([chunk])

    def test_search_documents_tool(self):
        tool = SearchDocumentsTool(self.backend)
        # Valid search
        res = tool.execute(query="startup sequence", top_k=2)
        self.assertTrue(res.success)
        self.assertEqual(res.data["query"], "startup sequence")
        self.assertGreaterEqual(len(res.evidence), 1)

        # Invalid search (empty query)
        res_empty = tool.execute(query="   ")
        self.assertFalse(res_empty.success)
        self.assertIn("query must not be empty", res_empty.error)

    def test_lookup_equipment_tool(self):
        tool = LookupEquipmentTool(self.backend)
        res = tool.execute(equipment_model="Hydraulic Pump P-100")
        self.assertTrue(res.success)
        self.assertEqual(res.data["equipment_model"], "Hydraulic Pump P-100")
        self.assertIn("pump_manual.pdf", res.data["matched_files"])

        # Empty model rejected
        res_bad = tool.execute(equipment_model="")
        self.assertFalse(res_bad.success)

    def test_inspect_image_tool(self):
        tool = InspectImageTool(self.backend)
        # Valid fixture image
        res = tool.execute(image_path="tests/fixtures/synthetic_plc_leds_normal.png")
        self.assertTrue(res.success)
        self.assertGreater(len(res.observations), 0)

        # Path traversal attack rejected
        res_traversal = tool.execute(image_path="../../etc/hosts")
        self.assertFalse(res_traversal.success)
        self.assertIn("SecurityError", res_traversal.error)

        # Nonexistent file in allowed dir
        res_missing = tool.execute(image_path="tests/fixtures/ghost_file.png")
        self.assertFalse(res_missing.success)
        self.assertIn("FileNotFoundError", res_missing.error)

    def test_ask_user_tool(self):
        tool = AskUserTool()
        res = tool.execute(
            question="Is the cooling fan rotating?",
            options=["Yes, normal speed", "Yes, slow/noisy", "No, stationary"],
        )
        self.assertTrue(res.success)
        self.assertEqual(res.data["type"], "clarification_request")
        self.assertEqual(len(res.data["options"]), 3)
        self.assertTrue(res.metadata["requires_human_input"])

        # Empty question rejected
        res_empty = tool.execute(question="  ")
        self.assertFalse(res_empty.success)

    def test_read_manual_page_tool_reports_unavailable(self):
        """Task 5: Expose read_manual_page as unavailable rather than faking support."""
        tool = ReadManualPageTool(self.backend)
        res = tool.execute(document_id="doc_pump_sop", page=1)
        self.assertFalse(res.success)
        self.assertIn("UNAVAILABLE", res.error)
        self.assertFalse(res.data["supported"])

    def test_tool_registry_manifest_and_dispatch(self):
        registry = ToolRegistry(self.backend)
        tools = registry.list_tools()
        self.assertIn("inspect_image", tools)
        self.assertIn("lookup_equipment", tools)
        self.assertIn("search_documents", tools)
        self.assertIn("ask_user", tools)
        self.assertIn("read_manual_page", tools)

        # Manifest
        manifest = registry.get_tool_manifest()
        self.assertEqual(len(manifest), 5)

        # Dispatch execution
        res = registry.execute_tool("ask_user", question="Confirm pressure bar?")
        self.assertTrue(res.success)

        # Dispatch non-existent tool
        res_fake = registry.execute_tool("fake_tool_xyz")
        self.assertFalse(res_fake.success)
        self.assertIn("NoSuchToolError", res_fake.error)


if __name__ == "__main__":
    unittest.main()
