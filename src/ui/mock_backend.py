"""In-memory mock backend conforming to BackendServiceProtocol for UI testing and offline development."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Answer, Chunk, Evidence, IndexingSummary

# Supported image extensions (validated at the UI layer; checked here for parity)
_SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

# Maximum image size accepted by the mock (mirrors real model limits)
_MAX_IMAGE_SIZE_MB = 20

# Mock vision response profiles keyed on filename substrings
_VISION_PROFILES: dict[str, dict] = {
    "blurry": {
        "success": False,
        "reason": "blurry_image",
        "observations": [],
        "text": (
            "⚠️ **[MOCK VISION RESPONSE]** Image quality is insufficient for reliable interpretation. "
            "The image appears to be blurry, low-resolution, or heavily compressed. "
            "No reliable visual observations can be extracted. "
            "Please retake the photo with adequate lighting, focus, and resolution (minimum 640×480 px)."
        ),
    },
    "unknown": {
        "success": False,
        "reason": "no_documentation_match",
        "observations": [
            "[MOCK] Unknown equipment enclosure visible — no matching product family identified.",
            "[MOCK] No nameplate, model number, or recognisable form factor could be matched to indexed documentation.",
        ],
        "text": (
            "⚠️ **[MOCK VISION RESPONSE]** The equipment visible in the image does not match any "
            "documentation in the indexed corpus. The model identifier is either absent, obscured, "
            "or does not correspond to indexed manuals. No guided procedure can be provided."
        ),
    },
    "ambiguous": {
        "success": False,
        "reason": "ambiguous_equipment_identity",
        "observations": [
            "[MOCK] S7-1200 series CPU housing detected — model variant (1211C / 1212C / 1214C / 1215C) cannot be determined.",
            "[MOCK] Product label partially obscured; specific CPU model cannot be confirmed from image alone.",
            "[MOCK] LED indicator state: visible, appears green/running, but requires model-specific confirmation.",
        ],
        "text": (
            "⚠️ **[MOCK VISION RESPONSE]** The equipment identity is ambiguous from the image provided. "
            "A Siemens SIMATIC S7-1200 series CPU is tentatively identified, but the specific model variant "
            "cannot be confirmed visually. Procedures differ between CPU 1211C, 1212C, 1214C, and 1215C. "
            "Please verify the CPU model number on the physical label and specify it when querying."
        ),
    },
    "normal": {
        "success": True,
        "reason": None,
        "observations": [
            "[MOCK] RUN/STOP indicator: solid green — CPU is in RUN state.",
            "[MOCK] ERROR LED: off — no active hardware or firmware fault detected.",
            "[MOCK] MAINT LED: off — no maintenance mode active.",
            "[MOCK] LINK TX/RX LED: flashing green — Ethernet communication active.",
        ],
        "text": None,  # Will be synthesised from text retrieval
    },
}


def _classify_image_by_filename(filename: str) -> str:
    """Returns a visual profile key based on filename substrings. Deterministic for testing."""
    lower = filename.lower()
    if "blurry" in lower:
        return "blurry"
    if "unknown" in lower:
        return "unknown"
    if "ambiguous" in lower:
        return "ambiguous"
    return "normal"


class MockBackendService:
    """Mock implementation of BackendServiceProtocol.

    Conforms to IndexingProtocol, RetrievalProtocol, and GenerationProtocol
    using in-memory stores and deterministic canned behaviors.
    """

    def __init__(self, collection_name: str = "mock_industrial_docs") -> None:
        self.collection_name = collection_name
        self._chunks: dict[str, Chunk] = {}

    # ── Indexing ─────────────────────────────────────────────────────────────

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

    # ── Retrieval ─────────────────────────────────────────────────────────────

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

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results: list[Evidence] = []
        for score, chunk in scored_chunks[:top_k]:
            if score > 0 or len(scored_chunks) <= top_k:
                source_id = f"{chunk.document_id}#p{chunk.page}#{chunk.chunk_id.split('#')[-1]}"
                results.append(Evidence(source_id=source_id, chunk=chunk))

        return results

    # ── Text Generation ────────────────────────────────────────────────────────

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

        negative_keywords = [
            "torque specification", "cylinder head bolt", "gearbox lubricant",
            "hydraulic pump rotor", "viscosity rating",
        ]
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

    # ── Vision Generation ──────────────────────────────────────────────────────

    def answer_with_image(
        self,
        question: str,
        image_path: Union[str, Path],
        equipment_model: Optional[str] = None,
    ) -> Answer:
        """Returns a clearly labelled mock visual response.

        This is a MOCK implementation. No actual image inference is performed.
        Visual observations are deterministically selected based on the image filename
        to exercise distinct UI states during development and testing.

        Raises:
            ValueError: If question is empty/whitespace, image format unsupported, or file too large.
            FileNotFoundError: If image_path does not exist.
        """
        if not question or not question.strip():
            raise ValueError("question must be non-empty and non-whitespace")

        path = Path(image_path)

        if not path.is_file():
            raise FileNotFoundError(f"Image file not found at '{path}'")

        suffix = path.suffix.lower()
        if suffix not in _SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Unsupported image format '{suffix}'. "
                f"Supported formats: {sorted(_SUPPORTED_IMAGE_EXTENSIONS)}"
            )

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > _MAX_IMAGE_SIZE_MB:
            raise ValueError(
                f"Image file size {size_mb:.1f} MB exceeds the {_MAX_IMAGE_SIZE_MB} MB limit."
            )

        profile_key = _classify_image_by_filename(path.name)
        profile = _VISION_PROFILES[profile_key]

        if not profile["success"]:
            # Non-interpretable image: return structured error with reason
            return Answer(
                text=profile["text"],
                evidence=[],
                observations=profile["observations"],
                insufficient_evidence=True,
            )

        # Interpretable image: synthesise text answer and attach observations
        base_answer = self.answer_question(question, equipment_model=equipment_model)
        observations = profile["observations"] + [
            f"[MOCK] Image analysed: '{path.name}' — visual state is consistent with documented operating conditions.",
        ]
        base_answer.observations = observations
        return base_answer
