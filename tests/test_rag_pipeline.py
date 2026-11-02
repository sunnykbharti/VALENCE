"""Unit and integration tests for Milestone 2B: Real Local Text RAG."""

import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from contracts import Answer, Chunk, Evidence, IndexingSummary
from backend.embedding import LocalEmbeddingEngine, _deterministic_pseudo_embedding
from backend.vector_store import PersistentVectorStore
from backend.retrieval import LocalRetriever
from backend.generation import LocalOllamaGenerator
from backend.service import RealBackend


class TestEmbeddingEngine(unittest.TestCase):
    def test_missing_model_directory_behavior(self):
        missing_dir = Path("models/missing_offline_weights_123")
        with self.assertRaises(FileNotFoundError) as ctx:
            LocalEmbeddingEngine(model_dir=missing_dir)
        self.assertIn("Automatic downloads from HuggingFace are strictly disabled", str(ctx.exception))

    def test_empty_model_directory_behavior(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir)
            with self.assertRaises(FileNotFoundError) as ctx:
                LocalEmbeddingEngine(model_dir=p)
            self.assertIn("is empty", str(ctx.exception))

    def test_deterministic_embedding_fn(self):
        def custom_embed(texts: list[str]) -> list[list[float]]:
            return [_deterministic_pseudo_embedding(t, dim=64) for t in texts]

        engine = LocalEmbeddingEngine(
            model_dir="models/placeholder",
            dimension=64,
            embed_fn=custom_embed,
        )
        vecs = engine.embed_texts(["Inspect emergency stop valve."])
        self.assertEqual(len(vecs), 1)
        self.assertEqual(len(vecs[0]), 64)

        # Query embedding validation
        with self.assertRaises(ValueError):
            engine.embed_query("   ")


class TestPersistentVectorStore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tmp_dir.name)
        self.store = PersistentVectorStore(
            storage_path=self.storage_path,
            collection_name="test_col",
            vector_dim=32,
        )

        self.chunk1 = Chunk(
            chunk_id="chk_c101",
            document_id="doc_sop_compressor",
            filename="sop_compressor.pdf",
            page=2,
            text="Verify cooling fan engages after 2 seconds of startup.",
            equipment_model="Model-X",
            synthetic=True,
        )
        self.vec1 = _deterministic_pseudo_embedding(self.chunk1.text, dim=32)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_index_persistence_and_duplicate_prevention(self):
        # 1. First index insertion
        summary = self.store.index_chunks_with_embeddings([self.chunk1], [self.vec1])
        self.assertEqual(summary.total_chunks_received, 1)
        self.assertEqual(summary.chunks_indexed, 1)
        self.assertEqual(summary.chunks_skipped, 0)
        self.assertEqual(summary.chunks_failed, 0)
        self.assertEqual(self.store.count(), 1)

        # 2. Duplicate unchanged re-indexing (idempotent)
        reindex_summary = self.store.index_chunks_with_embeddings([self.chunk1], [self.vec1])
        self.assertEqual(reindex_summary.total_chunks_received, 1)
        self.assertEqual(reindex_summary.chunks_indexed, 0)
        self.assertEqual(reindex_summary.chunks_skipped, 1)
        self.assertEqual(reindex_summary.chunks_failed, 0)

        # 3. Persistence across new instance
        store2 = PersistentVectorStore(
            storage_path=self.storage_path,
            collection_name="test_col",
            vector_dim=32,
        )
        self.assertEqual(store2.count(), 1)

    def test_metadata_update_reindexing(self):
        # Index initial chunk
        self.store.index_chunks_with_embeddings([self.chunk1], [self.vec1])

        # Updated metadata on same chunk_id
        updated_chunk = Chunk(
            chunk_id="chk_c101",
            document_id="doc_sop_compressor",
            filename="sop_compressor.pdf",
            page=2,
            text="Verify cooling fan engages after 2 seconds of startup.",
            equipment_model="Model-X-Updated",  # Changed equipment model
            synthetic=True,
        )
        summary = self.store.index_chunks_with_embeddings([updated_chunk], [self.vec1])
        self.assertEqual(summary.total_chunks_received, 1)
        self.assertEqual(summary.chunks_indexed, 1)  # Updated in-place
        self.assertEqual(summary.chunks_skipped, 0)


class TestRetrievalAgainstFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tmp_dir.name)

        def custom_embed(texts: list[str]) -> list[list[float]]:
            return [_deterministic_pseudo_embedding(t, dim=64) for t in texts]

        self.embed_engine = LocalEmbeddingEngine(
            model_dir="models/placeholder",
            dimension=64,
            embed_fn=custom_embed,
        )
        self.store = PersistentVectorStore(
            storage_path=self.storage_path,
            collection_name="test_retrieval",
            vector_dim=64,
        )
        self.retriever = LocalRetriever(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
        )

        self.chunk_press = Chunk(
            chunk_id="c_press_01",
            document_id="doc_compressor_sop",
            filename="compressor.pdf",
            page=3,
            text="Normal operating pressure is between 6.5 bar and 8.0 bar.",
            equipment_model="Compressor-X1",
            synthetic=True,
        )
        self.chunk_valve = Chunk(
            chunk_id="c_valve_02",
            document_id="doc_valve_sop",
            filename="valve.pdf",
            page=1,
            text="Torque safety valve bolts to 50 Nm using a calibrated torque wrench.",
            equipment_model="Valve-V20",
            synthetic=True,
        )

        # Index both fixture chunks
        chunks = [self.chunk_press, self.chunk_valve]
        vecs = self.embed_engine.embed_texts([c.text for c in chunks])
        self.store.index_chunks_with_embeddings(chunks, vecs)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_retrieval_and_inspectable_evidence(self):
        evidence = self.retriever.retrieve("What is the operating pressure?", top_k=2)
        self.assertGreater(len(evidence), 0)
        top = evidence[0]
        self.assertIsInstance(top, Evidence)
        self.assertEqual(top.chunk.chunk_id, "c_press_01")
        # Check source_id is grounded in actual metadata
        expected_source_id = f"{top.chunk.document_id}#p{top.chunk.page}#c{top.chunk.chunk_id[-4:]}"
        self.assertEqual(top.source_id, expected_source_id)

    def test_equipment_filtering(self):
        # Querying pressure for Valve-V20 should exclude Compressor-X1
        results = self.retriever.retrieve(
            "operating pressure",
            top_k=5,
            equipment_model="Valve-V20",
        )
        for ev in results:
            self.assertEqual(ev.chunk.equipment_model, "Valve-V20")

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            self.retriever.retrieve("")
        with self.assertRaises(ValueError):
            self.retriever.retrieve("valid query", top_k=0)


class TestGeneration(unittest.TestCase):
    def setUp(self):
        self.chunk = Chunk(
            chunk_id="c_gasket_01",
            document_id="doc_maintenance",
            filename="maintenance.pdf",
            page=5,
            text="Replace head gasket every 12 months or 2,000 engine hours.",
            equipment_model="Engine-E5",
            synthetic=True,
        )
        self.evidence = Evidence(source_id="doc_maintenance#p5#ct_01", chunk=self.chunk)

    def test_no_source_response_behavior(self):
        generator = LocalOllamaGenerator(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
        )
        ans = generator.answer_with_evidence(
            question="What is the torque for bolt B4?",
            evidence=[],  # No supporting evidence
            equipment_model="Engine-E5",
        )
        self.assertTrue(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 0)
        self.assertIn("Insufficient documentary evidence", ans.text)

    def test_mocked_generation_with_citations(self):
        # Mock generator function simulating Ollama response
        def mock_llm_call(prompt: str, system: str) -> str:
            self.assertIn("doc_maintenance#p5#ct_01", prompt)
            return "According to [doc_maintenance#p5#ct_01], the head gasket must be replaced every 12 months."

        generator = LocalOllamaGenerator(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            generate_fn=mock_llm_call,
        )

        ans = generator.answer_with_evidence(
            question="When should the head gasket be replaced?",
            evidence=[self.evidence],
            equipment_model="Engine-E5",
        )

        self.assertFalse(ans.insufficient_evidence)
        self.assertEqual(len(ans.evidence), 1)
        self.assertTrue(ans.validate_citations())
        self.assertIn("[doc_maintenance#p5#ct_01]", ans.text)


def _is_ollama_reachable() -> bool:
    """Read-only check to see if local Ollama daemon is reachable on localhost."""
    try:
        req = Request("http://localhost:11434/api/tags")
        with urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except (URLError, Exception):
        return False


class TestRealModelSmokeIntegration(unittest.TestCase):
    """Separately labeled real-model integration test."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tmp_dir.name)

        def custom_embed(texts: list[str]) -> list[list[float]]:
            return [_deterministic_pseudo_embedding(t, dim=64) for t in texts]

        self.embed_engine = LocalEmbeddingEngine(
            model_dir="models/placeholder",
            dimension=64,
            embed_fn=custom_embed,
        )
        self.store = PersistentVectorStore(
            storage_path=self.storage_path,
            collection_name="smoke_test_col",
            vector_dim=64,
        )

        # Synthetic manual excerpt
        self.chunk = Chunk(
            chunk_id="chk_real_sop_01",
            document_id="sop_air_compressor",
            filename="synthetic_sop.txt",
            page=3,
            text="Normal operating pressure is between 6.5 bar and 8.0 bar.",
            equipment_model="Model-X",
            synthetic=True,
        )
        vecs = self.embed_engine.embed_texts([self.chunk.text])
        self.store.index_chunks_with_embeddings([self.chunk], vecs)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_real_backend_end_to_end_smoke(self):
        """End-to-end smoke test through RealBackend interface with deterministic generator."""
        def deterministic_generate(prompt: str, system: str) -> str:
            return "Based on [sop_air_compressor#p3#p_01], operating pressure is between 6.5 bar and 8.0 bar."

        generator = LocalOllamaGenerator(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
            generate_fn=deterministic_generate,
        )

        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=generator,
        )

        # Acceptance query from the supplied manual
        answer = backend.answer_question(
            "What is the normal operating pressure for Model-X?",
            equipment_model="Model-X",
        )

        self.assertFalse(answer.insufficient_evidence)
        self.assertGreaterEqual(len(answer.evidence), 1)
        self.assertEqual(answer.evidence[0].chunk.chunk_id, "chk_real_sop_01")
        self.assertTrue(answer.validate_citations())
        self.assertIn("6.5 bar and 8.0 bar", answer.text)

    @unittest.skipUnless(_is_ollama_reachable(), "Requires local Ollama daemon active on localhost:11434")
    def test_live_ollama_model_smoke(self):
        """Live Ollama inference smoke test (runs only when daemon is active)."""
        generator = LocalOllamaGenerator(
            base_url="http://localhost:11434",
            model="llama3.2:3b",
        )
        backend = RealBackend(
            embedding_engine=self.embed_engine,
            vector_store=self.store,
            generator=generator,
        )
        answer = backend.answer_question(
            "What is the normal operating pressure?",
            equipment_model="Model-X",
        )
        self.assertTrue(answer.validate_citations())


if __name__ == "__main__":
    unittest.main()
