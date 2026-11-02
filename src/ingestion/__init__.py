"""Document ingestion and parsing package (Member A)."""

from src.ingestion.extractor import extract_pages
from src.ingestion.chunker import create_chunks_from_pages, split_text_into_segments
from src.ingestion.ingestor import PDFIngestor
from src.ingestion.mock import MockPDFIngestor

__all__ = [
    "extract_pages",
    "create_chunks_from_pages",
    "split_text_into_segments",
    "PDFIngestor",
    "MockPDFIngestor",
]
