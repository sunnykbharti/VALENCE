"""Centralized tool registry and dispatcher for VALENCE (Phase 2 Milestone 1B)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.tools.base import ToolResult
from backend.tools.inspect_image import InspectImageTool
from backend.tools.lookup_equipment import LookupEquipmentTool
from backend.tools.search_documents import SearchDocumentsTool
from backend.tools.ask_user import AskUserTool
from backend.tools.read_manual_page import ReadManualPageTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Manages available tools and dispatches validated tool invocations."""

    def __init__(self, backend_service=None) -> None:
        self.backend = backend_service
        self._tools: dict[str, Any] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Instantiates and registers the core validated tools."""
        self.register(InspectImageTool(self.backend))
        self.register(LookupEquipmentTool(self.backend))
        self.register(SearchDocumentsTool(self.backend))
        self.register(AskUserTool())
        self.register(ReadManualPageTool(self.backend))

    def register(self, tool: Any) -> None:
        """Registers a tool instance under its tool.name."""
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get_tool(self, name: str) -> Optional[Any]:
        """Retrieves a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """Returns names of all registered tools."""
        return sorted(list(self._tools.keys()))

    def get_tool_manifest(self) -> list[dict[str, Any]]:
        """Returns schemas and documentation for all registered tools."""
        manifest = []
        for name, tool in sorted(self._tools.items()):
            manifest.append({
                "name": name,
                "description": getattr(tool, "description", ""),
            })
        return manifest

    def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Dispatches an invocation to the named tool with typed error handling."""
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"NoSuchToolError: Tool '{name}' is not registered. Available: {self.list_tools()}",
            )

        try:
            return tool.execute(**kwargs)
        except TypeError as te:
            return ToolResult(
                success=False,
                error=f"InvalidArgumentError: Invalid arguments passed to '{name}': {te}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"ToolExecutionFailure: Tool '{name}' raised unexpected error: {e}",
            )

