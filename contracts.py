"""Shared contracts, data structures, and interface signatures for VALENCE.

Conventions & Invariants:
- Page numbers are 1-based original PDF page positions (page >= 1).
- chunk_id, document_id, filename, text, and source_id must be non-empty and non-whitespace.
- Document and chunk IDs must be deterministic.
- insufficient_evidence is strictly determined by documentary support, never LLM confidence scores.
- Answer.evidence contains only the supporting evidence selected for the answer.
- Every citation identifier in Answer.text (e.g., '[source_id]') must resolve to an Evidence item in Answer.evidence.
- Unknown equipment model must remain None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, Sequence, Union


@dataclass(frozen=True)
class Chunk:
    """Represents a text chunk extracted from a document with full lineage.

    Attributes:
        chunk_id: Unique deterministic identifier for the chunk.
        document_id: Deterministic identifier representing the source document.
        filename: Original file name or relative path.
        page: 1-based page position in original source document.
        text: Non-empty plain text content.
        equipment_model: Specific equipment model identifier if known, otherwise None.
        synthetic: True if generated synthetic test data; False for authentic documents.
    """
    chunk_id: str
    document_id: str
    filename: str
    page: int
    text: str
    equipment_model: Optional[str] = None
    synthetic: bool = False

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError(f"Page number must be >= 1 (1-based index), got {self.page}")
        if not self.chunk_id or not self.chunk_id.strip():
            raise ValueError("chunk_id must be non-empty and non-whitespace")
        if not self.document_id or not self.document_id.strip():
            raise ValueError("document_id must be non-empty and non-whitespace")
        if not self.filename or not self.filename.strip():
            raise ValueError("filename must be non-empty and non-whitespace")
        if not self.text or not self.text.strip():
            raise ValueError("text must not be empty or whitespace-only")


@dataclass(frozen=True)
class Evidence:
    """Retrieved evidence item supporting an answer.

    Attributes:
        source_id: Deterministic source reference (e.g., 'doc_a1b2#p3#c0').
        chunk: The underlying Chunk payload.
    """
    source_id: str
    chunk: Chunk

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise ValueError("source_id must be non-empty and non-whitespace")


@dataclass
class Answer:
    """Structured response to a technical user query.

    Attributes:
        text: The generated response or synthesis.
        evidence: Sequence of Evidence objects retrieved and used.
        insufficient_evidence: True if retrieved evidence does not substantiate
                               an answer. Must be based on documentary support.
        observations: List of tentative visual observations from image inputs.
    """
    text: str
    evidence: list[Evidence] = field(default_factory=list)
    insufficient_evidence: bool = False
    observations: list[str] = field(default_factory=list)

    def validate_citations(self) -> bool:
        """Verifies that all bracketed citations in text map to available evidence.

        Matches tokens formatted as [source_id] where source_id contains no closing bracket.
        """
        cited_ids = set(re.findall(r"\[([^\]]+)\]", self.text))
        available_ids = {e.source_id for e in self.evidence}
        return cited_ids.issubset(available_ids)


@dataclass(frozen=True)
class IndexingSummary:
    """Explicit summary of indexing operations.

    Invariant:
        total_chunks_received == chunks_indexed + chunks_skipped + chunks_failed
    """
    total_chunks_received: int
    chunks_indexed: int
    chunks_skipped: int
    chunks_failed: int
    collection_name: str
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.total_chunks_received < 0 or self.chunks_indexed < 0 or self.chunks_skipped < 0 or self.chunks_failed < 0:
            raise ValueError("Chunk counts cannot be negative")
        expected = self.chunks_indexed + self.chunks_skipped + self.chunks_failed
        if self.total_chunks_received != expected:
            raise ValueError(
                f"Invariant violation: total_chunks_received ({self.total_chunks_received}) != "
                f"chunks_indexed ({self.chunks_indexed}) + "
                f"chunks_skipped ({self.chunks_skipped}) + "
                f"chunks_failed ({self.chunks_failed})"
            )


# --- Interface Protocols ---

class DocumentIngestionProtocol(Protocol):
    def ingest_pdf(
        self,
        path: Union[str, Path],
        equipment_model: Optional[str] = None,
        synthetic: bool = False,
    ) -> list[Chunk]:
        """Ingests a PDF file, parses pages (1-based), and produces chunks.

        Reporting unreadable / blank pages:
            Pages with no extractable text are omitted from the returned list[Chunk]
            and logged via standard Python logging (`logger.warning("Page %d has no extractable text", page)`).
            No empty or whitespace Chunks are ever emitted.

        Raises:
            FileNotFoundError: If PDF does not exist at path.
            ValueError: If file is not a valid PDF or is completely unreadable.
        """
        ...


class IndexingProtocol(Protocol):
    def index_chunks(self, chunks: Sequence[Chunk]) -> IndexingSummary:
        """Embeds and indexes chunks into the local vector database.

        Duplicate & Re-indexing Semantics:
            - Unchanged re-indexing (matching chunk_id and identical content/metadata):
              skipped and counted in chunks_skipped.
            - Metadata change on identical chunk_id:
              reconciled in-place by updating index metadata and counted in chunks_indexed.
            - Validation errors / corrupt data: counted in chunks_failed.

        Raises:
            RuntimeError: If vector store or local embedding engine is unavailable.
        """
        ...


class RetrievalProtocol(Protocol):
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
        ...


class GenerationProtocol(Protocol):
    def answer_question(
        self,
        question: str,
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Answers query based strictly on retrieved local evidence.

        Raises:
            ValueError: If question is empty or whitespace-only.
        """
        ...

    def answer_with_image(
        self,
        question: str,
        image_path: Union[str, Path],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Answers query using local multimodal interpretation alongside SOP retrieval.

        Raises:
            ValueError: If question is empty or whitespace-only, or if image is invalid.
            FileNotFoundError: If image_path does not exist.
        """
        ...

