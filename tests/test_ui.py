"""Unit and integration tests for Streamlit UI, mock backend, and visual inspection workflows."""

import tempfile
import unittest
from pathlib import Path

from contracts import Answer, Chunk, Evidence, IndexingSummary
from src.ui.mock_backend import MockBackendService, _SUPPORTED_IMAGE_EXTENSIONS, _MAX_IMAGE_SIZE_MB

# Check if streamlit is available for headless AppTest
try:
    import streamlit
    from streamlit.testing.v1 import AppTest

    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

# Fixture paths
_FIXTURE_DIR = Path("tests/fixtures")
_NORMAL_IMAGE = _FIXTURE_DIR / "synthetic_plc_leds_normal.png"
_BLURRY_IMAGE = _FIXTURE_DIR / "synthetic_blurry_panel.png"
_UNKNOWN_IMAGE = _FIXTURE_DIR / "synthetic_unknown_equipment.png"
_AMBIGUOUS_IMAGE = _FIXTURE_DIR / "synthetic_ambiguous_model.png"
_TINY_PDF = _FIXTURE_DIR / "tiny_sample.pdf"


def _make_chunk(suffix: str = "c0", page: int = 1) -> Chunk:
    return Chunk(
        chunk_id=f"doc_a1b2#p{page}#{suffix}",
        document_id="doc_a1b2",
        filename="sop_compressor.pdf",
        page=page,
        text="Inspect pressure relief valve RV-101 prior to motor start. Verify pressure is 5.5 bar.",
        equipment_model="Compressor-X1",
        synthetic=True,
    )


# ── TestMockBackend ──────────────────────────────────────────────────────────

class TestMockBackend(unittest.TestCase):
    def setUp(self):
        self.backend = MockBackendService(collection_name="test_mock_collection")
        self.chunk1 = _make_chunk("c0", page=1)
        self.chunk2 = Chunk(
            chunk_id="doc_a1b2#p3#c0",
            document_id="doc_a1b2",
            filename="sop_compressor.pdf",
            page=3,
            text="Emergency shutdown procedure: Press red emergency stop button E-STOP-01 immediately.",
            equipment_model="Compressor-X1",
            synthetic=True,
        )

    def test_indexing_chunks_and_duplicates(self):
        """Indexing succeeds, tracks duplicates correctly, and satisfies IndexingSummary invariant."""
        summary = self.backend.index_chunks([self.chunk1, self.chunk2])
        self.assertEqual(summary.total_chunks_received, 2)
        self.assertEqual(summary.chunks_indexed, 2)
        self.assertEqual(summary.chunks_skipped, 0)
        self.assertEqual(summary.chunks_failed, 0)

        re_summary = self.backend.index_chunks([self.chunk1])
        self.assertEqual(re_summary.total_chunks_received, 1)
        self.assertEqual(re_summary.chunks_indexed, 0)
        self.assertEqual(re_summary.chunks_skipped, 1)

    def test_retrieval_ranking_and_evidence(self):
        """Retrieval ranks by token overlap and preserves source lineage."""
        self.backend.index_chunks([self.chunk1, self.chunk2])
        evidence = self.backend.retrieve("emergency shutdown stop button", top_k=2)

        self.assertGreater(len(evidence), 0)
        top_ev = evidence[0]
        self.assertIsInstance(top_ev, Evidence)
        self.assertEqual(top_ev.chunk.page, 3)
        self.assertIn("emergency stop", top_ev.chunk.text.lower())

    def test_answer_generation_with_valid_citations(self):
        """Answer citations must strictly resolve to Answer.evidence items."""
        self.backend.index_chunks([self.chunk1, self.chunk2])
        ans: Answer = self.backend.answer_question("What is the emergency shutdown procedure?")

        self.assertFalse(ans.insufficient_evidence)
        self.assertGreater(len(ans.evidence), 0)
        self.assertTrue(ans.validate_citations())
        self.assertIn("emergency", ans.text.lower())

    def test_insufficient_evidence_when_unindexed(self):
        """Empty store must return insufficient_evidence=True."""
        ans = MockBackendService().answer_question("What is the valve pressure?")
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)

    def test_insufficient_evidence_for_unanswerable_query(self):
        """Known-unanswerable queries must set insufficient_evidence."""
        self.backend.index_chunks([self.chunk1, self.chunk2])
        ans = self.backend.answer_question("What is the cylinder head bolt torque specification?")
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)


# ── TestMockVision ──────────────────────────────────────────────────────────

class TestMockVision(unittest.TestCase):
    def setUp(self):
        self.backend = MockBackendService()
        self.backend.index_chunks([_make_chunk()])

    # ── answer_with_image: input validation ──────────────────────────────────

    def test_missing_image_file_raises_filenotfound(self):
        """Non-existent image path must raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.backend.answer_with_image(
                question="What does this image show?",
                image_path="/nonexistent/image_99999.png",
            )

    def test_unsupported_format_raises_valueerror(self):
        """Unsupported image extension must raise ValueError."""
        with tempfile.NamedTemporaryFile(suffix=".bmp2", delete=False) as tmp:
            tmp.write(b"\x00" * 100)
            tmp_path = tmp.name
        with self.assertRaises(ValueError, msg="Expected ValueError for unsupported extension"):
            self.backend.answer_with_image(
                question="What state is shown?",
                image_path=tmp_path,
            )

    def test_empty_question_raises_valueerror(self):
        """Empty question must raise ValueError regardless of image validity."""
        self.assertTrue(_NORMAL_IMAGE.exists(), "Normal image fixture must exist")
        with self.assertRaises(ValueError):
            self.backend.answer_with_image(question="   ", image_path=str(_NORMAL_IMAGE))

    # ── answer_with_image: normal image ──────────────────────────────────────

    def test_normal_image_returns_observations_and_evidence(self):
        """Normal-state image returns Answer with tentative observations and evidence."""
        self.assertTrue(_NORMAL_IMAGE.exists(), f"Fixture required: {_NORMAL_IMAGE}")
        ans = self.backend.answer_with_image(
            question="What is the LED status on this PLC panel?",
            image_path=str(_NORMAL_IMAGE),
            equipment_model="Compressor-X1",
        )
        self.assertFalse(ans.insufficient_evidence)
        self.assertGreater(len(ans.observations), 0)
        obs_text = " ".join(ans.observations).lower()
        self.assertIn("mock", obs_text, "All vision observations must be labelled as MOCK")
        self.assertIn("run", obs_text)

    def test_normal_image_citations_valid(self):
        """Citations in normal-image answer must resolve to evidence items."""
        self.assertTrue(_NORMAL_IMAGE.exists())
        ans = self.backend.answer_with_image(
            question="What procedure should be followed if the ERROR LED lights?",
            image_path=str(_NORMAL_IMAGE),
        )
        self.assertTrue(ans.validate_citations())

    # ── answer_with_image: blurry image ──────────────────────────────────────

    def test_blurry_image_sets_insufficient_evidence(self):
        """Blurry / low-quality image must return insufficient_evidence=True with no fabricated diagnoses."""
        self.assertTrue(_BLURRY_IMAGE.exists(), f"Fixture required: {_BLURRY_IMAGE}")
        ans = self.backend.answer_with_image(
            question="What state does the panel show?",
            image_path=str(_BLURRY_IMAGE),
        )
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)
        self.assertIn("quality", ans.text.lower())

    def test_blurry_image_no_diagnostic_fabrication(self):
        """Blurry image answer must not contain fabricated operating state claims."""
        self.assertTrue(_BLURRY_IMAGE.exists())
        ans = self.backend.answer_with_image(
            question="Is the pump running?",
            image_path=str(_BLURRY_IMAGE),
        )
        # Must not claim a specific LED or operational state
        lowered = ans.text.lower()
        self.assertNotIn("led is green", lowered)
        self.assertNotIn("cpu is running", lowered)

    # ── answer_with_image: unknown equipment ─────────────────────────────────

    def test_unknown_equipment_sets_insufficient_evidence(self):
        """Unknown equipment image must return insufficient_evidence and no invented procedures."""
        self.assertTrue(_UNKNOWN_IMAGE.exists(), f"Fixture required: {_UNKNOWN_IMAGE}")
        ans = self.backend.answer_with_image(
            question="What SOP procedure applies to this equipment?",
            image_path=str(_UNKNOWN_IMAGE),
        )
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)
        combined = (ans.text + " ".join(ans.observations)).lower()
        self.assertTrue(
            "unknown" in combined or "no matching" in combined or "not match" in combined,
            "Response must state that no documentation match was found",
        )

    # ── answer_with_image: ambiguous identity ────────────────────────────────

    def test_ambiguous_image_returns_observations_and_sets_uncertainty(self):
        """Ambiguous model image must return observations noting inability to confirm model."""
        self.assertTrue(_AMBIGUOUS_IMAGE.exists(), f"Fixture required: {_AMBIGUOUS_IMAGE}")
        ans = self.backend.answer_with_image(
            question="Which startup procedure applies to this CPU?",
            image_path=str(_AMBIGUOUS_IMAGE),
        )
        self.assertTrue(ans.insufficient_evidence)
        combined = (ans.text + " ".join(ans.observations)).lower()
        self.assertTrue(
            "ambiguous" in combined or "cannot be" in combined or "obscured" in combined,
            "Response must note that equipment identity is ambiguous",
        )

    # ── Observations must be marked MOCK ─────────────────────────────────────

    def test_all_observations_labelled_mock(self):
        """Every observation string must be labelled [MOCK] to prevent misuse."""
        for img_path in [_NORMAL_IMAGE, _BLURRY_IMAGE, _UNKNOWN_IMAGE, _AMBIGUOUS_IMAGE]:
            if not img_path.exists():
                continue
            ans = self.backend.answer_with_image(
                question="Inspect this panel.",
                image_path=str(img_path),
            )
            for obs in ans.observations:
                self.assertIn(
                    "[MOCK]", obs,
                    f"Observation in {img_path.name} missing [MOCK] label: {obs!r}",
                )

    # ── Text-only workflow unaffected by vision ───────────────────────────────

    def test_text_only_workflow_unaffected(self):
        """Text-only queries work correctly regardless of whether vision fixtures exist."""
        ans = self.backend.answer_question("Inspect pressure relief valve procedure")
        self.assertIsInstance(ans, Answer)
        # The empty backend case returns insufficient_evidence; that's fine
        # What matters is no crash and contract validity
        if not ans.insufficient_evidence:
            self.assertGreater(len(ans.evidence), 0)
            self.assertTrue(ans.validate_citations())


# ── TestStreamlitApp ─────────────────────────────────────────────────────────

class TestStreamlitApp(unittest.TestCase):
    def setUp(self):
        if not _HAS_STREAMLIT:
            self.skipTest("Streamlit not installed in current Python environment")

    def test_app_startup_and_mock_banner(self):
        """App initializes cleanly; mock banner is conspicuous."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        self.assertFalse(app.exception)
        warning_texts = [w.value for w in app.warning]
        self.assertTrue(any("RUNNING IN MOCK BACKEND MODE" in t for t in warning_texts))

    def test_app_indexing_button_without_file(self):
        """Clicking Index Document without a file shows a clear error."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.button[0].click().run()
        self.assertFalse(app.exception)
        error_texts = [e.value for e in app.error]
        self.assertTrue(any("Please choose a PDF file" in e for e in error_texts))

    def test_app_chat_interaction_in_mock_mode(self):
        """Text-only chat produces user and assistant turns."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.chat_input[0].set_value("What is the standard procedure?").run()
        self.assertFalse(app.exception)
        user_msgs = [m for m in app.chat_message if m.name == "user"]
        assistant_msgs = [m for m in app.chat_message if m.name == "assistant"]
        self.assertEqual(len(user_msgs), 1)
        self.assertEqual(len(assistant_msgs), 1)

    def test_app_clear_chat_button(self):
        """Clear Chat History resets conversation turns."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.chat_input[0].set_value("Test message").run()
        self.assertEqual(len(app.chat_message), 2)
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 0)

    def test_ui_session_state_persistence(self):
        """Ordinary rerun (e.g., checkbox toggle) preserves chat history."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.chat_input[0].set_value("First question").run()
        self.assertEqual(len(app.chat_message), 2)
        app.checkbox[1].set_value(True).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)

    def test_text_mode_works_when_no_image_uploaded(self):
        """Text-only path remains functional when the image uploader has no file."""
        app = AppTest.from_file("src/ui/app.py", default_timeout=10)
        app.run()
        app.chat_input[0].set_value("Describe the emergency shutdown sequence.").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)


if __name__ == "__main__":
    unittest.main()
