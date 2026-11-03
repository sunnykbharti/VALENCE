"""Unit and integration tests for Milestone 3B: Local Vision-to-Retrieval Workflow."""

import tempfile
import unittest
from pathlib import Path

from contracts import Answer, Chunk, Evidence
from backend.embedding import LocalEmbeddingEngine, _deterministic_pseudo_embedding
from backend.vector_store import PersistentVectorStore
from backend.retrieval import LocalRetriever
from backend.generation import LocalOllamaGenerator
from backend.vision import LocalVisionEngine, VisualInterpretation
from backend.service import RealBackend

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestVisionWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tmp_dir.name)

        # Setup deterministic test embeddings & persistent store
        def custom_embed(texts: list[str]) -> list[list[float]]:
            return [_deterministic_pseudo_embedding(t, dim=64) for t in texts]

        self.embed_engine = LocalEmbeddingEngine(
            model_dir="models/placeholder",
            dimension=64,
            embed_fn=custom_embed,
        )
        self.store = PersistentVectorStore(
            storage_path=self.storage_path,
            collection_name="test_vision_col",
            vector_dim=64,
        )

        # Index synthetic SOP chunks
        self.chunk_comp = Chunk(
            chunk_id="chk_comp_01",
            document_id="doc_compressor_sop",
            filename="compressor_sop.pdf",
            page=1,
            text="Compressor-X1 startup sequence: verify oil sight glass and operating pressure is 6.5 to 8.0 bar.",
            equipment_model="Compressor-X1",
            synthetic=True,
        )
        self.chunk_pump = Chunk(
            chunk_id="chk_pump_02",
            document_id="doc_pump_sop",
            filename="pump_sop.pdf",
            page=2,
            text="Pump-P100 lubrication: apply grease to bearings every 250 operating hours.",
            equipment_model="Pump-P100",
            synthetic=True,
        )
        chunks = [self.chunk_comp, self.chunk_pump]
        vecs = self.embed_engine.embed_texts([c.text for c in chunks])
        self.store.index_chunks_with_embeddings(chunks, vecs)

        # Mock generator simulating grounded LLM answers
        def mock_generate(prompt: str, system: str) -> str:
            if "doc_compressor_sop" in prompt:
                return "According to [doc_compressor_sop#p1#cp_01], operating pressure must remain between 6.5 and 8.0 bar."
            if "doc_pump_sop" in prompt:
                return "According to [doc_pump_sop#p2#cp_02], bearings require grease every 250 hours."
            return "Insufficient documentary evidence found."

        self.generator = LocalOllamaGenerator(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            generate_fn=mock_generate,
        )

        # Create dummy image fixture
        self.test_img = self.storage_path / "nameplate_sample.png"
        self.test_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummy_image_data")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_readable_label_interpretation_and_retrieval(self):
        """Task: A readable label is interpreted and informs retrieval."""
        def mock_vision(img: Path, prompt: str) -> VisualInterpretation:
            return VisualInterpretation(
                observations=[
                    "Tentative observation: Nameplate clearly reads 'Model: Compressor-X1'.",
                    "Tentative observation: Pressure gauge needle rests at 7.2 bar.",
                ],
                detected_equipment="Compressor-X1",
                is_ambiguous=False,
                raw_description="Clear nameplate showing Model: Compressor-X1 with 7.2 bar gauge reading.",
            )

        vision_engine = LocalVisionEngine(vision_fn=mock_vision)
        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=self.generator,
            vision_engine=vision_engine,
        )

        # User asks without equipment model; vision infers Compressor-X1
        answer = backend.answer_with_image(
            question="What is the operating pressure range for this unit?",
            image_path=self.test_img,
            equipment_model=None,
        )

        self.assertFalse(answer.insufficient_evidence)
        self.assertGreater(len(answer.observations), 0)
        # Visual observations are preserved distinctly from answer text
        self.assertTrue(any("Compressor-X1" in obs for obs in answer.observations))
        self.assertTrue(any("7.2 bar" in obs for obs in answer.observations))
        # Grounded answer citations validate
        self.assertTrue(answer.validate_citations())
        self.assertIn("6.5 and 8.0 bar", answer.text)

    def test_unclear_image_does_not_silently_filter(self):
        """Task: An unclear image marks uncertainty and avoids silent filter application."""
        def mock_blurry_vision(img: Path, prompt: str) -> VisualInterpretation:
            return VisualInterpretation(
                observations=[
                    "Tentative observation: Image is underexposed and blurry.",
                    "Tentative observation: Nameplate text is partially illegible; possible model match is uncertain.",
                ],
                detected_equipment=None,
                is_ambiguous=True,
                raw_description="Unclear and blurry nameplate.",
            )

        vision_engine = LocalVisionEngine(vision_fn=mock_blurry_vision)
        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=self.generator,
            vision_engine=vision_engine,
        )

        answer = backend.answer_with_image(
            question="Inspect this part",
            image_path=self.test_img,
            equipment_model=None,
        )

        # Observations explicitly note ambiguity
        self.assertTrue(any("ambiguous" in obs.lower() for obs in answer.observations))

    def test_missing_vision_model_preserves_text_fallback(self):
        """Task: Missing vision model reports blocker and preserves text-only retrieval."""
        # Vision engine pointing to unreachable daemon without custom function
        vision_engine = LocalVisionEngine(
            base_url="http://127.0.0.1:19999",
            model="llama3.2-vision:11b",
        )
        is_avail, reason = vision_engine.check_availability()
        self.assertFalse(is_avail)
        self.assertIn("daemon is unreachable", reason)

        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=self.generator,
            vision_engine=vision_engine,
        )

        # Image inference falls back to text retrieval gracefully
        answer = backend.answer_with_image(
            question="What is the lubrication interval for Pump-P100?",
            image_path=self.test_img,
            equipment_model="Pump-P100",
        )

        # Check observation reports fallback
        self.assertTrue(any("unavailable" in obs.lower() for obs in answer.observations))
        # Grounded text answer is still successfully produced
        self.assertFalse(answer.insufficient_evidence)
        self.assertIn("250 hours", answer.text)
        self.assertTrue(answer.validate_citations())

    def test_no_matching_evidence_returns_insufficient_evidence(self):
        """Task: Valid image with query lacking documentary support declares insufficient evidence."""
        def mock_vision(img: Path, prompt: str) -> VisualInterpretation:
            return VisualInterpretation(
                observations=["Tentative observation: Visible component appears to be an electronic servo actuator."],
                detected_equipment="Actuator-Z9",
                is_ambiguous=False,
            )

        vision_engine = LocalVisionEngine(vision_fn=mock_vision)
        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=self.generator,
            vision_engine=vision_engine,
        )

        # Ask question about an unindexed piece of equipment
        answer = backend.answer_with_image(
            question="What is the wiring diagram for this actuator?",
            image_path=self.test_img,
            equipment_model="Actuator-Z9",
        )

        self.assertTrue(answer.insufficient_evidence)
        self.assertEqual(len(answer.evidence), 0)
        self.assertIn("Insufficient documentary evidence", answer.text)
        # Visual observations are preserved
        self.assertGreater(len(answer.observations), 0)

    def test_explicit_equipment_conflicting_with_image_observations(self):
        """Task: Explicit equipment model conflicting with image label is reported and not silently switched."""
        def mock_vision(img: Path, prompt: str) -> VisualInterpretation:
            return VisualInterpretation(
                observations=["Tentative observation: Metal stamp clearly indicates 'Model: Compressor-X1'."],
                detected_equipment="Compressor-X1",
                is_ambiguous=False,
            )

        vision_engine = LocalVisionEngine(vision_fn=mock_vision)
        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=self.generator,
            vision_engine=vision_engine,
        )

        # User explicitly supplied Pump-P100, but image is Compressor-X1
        answer = backend.answer_with_image(
            question="What is the operating maintenance procedure?",
            image_path=self.test_img,
            equipment_model="Pump-P100",
        )

        # Discrepancy must be flagged in observations
        conflict_obs = [obs for obs in answer.observations if "CONFLICT DETECTED" in obs]
        self.assertEqual(len(conflict_obs), 1)
        self.assertIn("Pump-P100", conflict_obs[0])
        self.assertIn("Compressor-X1", conflict_obs[0])
        # Did not silently switch to Compressor-X1: retrieved Pump-P100 manual
        for ev in answer.evidence:
            self.assertEqual(ev.chunk.equipment_model, "Pump-P100")

    def test_input_error_handling(self):
        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=self.generator,
        )

        # Nonexistent image
        with self.assertRaises(FileNotFoundError):
            backend.answer_with_image("valid question", "non_existent_img_123.jpg")

        # Empty image file
        empty_img = self.storage_path / "empty.png"
        empty_img.write_bytes(b"")
        with self.assertRaises(ValueError):
            backend.answer_with_image("valid question", empty_img)

        # Empty question
        with self.assertRaises(ValueError):
            backend.answer_with_image("   ", self.test_img)


if __name__ == "__main__":
    unittest.main()
