"""Configuration management for VALENCE local runtime (Member B).

Enforces air-gapped constraints, loopback-only endpoints, and local paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# Permitted loopback hostnames / IPs for air-gapped single-machine execution
ALLOWED_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_loopback_url(url: str) -> bool:
    """Validates that a URL targets exclusively a local loopback interface."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return hostname in ALLOWED_LOOPBACK_HOSTS
    except Exception:
        return False


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime configuration container with strict offline validation.

    Attributes:
        ollama_base_url: Loopback URL for local Ollama daemon.
        llm_model: Local text generation model identifier.
        vlm_model: Local vision-language model identifier.
        embedding_model_dir: Path to directory containing local embedding weights.
        index_dir: Path to local persistent vector store.
        collection_name: Qdrant collection name.
        mock_mode: Whether to run in explicit mock mode (no real inference).
    """
    ollama_base_url: str
    llm_model: str
    vlm_model: str
    embedding_model_dir: Path
    index_dir: Path
    collection_name: str
    mock_mode: bool

    def __post_init__(self) -> None:
        # Enforce loopback endpoint constraint
        if not is_loopback_url(self.ollama_base_url):
            raise ValueError(
                f"Air-gapped constraint violation: Inference endpoint must be a loopback address "
                f"({', '.join(sorted(ALLOWED_LOOPBACK_HOSTS))}). "
                f"Got non-loopback URL: '{self.ollama_base_url}'. "
                f"Remote endpoints, LAN addresses, and external hosts are strictly forbidden."
            )

        if not self.llm_model or not self.llm_model.strip():
            raise ValueError("llm_model must be a non-empty string.")

        if not self.vlm_model or not self.vlm_model.strip():
            raise ValueError("vlm_model must be a non-empty string.")

        if not self.collection_name or not self.collection_name.strip():
            raise ValueError("collection_name must be a non-empty string.")


def load_config() -> RuntimeConfig:
    """Loads runtime configuration from environment variables or safe defaults."""
    # Load .env file if present
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3.2:3b")
    vlm_model = os.getenv("OLLAMA_VLM_MODEL", "qwen2.5vl:7b")
    embed_dir = Path(os.getenv("EMBEDDING_MODEL_DIR", "models/all-MiniLM-L6-v2"))
    index_dir = Path(os.getenv("QDRANT_STORAGE_PATH", "data/qdrant_storage"))
    collection = os.getenv("QDRANT_COLLECTION_NAME", "industrial_docs")

    # MOCK_MODE defaults to True unless explicitly disabled via VALENCE_MOCK_MODE=0/false
    raw_mock = os.getenv("VALENCE_MOCK_MODE", "1").lower().strip()
    mock_mode = raw_mock not in ("0", "false", "no")

    return RuntimeConfig(
        ollama_base_url=ollama_url,
        llm_model=llm_model,
        vlm_model=vlm_model,
        embedding_model_dir=embed_dir,
        index_dir=index_dir,
        collection_name=collection,
        mock_mode=mock_mode,
    )

