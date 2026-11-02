"""Unit and integration tests for Phase 2 Milestone 2B: Bounded Local Tool Orchestrator."""

import json
import unittest
import urllib.request
from typing import Any

from contracts import Chunk, Evidence
from src.incidents.schema import Incident
from backend.mock_backend import MockBackend
from backend.tools.registry import ToolRegistry
from backend.orchestrator.schema import (
    ALLOWED_ACTIONS,
    ActionSelection,
    OrchestratorEvent,
    OrchestratorResult,
)
from backend.orchestrator.coordinator import BoundedOrchestrator, ORCHESTRATOR_SYSTEM_PROMPT


class TestOrchestratorUnit(unittest.TestCase):
    """Unit tests for bounded orchestrator safety guards, allowlists, and loop bounds."""

    def setUp(self):
        self.backend = MockBackend()
        self.registry = ToolRegistry(self.backend)

        # Base test incident
        valid_chunk = Chunk(
            chunk_id="chunk_a10vso",
            document_id="doc_a10vso_manual",
            filename="a10vso_manual.pdf",
            page=4,
            text="Rexroth A10VSO axial piston pump operating limits and thermal overload instructions.",
            equipment_model="Rexroth A10VSO",
        )
        self.incident = Incident(
            incident_id="INC-TEST-001",
            title="Overheating Hydraulic Pump",
            symptom="Pump temperature exceeds 80°C threshold.",
            equipment_model="Rexroth A10VSO",
            equipment_confirmed=True,
            evidence=[Evidence(source_id="doc_a10vso_manual#p4#c0", chunk=valid_chunk)],
        )

    def test_invalid_tool_action_rejected(self):
        """Action not in explicit allowlist is rejected and triggers parse failure."""
        bad_calls = ['{"action": "rm_rf_system", "parameters": {}, "rationale": "exploit"}']

        def mock_caller(messages):
            return bad_calls.pop(0) if bad_calls else '{"action": "ask_user", "parameters": {"question": "ok"}}'

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=3,
            max_parse_retries=0,
            model_caller=mock_caller,
        )
        res = orchestrator.run_investigation(self.incident)
        self.assertEqual(res.status, "PARSE_ERROR")
        self.assertTrue(any(e.event_type == "parse_failure" for e in res.events))

    def test_malformed_json_triggers_bounded_retry(self):
        """Malformed JSON output retries up to max_parse_retries and aborts safely if invalid."""
        malformed_outputs = [
            "This is not JSON at all",
            "{broken json without closing",
            "Still broken",
        ]

        def mock_caller(messages):
            return malformed_outputs.pop(0) if malformed_outputs else "{}"

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=3,
            max_parse_retries=2,
            model_caller=mock_caller,
        )
        res = orchestrator.run_investigation(self.incident)
        self.assertEqual(res.status, "PARSE_ERROR")

    def test_repeated_action_detection_aborts_loop(self):
        """Consecutive identical tool invocations with identical parameters are aborted."""
        repeated_output = json.dumps({
            "action": "search_documents",
            "parameters": {"query": "pump temperature", "top_k": 3},
            "rationale": "Searching for pump temperature SOP.",
        })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=5,
            model_caller=lambda msgs: repeated_output,
        )
        res = orchestrator.run_investigation(self.incident)
        self.assertEqual(res.status, "REPEATED_ACTION_ABORT")
        self.assertTrue(any(e.event_type == "repeated_action_aborted" for e in res.events))

    def test_max_steps_exceeded(self):
        """Bounded loop terminates when max_steps is reached."""
        step_counter = 0

        def alternating_caller(messages):
            nonlocal step_counter
            step_counter += 1
            return json.dumps({
                "action": "search_documents",
                "parameters": {"query": f"search query step {step_counter}"},
                "rationale": f"Executing step {step_counter}",
            })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=3,
            model_caller=alternating_caller,
        )
        res = orchestrator.run_investigation(self.incident)
        self.assertEqual(res.status, "MAX_STEPS_EXCEEDED")
        self.assertEqual(res.steps_executed, 3)

    def test_ask_user_pauses_investigation(self):
        """Calling ask_user pauses orchestrator and returns PAUSED_FOR_USER."""
        output = json.dumps({
            "action": "ask_user",
            "parameters": {
                "question": "Is the inlet pressure gauge reading above 2 bar?",
                "options": ["Yes", "No", "Gauge broken"],
            },
            "rationale": "Need operator verification of suction line pressure.",
        })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=5,
            model_caller=lambda msgs: output,
        )
        res = orchestrator.run_investigation(self.incident)
        self.assertEqual(res.status, "PAUSED_FOR_USER")
        self.assertTrue(any(e.event_type == "clarification_request" for e in res.events))

    def test_resume_investigation_integrates_user_response(self):
        """Resuming incorporates clarification response and continues without re-running past steps."""
        step_outputs = [
            # Step 1: pause for user
            json.dumps({
                "action": "ask_user",
                "parameters": {"question": "Confirm valve position?"},
                "rationale": "Clarification needed",
            }),
            # Step 2 (after resume): finish with guidance
            json.dumps({
                "action": "finish",
                "parameters": {"guidance": "Valve confirmed open. Proceed with flush."},
                "rationale": "Procedure completed",
            }),
        ]

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=5,
            model_caller=lambda msgs: step_outputs.pop(0),
        )

        # Initial run: pauses
        res1 = orchestrator.run_investigation(self.incident)
        self.assertEqual(res1.status, "PAUSED_FOR_USER")

        # Resume with user answer
        res2 = orchestrator.resume_investigation(
            incident=self.incident,
            user_response="Valve is confirmed 100% OPEN.",
            past_events=res1.events,
        )
        self.assertEqual(res2.status, "COMPLETED")
        self.assertIn("Valve confirmed open", res2.final_answer)
        self.assertTrue(any(e.event_type == "user_clarification_received" for e in res2.events))

    def test_deterministic_guard_prevents_unconfirmed_finish(self):
        """Hard constraint: Attempting to 'finish' with unconfirmed equipment is overridden to 'ask_user'."""
        unconfirmed_inc = Incident(
            incident_id="INC-UNCONFIRMED",
            title="Mysterious Noise",
            symptom="Whining sound from drive train.",
            equipment_model=None,
            equipment_confirmed=False,
        )

        finish_output = json.dumps({
            "action": "finish",
            "parameters": {"guidance": "Tighten drive belt to 40 Nm."},
            "rationale": "Assumed generic belt drive.",
        })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=3,
            model_caller=lambda msgs: finish_output,
        )
        res = orchestrator.run_investigation(unconfirmed_inc)
        # Deterministic guard must intercept finish and pause for user!
        self.assertEqual(res.status, "PAUSED_FOR_USER")
        self.assertTrue(any(e.action == "ask_user" for e in res.events))

    def test_deterministic_guard_escalates_on_equipment_mismatch(self):
        """Model attempts to finish with mismatched equipment -> deterministic guard escalates with EQUIPMENT_MISMATCH."""
        mismatched_chunk = Chunk(
            chunk_id="chunk_1500",
            document_id="doc_s71500",
            filename="s71500.pdf",
            page=1,
            text="S7-1500 CPU 1516 instructions.",
            equipment_model="S7-1500 CPU 1516",
        )
        ev_mismatch = Evidence(source_id="doc_s71500#p1#c0", chunk=mismatched_chunk)
        inc = Incident(
            incident_id="INC-MISMATCH",
            title="CPU Alarm",
            symptom="Overtemp",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
            evidence=[ev_mismatch],
        )

        finish_output = json.dumps({
            "action": "finish",
            "parameters": {"guidance": "Reset CPU breaker."},
            "rationale": "Done",
        })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=2,
            model_caller=lambda msgs: finish_output,
        )
        res = orchestrator.run_investigation(inc)
        self.assertEqual(res.status, "ESCALATED")
        self.assertEqual(res.escalation.reason, "EQUIPMENT_MISMATCH")
        self.assertIsNotNone(res.handover)

    def test_deterministic_guard_escalates_on_contradictory_sources(self):
        """Model attempts to finish with contradictory torque instructions -> escalates with CONTRADICTORY_INSTRUCTIONS."""
        ev_t45 = Evidence(
            source_id="doc_a#p1#c0",
            chunk=Chunk("c1", "doc_a", "a.pdf", 1, "Torque bolts to 45 Nm.", equipment_model="Rexroth A10VSO"),
        )
        ev_t65 = Evidence(
            source_id="doc_b#p1#c0",
            chunk=Chunk("c2", "doc_b", "b.pdf", 1, "Torque bolts to 65 Nm.", equipment_model="Rexroth A10VSO"),
        )
        inc = Incident(
            incident_id="INC-CONTRADICT",
            title="Flange Mount",
            symptom="Mounting pump",
            equipment_model="Rexroth A10VSO",
            equipment_confirmed=True,
            evidence=[ev_t45, ev_t65],
        )

        finish_output = json.dumps({
            "action": "finish",
            "parameters": {"guidance": "Torque to 45 Nm."},
            "rationale": "Chose doc A arbitrarily",
        })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=2,
            model_caller=lambda msgs: finish_output,
        )
        res = orchestrator.run_investigation(inc)
        self.assertEqual(res.status, "ESCALATED")
        self.assertEqual(res.escalation.reason, "CONTRADICTORY_INSTRUCTIONS")

    def test_deterministic_guard_escalates_on_invalid_evidence_id(self):
        """Model attempts to finish citing evidence ID not in incident -> escalates with INVALID_EVIDENCE_REFERENCE."""
        valid_ev = Evidence(
            source_id="doc_valid#p1#c0",
            chunk=Chunk("c1", "doc_valid", "v.pdf", 1, "Valid pump SOP text.", equipment_model="Rexroth A10VSO"),
        )
        inc = Incident(
            incident_id="INC-INVALID-REF",
            title="Pump Check",
            symptom="Check pressure",
            equipment_model="Rexroth A10VSO",
            equipment_confirmed=True,
            evidence=[valid_ev],
        )

        finish_with_fake_id = json.dumps({
            "action": "finish",
            "parameters": {
                "guidance": "Check pump inlet.",
                "evidence_ids": ["doc_hallucinated#p99#c0"],
            },
            "rationale": "Cited hallucinated doc",
        })

        orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            max_steps=2,
            model_caller=lambda msgs: finish_with_fake_id,
        )
        res = orchestrator.run_investigation(inc)
        self.assertEqual(res.status, "ESCALATED")
        self.assertEqual(res.escalation.reason, "INVALID_EVIDENCE_REFERENCE")



class TestRealLocalModelOrchestration(unittest.TestCase):
    """Integration test against the actual local model (qwen2.5:latest).

    Acceptance:
    The real local model selects different valid actions for:
    - confirmed equipment with sufficient information;
    - unclear equipment identity requiring clarification.
    """

    @classmethod
    def setUpClass(cls):
        # Check if local Ollama daemon is reachable
        cls.ollama_available = False
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                tags = json.loads(resp.read().decode())
                models = [m.get("name", "") for m in tags.get("models", [])]
                if any("qwen2.5" in m for m in models):
                    cls.ollama_available = True
        except Exception:
            cls.ollama_available = False

    def setUp(self):
        if not self.ollama_available:
            self.skipTest("Local Ollama daemon with qwen2.5:latest is not reachable in current environment.")
        self.backend = MockBackend()
        self.registry = ToolRegistry(self.backend)
        self.orchestrator = BoundedOrchestrator(
            tool_registry=self.registry,
            model_name="qwen2.5:latest",
            ollama_base_url="http://localhost:11434",
            max_steps=2,
            tool_timeout_seconds=20.0,
        )

    def test_real_model_selects_different_actions_for_confirmed_vs_unclear(self):
        """Verifies real local model produces distinct, schema-conforming actions for distinct states."""
        # 1. Confirmed equipment with clear technical symptom
        confirmed_incident = Incident(
            incident_id="INC-CONFIRMED-01",
            title="Overheating CPU Module",
            symptom="Rack temperature reads 68C. CPU DIAG LED is blinking amber.",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
        )
        res_confirmed = self.orchestrator.run_investigation(confirmed_incident)
        action_confirmed = res_confirmed.events[0].action
        self.assertIn(action_confirmed, ALLOWED_ACTIONS)
        self.assertIn(action_confirmed, ["search_documents", "lookup_equipment"])

        # 2. Unclear equipment identity requiring clarification
        unclear_incident = Incident(
            incident_id="INC-UNCLEAR-02",
            title="Pneumatic Valve Pressure Loss",
            symptom="Supply pressure dropped to 30 bar. Unknown valve manifold.",
            equipment_model=None,
            equipment_confirmed=False,
        )
        res_unclear = self.orchestrator.run_investigation(unclear_incident)
        action_unclear = res_unclear.events[0].action
        self.assertIn(action_unclear, ALLOWED_ACTIONS)
        self.assertIn(action_unclear, ["ask_user", "escalate"])

        # 3. Assert distinct actions were chosen by the real model!
        self.assertNotEqual(
            action_confirmed,
            action_unclear,
            f"Real model must discriminate: confirmed={action_confirmed}, unclear={action_unclear}",
        )


if __name__ == "__main__":
    unittest.main()

