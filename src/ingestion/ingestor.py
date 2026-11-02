"""Document ingestion and chunking implementation (Member A).

Provides deterministic chunking, page-level tracking, and contract-compliant
Chunk extraction.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Chunk, DocumentIngestionProtocol

logger = logging.getLogger("valence.ingestion")


def _deterministic_document_id(filename: str) -> str:
    """Computes a deterministic document identifier from filename."""
    digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]
    return f"doc_{digest}"


def _chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Splits a single page's text into overlapping chunks.

    Ensures no chunk is empty or whitespace-only.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= chunk_size:
        return [clean_text]

    chunks: list[str] = []
    start = 0
    stride = max(1, chunk_size - chunk_overlap)

    while start < len(clean_text):
        end = start + chunk_size
        chunk = clean_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += stride

    return chunks


class MockPDFIngestor:
    """Mock ingestor for testing and offline development without PDF dependencies.

    Parses text or synthetic documents using page markers (e.g. form-feed '\\x0c'
    or '--- Page X ---'), returning valid Chunk instances.
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
        """Ingests a document or synthetic text file.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file is empty or not readable.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Document not found at: {p}")

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback for binary / mock PDF bytes
            raw = p.read_bytes()
            # Attempt to extract readable ASCII chunks
            import re
            extracted = re.findall(rb"\((.*?)\)\s*Tj", raw)
            if extracted:
                content = "\n".join(b.decode("latin1", errors="ignore") for b in extracted)
            else:
                content = raw.decode("latin1", errors="ignore")

        if not content.strip():
            raise ValueError(f"Document at {p} contains no readable content.")

        # Split on standard page break markers or form-feed
        if "\x0c" in content:
            raw_pages = content.split("\x0c")
        elif "--- Page " in content:
            import re
            raw_pages = re.split(r"--- Page \d+ ---", content)
            if raw_pages and not raw_pages[0].strip():
                raw_pages = raw_pages[1:]
        else:
            raw_pages = [content]

        doc_id = _deterministic_document_id(p.name)
        chunks: list[Chunk] = []

        for page_idx, page_content in enumerate(raw_pages, start=1):
            stripped_page = page_content.strip()
            if not stripped_page:
                logger.warning("Page %d of %s has no extractable text; skipping.", page_idx, p.name)
                continue

            page_chunks = _chunk_text(
                stripped_page,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

            for chunk_idx, text_segment in enumerate(page_chunks):
                chunk_id = f"{doc_id}_p{page_idx}_c{chunk_idx}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        filename=p.name,
                        page=page_idx,
                        text=text_segment,
                        equipment_model=equipment_model,
                        synthetic=synthetic,
                    )
                )

        return chunks


class PDFIngestor:
    """Production PDF ingestor using local PDF extraction libraries.

    Requires pypdf or PyMuPDF (fitz) installed.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest_pdf(
        self,
        path: Union[str, Path],
        equipment_model: Optional[str] = None,
        synthetic: bool = False,
    ) -> list[Chunk]:
        """Ingests a real PDF file using available local libraries.

        Raises:
            FileNotFoundError: If PDF does not exist.
            ValueError: If file is not a valid PDF.
            RuntimeError: If no PDF parsing library is installed.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"PDF not found at: {p}")

        if p.suffix.lower() != ".pdf":
            raise ValueError(f"File {p.name} is not a PDF file.")

        # Check for PyMuPDF (fitz) or pypdf
        try:
            import fitz  # PyMuPDF
            return self._ingest_with_fitz(p, equipment_model, synthetic)
        except ImportError:
            pass

        try:
            import pypdf
            return self._ingest_with_pypdf(p, equipment_model, synthetic)
        except ImportError:
            pass

        raise RuntimeError(
            "No PDF extraction library available (PyMuPDF or pypdf). "
            "Approval from Member B is required to install PDF dependencies."
        )

    def _ingest_with_fitz(
        self,
        p: Path,
        equipment_model: Optional[str],
        synthetic: bool,
    ) -> list[Chunk]:
        import fitz

        try:
            doc = fitz.open(str(p))
        except Exception as e:
            raise ValueError(f"Failed to open PDF {p}: {e}") from e

        doc_id = _deterministic_document_id(p.name)
        chunks: list[Chunk] = []

        for page_idx in range(len(doc)):
            page_num = page_idx + 1  # 1-based page index
            page = doc[page_idx]
            page_text = page.get_text().strip()

            if not page_text:
                logger.warning("Page %d of %s has no extractable text; skipping.", page_num, p.name)
                continue

            page_chunks = _chunk_text(
                page_text,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

            for c_idx, text_segment in enumerate(page_chunks):
                chunk_id = f"{doc_id}_p{page_num}_c{c_idx}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        filename=p.name,
                        page=page_num,
                        text=text_segment,
                        equipment_model=equipment_model,
                        synthetic=synthetic,
                    )
                )

        doc.close()
        return chunks

    def _ingest_with_pypdf(
        self,
        p: Path,
        equipment_model: Optional[str],
        synthetic: bool,
    ) -> list[Chunk]:
        import pypdf

        try:
            reader = pypdf.PdfReader(str(p))
        except Exception as e:
            raise ValueError(f"Failed to read PDF {p}: {e}") from e

        doc_id = _deterministic_document_id(p.name)
        chunks: list[Chunk] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()

            if not page_text:
                logger.warning("Page %d of %s has no extractable text; skipping.", page_idx, p.name)
                continue

            page_chunks = _chunk_text(
                page_text,
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

            for c_idx, text_segment in enumerate(page_chunks):
                chunk_id = f"{doc_id}_p{page_idx}_c{c_idx}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        filename=p.name,
                        page=page_idx,
                        text=text_segment,
                        equipment_model=equipment_model,
                        synthetic=synthetic,
                    )
                )

        return chunks

