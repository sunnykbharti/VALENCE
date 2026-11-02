"""Deterministic chunking and identifier generation for industrial documents.

Preserves original 1-based page positions, generates stable deterministic IDs,
and respects document boundaries and metadata contracts.
"""

from __future__ import annotations

import logging
from typing import Optional
from contracts import Chunk

logger = logging.getLogger(__name__)


def split_text_into_segments(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Splits text into overlapping chunks respecting natural paragraph and word boundaries.

    Args:
        text: Input string to segment.
        chunk_size: Maximum character length per chunk.
        chunk_overlap: Character overlap between consecutive chunks.

    Returns:
        List of non-empty text strings.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= chunk_size:
        return [clean_text]

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 4)

    segments: list[str] = []
    start = 0
    total_len = len(clean_text)

    while start < total_len:
        end = min(start + chunk_size, total_len)

        if end < total_len:
            # Try to break at a paragraph boundary
            para_break = clean_text.rfind("\n\n", start + chunk_overlap, end)
            if para_break != -1:
                end = para_break + 2
            else:
                # Try to break at a newline boundary
                line_break = clean_text.rfind("\n", start + chunk_overlap, end)
                if line_break != -1:
                    end = line_break + 1
                else:
                    # Try to break at a sentence or word boundary
                    word_break = clean_text.rfind(" ", start + chunk_overlap, end)
                    if word_break != -1:
                        end = word_break + 1

        chunk_str = clean_text[start:end].strip()
        if chunk_str:
            segments.append(chunk_str)

        if end >= total_len:
            break

        start = max(start + 1, end - chunk_overlap)

    return segments


def create_chunks_from_pages(
    pages_text: dict[int, str],
    document_id: str,
    filename: str,
    equipment_model: Optional[str] = None,
    synthetic: bool = False,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """Converts page-by-page extracted text into a sequence of verified Chunk objects.

    Reporting unreadable / blank pages:
        Pages with no extractable text are omitted from the returned list[Chunk]
        and logged via standard Python logging (`logger.warning("Page %d has no extractable text", page)`).
        No empty or whitespace Chunks are ever emitted.

    Args:
        pages_text: Mapping from 1-based page numbers to extracted text.
        document_id: Deterministic document identifier.
        filename: Original file name.
        equipment_model: Identified equipment model or None.
        synthetic: True if synthetic test data; False for authentic documents.
        chunk_size: Target character chunk size.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of immutable Chunk instances.

    Raises:
        ValueError: If all pages are empty or completely unreadable.
    """
    chunks: list[Chunk] = []

    for page_num in sorted(pages_text.keys()):
        raw_text = pages_text[page_num]
        clean_text = raw_text.strip() if raw_text else ""

        if not clean_text:
            logger.warning("Page %d has no extractable text", page_num)
            continue

        segments = split_text_into_segments(clean_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for c_idx, seg in enumerate(segments):
            chunk_id = f"{document_id}#p{page_num}#c{c_idx}"
            chunk = Chunk(
                chunk_id=chunk_id,
                document_id=document_id,
                filename=filename,
                page=page_num,
                text=seg,
                equipment_model=equipment_model,
                synthetic=synthetic,
            )
            chunks.append(chunk)

    if not chunks:
        raise ValueError(f"PDF '{filename}' is completely unreadable or contains no extractable text")

    return chunks

