"""Local environment and model diagnostics for VALENCE (Member B).

Provides actionable diagnostics for missing model weights, unreachable local
runtimes, and uninitialized directories before execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import RuntimeConfig, load_config


@dataclass
class DiagnosticCheck:
    """Individual diagnostic check result."""
    name: str
    passed: bool
    message: str
    actionable_fix: Optional[str] = None


@dataclass
class DiagnosticReport:
    """Consolidated diagnostic report."""
    checks: list[DiagnosticCheck] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        lines = ["=== VALENCE Local Runtime Diagnostics ==="]
        for c in self.checks:
            status = "PASS" if c.passed else "FAIL"
            lines.append(f"[{status}] {c.name}: {c.message}")
            if not c.passed and c.actionable_fix:
                lines.append(f"       -> Action required: {c.actionable_fix}")
        lines.append("==========================================")
        return "\n".join(lines)


def check_embedding_model(path: Path) -> DiagnosticCheck:
    """Verifies existence of local sentence-transformer model directory."""
    if not path.exists():
        return DiagnosticCheck(
            name="Embedding Model Directory",
            passed=False,
            message=f"Directory '{path}' does not exist.",
            actionable_fix=(
                f"During online preparation, download embedding model weights into '{path}'. "
                f"Example: git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 {path}"
            ),
        )

    # Check for typical weight/config markers
    model_files = [f.name for f in path.glob("*") if f.is_file()]
    has_weights = any(
        f.endswith((".safetensors", ".bin", ".onnx", ".json"))
        for f in model_files
    )
    if not has_weights:
        return DiagnosticCheck(
            name="Embedding Model Weights",
            passed=False,
            message=f"Directory '{path}' contains no model weight files.",
            actionable_fix=f"Populate '{path}' with valid model weights (config.json, model.safetensors, etc.).",
        )

    return DiagnosticCheck(
        name="Embedding Model Directory",
        passed=True,
        message=f"Found model directory with {len(model_files)} files at '{path}'.",
    )


def check_index_directory(path: Path) -> DiagnosticCheck:
    """Verifies that vector index storage directory exists or can be created."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return DiagnosticCheck(
            name="Vector Index Directory",
            passed=True,
            message=f"Index storage directory is ready at '{path}'.",
        )
    except Exception as e:
        return DiagnosticCheck(
            name="Vector Index Directory",
            passed=False,
            message=f"Cannot access or create '{path}': {e}",
            actionable_fix=f"Ensure write permissions exist for '{path}'.",
        )


def check_ollama_daemon(base_url: str) -> tuple[DiagnosticCheck, list[str]]:
    """Pings local Ollama daemon and fetches installed models."""
    tags_url = f"{base_url.rstrip('/')}/api/tags"
    req = Request(tags_url, headers={"User-Agent": "VALENCE-Diagnostics"})

    try:
        with urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                return (
                    DiagnosticCheck(
                        name="Ollama Local Daemon",
                        passed=True,
                        message=f"Daemon reachable at '{base_url}'. {len(models)} model(s) installed.",
                    ),
                    models,
                )
    except URLError as e:
        return (
            DiagnosticCheck(
                name="Ollama Local Daemon",
                passed=False,
                message=f"Cannot connect to local Ollama daemon at '{base_url}': {e}",
                actionable_fix="Start the local Ollama daemon by running 'ollama serve' in a terminal.",
            ),
            [],
        )
    except Exception as e:
        return (
            DiagnosticCheck(
                name="Ollama Local Daemon",
                passed=False,
                message=f"Unexpected error connecting to '{base_url}': {e}",
                actionable_fix="Verify Ollama installation and ensure localhost:11434 is accessible.",
            ),
            [],
        )

    return (
        DiagnosticCheck(
            name="Ollama Local Daemon",
            passed=False,
            message=f"Unexpected response from '{tags_url}'.",
            actionable_fix="Verify local Ollama service status.",
        ),
        [],
    )


def check_model_installed(model_name: str, installed_models: list[str], role: str) -> DiagnosticCheck:
    """Verifies whether a specific required model is pulled locally."""
    # Ollama names can include tag (e.g. 'llama3.2:3b' or 'llama3.2:3b-instruct')
    target = model_name.lower().split(":")[0]
    matched = any(target in m.lower() for m in installed_models)

    if matched:
        return DiagnosticCheck(
            name=f"Local {role} Model ({model_name})",
            passed=True,
            message=f"Model '{model_name}' is available locally.",
        )

    return DiagnosticCheck(
        name=f"Local {role} Model ({model_name})",
        passed=False,
        message=f"Model '{model_name}' is not found in local Ollama repository.",
        actionable_fix=f"Run 'ollama pull {model_name}' during online preparation before operating offline.",
    )


def run_diagnostics(config: Optional[RuntimeConfig] = None) -> DiagnosticReport:
    """Executes all diagnostics and returns a consolidated report."""
    cfg = config or load_config()
    checks: list[DiagnosticCheck] = []

    # 1. Embedding Model
    checks.append(check_embedding_model(cfg.embedding_model_dir))

    # 2. Vector Index Directory
    checks.append(check_index_directory(cfg.index_dir))

    # 3. Local Ollama Daemon & Models
    ollama_check, installed_models = check_ollama_daemon(cfg.ollama_base_url)
    checks.append(ollama_check)

    if ollama_check.passed:
        checks.append(check_model_installed(cfg.llm_model, installed_models, "LLM"))
        checks.append(check_model_installed(cfg.vlm_model, installed_models, "VLM"))
    else:
        checks.append(
            DiagnosticCheck(
                name=f"Local LLM Model ({cfg.llm_model})",
                passed=False,
                message="Skipped check because Ollama daemon is unreachable.",
                actionable_fix="Start Ollama daemon first.",
            )
        )
        checks.append(
            DiagnosticCheck(
                name=f"Local VLM Model ({cfg.vlm_model})",
                passed=False,
                message="Skipped check because Ollama daemon is unreachable.",
                actionable_fix="Start Ollama daemon first.",
            )
        )

    return DiagnosticReport(checks=checks)

