"""Unified local backend service for VALENCE (Member B).

Coordinates real local embeddings, persistent vector store, retrieval, and Ollama generation.
Conforms strictly to BackendServiceProtocol in contracts.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Answer, Chunk, Evidence, IndexingSummary
from config import RuntimeConfig, load_config
from backend.embedding import LocalEmbeddingEngine
from backend.vector_store import PersistentVectorStore
from backend.retrieval import LocalRetriever
from backend.generation import LocalOllamaGenerator

logger = logging.getLogger("valence.backend")


class RealBackend:
    """Production local backend engine running air-gapped on device.

    Coordinates:
    - Local embedding generation (without remote downloads)
    - Persistent Qdrant / disk-backed vector storage
    - Local retrieval with metadata-grounded Evidence
    - Local Ollama LLM text generation
    """

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        embedding_engine: Optional[LocalEmbeddingEngine] = None,
        vector_store: Optional[PersistentVectorStore] = None,
        generator: Optional[LocalOllamaGenerator] = None,
    ) -> None:
        self.config = config or load_config()

        # Initialize Embedding Engine
        self.embedding_engine = embedding_engine or LocalEmbeddingEngine(
            model_dir=self.config.embedding_model_dir,
        )

        # Initialize Persistent Vector Store
        self.vector_store = vector_store or PersistentVectorStore(
            storage_path=self.config.index_dir,
            collection_name=self.config.collection_name,
            vector_dim=self.embedding_engine.dimension,
        )

        # Initialize Retriever
        self.retriever = LocalRetriever(
            embedding_engine=self.embedding_engine,
            vector_store=self.vector_store,
        )

        # Initialize Generator
        self.generator = generator or LocalOllamaGenerator(
            base_url=self.config.ollama_base_url,
            model=self.config.llm_model,
        )

    def index_chunks(self, chunks: Sequence[Chunk]) -> IndexingSummary:
        """Indexes chunks into local persistent vector store."""
        if not chunks:
            return IndexingSummary(
                total_chunks_received=0,
                chunks_indexed=0,
                chunks_skipped=0,
                chunks_failed=0,
                collection_name=self.config.collection_name,
                errors=[],
            )

        texts = [c.text for c in chunks]
        embeddings = self.embedding_engine.embed_texts(texts)
        return self.vector_store.index_chunks_with_embeddings(chunks, embeddings)

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        equipment_model: Optional[str] = None,
    ) -> list[Evidence]:
        """Retrieves inspectable Evidence instances matching question."""
        return self.retriever.retrieve(
            question=question,
            top_k=top_k,
            equipment_model=equipment_model,
        )

    def answer_question(
        self,
        question: str,
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Generates grounded answer citing retrieved evidence."""
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        evidence = self.retrieve(question, top_k=3, equipment_model=equipment_model)
        return self.generator.answer_with_evidence(
            question=question,
            evidence=evidence,
            equipment_model=equipment_model,
        )

    def answer_with_image(
        self,
        question: str,
        image_path: Union[str, Path],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Grounds question in retrieved evidence with image context.

        (Full multimodal VLM inference integrated in Milestone 3B).
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        img = Path(image_path)
        if not img.exists():
            raise FileNotFoundError(f"Inspection image not found at: {img}")

        evidence = self.retrieve(question, top_k=3, equipment_model=equipment_model)
        base_answer = self.generator.answer_with_evidence(
            question=question,
            evidence=evidence,
            equipment_model=equipment_model,
        )

        base_answer.observations = [
            f"Image '{img.name}' registered for inspection.",
            f"Image dimensions and file check: {img.stat().st_size} bytes.",
        ]
        return base_answer

