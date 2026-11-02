"""Tool for reading raw manual pages on-demand (Phase 2 Milestone 1B).

Exposes exact backend capability:
Per Task 5: 'Add read_manual_page only if the current backend supports it;
otherwise expose it as unavailable rather than faking support.'
"""

from __future__ import annotations

from dataclasses import dataclass
from backend.tools.base import ToolResult


@dataclass(frozen=True)
class ReadManualPageArgs:
    """Typed arguments for read_manual_page tool."""
    document_id: str
    page: int


class ReadManualPageTool:
    """Tool that exposes raw manual page reading, returning explicit unavailable status if unsupported."""

    name: str = "read_manual_page"
    description: str = (
        "Read an exact original page from a manual given document_id and 1-based page number. "
        "Exposes unavailable error if the underlying backend does not provide on-demand page rendering."
    )

    def __init__(self, backend_service=None) -> None:
        self.backend = backend_service

    def execute(self, document_id: str, page: int) -> ToolResult:
        """Executes manual page lookup if supported, otherwise returns explicit UNAVAILABLE error."""
        if not document_id or not document_id.strip():
            return ToolResult(success=False, error="document_id must not be empty.")
        if page < 1:
            return ToolResult(success=False, error=f"page must be >= 1 (1-based), got {page}")

        # Check if underlying backend actually supports on-demand page lookup
        if self.backend is not None and hasattr(self.backend, "read_manual_page"):
            try:
                page_text = self.backend.read_manual_page(document_id=document_id.strip(), page=page)
                return ToolResult(
                    success=True,
                    data={
                        "document_id": document_id.strip(),
                        "page": page,
                        "text": page_text,
                    },
                )
            except Exception as e:
                return ToolResult(success=False, error=f"PageReadError: {e}")

        # Backend does not support direct page reading: report UNAVAILABLE rather than faking support
        return ToolResult(
            success=False,
            error=(
                f"UNAVAILABLE: read_manual_page is not supported by the local backend service "
                f"for document '{document_id}', page {page}. Use search_documents for indexed retrieval."
            ),
            data={"supported": False, "document_id": document_id, "page": page},
        )
