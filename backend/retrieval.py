"""Local semantic retrieval module for VALENCE (Member B).

Performs vector search over persistent storage, enforces input validation,
respects equipment_model filters, and constructs inspectable source evidence.
"""

from __future__ import annotations

import logging
from typing import Optional

from contracts import Chunk, Evidence, RetrievalProtocol
from backend.embedding import LocalEmbeddingEngine
from backend.vector_store import PersistentVectorStore

logger = logging.getLogger("valence.retrieval")


class LocalRetriever(RetrievalProtocol):
    """Retrieves inspectable Evidence instances based on vector similarity."""

    def __init__(
        self,
        embedding_engine: LocalEmbeddingEngine,
        vector_store: PersistentVectorStore,
    ) -> None:
        self.embedding_engine = embedding_engine
        self.vector_store = vector_store

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        equipment_model: Optional[str] = None,
    ) -> list[Evidence]:
        """Retrieves top_k most relevant Evidence items for the question.

        Raises:
            ValueError: If question is empty/whitespace or top_k < 1.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        if not isinstance(top_k, int) or top_k < 1:
            raise ValueError(f"top_k must be an integer >= 1, got {top_k}")

        query_vec = self.embedding_engine.embed_query(question.strip())
        results = self.vector_store.search_similar(
            query_vector=query_vec,
            top_k=top_k,
            equipment_model=equipment_model,
            query_text=question.strip(),
        )

        evidence_list: list[Evidence] = []
        for score, chunk in results:
            # Deterministic, inspectable source reference derived from metadata
            source_id = f"{chunk.document_id}#p{chunk.page}#c{chunk.chunk_id[-4:]}"
            evidence_list.append(Evidence(source_id=source_id, chunk=chunk))

        return evidence_list

