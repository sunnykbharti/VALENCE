"""Explicit deterministic mock backend implementation for VALENCE (Member B).

Conforms strictly to contracts.py and BackendServiceProtocol.
Provides transparent in-memory indexing, deterministic lexical retrieval,
and synthetic answering for decoupled development and smoke testing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Answer, Chunk, Evidence, IndexingSummary


_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "let's", "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    "often", "check", "please", "tell",
}


def _content_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if t not in _STOPWORDS and len(t) > 2}


class MockBackend:
    """Deterministic, in-memory mock engine.

    All outputs are explicitly labeled as mock inference so they cannot
    be mistaken for real model outputs.
    """

    def __init__(self, collection_name: str = "mock_collection") -> None:
        self.collection_name = collection_name
        # Map of chunk_id -> Chunk
        self._store: dict[str, Chunk] = {}

    def index_chunks(self, chunks: Sequence[Chunk]) -> IndexingSummary:
        """Stores chunks in-memory with deterministic duplicate handling.

        Invariant:
            total_chunks_received == chunks_indexed + chunks_skipped + chunks_failed
        """
        indexed = 0
        skipped = 0
        failed = 0
        errors: list[str] = []

        for chunk in chunks:
            try:
                # Basic validation
                if not isinstance(chunk, Chunk):
                    failed += 1
                    errors.append(f"Invalid chunk type: {type(chunk)}")
                    continue

                if chunk.chunk_id in self._store:
                    existing = self._store[chunk.chunk_id]
                    # Check if identical (unchanged re-indexing)
                    if (
                        existing.text == chunk.text
                        and existing.document_id == chunk.document_id
                        and existing.page == chunk.page
                        and existing.equipment_model == chunk.equipment_model
                        and existing.synthetic == chunk.synthetic
                    ):
                        skipped += 1
                        continue
                    else:
                        # Metadata or text change -> reconcile in-place
                        self._store[chunk.chunk_id] = chunk
                        indexed += 1
                else:
                    self._store[chunk.chunk_id] = chunk
                    indexed += 1
            except Exception as e:
                failed += 1
                errors.append(f"Failed to process chunk '{getattr(chunk, 'chunk_id', 'unknown')}': {e}")

        total = len(chunks)
        return IndexingSummary(
            total_chunks_received=total,
            chunks_indexed=indexed,
            chunks_skipped=skipped,
            chunks_failed=failed,
            collection_name=self.collection_name,
            errors=errors,
        )

    def retrieve(
        self,
        question: str,
        top_k: int = 5,
        equipment_model: Optional[str] = None,
    ) -> list[Evidence]:
        """Retrieves top_k most relevant Evidence items using simple deterministic lexical overlap.

        Raises:
            ValueError: If question is empty/whitespace or top_k < 1.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")
        if top_k < 1:
            raise ValueError(f"top_k must be an integer >= 1, got {top_k}")

        q_tokens = _content_tokens(question)
        if not q_tokens:
            return []

        # Count document frequencies across store for BM25 IDF weighting
        total_docs = max(1, len(self._store))
        doc_freqs: dict[str, int] = {}
        for chunk in self._store.values():
            tokens = _content_tokens(chunk.text)
            for t in tokens:
                doc_freqs[t] = doc_freqs.get(t, 0) + 1

        # Extract search phrases
        clean_q = re.sub(r"[^\w\s]", " ", question.lower())
        q_words = [w for w in clean_q.split() if w not in _STOPWORDS and len(w) > 2]
        phrases = [f"{q_words[i]} {q_words[i+1]}" for i in range(len(q_words) - 1)]

        scored_chunks: list[tuple[float, Chunk]] = []
        for chunk in self._store.values():
            # If equipment_model filter is provided, chunk must match
            if equipment_model is not None:
                if chunk.equipment_model != equipment_model:
                    continue

            c_words = [t for t in re.findall(r"\w+", chunk.text.lower()) if t not in _STOPWORDS and len(t) > 2]
            c_counts: dict[str, int] = {}
            for w in c_words:
                c_counts[w] = c_counts.get(w, 0) + 1

            score = 0.0
            for t in q_tokens.intersection(set(c_words)):
                tf = c_counts[t]
                df = doc_freqs.get(t, 1)
                import math
                idf = math.log((total_docs + 1) / (df + 1)) + 1.0
                score += (tf / (tf + 1.2)) * idf

            c_lower = chunk.text.lower()
            for p in phrases:
                if p in c_lower:
                    score += 5.0

            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort by score descending, then deterministically by chunk_id
        scored_chunks.sort(key=lambda item: (-item[0], item[1].chunk_id))

        results: list[Evidence] = []
        for _, chunk in scored_chunks[:top_k]:
            source_id = f"{chunk.document_id}#p{chunk.page}#c{chunk.chunk_id[-4:]}"
            results.append(Evidence(source_id=source_id, chunk=chunk))

        return results

    def answer_question(
        self,
        question: str,
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Generates deterministic mock answer citing retrieved evidence.

        Raises:
            ValueError: If question is empty or whitespace-only.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        evidence = self.retrieve(question, top_k=3, equipment_model=equipment_model)

        # Documentary support check: if no evidence found, declare insufficient_evidence
        if not evidence:
            model_info = f" for equipment '{equipment_model}'" if equipment_model else ""
            return Answer(
                text=f"MOCK INFERENCE (NOT REAL LLM OUTPUT): Insufficient documentary evidence found{model_info} to answer: '{question}'.",
                evidence=[],
                insufficient_evidence=True,
                observations=[],
            )

        # Construct citation references that map strictly to retrieved evidence
        selected_evidence = evidence[:2]
        citation_tokens = " ".join(f"[{e.source_id}]" for e in selected_evidence)
        first_chunk_text = selected_evidence[0].chunk.text
        q_lower = question.lower()
        chunk_lower = first_chunk_text.lower()

        # Check for LED status diagnostics in evidence
        if "solid yellow" in q_lower and "cpu in stop" in chunk_lower:
            guidance = "a solid yellow RUN/STOP LED indicates that the CPU is in STOP mode. Always cross-reference with the diagnostic buffer before acting."
        elif "solid green" in q_lower and "cpu in run" in chunk_lower:
            guidance = "a solid green RUN/STOP LED indicates that the CPU is in RUN mode."
        elif "alternating" in q_lower and "startup" in chunk_lower:
            guidance = "an alternating yellow/green RUN/STOP LED indicates that the CPU is in STARTUP mode."
        elif "flashing red" in q_lower and "error" in chunk_lower:
            guidance = "a flashing red ERROR LED indicates an error such as internal fault, memory card error, or configuration error."
        else:
            # Extract the most salient sentence from the chunk
            sentences = [s.strip() for s in re.split(r"[\n\.]+", first_chunk_text) if len(s.strip()) > 10]
            q_toks = _content_tokens(question)
            best_sentence = None
            if sentences and q_toks:
                scored_sentences = [
                    (len(q_toks.intersection(_content_tokens(s))), s)
                    for s in sentences
                ]
                scored_sentences.sort(key=lambda x: -x[0])
                if scored_sentences and scored_sentences[0][0] >= 2:
                    best_sentence = scored_sentences[0][1]

            if best_sentence:
                guidance = f"the relevant procedure states: \"{best_sentence}\"."
            else:
                first_chunk_preview = first_chunk_text[:80].replace("\n", " ")
                guidance = f"the relevant procedure states: \"{first_chunk_preview}...\". "

        mock_text = (
            f"MOCK INFERENCE (NOT REAL LLM OUTPUT): Based on {citation_tokens}, "
            f"{guidance} "
            f"Verify all safety precautions before proceeding."
        )

        return Answer(
            text=mock_text,
            evidence=selected_evidence,
            insufficient_evidence=False,
            observations=[],
        )

    def answer_with_image(
        self,
        question: str,
        image_path: Union[str, Path],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Generates deterministic mock visual observations and SOP grounding.

        Raises:
            ValueError: If question is empty/whitespace or image is invalid.
            FileNotFoundError: If image_path does not exist.
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty or whitespace-only.")

        img = Path(image_path)
        if not img.exists():
            raise FileNotFoundError(f"Inspection image not found at: {img}")

        if img.stat().st_size == 0:
            raise ValueError(f"Image file at '{img}' is empty or corrupt.")

        # Perform mock retrieval for grounding
        evidence = self.retrieve(question, top_k=2, equipment_model=equipment_model)

        observations = [
            f"MOCK OBSERVATION: Inspection image '{img.name}' loaded successfully.",
            f"MOCK OBSERVATION: Surface wear indicator detected at component quadrant 2.",
            f"MOCK OBSERVATION: Gauge reading appears within nominal range according to preliminary visual check.",
        ]

        if not evidence:
            return Answer(
                text=f"MOCK INFERENCE (NOT REAL LLM OUTPUT): Insufficient documentary support found for visual inspection of '{img.name}'.",
                evidence=[],
                insufficient_evidence=True,
                observations=observations,
            )

        citation = f"[{evidence[0].source_id}]"
        mock_text = (
            f"MOCK INFERENCE (NOT REAL LLM OUTPUT): Image analysis of '{img.name}' compared against SOP reference {citation}. "
            f"The observed condition corresponds to standard operating parameters."
        )

        return Answer(
            text=mock_text,
            evidence=evidence[:1],
            insufficient_evidence=False,
            observations=observations,
        )

    def evaluate_applicability(
        self,
        incident,
        proposed_checks=None,
    ):
        """Evaluates applicability and escalation rules for an incident."""
        from backend.applicability import evaluate_incident_applicability
        return evaluate_incident_applicability(incident, proposed_checks)

    def generate_handover(
        self,
        incident,
        escalation=None,
    ):
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


