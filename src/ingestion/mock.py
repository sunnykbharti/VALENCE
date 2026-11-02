"""Deterministic mock ingestor for isolated offline development and testing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Union

from contracts import Chunk, DocumentIngestionProtocol
from src.ingestion.chunker import create_chunks_from_pages


class MockPDFIngestor:
    """Mock document ingestor conforming to DocumentIngestionProtocol.

    Allows Member B to test indexing and retrieval without external PDF dependencies.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest_pdf(
        self,
        path: Union[str, Path],
        equipment_model: Optional[str] = None,
        synthetic: bool = True,
    ) -> list[Chunk]:
        """Produces deterministic sample chunks from mock data or existing PDF."""
        path_str = str(path)
        if not path_str or not path_str.strip():
            raise ValueError("path must be non-empty and non-whitespace")

        file_path = Path(path)
        filename = file_path.name

        # If it's a real file, verify it exists unless it's an explicit mock string identifier
        if not file_path.exists() and not (path_str.startswith("mock") or "mock" in filename):
            raise FileNotFoundError(f"Mock target file not found: {path}")

        # Deterministic document ID based on filename
        doc_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]
        document_id = f"mock_{doc_hash}"

        # Canned multi-page industrial procedures
        canned_pages = {
            1: (
                "Section 1: Pre-Operational Safety Verification.\n"
                "Inspect pressure relief valve RV-101. Verify emergency stop circuit E-STOP-01 is energized.\n"
                "Confirm pneumatic supply line is set between 5.5 bar and 6.0 bar prior to main motor start."
            ),
            2: "",  # Deliberate blank page for unreadable/blank page testing
            3: (
                "Section 3: Standard Startup Sequence.\n"
                "1. Switch main isolator Q1 to position ON.\n"
                "2. Acknowledge safety guard interlocks on HMI screen 10.\n"
                "3. Press illuminated blue RESET button followed by green START button within 5 seconds."
            ),
        }

        return create_chunks_from_pages(
            pages_text=canned_pages,
            document_id=document_id,
            filename=filename,
            equipment_model=equipment_model or "MOCK-EQUIPMENT-01",
            synthetic=synthetic,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

