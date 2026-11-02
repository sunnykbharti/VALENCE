"""Local backend runtime package for VALENCE (Member B)."""

from backend.mock_backend import MockBackend
from backend.service import RealBackend
from backend.embedding import LocalEmbeddingEngine
from backend.vector_store import PersistentVectorStore
from backend.retrieval import LocalRetriever
from backend.generation import LocalOllamaGenerator
from backend.vision import LocalVisionEngine, VisualInterpretation
from backend.diagnostics import run_diagnostics, DiagnosticReport
from backend.applicability import (
    ProposedCheck,
    EscalationDecision,
    validate_equipment_applicability,
    detect_contradictions,
    validate_proposed_checks,
    evaluate_incident_applicability,
)
from backend.handover import (
    HandoverReport,
    generate_handover,
    promote_incident_to_knowledge_chunk,
)
from backend.tools import (
    ToolResult,
    validate_safe_filesystem_path,
    ToolRegistry,
    InspectImageTool,
    LookupEquipmentTool,
    SearchDocumentsTool,
    AskUserTool,
    ReadManualPageTool,
)
from backend.orchestrator import (
    ALLOWED_ACTIONS,
    ActionSelection,
    OrchestratorEvent,
    OrchestratorResult,
    BoundedOrchestrator,
)

__all__ = [
    "MockBackend",
    "RealBackend",
    "LocalEmbeddingEngine",
    "PersistentVectorStore",
    "LocalRetriever",
    "LocalOllamaGenerator",
    "LocalVisionEngine",
    "VisualInterpretation",
    "run_diagnostics",
    "DiagnosticReport",
    "ProposedCheck",
    "EscalationDecision",
    "validate_equipment_applicability",
    "detect_contradictions",
    "validate_proposed_checks",
    "evaluate_incident_applicability",
    "HandoverReport",
    "generate_handover",
    "promote_incident_to_knowledge_chunk",
    "ToolResult",
    "validate_safe_filesystem_path",
    "ToolRegistry",
    "InspectImageTool",
    "LookupEquipmentTool",
    "SearchDocumentsTool",
    "AskUserTool",
    "ReadManualPageTool",
    "ALLOWED_ACTIONS",
    "ActionSelection",
    "OrchestratorEvent",
    "OrchestratorResult",
    "BoundedOrchestrator",
]
