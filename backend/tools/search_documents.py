"""Tool for grounded semantic and keyword document search (Phase 2 Milestone 1B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.tools.base import ToolResult


@dataclass(frozen=True)
class SearchDocumentsArgs:
    """Typed arguments for search_documents tool."""
    query: str
    equipment_model: Optional[str] = None
    top_k: int = 5


class SearchDocumentsTool:
    """Tool that wraps local vector retrieval across indexed technical documentation."""

    name: str = "search_documents"
    description: str = (
        "Search indexed equipment manuals, troubleshooting guides, and SOPs for relevant text passages."
    )

    def __init__(self, backend_service) -> None:
        self.backend = backend_service

    def execute(
        self,
        query: str,
        equipment_model: Optional[str] = None,
        top_k: int = 5,
    ) -> ToolResult:
        """Executes grounded document search."""
        if not query or not query.strip():
            return ToolResult(success=False, error="query must not be empty or whitespace-only.")
        if top_k < 1:
            return ToolResult(success=False, error=f"top_k must be >= 1, got {top_k}")

        clean_query = query.strip()
        clean_model = equipment_model.strip() if equipment_model and equipment_model.strip() else None

        try:
            evidence = self.backend.retrieve(
                question=clean_query,
                top_k=top_k,
                equipment_model=clean_model,
            )

            results_summary = [
                {
                    "source_id": e.source_id,
                    "filename": e.chunk.filename,
                    "page": e.chunk.page,
                    "equipment_model": e.chunk.equipment_model,
                    "text_preview": e.chunk.text[:120] + "..." if len(e.chunk.text) > 120 else e.chunk.text,
                }
                for e in evidence
            ]

            return ToolResult(
                success=True,
                data={
                    "query": clean_query,
                    "equipment_filter": clean_model,
                    "results_count": len(evidence),
                    "items": results_summary,
                },
                evidence=evidence,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"DocumentSearchError: {e}")
