"""Smoke and unit tests for Member B configuration, diagnostics, and mock backend."""

import os
import tempfile
import unittest
from pathlib import Path

from contracts import Answer, Chunk, Evidence, IndexingSummary
from config import RuntimeConfig, is_loopback_url, load_config
from backend.diagnostics import (
    check_embedding_model,
    check_index_directory,
    run_diagnostics,
)
from backend.mock_backend import MockBackend
from src.services import create_backend, create_ingestor

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestConfiguration(unittest.TestCase):
    def test_loopback_acceptance(self):
        self.assertTrue(is_loopback_url("http://localhost:11434"))
        self.assertTrue(is_loopback_url("http://127.0.0.1:11434"))
        self.assertTrue(is_loopback_url("http://[::1]:11434"))
        self.assertTrue(is_loopback_url("http://localhost:8080/v1"))

    def test_non_loopback_rejection(self):
        self.assertFalse(is_loopback_url("http://remote.host.com:11434"))
        self.assertFalse(is_loopback_url("http://192.168.1.45:11434"))
        self.assertFalse(is_loopback_url("https://api.openai.com"))
        self.assertFalse(is_loopback_url("http://10.0.0.1:11434"))

    def test_runtime_config_rejects_external_endpoint(self):
        with self.assertRaises(ValueError) as ctx:
            RuntimeConfig(
                ollama_base_url="http://external-server:11434",
                llm_model="llama3.2:3b",
                vlm_model="llama3.2-vision:11b",
                embedding_model_dir=Path("models/embed"),
                index_dir=Path("data/qdrant"),
                collection_name="docs",
                mock_mode=True,
            )
        self.assertIn("Air-gapped constraint violation", str(ctx.exception))

    def test_runtime_config_defaults(self):
        cfg = load_config()
        self.assertTrue(is_loopback_url(cfg.ollama_base_url))
        self.assertEqual(cfg.llm_model, "llama3.2:3b")
        self.assertEqual(cfg.vlm_model, "llama3.2-vision:11b")
        self.assertTrue(cfg.mock_mode)


class TestDiagnostics(unittest.TestCase):
    def test_missing_embedding_model_diagnostic(self):
        missing_path = Path("models/non_existent_model_dir_xyz")
        check = check_embedding_model(missing_path)
        self.assertFalse(check.passed)
        self.assertIn("does not exist", check.message)
        self.assertIsNotNone(check.actionable_fix)
        self.assertIn("During online preparation", check.actionable_fix)

    def test_present_embedding_model_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)
            (p / "config.json").write_text("{}")
            (p / "model.safetensors").write_bytes(b"dummy")
            check = check_embedding_model(p)
            self.assertTrue(check.passed)

    def test_index_directory_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "sub_idx"
            check = check_index_directory(target)
            self.assertTrue(check.passed)
            self.assertTrue(target.exists())

    def test_run_diagnostics_report(self):
        report = run_diagnostics()
        summary = report.summary()
        self.assertIn("VALENCE Local Runtime Diagnostics", summary)
        self.assertIn("Embedding Model Directory", summary)
        self.assertIn("Ollama Local Daemon", summary)


class TestMockBackend(unittest.TestCase):
    def setUp(self):
        self.backend = create_backend(mock=True, collection_name="test_backend_smoke")
        self.assertTrue(isinstance(self.backend, MockBackend))

        # Sample test chunk fixture
        self.chunk1 = Chunk(
            chunk_id="chk_pump_01",
            document_id="doc_pump_manual",
            filename="pump_manual.pdf",
            page=4,
            text="For hydraulic pump P-100, replace intake gasket every 500 operating hours. Torque bolts to 45 Nm.",
            equipment_model="Pump-P100",
            synthetic=True,
        )
        self.chunk2 = Chunk(
            chunk_id="chk_valv_02",
            document_id="doc_valve_manual",
            filename="valve_manual.pdf",
            page=2,
            text="Safety relief valve V-20 activates when pressure exceeds 10 bar.",
            equipment_model="Valve-V20",
            synthetic=True,
        )

    def test_indexing_summary_invariant_and_deduplication(self):
        summary = self.backend.index_chunks([self.chunk1, self.chunk2])
        self.assertEqual(summary.total_chunks_received, 2)
        self.assertEqual(summary.chunks_indexed, 2)
        self.assertEqual(summary.chunks_skipped, 0)
        self.assertEqual(summary.chunks_failed, 0)

        # Re-indexing identical chunks -> skipped
        reindex_summary = self.backend.index_chunks([self.chunk1])
        self.assertEqual(reindex_summary.total_chunks_received, 1)
        self.assertEqual(reindex_summary.chunks_indexed, 0)
        self.assertEqual(reindex_summary.chunks_skipped, 1)
        self.assertEqual(reindex_summary.chunks_failed, 0)

    def test_retrieval_and_filtering(self):
        self.backend.index_chunks([self.chunk1, self.chunk2])

        # Basic lexical retrieval
        results = self.backend.retrieve("hydraulic pump intake gasket", top_k=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].chunk.chunk_id, "chk_pump_01")

        # Equipment filtering
        filtered = self.backend.retrieve("pressure relief", equipment_model="Pump-P100")
        for ev in filtered:
            self.assertEqual(ev.chunk.equipment_model, "Pump-P100")

        # Empty question raises ValueError
        with self.assertRaises(ValueError):
            self.backend.retrieve("   ")

        # Invalid top_k raises ValueError
        with self.assertRaises(ValueError):
            self.backend.retrieve("valid question", top_k=0)

    def test_answer_question_with_citations_and_mock_label(self):
        self.backend.index_chunks([self.chunk1])

        ans = self.backend.answer_question("When should the intake gasket be replaced?", equipment_model="Pump-P100")
        self.assertIsInstance(ans, Answer)
        self.assertFalse(ans.insufficient_evidence)
        self.assertGreater(len(ans.evidence), 0)
        # Explicit mock label required
        self.assertIn("MOCK INFERENCE (NOT REAL LLM OUTPUT)", ans.text)
        # Citations must strictly validate against returned evidence
        self.assertTrue(ans.validate_citations())

    def test_insufficient_evidence_when_no_documentary_support(self):
        # Empty index or unmatched query
        ans = self.backend.answer_question("What is the nuclear reactor core temperature?")
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)
        self.assertIn("Insufficient documentary evidence", ans.text)

    def test_answer_with_image_smoke(self):
        self.backend.index_chunks([self.chunk1])

        fixture_img = FIXTURES_DIR / "sample_inspection.png"
        fixture_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummy_test_bytes")

        try:
            ans = self.backend.answer_with_image(
                question="Inspect pump gasket condition",
                image_path=fixture_img,
                equipment_model="Pump-P100",
            )
            self.assertIsInstance(ans, Answer)
            self.assertIn("MOCK INFERENCE (NOT REAL LLM OUTPUT)", ans.text)
            self.assertGreater(len(ans.observations), 0)
            self.assertTrue(all(obs.startswith("MOCK OBSERVATION:") for obs in ans.observations))
            self.assertTrue(ans.validate_citations())
        finally:
            if fixture_img.exists():
                fixture_img.unlink()

    def test_answer_with_image_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.backend.answer_with_image(
                question="Inspect part",
                image_path="non_existent_inspection_photo_999.png",
            )


class TestPipelineSmokeIntegration(unittest.TestCase):
    """End-to-end smoke test integrating Member A mock ingestor and Member B mock backend."""

    def test_ingestion_to_backend_pipeline(self):
        synthetic_sop = Path(__file__).parents[1] / "data" / "synthetic" / "synthetic_sop.txt"
        ingestor = create_ingestor(mock=True)
        chunks = ingestor.ingest_pdf(synthetic_sop, equipment_model="Model-X", synthetic=True)

        self.assertGreater(len(chunks), 0)

        backend = create_backend(mock=True)
        summary = backend.index_chunks(chunks)

        self.assertEqual(summary.total_chunks_received, len(chunks))
        self.assertEqual(summary.chunks_indexed, len(chunks))
        self.assertEqual(summary.chunks_failed, 0)

        # Query indexed SOP
        answer = backend.answer_question("What is the normal operating pressure?", equipment_model="Model-X")
        self.assertFalse(answer.insufficient_evidence)
        self.assertTrue(answer.validate_citations())
        self.assertIn("MOCK INFERENCE (NOT REAL LLM OUTPUT)", answer.text)


if __name__ == "__main__":
    unittest.main()
