"""Unit and integration tests for Streamlit UI, mock backend, and session state management."""

import unittest
from pathlib import Path

from contracts import Answer, Chunk, Evidence, IndexingSummary
from src.ui.mock_backend import MockBackendService

# Check if streamlit is available for headless AppTest
try:
    import streamlit
    from streamlit.testing.v1 import AppTest

    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False


class TestMockBackend(unittest.TestCase):
    def setUp(self):
        self.backend = MockBackendService(collection_name="test_mock_collection")
        self.sample_chunk_1 = Chunk(
            chunk_id="doc_a1b2#p1#c0",
            document_id="doc_a1b2",
            filename="sop_compressor.pdf",
            page=1,
            text="Inspect pressure relief valve RV-101 prior to motor start. Verify pressure is 5.5 bar.",
            equipment_model="Compressor-X1",
            synthetic=True,
        )
        self.sample_chunk_2 = Chunk(
            chunk_id="doc_a1b2#p3#c0",
            document_id="doc_a1b2",
            filename="sop_compressor.pdf",
            page=3,
            text="Emergency shutdown procedure: Press red emergency stop button E-STOP-01 immediately.",
            equipment_model="Compressor-X1",
            synthetic=True,
        )

    def test_indexing_chunks_and_duplicates(self):
        """Indexing chunks succeeds, respects invariants, and detects duplicates."""
        summary = self.backend.index_chunks([self.sample_chunk_1, self.sample_chunk_2])
        self.assertEqual(summary.total_chunks_received, 2)
        self.assertEqual(summary.chunks_indexed, 2)
        self.assertEqual(summary.chunks_skipped, 0)
        self.assertEqual(summary.chunks_failed, 0)

        # Duplicate re-indexing should be counted in chunks_skipped
        re_summary = self.backend.index_chunks([self.sample_chunk_1])
        self.assertEqual(re_summary.total_chunks_received, 1)
        self.assertEqual(re_summary.chunks_indexed, 0)
        self.assertEqual(re_summary.chunks_skipped, 1)

    def test_retrieval_ranking_and_evidence(self):
        """Retrieval ranks relevant chunks and preserves source lineage."""
        self.backend.index_chunks([self.sample_chunk_1, self.sample_chunk_2])
        evidence = self.backend.retrieve("emergency shutdown stop button", top_k=2)

        self.assertGreater(len(evidence), 0)
        top_ev = evidence[0]
        self.assertIsInstance(top_ev, Evidence)
        self.assertEqual(top_ev.chunk.page, 3)
        self.assertIn("emergency stop", top_ev.chunk.text.lower())

    def test_answer_generation_with_valid_citations(self):
        """Answer citations must strictly resolve against Answer.evidence."""
        self.backend.index_chunks([self.sample_chunk_1, self.sample_chunk_2])
        ans: Answer = self.backend.answer_question("What is the emergency shutdown procedure?")

        self.assertFalse(ans.insufficient_evidence)
        self.assertGreater(len(ans.evidence), 0)
        self.assertTrue(ans.validate_citations())
        self.assertIn("emergency", ans.text.lower())

    def test_insufficient_evidence_when_unindexed(self):
        """Empty vector store must return insufficient_evidence=True without crashing."""
        empty_backend = MockBackendService()
        ans = empty_backend.answer_question("What is the valve pressure?")
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)

    def test_insufficient_evidence_for_unanswerable_query(self):
        """Questions lacking documentary support must declare insufficient_evidence."""
        self.backend.index_chunks([self.sample_chunk_1, self.sample_chunk_2])
        ans = self.backend.answer_question("What is the cylinder head bolt torque specification?")
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)


class TestStreamlitApp(unittest.TestCase):
    def setUp(self):
        if not _HAS_STREAMLIT:
            self.skipTest("Streamlit not installed in current Python environment")

    def test_app_startup_and_mock_banner(self):
        """App initializes cleanly and renders conspicuous mock banner in default mode."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()

        self.assertFalse(app.exception)
        # Verify title and mock banner
        warning_texts = [w.value for w in app.warning]
        self.assertTrue(any("RUNNING IN MOCK BACKEND MODE" in txt for txt in warning_texts))

    def test_app_indexing_button_without_file(self):
        """Clicking Index Document without uploading a file displays an explicit error message."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        error_texts = [e.value for e in app.error]
        self.assertTrue(any("Please choose a PDF file" in err for err in error_texts))

    def test_app_chat_interaction_in_mock_mode(self):
        """Submitting a chat query creates user and assistant turns with evidence."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()

        # Submit question via chat input
        app.chat_input[0].set_value("What is the standard procedure?").run()
        self.assertFalse(app.exception)

        # Verify chat history contains both user and assistant turns
        user_msgs = [m for m in app.chat_message if m.name == "user"]
        assistant_msgs = [m for m in app.chat_message if m.name == "assistant"]
        self.assertEqual(len(user_msgs), 1)
        self.assertEqual(len(assistant_msgs), 1)

    def test_app_clear_chat_button(self):
        """Clicking Clear Chat History resets the active conversation turns."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.chat_input[0].set_value("Test message").run()
        self.assertEqual(len(app.chat_message), 2)

        # Click Clear Chat button (button index 1)
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 0)

    def test_ui_session_state_persistence(self):
        """Rerunning app without new input preserves chat history and does not crash."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.chat_input[0].set_value("First question").run()
        self.assertEqual(len(app.chat_message), 2)

        # Trigger second rerun (e.g. toggling synthetic checkbox)
        app.checkbox[1].set_value(True).run()
        self.assertFalse(app.exception)
        # Chat history remains preserved
        self.assertEqual(len(app.chat_message), 2)


if __name__ == "__main__":
    unittest.main()
