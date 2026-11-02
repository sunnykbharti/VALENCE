"""Tool for local visual inspection of equipment images (Phase 2 Milestone 1B)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from backend.tools.base import ToolResult, validate_safe_filesystem_path


@dataclass(frozen=True)
class InspectImageArgs:
    """Typed arguments for inspect_image tool."""
    image_path: str
    question: str = "Inspect visible equipment label, indicators, and physical condition"


class InspectImageTool:
    """Tool that wraps local vision interpreter with strict path sandboxing."""

    name: str = "inspect_image"
    description: str = (
        "Inspect an equipment image to identify visible nameplate labels, model numbers, "
        "and physical condition cues. Rejects unauthorized filesystem paths."
    )

    def __init__(self, backend_service) -> None:
        self.backend = backend_service

    def execute(self, image_path: str, question: Optional[str] = None) -> ToolResult:
        """Executes visual inspection with path validation."""
        q = question or "Inspect visible equipment label and physical condition"
        if not image_path or not image_path.strip():
            return ToolResult(success=False, error="image_path must be a non-empty string.")

        # 1. Enforce path security
        try:
            safe_path = validate_safe_filesystem_path(image_path)
        except PermissionError as pe:
            return ToolResult(success=False, error=f"SecurityError: {pe}")
        except FileNotFoundError as fe:
            return ToolResult(success=False, error=f"FileNotFoundError: {fe}")
        except Exception as ex:
            return ToolResult(success=False, error=f"PathValidationError: {ex}")

        # 2. Invoke backend vision engine
        try:
            if hasattr(self.backend, "vision_engine") and self.backend.vision_engine:
                visual_result = self.backend.vision_engine.interpret_equipment_image(
                    image_path=safe_path,
                    prompt_context=q,
                )
                return ToolResult(
                    success=True,
                    data={
                        "image_path": str(safe_path),
                        "detected_equipment": visual_result.detected_equipment,
                        "is_ambiguous": visual_result.is_ambiguous,
                        "confidence_note": visual_result.confidence_note,
                    },
                    observations=visual_result.observations,
                )
            elif hasattr(self.backend, "answer_with_image"):
                ans = self.backend.answer_with_image(question=q, image_path=safe_path)
                return ToolResult(
                    success=True,
                    data={
                        "image_path": str(safe_path),
                        "summary_text": ans.text,
                        "insufficient_evidence": ans.insufficient_evidence,
                    },
                    evidence=ans.evidence,
                    observations=ans.observations,
                )
            else:
                return ToolResult(
                    success=False,
                    error="Vision processing unavailable: Backend does not expose vision engine or answer_with_image.",
                )
        except Exception as e:
            return ToolResult(success=False, error=f"VisionExecutionError: {e}")

