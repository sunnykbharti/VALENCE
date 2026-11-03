"""Unified local backend service for VALENCE (Member B).

Coordinates real local embeddings, persistent vector store, retrieval, and Ollama generation.
Conforms strictly to BackendServiceProtocol in contracts.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Answer, Chunk, Evidence, IndexingSummary
from config import RuntimeConfig, load_config
from backend.embedding import LocalEmbeddingEngine
from backend.vector_store import PersistentVectorStore
from backend.retrieval import LocalRetriever
from backend.generation import LocalOllamaGenerator
from backend.vision import LocalVisionEngine, VisualInterpretation

logger = logging.getLogger("valence.backend")


class RealBackend:
    """Production local backend engine running air-gapped on device.

    Coordinates:
    - Local embedding generation (without remote downloads)
    - Persistent Qdrant / disk-backed vector storage
    - Local retrieval with metadata-grounded Evidence
    - Local Ollama LLM text generation
    """

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        embedding_engine: Optional[LocalEmbeddingEngine] = None,
        vector_store: Optional[PersistentVectorStore] = None,
        generator: Optional[LocalOllamaGenerator] = None,
        vision_engine: Optional[LocalVisionEngine] = None,
    ) -> None:
        self.config = config or load_config()

        # Initialize Embedding Engine
        if embedding_engine is not None:
            self.embedding_engine = embedding_engine
        else:
            try:
                self.embedding_engine = LocalEmbeddingEngine(
                    model_dir=self.config.embedding_model_dir,
                )
            except FileNotFoundError as e:
                from backend.embedding import _deterministic_pseudo_embedding
                logger.warning(
                    "Local embedding model directory '%s' not found (%s). "
                    "Operating with deterministic local pseudo-embedding fallback.",
                    self.config.embedding_model_dir,
                    e,
                )
                self.embedding_engine = LocalEmbeddingEngine(
                    model_dir=self.config.embedding_model_dir,
                    dimension=384,
                    embed_fn=lambda texts: [_deterministic_pseudo_embedding(t, dim=384) for t in texts],
                )

        # Initialize Persistent Vector Store
        self.vector_store = vector_store or PersistentVectorStore(
            storage_path=self.config.index_dir,
            collection_name=self.config.collection_name,
            vector_dim=self.embedding_engine.dimension,
        )

        # Initialize Retriever
        self.retriever = LocalRetriever(
            embedding_engine=self.embedding_engine,
            vector_store=self.vector_store,
        )

        # Initialize Generator
        self.generator = generator or LocalOllamaGenerator(
            base_url=self.config.ollama_base_url,
            model=self.config.llm_model,
        )

        # Initialize Vision Engine (Milestone 3B)
        self.vision_engine = vision_engine or LocalVisionEngine(
            base_url=self.config.ollama_base_url,
            model=self.config.vlm_model,
        )

    def index_chunks(self, chunks: Sequence[Chunk]) -> IndexingSummary:
        """Indexes chunks into local persistent vector store."""
        if not chunks:
            return IndexingSummary(
                total_chunks_received=0,
                chunks_indexed=0,
                chunks_skipped=0,
                chunks_failed=0,
                collection_name=self.config.collection_name,
                errors=[],
            )

        texts = [c.text for c in chunks]
        embeddings = self.embedding_engine.embed_texts(texts)
        return self.vector_store.index_chunks_with_embeddings(chunks, embeddings)

    def delete_document(
        self,
        filename: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> int:
        """Purges document chunks from the persistent vector store."""
        return self.vector_store.delete_document_chunks(filename=filename, document_id=document_id)

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        equipment_model: Optional[str] = None,
    ) -> list[Evidence]:
        """Retrieves inspectable Evidence instances matching question."""
        return self.retriever.retrieve(
            question=question,
            top_k=top_k,
            equipment_model=equipment_model,
        )

    def answer_question(
        self,
        question: str,
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Generates grounded answer citing retrieved evidence."""
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        evidence = self.retrieve(question, top_k=3, equipment_model=equipment_model)
        return self.generator.answer_with_evidence(
            question=question,
            evidence=evidence,
            equipment_model=equipment_model,
        )

    def answer_with_image(
        self,
        question: str,
        image_path: Union[str, Path],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Grounds question in retrieved evidence informed by visual observations.

        - Extracts visible text, labels, and gauge readings.
        - Keeps visual observations separate from retrieved SOP guidance.
        - Resolves equipment ambiguity and detects user vs image model conflicts.
        - Preserves text-only operation if vision fails.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        img = Path(image_path)
        if not img.exists():
            raise FileNotFoundError(f"Inspection image not found at: {img}")

        if img.stat().st_size == 0:
            raise ValueError(f"Image at '{img}' is empty or corrupt (0 bytes).")

        # 1. Process image with local vision engine
        visual_result = self.vision_engine.inspect_image(img, question)

        effective_model = equipment_model
        # 2. Check for conflict between supplied equipment_model and visually detected model
        if equipment_model is not None:
            if visual_result.detected_equipment and visual_result.detected_equipment.lower() != equipment_model.lower():
                visual_result.observations.append(
                    f"CONFLICT DETECTED: Supplied equipment model '{equipment_model}' conflicts with visible nameplate "
                    f"'{visual_result.detected_equipment}'. Manual retrieval not silently overridden."
                )
                # Keep user's requested model
                effective_model = equipment_model
        else:
            # User did not supply model; check if vision unambiguously detected one
            if visual_result.detected_equipment and not visual_result.is_ambiguous:
                effective_model = visual_result.detected_equipment
                visual_result.observations.append(
                    f"Tentative equipment filter '{effective_model}' applied based on visible nameplate."
                )
            elif visual_result.is_ambiguous:
                effective_model = None
                visual_result.observations.append(
                    "Equipment identity is ambiguous from image; omitting model filter to prevent misapplication."
                )

        # 3. Inform retrieval: construct query incorporating visual observations
        key_visual_terms = " ".join(
            obs.replace("Tentative observation:", "").strip()
            for obs in visual_result.observations
            if "CONFLICT" not in obs and "unavailable" not in obs
        )
        enriched_query = f"{question} {key_visual_terms}".strip()

        evidence = self.retrieve(enriched_query, top_k=3, equipment_model=effective_model)
        # Fall back to base question if enriched query returned nothing
        if not evidence and enriched_query != question:
            evidence = self.retrieve(question, top_k=3, equipment_model=effective_model)

        # 4. Synthesize Answer
        if not evidence:
            model_info = f" for equipment '{effective_model}'" if effective_model else ""
            return Answer(
                text=f"Insufficient documentary evidence found in manuals{model_info} to answer query with image '{img.name}'.",
                evidence=[],
                insufficient_evidence=True,
                observations=visual_result.observations,
            )

        base_answer = self.generator.answer_with_evidence(
            question=question,
            evidence=evidence,
            equipment_model=effective_model,
        )

        # 5. Visual observations remain distinctly populated
        base_answer.observations = visual_result.observations
        return base_answer

    def inspect_crop(
        self,
        image_path: Union[str, Path],
        box_pct: tuple[float, float, float, float],
        user_question: Optional[str] = None,
    ) -> tuple[CropInspectionResult, Path]:
        """Crops user-selected image region and performs local visual inspection.

        Returns:
            (CropInspectionResult, cropped_image_path)
        """
        from src.utils.image_crop import crop_image_region

        crop_path, crop_id, crop_coords = crop_image_region(image_path, box_pct)
        result = self.vision_engine.inspect_crop(
            crop_path=crop_path,
            crop_id=crop_id,
            crop_coords=crop_coords,
            user_question=user_question,
        )
        return result, crop_path

    def evaluate_applicability(
        self,
        incident: Incident,
        proposed_checks: Optional[Sequence[ProposedCheck]] = None,
    ) -> EscalationDecision:
        """Evaluates applicability and escalation rules for an incident."""
        from backend.applicability import evaluate_incident_applicability
        return evaluate_incident_applicability(incident, proposed_checks)

    def generate_handover(
        self,
        incident: Incident,
        escalation: Optional[EscalationDecision] = None,
    ) -> HandoverReport:
        """Generates an auditable handover report from persisted incident facts."""
        from backend.handover import generate_handover
        return generate_handover(incident, escalation)

    @property
    def agent_executor(self):
        if getattr(self, "_agent_executor", None) is None:
            from backend.agent import AgentExecutor
            from src.services import create_incident_service
            self._agent_executor = AgentExecutor(backend=self, incident_service=create_incident_service(mock=True))
        return self._agent_executor

    def set_incident_service(self, incident_service) -> None:
        """Configures or updates the incident service used by the agent executor."""
        if getattr(self, "_agent_executor", None) is None:
            from backend.agent import AgentExecutor
            self._agent_executor = AgentExecutor(backend=self, incident_service=incident_service)
        else:
            self._agent_executor.incident_service = incident_service

    def start_investigation(self, incident_id: str, query: Optional[str] = None, incident_service=None):
        """Initiates an automated agent investigation workflow for an incident."""
        if incident_service is not None:
            self.set_incident_service(incident_service)
        return self.agent_executor.start_investigation(incident_id=incident_id, query=query)

    def resume_investigation(self, execution_id: str, user_response: str, incident_service=None):
        """Resumes an investigation paused for operator clarification."""
        if incident_service is not None:
            self.set_incident_service(incident_service)
        return self.agent_executor.resume_investigation(execution_id=execution_id, user_response=user_response)

    def cancel_execution(self, execution_id: str):
        """Cancels or pauses active execution."""
        return self.agent_executor.cancel_execution(execution_id=execution_id)

    def get_execution(self, execution_id: str):
        """Fetches existing execution by ID."""
        return self.agent_executor.get_execution(execution_id=execution_id)



