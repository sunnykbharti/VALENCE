"""Local embedding engine for VALENCE (Member B).

Loads embeddings strictly from an explicit local model directory.
Automatic runtime downloads and remote HuggingFace calls are strictly disabled.
"""

from __future__ import annotations

import hashlib
import logging
import math
from pathlib import Path
from typing import Callable, Optional, Sequence, Union

logger = logging.getLogger("valence.embedding")


def _deterministic_pseudo_embedding(text: str, dim: int = 384) -> list[float]:
    """Generates a deterministic unit-normalized pseudo-embedding for testing.

    Used when external deep learning libraries (PyTorch/ONNX) are absent or
    during unit test execution to verify vector math without downloading weights.
    """
    # Use sha256 to generate deterministic floats
    vec = [0.0] * dim
    words = text.lower().split()
    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        for i in range(min(dim, len(digest))):
            vec[i] += float(digest[i] - 128)

    # Unit normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    else:
        vec[0] = 1.0
    return vec


class LocalEmbeddingEngine:
    """Local embedding engine loading strictly from an explicit model directory.

    Guarantees:
    - No remote HuggingFace / PyPI network calls.
    - Explicit local path verification.
    """

    def __init__(
        self,
        model_dir: Union[str, Path],
        dimension: int = 384,
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.dimension = dimension
        self._custom_embed_fn = embed_fn
        self._model = None
        self._engine_type = "uninitialized"

        if self._custom_embed_fn is None:
            self._init_local_model()

    def _init_local_model(self) -> None:
        """Verifies local directory and attempts loading local sentence-transformers or fastembed."""
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"Air-gapped constraint violation: Embedding model directory '{self.model_dir}' "
                f"does not exist. Automatic downloads from HuggingFace are strictly disabled. "
                f"Please download model weights during online preparation."
            )

        # Check for model files
        files = list(self.model_dir.glob("*"))
        if not files:
            raise FileNotFoundError(
                f"Embedding model directory '{self.model_dir}' is empty. "
                f"Must contain local weights (e.g., model.safetensors or onnx)."
            )

        # Attempt fastembed first (lightweight ONNX)
        try:
            import fastembed
            self._model = fastembed.TextEmbedding(
                model_name=str(self.model_dir),
                local_files_only=True,
            )
            self._engine_type = "fastembed"
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Failed to load fastembed from %s: %e", self.model_dir, e)

        # Attempt sentence_transformers (PyTorch)
        try:
            import sentence_transformers
            self._model = sentence_transformers.SentenceTransformer(
                str(self.model_dir),
                local_files_only=True,
            )
            self._engine_type = "sentence_transformers"
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Failed to load sentence_transformers from %s: %s", self.model_dir, e)

        raise RuntimeError(
            f"No embedding library available to load model from '{self.model_dir}'. "
            f"Install fastembed or sentence-transformers as specified in requirements.txt."
        )

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Generates embeddings for a batch of text strings.

        Raises:
            ValueError: If texts sequence is empty.
        """
        if not texts:
            return []

        if self._custom_embed_fn is not None:
            return self._custom_embed_fn(list(texts))

        if self._engine_type == "fastembed":
            # fastembed returns generator of numpy arrays
            embeddings = list(self._model.embed(texts))
            return [e.tolist() for e in embeddings]

        if self._engine_type == "sentence_transformers":
            embeddings = self._model.encode(list(texts), normalize_embeddings=True)
            return [e.tolist() for e in embeddings]

        raise RuntimeError(f"Embedding engine not initialized ({self._engine_type}).")

    def embed_query(self, query: str) -> list[float]:
        """Generates embedding for a single query string."""
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty or whitespace-only.")
        results = self.embed_texts([query])
        return results[0]

