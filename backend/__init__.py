"""Local backend runtime package for VALENCE (Member B)."""

from backend.mock_backend import MockBackend
from backend.service import RealBackend
from backend.embedding import LocalEmbeddingEngine
from backend.vector_store import PersistentVectorStore
from backend.retrieval import LocalRetriever
from backend.generation import LocalOllamaGenerator
from backend.diagnostics import run_diagnostics, DiagnosticReport

__all__ = [
    "MockBackend",
    "RealBackend",
    "LocalEmbeddingEngine",
    "PersistentVectorStore",
    "LocalRetriever",
    "LocalOllamaGenerator",
    "run_diagnostics",
    "DiagnosticReport",
]
