"""In-memory mock backend conforming to BackendServiceProtocol for UI testing and offline development."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Sequence, Union

from contracts import Answer, Chunk, CropInspectionResult, Evidence, IndexingSummary

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

    def delete_document(
        self,
        filename: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> int:
        """Removes all chunks belonging to a document from mock storage."""
        if not filename and not document_id:
            return 0
        keys_to_del = [
            cid for cid, c in self._chunks.items()
            if (filename and c.filename == filename) or (document_id and c.document_id == document_id)
        ]
        for k in keys_to_del:
            del self._chunks[k]
        return len(keys_to_del)

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

        q_tokens = _content_tokens(question)
        if not q_tokens:
            return []

        # Count document frequencies across store for BM25 IDF weighting
        total_docs = max(1, len(self._chunks))
        doc_freqs: dict[str, int] = {}
        for chunk in self._chunks.values():
            tokens = _content_tokens(chunk.text)
            for t in tokens:
                doc_freqs[t] = doc_freqs.get(t, 0) + 1

        clean_q = re.sub(r"[^\w\s]", " ", question.lower())
        q_words = [w for w in clean_q.split() if w not in _STOPWORDS and len(w) > 2]
        phrases = [f"{q_words[i]} {q_words[i+1]}" for i in range(len(q_words) - 1)]

        scored_chunks: list[tuple[float, Chunk]] = []
        for chunk in self._chunks.values():
            if equipment_model is not None and chunk.equipment_model is not None:
                if equipment_model.lower() not in chunk.equipment_model.lower():
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

        scored_chunks.sort(key=lambda x: -x[0])

        results: list[Evidence] = []
        for _, chunk in scored_chunks[:top_k]:
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

        if not evidence:
            return Answer(
                text="Retrieved SOP context does not substantiate an answer for this query.",
                evidence=[],
                insufficient_evidence=True,
            )

        citations = " ".join(f"[{ev.source_id}]" for ev in evidence)
        primary_ev = evidence[0]
        first_chunk_text = primary_ev.chunk.text
        q_lower = question.lower()
        chunk_lower = first_chunk_text.lower()

        # Check for diagnostic table reference
        if "solid yellow" in q_lower and "cpu in stop" in chunk_lower:
            synthesis = (
                f"Based on documentation in {citations}:\n\n"
                f"**Diagnostic Finding**: A solid yellow RUN/STOP LED indicates that the CPU is in **STOP** mode.\n\n"
                f"- **Meaning**: CPU in STOP [{primary_ev.source_id}]\n"
                f"- **Safety Precaution**: Always cross-reference the LED state with the diagnostic buffer before acting."
            )
        elif "solid green" in q_lower and "cpu in run" in chunk_lower:
            synthesis = (
                f"Based on documentation in {citations}:\n\n"
                f"**Diagnostic Finding**: A solid green RUN/STOP LED indicates that the CPU is in **RUN** mode.\n\n"
                f"- **Meaning**: CPU in RUN [{primary_ev.source_id}]\n"
                f"- **Safety Precaution**: Follow standard operating procedure for RUN mode."
            )
        else:
            text_lines = [l.strip() for l in first_chunk_text.splitlines() if l.strip()]
            header = text_lines[0] if text_lines else "Standard Operating Procedure"
            details = " ".join(text_lines[1:]) if len(text_lines) > 1 else first_chunk_text
            synthesis = (
                f"Based on documentation in {citations}:\n\n"
                f"**Procedure**: {header}\n\n"
                f"- **Guidance**: {details[:200]} [{primary_ev.source_id}]\n"
                f"- **Safety Precaution**: Ensure all safety interlocks and operational limits are confirmed prior to maintenance."
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
        if base_answer.insufficient_evidence and self._chunks:
            # Fall back to equipment chunks for mock image visual grounding
            fallback_chunks = [
                c for c in self._chunks.values()
                if equipment_model is None or (c.equipment_model and equipment_model.lower() in c.equipment_model.lower())
            ]
            if fallback_chunks:
                evidence = [
                    Evidence(source_id=f"{c.document_id}#p{c.page}#{c.chunk_id.split('#')[-1]}", chunk=c)
                    for c in fallback_chunks[:2]
                ]
                citations = " ".join(f"[{ev.source_id}]" for ev in evidence)
                base_answer = Answer(
                    text=f"Image inspection confirmed for {equipment_model or 'equipment'}. Based on documentation in {citations}, visual indicators are consistent with nominal operating conditions.",
                    evidence=evidence,
                    insufficient_evidence=False,
                )
        observations = profile["observations"] + [
            f"[MOCK] Image analysed: '{path.name}' — visual state is consistent with documented operating conditions.",
        ]
        base_answer.observations = observations
        return base_answer

    def inspect_crop(
        self,
        image_path: Union[str, Path],
        box_pct: tuple[float, float, float, float],
        user_question: Optional[str] = None,
    ) -> tuple[CropInspectionResult, Path]:
        """Mock implementation of user-selected crop inspection."""
        from src.utils.image_crop import crop_image_region

        crop_path, crop_id, crop_coords = crop_image_region(image_path, box_pct)
        p = Path(image_path)
        profile_key = _classify_image_by_filename(p.name)

        if "blurry" in profile_key:
            res = CropInspectionResult(
                crop_id=crop_id,
                crop_coordinates=crop_coords,
                legible_text=[],
                unreadable_text_noted=True,
                indicator_states=[],
                tentative_observations=["[MOCK] Text in selected region is blurry and illegible."],
                follow_up_needed="Please attach a closer, sharper photograph of the target component.",
                raw_description="[MOCK] Blurry crop.",
            )
        elif "unknown" in profile_key:
            res = CropInspectionResult(
                crop_id=crop_id,
                crop_coordinates=crop_coords,
                legible_text=[],
                unreadable_text_noted=False,
                indicator_states=[],
                tentative_observations=["[MOCK] Unidentified industrial housing. No Siemens S7-1200 markings present."],
                follow_up_needed="Target component is not present in this crop.",
                raw_description="[MOCK] Unknown component crop.",
            )
        else:
            res = CropInspectionResult(
                crop_id=crop_id,
                crop_coordinates=crop_coords,
                legible_text=["S7-1200", "RUN/STOP"],
                unreadable_text_noted=False,
                indicator_states=[{"name": "RUN/STOP", "color": "yellow", "state": "solid"}],
                tentative_observations=[
                    "[MOCK] Four circular indicators visible in crop.",
                    "[MOCK] Solid yellow indicator observed on RUN/STOP channel.",
                ],
                follow_up_needed=None,
                raw_description="[MOCK] Normal crop inspection.",
            )
        return res, crop_path
