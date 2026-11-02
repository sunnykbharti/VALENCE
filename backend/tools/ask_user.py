"""Tool for interactive user clarification and confirmation (Phase 2 Milestone 1B)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from backend.tools.base import ToolResult


@dataclass(frozen=True)
class AskUserArgs:
    """Typed arguments for ask_user tool."""
    question: str
    options: Optional[list[str]] = None
    context: Optional[str] = None


class AskUserTool:
    """Tool that formats a structured clarification or confirmation request for the human operator."""

    name: str = "ask_user"
    description: str = (
        "Request clarification or confirmation from the human operator when equipment identity, "
        "revisions, or physical conditions are ambiguous."
    )

    def execute(
        self,
        question: str,
        options: Optional[Sequence[str]] = None,
        context: Optional[str] = None,
    ) -> ToolResult:
        """Executes clarification request formatting."""
        if not question or not question.strip():
            return ToolResult(success=False, error="question must not be empty or whitespace-only.")

        clean_q = question.strip()
        opts = list(options) if options else []

        return ToolResult(
            success=True,
            data={
                "type": "clarification_request",
                "question": clean_q,
                "options": opts,
                "context": context.strip() if context and context.strip() else None,
                "status": "pending_operator_response",
            },
            metadata={"requires_human_input": True},
        )

