"""Public service factory facade for VALENCE.

Decouples Member A (UI/Ingestion) and Member B (Backend) implementations
while allowing explicit mock selection for testing and offline development.
"""

from __future__ import annotations

from typing import Optional, Protocol
from contracts import (
    DocumentIngestionProtocol,
    IndexingProtocol,
    RetrievalProtocol,
    GenerationProtocol,
)


class BackendServiceProtocol(
    IndexingProtocol,
    RetrievalProtocol,
    GenerationProtocol,
    Protocol,
):
    """Unified backend protocol covering indexing, retrieval, and generation."""
    ...


def create_ingestor(
    mock: bool = False,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> DocumentIngestionProtocol:
    """Factory creating the document ingestion service.

    Args:
        mock: If True, returns a deterministic mock ingestor producing sample chunks.
        chunk_size: Target token/character chunk size.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        An instance conforming to DocumentIngestionProtocol.
    """
    from src.ingestion.ingestor import MockPDFIngestor, PDFIngestor

    if mock:
        return MockPDFIngestor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return PDFIngestor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def create_backend(
    mock: bool = False,
    collection_name: Optional[str] = None,
) -> BackendServiceProtocol:
    """Factory creating the retrieval and generation backend.

    Args:
        mock: If True, returns an in-memory mock engine with canned answers and evidence.
        collection_name: Optional name of the Qdrant collection to target.

    Returns:
        An instance conforming to BackendServiceProtocol.
    """
    raise NotImplementedError("create_backend must be implemented in Member B backend module")

