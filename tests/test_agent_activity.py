"""Unit and integration tests for Phase 2 Milestone 2A: Agent Activity, Clarification, and State Visibility.

Tests:
1. Activity panel and real tool events (tool_name, short_purpose, outcome, status).
2. Backend-supplied events; no invented activity or private chain-of-thought.
3. Clarification questions and user-response submission.
4. Resuming the SAME incident after a clarification response.
5. Concurrency guard preventing duplicate submissions while execution is active.
6. Display of all 5 states: waiting, completed, failed, cancelled, escalated.
7. Cancel / pause control supported by the backend.
8. Preservation of Phase 1 interface as a fallback.
"""

import unittest
from contracts import Chunk, Evidence
from backend.mock_backend import MockBackend
from src.incidents.schema import Incident
from src.incidents.mock_service import MockIncidentService
from src.incidents.agent_schema import (
    AgentExecution,
    ClarificationRequest,
    ToolEvent,
    VALID_EXECUTION_STATES,
    VALID_EVENT_STATUSES,
)
from backend.agent import AgentExecutor


class TestAgentDataContracts(unittest.TestCase):
    """Tests for ToolEvent, ClarificationRequest, and AgentExecution schema invariants."""

    def test_valid_tool_event(self):
        evt = ToolEvent(
            event_id="EVT-01",
            tool_name="retrieve_evidence",
            short_purpose="Query local vector index for diagnostic procedures",
            outcome="Retrieved 2 chunks",
            status="completed",
        )
        self.assertEqual(evt.event_id, "EVT-01")
        self.assertEqual(evt.tool_name, "retrieve_evidence")
        self.assertEqual(evt.status, "completed")
        self.assertIsNotNone(evt.timestamp)

    def test_tool_event_validation(self):
        # Empty tool_name
        with self.assertRaises(ValueError):
            ToolEvent(event_id="EVT-02", tool_name="  ", short_purpose="Check")

        # Empty short_purpose
        with self.assertRaises(ValueError):
            ToolEvent(event_id="EVT-03", tool_name="my_tool", short_purpose="")

        # Invalid status
        with self.assertRaises(ValueError):
            ToolEvent(
                event_id="EVT-04",
                tool_name="my_tool",
                short_purpose="Check",
                status="invalid_status",
            )

    def test_valid_clarification_request(self):
        clarif = ClarificationRequest(
            clarification_id="CLR-01",
            incident_id="INC-2026-001",
            question="Please confirm equipment model.",
            parameter="equipment_model",
            options=["S7-1200", "S7-1500"],
        )
        self.assertEqual(clarif.clarification_id, "CLR-01")
        self.assertEqual(clarif.status, "pending")
        self.assertIsNone(clarif.response)

    def test_clarification_request_validation(self):
        with self.assertRaises(ValueError):
            ClarificationRequest(
                clarification_id="CLR-02",
                incident_id="INC-01",
                question="",
                parameter="equipment_model",
            )

    def test_agent_execution_invariants(self):
        exec_obj = AgentExecution(
            execution_id="EXEC-01",
            incident_id="INC-01",
            query="Overheating diagnostic",
            state="running",
        )
        self.assertEqual(exec_obj.state, "running")
        self.assertEqual(len(exec_obj.events), 0)

        # Invalid state
        with self.assertRaises(ValueError):
            AgentExecution(
                execution_id="EXEC-02",
                incident_id="INC-01",
                query="Query",
                state="non_existent_state",
            )


class TestAgentExecutionLifecycle(unittest.TestCase):
    """Tests for agent investigation lifecycle, real tool calls, and state transitions."""

    def setUp(self):
        self.backend = MockBackend(collection_name="test_agent_collection")
        # Seed test documents
        c1 = Chunk(
            chunk_id="chunk_s7_01",
            document_id="doc_s71200",
            filename="s71200_manual.pdf",
            page=10,
            text="Siemens S7-1200 CPU 1214C overheating procedure: Check cabinet airflow and fan operation.",
            equipment_model="S7-1200 CPU 1214C",
        )
        self.backend.index_chunks([c1])

        self.service = MockIncidentService(populate_defaults=False)
        self.executor = AgentExecutor(backend=self.backend, incident_service=self.service)

    def test_real_tool_events_completed_workflow(self):
        """When equipment is already confirmed, execution proceeds through real tools to 'completed'."""
        inc = self.service.create_incident(
            title="S7-1200 CPU Overheating",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
        )

        execution = self.executor.start_investigation(inc.incident_id)

        # Invariant: execution completes successfully
        self.assertEqual(execution.state, "completed")
        self.assertIsNotNone(execution.answer)

        # Task 1 & 2: Real tool events supplied by backend; no invented activity
        tool_names = [e.tool_name for e in execution.events]
        self.assertIn("retrieve_evidence", tool_names)
        self.assertIn("validate_applicability", tool_names)
        self.assertIn("synthesize_guidance", tool_names)

        # All events have structured action, short purpose, outcome, status
        for evt in execution.events:
            self.assertTrue(bool(evt.tool_name.strip()))
            self.assertTrue(bool(evt.short_purpose.strip()))
            self.assertTrue(bool(evt.outcome.strip()))
            self.assertIn(evt.status, VALID_EVENT_STATUSES)

    def test_unconfirmed_equipment_triggers_waiting_and_clarification(self):
        """Task 3: When equipment is unconfirmed, agent pauses in 'waiting' state with clarification question."""
        inc = self.service.create_incident(
            title="Unidentified Unit Alarm",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model=None,
            equipment_confirmed=False,
        )

        execution = self.executor.start_investigation(inc.incident_id)

        # Task 6: Display 'waiting' state
        self.assertEqual(execution.state, "waiting")
        self.assertIsNotNone(execution.clarification)
        self.assertEqual(execution.clarification.status, "pending")
        self.assertEqual(execution.clarification.parameter, "equipment_model")
        self.assertIn("confirm", execution.clarification.question.lower())

        # Waiting tool event
        waiting_events = [e for e in execution.events if e.status == "waiting"]
        self.assertEqual(len(waiting_events), 1)
        self.assertEqual(waiting_events[0].tool_name, "validate_applicability")

    def test_resume_same_incident_after_clarification(self):
        """Task 4: Operator answers clarification; execution resumes on the SAME incident."""
        inc = self.service.create_incident(
            title="Hydraulic Pressure Warning",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model=None,
            equipment_confirmed=False,
        )
        orig_incident_id = inc.incident_id

        # Start -> enters waiting
        execution = self.executor.start_investigation(orig_incident_id)
        self.assertEqual(execution.state, "waiting")

        # Resume with operator clarification
        confirmed_model = "S7-1200 CPU 1214C"
        resumed_exec = self.executor.resume_investigation(
            execution_id=execution.execution_id,
            user_response=confirmed_model,
        )

        # Invariant: Resumed on the SAME incident
        self.assertEqual(resumed_exec.incident_id, orig_incident_id)
        self.assertEqual(resumed_exec.state, "completed")
        self.assertEqual(resumed_exec.clarification.status, "answered")
        self.assertEqual(resumed_exec.clarification.response, confirmed_model)

        # Check incident was updated in-place without duplicating
        updated_inc = self.service.get_incident(orig_incident_id)
        self.assertEqual(updated_inc.equipment_model, confirmed_model)
        self.assertTrue(updated_inc.equipment_confirmed)

        # Event stream contains apply_clarification tool event
        tool_names = [e.tool_name for e in resumed_exec.events]
        self.assertIn("apply_clarification", tool_names)
        self.assertIn("synthesize_guidance", tool_names)

    def test_duplicate_submission_prevention(self):
        """Task 5: Prevent duplicate submissions while execution is active or after already answered."""
        inc = self.service.create_incident(
            title="Bearing Temperature",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model=None,
            equipment_confirmed=False,
        )

        execution = self.executor.start_investigation(inc.incident_id)
        self.assertEqual(execution.state, "waiting")

        # Attempting to start another investigation on the same active incident is blocked
        with self.assertRaises(RuntimeError) as ctx:
            self.executor.start_investigation(inc.incident_id)
        self.assertIn("already active", str(ctx.exception))

        # Successfully resume once
        self.executor.resume_investigation(execution.execution_id, "S7-1200 CPU 1214C")
        self.assertEqual(execution.state, "completed")

        # Attempting to resume again is blocked
        with self.assertRaises(ValueError) as ctx:
            self.executor.resume_investigation(execution.execution_id, "S7-1200 CPU 1214C")
        self.assertIn("not awaiting clarification", str(ctx.exception))

    def test_cancel_control(self):
        """Task 7: Cancel / pause control transitions state to 'cancelled' and halts actions."""
        inc = self.service.create_incident(
            title="Pump Cavitation",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model=None,
            equipment_confirmed=False,
        )

        execution = self.executor.start_investigation(inc.incident_id)
        self.assertEqual(execution.state, "waiting")

        # Cancel the execution
        cancelled_exec = self.executor.cancel_execution(execution.execution_id)

        self.assertEqual(cancelled_exec.state, "cancelled")
        # Tool events updated to cancelled
        cancel_events = [e for e in cancelled_exec.events if e.tool_name == "cancel_investigation"]
        self.assertEqual(len(cancel_events), 1)
        self.assertEqual(cancel_events[0].status, "cancelled")

    def test_escalated_state_on_equipment_mismatch(self):
        """Task 6: Display 'escalated' state when applicability rules detect mismatch."""
        inc = self.service.create_incident(
            title="S7-1500 Controller Diagnostic",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model="S7-1500 CPU 1516",  # Does NOT match S7-1200 chunk!
            equipment_confirmed=True,
        )

        execution = self.executor.start_investigation(inc.incident_id)

        self.assertEqual(execution.state, "escalated")
        self.assertIsNotNone(execution.escalation)
        self.assertTrue(execution.escalation.escalate)
        self.assertEqual(execution.escalation.reason, "EQUIPMENT_MISMATCH")

        # Tool event reflected as escalated
        escalated_events = [e for e in execution.events if e.status == "escalated"]
        self.assertGreaterEqual(len(escalated_events), 1)

    def test_backend_direct_integration(self):
        """Backend service exposes start_investigation, resume_investigation, cancel_execution directly."""
        inc = self.service.create_incident(
            title="Integrated Test Incident",
            symptom="Siemens S7-1200 CPU 1214C overheating procedure",
            equipment_model="S7-1200 CPU 1214C",
            equipment_confirmed=True,
        )

        # Call via backend method
        exec_res = self.backend.start_investigation(
            incident_id=inc.incident_id,
            incident_service=self.service,
        )
        self.assertEqual(exec_res.state, "completed")

        fetched = self.backend.get_execution(exec_res.execution_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.execution_id, exec_res.execution_id)


class TestAgentActivityUI(unittest.TestCase):
    """UI integration tests using Streamlit AppTest for Phase 2 Milestone 2A."""

    def test_ui_phase1_fallback_chat(self):
        """Task 8: Preserve working Phase 1 chat interface as fallback."""
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        self.assertFalse(app.exception)
        # Phase 1 chat input operates normally
        app.chat_input[0].set_value("What is the nominal operating pressure?").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)

    def test_ui_incident_selection_and_agent_execution(self):
        """Tasks 1, 2, 6: Select incident, run investigation, view activity panel with backend events."""
        from streamlit.testing.v1 import AppTest
        from contracts import Chunk

        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        self.assertFalse(app.exception)

        # Index chunk into backend
        backend = app.session_state.backend
        c = Chunk(
            chunk_id="chunk_plc_diag",
            document_id="doc_plc",
            filename="s71200_manual.pdf",
            page=4,
            text="PLC rack temperature sensor reads 68°C. Amber DIAG LED indicates overtemperature threshold.",
            equipment_model="S7-1200 CPU 1214C",
        )
        backend.index_chunks([c])

        # Select INC-2026-001 (has confirmed equipment model)
        app.selectbox[0].select("INC-2026-001: Overheating Warning on S7-1200 CPU Module [INVESTIGATING]").run()
        self.assertFalse(app.exception)

        # Find and click "Run Automated Agent Investigation" button
        agent_btn = None
        for btn in app.button:
            if "Run Automated Agent Investigation" in getattr(btn, "label", ""):
                agent_btn = btn
                break
        self.assertIsNotNone(agent_btn, "Agent investigation button should be present in UI")
        agent_btn.click().run()
        self.assertFalse(app.exception)

        # Check that execution was created and rendered
        self.assertIn("active_execution_INC-2026-001", app.session_state)
        exec_obj = app.session_state["active_execution_INC-2026-001"]
        self.assertIsNotNone(exec_obj)
        self.assertEqual(exec_obj.state, "completed")
        self.assertGreaterEqual(len(exec_obj.events), 3)

        # Verify real backend tool events are rendered in UI markdown
        all_markdown = " ".join([m.value for m in app.markdown])
        self.assertIn("retrieve_evidence", all_markdown)
        self.assertIn("validate_applicability", all_markdown)
        self.assertIn("synthesize_guidance", all_markdown)
        self.assertIn("EXECUTION COMPLETED", all_markdown)

    def test_ui_clarification_and_resume_same_incident(self):
        """Tasks 3, 4, 5: Clarification requested on unconfirmed equipment, operator submits, resumes same incident."""
        from streamlit.testing.v1 import AppTest
        from contracts import Chunk

        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        self.assertFalse(app.exception)

        backend = app.session_state.backend
        c = Chunk(
            chunk_id="chunk_hydr_diag",
            document_id="doc_hydr",
            filename="hydraulic_manual.pdf",
            page=2,
            text="Line pressure dropped to 35 bar. Low pressure interlock tripped.",
            equipment_model="Rexroth A10VSO",
        )
        backend.index_chunks([c])

        # Select INC-2026-002 (unconfirmed equipment)
        app.selectbox[0].select("INC-2026-002: Hydraulic Infeed Pressure Drop [OPEN]").run()
        self.assertFalse(app.exception)

        # Click run agent investigation
        agent_btn = [b for b in app.button if "Run Automated Agent Investigation" in getattr(b, "label", "")][0]
        agent_btn.click().run()
        self.assertFalse(app.exception)

        self.assertIn("active_execution_INC-2026-002", app.session_state)
        exec_obj = app.session_state["active_execution_INC-2026-002"]
        self.assertIsNotNone(exec_obj)
        self.assertEqual(exec_obj.state, "waiting")
        self.assertIsNotNone(exec_obj.clarification)

        all_markdown = " ".join([m.value for m in app.markdown])
        self.assertIn("WAITING FOR OPERATOR CLARIFICATION", all_markdown)
        self.assertIn("Operator Clarification Required", all_markdown)

        # Submit clarification response
        resume_btn = [b for b in app.button if "Submit Clarification & Resume" in getattr(b, "label", "")][0]
        # Set text input value
        text_inputs = [t for t in app.text_input if "confirm equipment_model" in getattr(t, "label", "").lower() or "enter or confirm" in getattr(t, "label", "").lower()]
        self.assertGreaterEqual(len(text_inputs), 1)
        text_inputs[0].set_value("Rexroth A10VSO")
        resume_btn.click().run()
        self.assertFalse(app.exception)

        # Verify execution resumed on the SAME incident without duplication
        self.assertIn("active_execution_INC-2026-002", app.session_state)
        updated_exec = app.session_state["active_execution_INC-2026-002"]
        self.assertIsNotNone(updated_exec)
        self.assertEqual(updated_exec.incident_id, "INC-2026-002")
        self.assertEqual(updated_exec.state, "completed")

        # Verify incident record in session service has confirmed model
        inc = app.session_state.incident_service.get_incident("INC-2026-002")
        self.assertEqual(inc.equipment_model, "Rexroth A10VSO")
        self.assertTrue(inc.equipment_confirmed)

