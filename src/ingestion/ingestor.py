"""Document ingestion implementation for PDF files conforming to DocumentIngestionProtocol."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from contracts import Chunk, DocumentIngestionProtocol
from src.ingestion.chunker import create_chunks_from_pages
from src.ingestion.extractor import extract_pages

logger = logging.getLogger(__name__)


class PDFIngestor:
    """Production-grade offline PDF document ingestor implementing DocumentIngestionProtocol."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

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
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"PDF file does not exist: {path}")

        filename = file_path.name
        pages_text, document_id = extract_pages(file_path)

        chunks = create_chunks_from_pages(
            pages_text=pages_text,
            document_id=document_id,
            filename=filename,
            equipment_model=equipment_model,
            synthetic=synthetic,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        logger.info(
            "Successfully ingested '%s' (%s): %d chunks across %d pages",
            filename,
            document_id,
            len(chunks),
            len(pages_text),
        )
        return chunks

