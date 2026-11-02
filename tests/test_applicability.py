"""Unit tests for Phase 2 Milestone 3B: Applicability, Contradiction Detection, Escalation, and Handover Governance."""

import unittest
from contracts import Chunk, Evidence
from src.incidents.schema import Incident
from backend.applicability import (
    ProposedCheck,
    EscalationDecision,
    validate_equipment_applicability,
    detect_contradictions,
    validate_proposed_checks,
    evaluate_incident_applicability,
)
from backend.handover import (
    HandoverReport,
    generate_handover,
    promote_incident_to_knowledge_chunk,
)


class TestApplicabilityAndEscalation(unittest.TestCase):
    """Tests for equipment metadata validation, contradictions, and escalation."""

    def setUp(self):
        self.chunk_s7_1200 = Chunk(
            chunk_id="chunk_s7_1200_01",
            document_id="doc_s71200_manual",
            filename="s71200_manual.pdf",
            page=12,
            text="Siemens S7-1200 CPU 1214C diagnostic instructions. DIAG LED blinks amber on overtemperature.",
            equipment_model="S7-1200 CPU 1214C",
        )
        self.ev_s7_1200 = Evidence(source_id="doc_s71200_manual#p12#c0", chunk=self.chunk_s7_1200)

        self.chunk_s7_1500 = Chunk(
            chunk_id="chunk_s7_1500_01",
            document_id="doc_s71500_manual",
            filename="s71500_manual.pdf",
            page=45,
            text="Siemens S7-1500 CPU 1516 system manual. Diagnostic buffer error logging instructions.",
            equipment_model="S7-1500 CPU 1516",
        )
        self.ev_s7_1500 = Evidence(source_id="doc_s71500_manual#p45#c0", chunk=self.chunk_s7_1500)

    def test_absent_evidence_escalates(self):
        """No documentary evidence attached -> escalates with reason ABSENT_EVIDENCE."""
        inc = Incident(
            incident_id="INC-001",
            title="Overheating Inverter",
            symptom="Inverter heatsink reads 92C.",
            equipment_model="Micromaster 440",
            equipment_confirmed=True,
            evidence=[],
        )
        decision = evaluate_incident_applicability(inc)
        self.assertTrue(decision.escalate)
        self.assertEqual(decision.reason, "ABSENT_EVIDENCE")
        self.assertIn("No documentary evidence", decision.details)

    def test_unknown_equipment_escalates(self):
        """Target equipment model is unknown (None) -> escalates with reason UNKNOWN_EQUIPMENT."""
        inc = Incident(
            incident_id="INC-002",
            title="Line Trip",
            symptom="Breaker tripped during stage 2 compression.",
            equipment_model=None,
            equipment_confirmed=False,
            evidence=[self.ev_s7_1200],
        )
        decision = evaluate_incident_applicability(inc)
        self.assertTrue(decision.escalate)
        self.assertEqual(decision.reason, "UNKNOWN_EQUIPMENT")
        self.assertIn("Target equipment identity is unknown", decision.details)

    def test_equipment_mismatch_escalates(self):
        """Target equipment does not match retrieved document metadata -> escalates with EQUIPMENT_MISMATCH."""
        inc = Incident(
            incident_id="INC-003",
            title="PLC Diagnostic Fault",
            symptom="CPU fault LED active.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[self.ev_s7_1500],  # Document applies to S7-1500!
        )
        decision = evaluate_incident_applicability(inc)
        self.assertTrue(decision.escalate)
        self.assertEqual(decision.reason, "EQUIPMENT_MISMATCH")
        self.assertIn("does not match retrieved document equipment model", decision.details)
        self.assertIn(self.ev_s7_1500.source_id, decision.blocking_sources)

    def test_missing_revision_escalates(self):
        """Retrieved document specifies firmware revision, but target has none or mismatch -> escalates with MISSING_REVISION."""
        chunk_with_rev = Chunk(
            chunk_id="chunk_rev_01",
            document_id="doc_firmware",
            filename="firmware_guide.pdf",
            page=2,
            text="For S7-1200 CPU 1214C with Firmware v4.2 or higher, verify Web Server certificate.",
            equipment_model="S7-1200 CPU 1214C",
        )
        ev_rev = Evidence(source_id="doc_firmware#p2#c0", chunk=chunk_with_rev)

        # Target lacks revision
        inc_no_rev = Incident(
            incident_id="INC-004",
            title="Web Server TLS Error",
            symptom="Cannot access web server.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            firmware_revision=None,
            evidence=[ev_rev],
        )
        dec_no_rev = evaluate_incident_applicability(inc_no_rev)
        self.assertTrue(dec_no_rev.escalate)
        self.assertEqual(dec_no_rev.reason, "MISSING_REVISION")
        self.assertIn("specifies revision requirement '4.2'", dec_no_rev.details)

        # Target has incompatible revision
        inc_wrong_rev = Incident(
            incident_id="INC-005",
            title="Web Server TLS Error",
            symptom="Cannot access web server.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            firmware_revision="v2.1",
            evidence=[ev_rev],
        )
        dec_wrong_rev = evaluate_incident_applicability(inc_wrong_rev)
        self.assertTrue(dec_wrong_rev.escalate)
        self.assertEqual(dec_wrong_rev.reason, "MISSING_REVISION")
        self.assertIn("Revision mismatch", dec_wrong_rev.details)

    def test_contradictory_sources_torque_detected_and_escalated(self):
        """Retrieved chunks with conflicting torque values -> escalates with CONTRADICTORY_INSTRUCTIONS."""
        chunk_torque_45 = Chunk(
            chunk_id="chunk_t45",
            document_id="doc_sop_old",
            filename="sop_rev1.pdf",
            page=5,
            text="S7-1200 CPU 1214C terminal block installation. Torque flange bolts to 45 Nm.",
            equipment_model="S7-1200 CPU 1214C",
        )
        chunk_torque_65 = Chunk(
            chunk_id="chunk_t65",
            document_id="doc_sop_new",
            filename="sop_rev2.pdf",
            page=5,
            text="S7-1200 CPU 1214C terminal block installation. Torque flange bolts to 65 Nm.",
            equipment_model="S7-1200 CPU 1214C",
        )
        ev_45 = Evidence(source_id="doc_sop_old#p5#c0", chunk=chunk_torque_45)
        ev_65 = Evidence(source_id="doc_sop_new#p5#c0", chunk=chunk_torque_65)

        inc = Incident(
            incident_id="INC-006",
            title="Terminal Block Reassembly",
            symptom="Need reassembly torque spec.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[ev_45, ev_65],
        )
        decision = evaluate_incident_applicability(inc)
        self.assertTrue(decision.escalate)
        self.assertEqual(decision.reason, "CONTRADICTORY_INSTRUCTIONS")
        self.assertIn("Contradictory Torque specification detected", decision.details)
        self.assertIn("Silent resolution is prohibited", decision.details)
        self.assertIn(ev_45.source_id, decision.blocking_sources)
        self.assertIn(ev_65.source_id, decision.blocking_sources)

    def test_contradictory_sources_rotation_detected(self):
        """Retrieved chunks with opposing rotational directions -> contradiction detected."""
        chunk_cw = Chunk(
            chunk_id="c_cw",
            document_id="doc_valve_a",
            filename="manual_a.pdf",
            page=1,
            text="Emergency isolation: turn valve clockwise to shut off supply.",
        )
        chunk_ccw = Chunk(
            chunk_id="c_ccw",
            document_id="doc_valve_b",
            filename="manual_b.pdf",
            page=1,
            text="Emergency isolation: turn valve counter-clockwise to vent pressure.",
        )
        ev_cw = Evidence(source_id="doc_valve_a#p1#c0", chunk=chunk_cw)
        ev_ccw = Evidence(source_id="doc_valve_b#p1#c0", chunk=chunk_ccw)

        contradictions = detect_contradictions([ev_cw, ev_ccw])
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0]["type"], "Rotational direction directive")

    def test_invalid_evidence_id_in_proposed_check_escalates(self):
        """Proposed check referencing an evidence ID that does not belong to the incident -> escalates with INVALID_EVIDENCE_REFERENCE."""
        inc = Incident(
            incident_id="INC-007",
            title="Diagnostic Check",
            symptom="Overheat",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[self.ev_s7_1200],
        )
        foreign_check = ProposedCheck(
            check_id="CHK-01",
            step_number=1,
            instruction="Measure rack inlet airflow.",
            evidence_ids=["foreign_doc_id#p99#c0"],  # Not in inc.evidence!
        )
        decision = evaluate_incident_applicability(inc, proposed_checks=[foreign_check])
        self.assertTrue(decision.escalate)
        self.assertEqual(decision.reason, "INVALID_EVIDENCE_REFERENCE")
        self.assertIn("foreign_doc_id#p99#c0", decision.details)

    def test_confirmed_applicable_incident_passes(self):
        """Incident with matching equipment, matching revision, and valid checks -> CONFIRMED_APPLICABLE."""
        inc = Incident(
            incident_id="INC-008",
            title="Overheating S7-1200",
            symptom="Rack temperature high.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[self.ev_s7_1200],
        )
        valid_check = ProposedCheck(
            check_id="CHK-01",
            step_number=1,
            instruction="Inspect CPU DIAG LED status.",
            evidence_ids=[self.ev_s7_1200.source_id],
        )
        decision = evaluate_incident_applicability(inc, proposed_checks=[valid_check])
        self.assertFalse(decision.escalate)
        self.assertEqual(decision.reason, "CONFIRMED_APPLICABLE")


class TestHandoverAndKnowledgeGuard(unittest.TestCase):
    """Tests for shift handover completeness, observation separation, and knowledge promotion guards."""

    def test_incomplete_handover_reports_missing_fields(self):
        """Mitigated incident missing technician findings and confirmed model -> handover marked incomplete."""
        inc = Incident(
            incident_id="INC-009",
            title="Interlock Trip",
            symptom="Emergency stop contact welded.",
            equipment_model=None,
            equipment_confirmed=False,
            status="mitigated",
            technician_findings=[],  # Empty!
        )
        handover = generate_handover(inc)
        self.assertFalse(handover.is_complete)
        self.assertIn("technician_findings", handover.missing_fields)
        self.assertIn("confirmed_equipment_model", handover.missing_fields)

    def test_observations_interpretations_findings_kept_distinct(self):
        """Observations, system interpretations, and technician findings must be strictly separated."""
        inc = Incident(
            incident_id="INC-010",
            title="Compressor Seal Leak",
            symptom="Oil film on cylinder head.",
            equipment_model="Atlas Copco GA37",
            equipment_confirmed=True,
            status="investigating",
            observations=["Oil sheen on cooling fin 3.", "Slight burning smell."],
            interpretations=["Possible gasket blowout due to high discharge temperature."],
            technician_findings=["Gasket intact; leak originated from loose oil return fitting."],
        )
        handover = generate_handover(inc)
        self.assertEqual(len(handover.tentative_observations), 2)
        self.assertTrue(all(obs.startswith("[TENTATIVE OBSERVATION]") for obs in handover.tentative_observations))

        self.assertEqual(len(handover.system_interpretations), 1)
        self.assertTrue(all(i.startswith("[SYSTEM INTERPRETATION - NOT AUTHORITATIVE]") for i in handover.system_interpretations))

        self.assertEqual(len(handover.technician_findings), 1)
        self.assertTrue(all(f.startswith("[VERIFIED TECHNICIAN FINDING]") for f in handover.technician_findings))

    def test_unreviewed_incident_blocked_from_knowledge_promotion(self):
        """Task 10: Never convert an unreviewed incident into authoritative knowledge."""
        inc = Incident(
            incident_id="INC-011",
            title="Solved Mystery Leak",
            symptom="Water pipe dripping.",
            equipment_model="Chiller Unit 1",
            equipment_confirmed=True,
            status="resolved",
            technician_findings=["Replaced O-ring."],
            reviewed_by_engineer=None,  # Not reviewed!
            engineer_signoff=False,     # No sign-off!
        )
        handover = generate_handover(inc)
        self.assertFalse(handover.authoritative_knowledge_eligible)
        self.assertIn("PROMOTION BLOCKED", handover.knowledge_guard_reason)

        with self.assertRaises(PermissionError):
            promote_incident_to_knowledge_chunk(inc, handover)

    def test_signed_off_incident_promoted_to_authoritative_chunk(self):
        """Fully reviewed and signed-off resolved incident is converted to authoritative knowledge chunk."""
        inc = Incident(
            incident_id="INC-012",
            title="Infeed Alignment Procedure",
            symptom="Belt wander on drive pulley.",
            equipment_model="Dorner 2200",
            equipment_confirmed=True,
            status="resolved",
            technician_findings=["Adjusted tensioning bolt 2 turns clockwise. Tracking verified."],
            reviewed_by_engineer="Lead Engineer Mike R.",
            engineer_signoff=True,
        )
        handover = generate_handover(inc)
        self.assertTrue(handover.is_complete)
        self.assertTrue(handover.authoritative_knowledge_eligible)

        chunk = promote_incident_to_knowledge_chunk(inc, handover)
        self.assertEqual(chunk.equipment_model, "Dorner 2200")
        self.assertEqual(chunk.page, 1)
        self.assertIn("AUTHORITATIVE RESOLUTION NOTE", chunk.text)
        self.assertIn("Adjusted tensioning bolt", chunk.text)
        self.assertIn("Approved By: Lead Engineer Mike R.", chunk.text)

    def test_active_escalation_blocks_knowledge_promotion(self):
        """Even with engineer sign-off, an active unresolved escalation blocks promotion."""
        inc = Incident(
            incident_id="INC-013",
            title="Torque Spec Dispute",
            symptom="Bolts shearing.",
            equipment_model="Dorner 2200",
            equipment_confirmed=True,
            status="resolved",
            technician_findings=["Torqued to 50 Nm."],
            reviewed_by_engineer="Lead Engineer Mike R.",
            engineer_signoff=True,
        )
        escalation = EscalationDecision(
            escalate=True,
            reason="CONTRADICTORY_INSTRUCTIONS",
            details="Conflicting torque specs between manuals.",
        )
        handover = generate_handover(inc, escalation=escalation)
        self.assertFalse(handover.authoritative_knowledge_eligible)
        self.assertIn("Active escalation 'CONTRADICTORY_INSTRUCTIONS' remains unresolved", handover.knowledge_guard_reason)


if __name__ == "__main__":
    unittest.main()

