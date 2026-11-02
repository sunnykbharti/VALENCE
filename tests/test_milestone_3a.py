"""Unit and integration tests for Phase 2 Milestone 3A.

Goal: Support evidence-linked findings and a useful handover.

Tasks verified:
1. Display each proposed documented check with its source evidence.
2. Let the technician record a finding without implying the application performed the check.
3. Display equipment/manual mismatch and missing-evidence messages.
4. Add a structured handover preview containing:
   symptom, equipment confirmation, observations, sources,
   technician findings, unresolved questions, escalation reason.
5. Allow the user to review before saving or exporting the handover.
6. Label generated summaries and synthetic incident data clearly.
7. Keep unreviewed outcomes separate from reviewed outcomes.
   Do not imply reviewer approval if authentication/authorization has not been implemented.
"""

import json
import unittest
from contracts import Chunk, Evidence
from src.incidents.schema import Incident
from src.incidents.mock_service import MockIncidentService
from backend.applicability import (
    ProposedCheck,
    EscalationDecision,
    extract_proposed_checks,
    validate_proposed_checks,
    validate_equipment_applicability,
    evaluate_incident_applicability,
)
from backend.handover import (
    HandoverReport,
    generate_handover,
    promote_incident_to_knowledge_chunk,
)


class TestMilestone3AElements(unittest.TestCase):
    """Unit tests for Milestone 3A backend models, check derivation, and handover governance."""

    def setUp(self):
        self.chunk_manual = Chunk(
            chunk_id="chunk_s7_p14",
            document_id="doc_s71200",
            filename="s71200_system_manual.pdf",
            page=14,
            text=(
                "For CPU 1214C overheating troubleshooting: "
                "1. Measure cabinet intake temperature using calibrated thermal probe. "
                "2. Inspect ventilation fan for physical blockage or seized rotor. "
                "Warning: Isolate and de-energize main supply before fan replacement."
            ),
            equipment_model="S7-1200 CPU 1214C",
            synthetic=True,
        )
        self.ev_manual = Evidence(source_id="doc_s71200#p14#c0", chunk=self.chunk_manual)

        self.service = MockIncidentService(populate_defaults=False)

    def test_task1_extract_proposed_checks_linked_to_source_evidence(self):
        """Task 1: Display each proposed documented check with its source evidence."""
        checks = extract_proposed_checks([self.ev_manual])
        self.assertGreaterEqual(len(checks), 2)

        chk1 = checks[0]
        self.assertTrue(chk1.check_id.startswith("CHK-"))
        self.assertEqual(chk1.step_number, 1)
        self.assertIn(self.ev_manual.source_id, chk1.evidence_ids)
        self.assertTrue(bool(chk1.instruction.strip()))

        # Verify all proposed checks reference valid attached evidence
        is_valid, invalid_ids = validate_proposed_checks(checks, [self.ev_manual])
        self.assertTrue(is_valid)
        self.assertEqual(len(invalid_ids), 0)

        # Precaution detection check
        precaution_checks = [c for c in checks if c.safety_precaution]
        self.assertGreaterEqual(len(precaution_checks), 1)
        self.assertIn("isolation", precaution_checks[0].safety_precaution.lower())

    def test_task2_technician_records_findings_without_system_execution(self):
        """Task 2: Let technician record physical finding without implying application performed check."""
        inc = self.service.create_incident(
            title="Cabinet Temperature High",
            symptom="Intake sensor reads 64°C",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[self.ev_manual],
        )

        finding_text = "[CHK-01 Physical Finding]: Intake thermal probe reads 63.8°C; fan blades dusty but spin freely."
        updated = self.service.add_technician_findings(inc.incident_id, [finding_text])

        self.assertEqual(len(updated.technician_findings), 1)
        self.assertEqual(updated.technician_findings[0], finding_text)
        # Invariant: Observations remain distinct from physical findings
        self.assertEqual(len(updated.observations), 0)

    def test_task3_display_equipment_mismatch_and_missing_evidence(self):
        """Task 3: Display equipment/manual mismatch and missing-evidence messages."""
        # 1. Missing evidence scenario
        inc_no_ev = Incident(
            incident_id="INC-301",
            title="Alarm Without Docs",
            symptom="Inverter trip code 0x41",
            equipment_model="Micromaster 440",
            equipment_confirmed=True,
            evidence=[],
        )
        dec_no_ev = evaluate_incident_applicability(inc_no_ev)
        self.assertTrue(dec_no_ev.escalate)
        self.assertEqual(dec_no_ev.reason, "ABSENT_EVIDENCE")

        # 2. Equipment mismatch scenario
        inc_mismatch = Incident(
            incident_id="INC-302",
            title="Drive Fault on S7-1500",
            symptom="CPU diag LED red",
            equipment_model="S7-1500 CPU 1516",
            equipment_confirmed=True,
            evidence=[self.ev_manual],  # Document applies to S7-1200!
        )
        dec_mismatch = evaluate_incident_applicability(inc_mismatch)
        self.assertTrue(dec_mismatch.escalate)
        self.assertEqual(dec_mismatch.reason, "EQUIPMENT_MISMATCH")
        self.assertIn("does not match retrieved document", dec_mismatch.details)

        # 3. Unconfirmed equipment scenario
        inc_unconfirmed = Incident(
            incident_id="INC-303",
            title="Unknown PLC Trip",
            symptom="Power fault LED on",
            equipment_model=None,
            equipment_confirmed=False,
            evidence=[self.ev_manual],
        )
        dec_unconfirmed = evaluate_incident_applicability(inc_unconfirmed)
        self.assertTrue(dec_unconfirmed.escalate)
        self.assertEqual(dec_unconfirmed.reason, "UNKNOWN_EQUIPMENT")

    def test_task4_structured_handover_preview_content(self):
        """Task 4: Structured handover preview contains symptom, confirmation, observations, sources, technician findings, unresolved questions, escalation reason."""
        inc = Incident(
            incident_id="INC-304",
            title="S7-1200 Overheating",
            symptom="Intake sensor reads 68°C under load.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            status="investigating",
            observations=["DIAG LED flashing amber at 2Hz.", "Cabinet door latch loose."],
            technician_findings=["[CHK-01 Physical Finding]: Intake thermocouple calibrated; reads nominal."],
            evidence=[self.ev_manual],
        )
        escalation = EscalationDecision(
            escalate=True,
            reason="MISSING_REVISION",
            details="Firmware revision v4.2 required for web diagnostics.",
            action_required="Verify firmware revision on physical nameplate.",
        )

        handover = generate_handover(inc, escalation=escalation)

        # Verify all required structured components
        self.assertEqual(handover.symptom, "Intake sensor reads 68°C under load.")
        self.assertEqual(handover.equipment_model, "S7-1200 CPU 1214C")
        self.assertTrue(handover.equipment_confirmed)
        self.assertEqual(len(handover.tentative_observations), 2)
        self.assertEqual(len(handover.technician_findings), 1)
        self.assertGreaterEqual(len(handover.sources), 1)
        self.assertIn(self.ev_manual.source_id, handover.sources[0])
        self.assertGreaterEqual(len(handover.unresolved_questions), 1)
        self.assertEqual(handover.escalation.reason, "MISSING_REVISION")

        # Verify markdown text reflects all items
        md = handover.markdown_text
        self.assertIn("Intake sensor reads 68°C under load.", md)
        self.assertIn("S7-1200 CPU 1214C", md)
        self.assertIn("doc_s71200#p14#c0", md)
        self.assertIn("DIAG LED flashing amber", md)
        self.assertIn("Intake thermocouple calibrated", md)
        self.assertIn("MISSING_REVISION", md)

    def test_task5_user_review_notes_and_export_serialization(self):
        """Task 5: User reviews before saving or exporting; exportable to markdown and structured JSON."""
        inc = Incident(
            incident_id="INC-305",
            title="Conveyor Sensor Misaligned",
            symptom="Photoelectric eye flickering",
            equipment_model="Banner QS18",
            equipment_confirmed=True,
            status="investigating",
            evidence=[self.ev_manual],
            technician_findings=["Re-aligned sensor reflector bracket; signal steady."],
        )

        review_notes = "Shift 1 handoff: Sensor aligned; running batch 4 under observation for 30 minutes."
        handover = generate_handover(inc, user_review_notes=review_notes)

        self.assertEqual(handover.user_review_notes, review_notes)
        self.assertIn(review_notes, handover.markdown_text)

        # JSON Export serialization
        data = handover.to_dict()
        self.assertEqual(data["incident_id"], "INC-305")
        self.assertEqual(data["user_review_notes"], review_notes)
        self.assertEqual(len(data["technician_findings"]), 1)
        # JSON dump must succeed without circular references or serialization errors
        json_str = json.dumps(data)
        self.assertIn("Banner QS18", json_str)

    def test_task6_clear_labels_for_generated_summaries_and_synthetic_data(self):
        """Task 6: Clearly label generated summaries and synthetic incident data."""
        inc = Incident(
            incident_id="INC-306",
            title="Synthetic Benchmark Test Incident",
            symptom="Synthetic load simulation exceeded 80%",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[self.ev_manual],
        )
        handover = generate_handover(inc)

        self.assertTrue(handover.is_synthetic)
        self.assertIn("🤖 **[GENERATED SUMMARY - REQUIRES HUMAN REVIEW]**", handover.markdown_text)
        self.assertIn("🔶 **[SYNTHETIC TEST BENCHMARK DATA - NOT FOR PRODUCTION DISPATCH]**", handover.markdown_text)

    def test_task7_unreviewed_outcomes_kept_separate_and_no_implied_approval(self):
        """Task 7: Keep unreviewed outcomes separate; do not imply reviewer approval without authentication."""
        inc = Incident(
            incident_id="INC-307",
            title="Field Motor Bearing Wear",
            symptom="Vibration velocity 4.5 mm/s",
            equipment_model="WEG W22 Motor",
            equipment_confirmed=True,
            status="investigating",
            observations=["High frequency vibration hum."],
            interpretations=["Bearing inner race defect likely."],
            technician_findings=["Greased drive-end bearing; vibration dropped to 1.8 mm/s."],
            reviewed_by_engineer=None,  # No authenticated engineer
            engineer_signoff=False,
        )
        handover = generate_handover(inc)

        self.assertFalse(handover.is_reviewed)
        self.assertIn("⚠️ **[UNREVIEWED OUTCOME - NO AUTHORIZED SIGN-OFF]**", handover.markdown_text)
        self.assertIn("Authentication/authorization is not implemented", handover.review_disclaimer)
        self.assertIn("Authorization Disclaimer", handover.markdown_text)

        # Invariant: Tentative observations, system interpretations, and technician findings are strictly segregated
        self.assertTrue(all(obs.startswith("[TENTATIVE OBSERVATION]") for obs in handover.tentative_observations))
        self.assertTrue(all(i.startswith("[SYSTEM INTERPRETATION - NOT AUTHORITATIVE]") for i in handover.system_interpretations))
        self.assertTrue(all(f.startswith("[VERIFIED TECHNICIAN FINDING]") for f in handover.technician_findings))


class TestMilestone3AUI(unittest.TestCase):
    """UI integration tests using Streamlit AppTest for Phase 2 Milestone 3A."""

    def test_ui_proposed_checks_and_technician_finding_flow(self):
        """Tasks 1, 2, 3, 5: AppTest renders proposed checks, mismatch warnings, and allows recording technician findings."""
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        self.assertFalse(app.exception)

        # Index chunk into backend
        backend = app.session_state.backend
        c = Chunk(
            chunk_id="chunk_plc_check",
            document_id="doc_s71200",
            filename="s71200_sop.pdf",
            page=8,
            text="Step: Check cabinet intake fan and measure ambient airflow velocity. Isolate power before touching blades.",
            equipment_model="S7-1200 CPU 1214C",
        )
        backend.index_chunks([c])

        # Select INC-2026-001 (S7-1200 CPU 1214C)
        app.selectbox[0].select("INC-2026-001: Overheating Warning on S7-1200 CPU Module [INVESTIGATING]").run()
        self.assertFalse(app.exception)

        # Attach evidence to incident in session service
        ev = Evidence(source_id="doc_s71200#p8#c0", chunk=c)
        app.session_state.incident_service.attach_evidence("INC-2026-001", [ev])
        app.run()
        self.assertFalse(app.exception)

        all_markdown = " ".join([m.value for m in app.markdown])

        # Task 1: Proposed documented checks rendered with instruction and source
        self.assertIn("Proposed Documented Checks", all_markdown)
        self.assertIn("doc_s71200#p8#c0", all_markdown)

        # Task 2: Physical check disclaimer rendered
        self.assertIn("Physical Check Disclaimer", all_markdown)

        # Record a technician finding
        finding_inputs = [t for t in app.text_input if "finding for chk-01" in getattr(t, "label", "").lower()]
        self.assertGreaterEqual(len(finding_inputs), 1)
        finding_inputs[0].set_value("Airflow measured at 1.8 m/s; fan spins freely.")

        save_finding_btns = [b for b in app.button if "Save Finding" in getattr(b, "label", "")]
        self.assertGreaterEqual(len(save_finding_btns), 1)
        save_finding_btns[0].click().run()
        self.assertFalse(app.exception)

        # Verify technician finding was persisted to incident
        inc = app.session_state.incident_service.get_incident("INC-2026-001")
        self.assertGreaterEqual(len(inc.technician_findings), 1)
        self.assertIn("Airflow measured at 1.8 m/s", inc.technician_findings[0])

        # Tasks 4, 5, 6, 7: Shift handover preview rendered with export buttons
        all_md_after = " ".join([m.value for m in app.markdown])
        self.assertIn("GENERATED SUMMARY - REQUIRES HUMAN REVIEW", all_md_after)
        self.assertIn("UNREVIEWED OUTCOME - NO AUTHORITATIVE SIGN-OFF", all_md_after)

        # Verify export download buttons exist
        download_btns = app.get("download_button")
        self.assertEqual(len(download_btns), 2)

        # Verify save handover button exists in buttons
        save_handover_btns = [b for b in app.button if "Save Handover to Incident" in getattr(b, "label", "")]
        self.assertEqual(len(save_handover_btns), 1)


if __name__ == "__main__":
    unittest.main()
