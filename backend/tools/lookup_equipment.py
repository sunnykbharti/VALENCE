"""Tool for querying equipment specifications and matching manuals (Phase 2 Milestone 1B)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.tools.base import ToolResult


@dataclass(frozen=True)
class LookupEquipmentArgs:
    """Typed arguments for lookup_equipment tool."""
    equipment_model: str


class LookupEquipmentTool:
    """Tool that queries the local vector store for documentation applicable to an equipment model."""

    name: str = "lookup_equipment"
    description: str = (
        "Look up indexed technical manuals, specifications, and SOPs for a specific equipment model."
    )

    def __init__(self, backend_service) -> None:
        self.backend = backend_service

    def execute(self, equipment_model: str) -> ToolResult:
        """Executes equipment lookup."""
        if not equipment_model or not equipment_model.strip():
            return ToolResult(success=False, error="equipment_model must be a non-empty string.")

        clean_model = equipment_model.strip()

        try:
            # Query the backend with equipment filtering
            evidence = self.backend.retrieve(
                question=f"Specifications and operational overview for {clean_model}",
                top_k=5,
                equipment_model=clean_model,
            )

            matched_files = sorted(list({e.chunk.filename for e in evidence}))
            matched_docs = sorted(list({e.chunk.document_id for e in evidence}))

            return ToolResult(
                success=True,
                data={
                    "equipment_model": clean_model,
                    "matched_document_count": len(matched_docs),
                    "matched_documents": matched_docs,
                    "matched_files": matched_files,
                    "retrieved_chunk_count": len(evidence),
                },
                evidence=evidence,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"EquipmentLookupError: {e}")

