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


from src.ingestion import MockPDFIngestor, PDFIngestor


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
    if mock:
        from backend.mock_backend import MockBackend
        return MockBackend(collection_name=collection_name or "mock_collection")

    from backend.service import RealBackend
    from config import load_config
    cfg = load_config()
    if collection_name:
        from dataclasses import replace
        cfg = replace(cfg, collection_name=collection_name)
    return RealBackend(config=cfg)
