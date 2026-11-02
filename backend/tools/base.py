"""Base classes, structured results, and security validation for VALENCE tools.

Enforces air-gapped security:
- Rejects arbitrary model-supplied filesystem paths outside approved directories.
- Validates typed arguments and returns standardized ToolResult dataclasses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from contracts import Evidence


@dataclass(frozen=True)
class ToolResult:
    """Standardized structured result returned by every tool.

    Attributes:
        success: True if tool executed successfully; False if error occurred.
        data: Arbitrary structured payload returned by the tool.
        error: Human-readable error description if success=False.
        evidence: List of supporting Evidence objects, if applicable.
        observations: List of tentative visual observations, if applicable.
        metadata: Additional diagnostic information.
    """
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    evidence: list[Evidence] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_safe_filesystem_path(
    user_path: Union[str, Path],
    allowed_roots: Optional[Sequence[Union[str, Path]]] = None,
) -> Path:
    """Validates that a path does not escape authorized workspace directories.

    Args:
        user_path: The path provided by a caller or LLM.
        allowed_roots: Sequence of allowed base directory paths.
                       Defaults to workspace directories: data, tests/fixtures, models.

    Raises:
        SecurityError: If path contains traversal sequences or points outside allowed roots.
        FileNotFoundError: If the target file does not exist.
    """
    if allowed_roots is None:
        allowed_roots = [
            Path("data").resolve(),
            Path("tests/fixtures").resolve(),
            Path("models").resolve(),
        ]
    else:
        allowed_roots = [Path(r).resolve() for r in allowed_roots]

    raw_path = Path(user_path)

    # Check for obvious traversal tokens before resolving
    path_str = str(user_path)
    if ".." in path_str.split(os.sep) or path_str.startswith("~"):
        raise PermissionError(
            f"Security violation: Path traversal sequence ('..') detected in path: '{user_path}'"
        )

    # Resolve absolute canonical path
    resolved = raw_path.resolve()

    # Verify that resolved path is within at least one allowed root
    is_allowed = any(
        resolved == root or root in resolved.parents
        for root in allowed_roots
    )

    if not is_allowed:
        allowed_str = ", ".join(str(r) for r in allowed_roots)
        raise PermissionError(
            f"Security violation: Path '{user_path}' resolves to '{resolved}', which is outside "
            f"the authorized directories: [{allowed_str}]."
        )

    if not resolved.exists():
        raise FileNotFoundError(f"Validated file path does not exist: '{resolved}'")

    return resolved

