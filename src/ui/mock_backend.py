"""In-memory mock backend conforming to BackendServiceProtocol for UI testing and offline development."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Answer, Chunk, Evidence, IndexingSummary


class MockBackendService:
    """Mock implementation of BackendServiceProtocol.

    Conforms to IndexingProtocol, RetrievalProtocol, and GenerationProtocol
    using in-memory stores and deterministic canned behaviors.
    """

    def __init__(self, collection_name: str = "mock_industrial_docs") -> None:
        self.collection_name = collection_name
        self._chunks: dict[str, Chunk] = {}

    def index_chunks(self, chunks: Sequence[Chunk]) -> IndexingSummary:
        """Indexes chunks into the in-memory store, tracking duplicates."""
        indexed_count = 0
        skipped_count = 0
        failed_count = 0
        errors: list[str] = []

        for chunk in chunks:
            if not isinstance(chunk, Chunk):
                failed_count += 1
                errors.append(f"Invalid chunk payload: {chunk}")
                continue

            existing = self._chunks.get(chunk.chunk_id)
            if existing is not None:
                if existing.text == chunk.text and existing.equipment_model == chunk.equipment_model:
                    skipped_count += 1
                    continue
                else:
                    # In-place metadata update
                    self._chunks[chunk.chunk_id] = chunk
                    indexed_count += 1
            else:
                self._chunks[chunk.chunk_id] = chunk
                indexed_count += 1

        return IndexingSummary(
            total_chunks_received=len(chunks),
            chunks_indexed=indexed_count,
            chunks_skipped=skipped_count,
            chunks_failed=failed_count,
            collection_name=self.collection_name,
            errors=errors,
        )

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        equipment_model: Optional[str] = None,
    ) -> list[Evidence]:
        """Retrieves top_k most relevant Evidence items based on token overlap."""
        if not question or not question.strip():
            raise ValueError("question must be non-empty and non-whitespace")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")

        if not self._chunks:
            return []

        q_tokens = set(re.findall(r"\w+", question.lower()))

        scored_chunks: list[tuple[int, Chunk]] = []
        for chunk in self._chunks.values():
            if equipment_model is not None and chunk.equipment_model is not None:
                if equipment_model.lower() not in chunk.equipment_model.lower():
                    continue

            c_tokens = set(re.findall(r"\w+", chunk.text.lower()))
            overlap = len(q_tokens.intersection(c_tokens))
            scored_chunks.append((overlap, chunk))

        # Sort descending by token overlap
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results: list[Evidence] = []
        for score, chunk in scored_chunks[:top_k]:
            if score > 0 or len(scored_chunks) <= top_k:
                source_id = f"{chunk.document_id}#p{chunk.page}#{chunk.chunk_id.split('#')[-1]}"
                results.append(Evidence(source_id=source_id, chunk=chunk))

        return results

    def answer_question(
        self,
        question: str,
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Answers query using mock evidence retrieval."""
        if not question or not question.strip():
            raise ValueError("question must be non-empty and non-whitespace")

        if not self._chunks:
            return Answer(
                text="No indexed documents available.",
                evidence=[],
                insufficient_evidence=True,
            )

        evidence = self.retrieve(question, top_k=3, equipment_model=equipment_model)

        # Check for unanswerable / unsupported questions
        negative_keywords = ["torque specification", "cylinder head bolt", "gearbox lubricant", "hydraulic pump rotor"]
        is_negative = any(kw in question.lower() for kw in negative_keywords)

        if not evidence or is_negative:
            return Answer(
                text="Retrieved SOP context does not substantiate an answer for this query.",
                evidence=[],
                insufficient_evidence=True,
            )

        citations = " ".join(f"[{ev.source_id}]" for ev in evidence)
        synthesis = (
            f"According to {citations}, the standard operating procedure indicates: "
            f"{evidence[0].chunk.text[:250]}..."
        )
        return Answer(
            text=synthesis,
            evidence=evidence,
            insufficient_evidence=False,
            observations=[],
        )

    def answer_with_image(
        self,
        question: str,
        image_path: Union[str, Path],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Answers query alongside image visual observations."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found at '{path}'")

        ans = self.answer_question(question, equipment_model=equipment_model)
        ans.observations = [
            f"Observed visual state from inspection file '{path.name}'",
            "Status LEDs and physical enclosure match normal operating conditions.",
        ]
        return ans

