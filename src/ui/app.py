"""Main Streamlit application for VALENCE (Milestone 3A).

Provides text-only and image-assisted chat, document upload, explicit indexing,
evidence inspection, insufficient-evidence declarations, mock mode indicators,
and explicit visual observation panels clearly distinct from documented guidance.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st

from contracts import Answer, IndexingSummary
from src.services import BackendServiceProtocol, create_ingestor

logger = logging.getLogger(__name__)

# ── Image upload constants ────────────────────────────────────────────────────
_SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp", "tiff", "webp"]
_SUPPORTED_IMAGE_EXTS = {f".{t}" for t in _SUPPORTED_IMAGE_TYPES}
_MAX_IMAGE_SIZE_MB = 20


# ── Backend factory ────────────────────────────────────────────────────────────

def get_or_create_backend(use_mock: bool) -> tuple[Optional[BackendServiceProtocol], Optional[str]]:
    """Retrieves or initializes the backend service instance.

    Returns:
        (backend_instance, error_message)
    """
    if use_mock:
        try:
            from src.services import create_backend
            return create_backend(mock=True), None
        except NotImplementedError:
            from src.ui.mock_backend import MockBackendService
            return MockBackendService(), None
        except Exception as e:
            return None, f"Mock backend initialization failed: {e}"
    else:
        try:
            from src.services import create_backend
            return create_backend(mock=False), None
        except NotImplementedError:
            return None, (
                "Live backend is not implemented yet by Member B "
                "(create_backend raised NotImplementedError)."
            )
        except RuntimeError as e:
            return None, f"Local backend connection failed: {e}"
        except Exception as e:
            return None, f"Backend unavailable: {e}"


# ── Session state ──────────────────────────────────────────────────────────────

def init_session_state() -> None:
    """Initializes persistent session state keys."""
    defaults: dict = {
        "chat_history": [],
        "indexed_docs": {},
        "backend": None,
        "use_mock": True,
        "last_indexing_summary": None,
        "backend_error": None,
        # Vision state — persists until user clears or uploads new image
        "vision_image_path": None,
        "vision_image_name": None,
        "vision_mode_active": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ── Evidence / observations renderers ─────────────────────────────────────────

def _render_evidence_drawer(answer: Answer) -> None:
    """Renders the Supporting Evidence collapsible drawer from Answer.evidence."""
    if answer.evidence:
        with st.expander(
            f"📚 Supporting Evidence ({len(answer.evidence)} citations)",
            expanded=False,
        ):
            for ev in answer.evidence:
                st.markdown(
                    f"**Source: `{ev.source_id}`** — File: `{ev.chunk.filename}` (Page {ev.chunk.page})"
                )
                meta_parts: list[str] = []
                if ev.chunk.equipment_model:
                    meta_parts.append(f"Model: `{ev.chunk.equipment_model}`")
                if ev.chunk.synthetic:
                    meta_parts.append("`[Synthetic]`")
                if meta_parts:
                    st.caption(" | ".join(meta_parts))
                st.info(ev.chunk.text)


def _render_visual_observations(answer: Answer, use_mock: bool) -> None:
    """Renders visual observations clearly separated from documented guidance."""
    if answer.observations:
        with st.expander("👁️ Tentative Visual Observations", expanded=True):
            if use_mock:
                st.caption(
                    "🔶 **[MOCK VISION RESPONSE]** — These observations are simulated. "
                    "No actual image inference has been performed."
                )
            st.warning(
                "⚠️ Visual observations are **tentative** and must not be used as confirmed diagnoses. "
                "Always verify against physical inspection and official documentation."
            )
            for obs in answer.observations:
                st.markdown(f"- {obs}")


def _render_assistant_message(msg: dict, use_mock: bool) -> None:
    """Renders a complete assistant chat message including all panels."""
    answer: Answer = msg["answer"]
    image_name: Optional[str] = msg.get("image_name")

    with st.chat_message("assistant"):
        if image_name:
            st.caption(f"🖼️ Image inspection: `{image_name}`")

        if answer.insufficient_evidence:
            st.warning(
                "⚠️ **Insufficient Documentary Evidence**: The retrieved manuals and SOPs do not "
                "substantiate an answer to this query."
            )

        st.markdown(answer.text)
        _render_evidence_drawer(answer)
        _render_visual_observations(answer, use_mock)


# ── Image format / size validation ────────────────────────────────────────────

def _validate_uploaded_image(uploaded_file) -> Optional[str]:
    """Returns an error string if the uploaded image is invalid, otherwise None."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in _SUPPORTED_IMAGE_EXTS:
        return (
            f"Unsupported image format `{suffix}`. "
            f"Accepted: {', '.join(sorted(_SUPPORTED_IMAGE_EXTS))}"
        )
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > _MAX_IMAGE_SIZE_MB:
        return (
            f"Image file size {size_mb:.1f} MB exceeds the {_MAX_IMAGE_SIZE_MB} MB limit. "
            "Please reduce file size or resolution."
        )
    return None


# ── Main app ──────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="VALENCE - Industrial Knowledge Assistant",
        page_icon="⚙️",
        layout="wide",
    )
    init_session_state()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    st.sidebar.title("⚙️ System Control")

    use_mock = st.sidebar.checkbox(
        "Run in Mock Mode",
        value=st.session_state.use_mock,
        help=(
            "Simulates vector retrieval and LLM generation in-memory. "
            "Vision responses are also mocked — no real image inference is performed."
        ),
        key="mock_mode_toggle",
    )

    # Re-initialize backend if mode toggled or uninitialized
    if st.session_state.backend is None or st.session_state.use_mock != use_mock:
        st.session_state.use_mock = use_mock
        backend_inst, err = get_or_create_backend(use_mock=use_mock)
        st.session_state.backend = backend_inst
        st.session_state.backend_error = err

    backend: Optional[BackendServiceProtocol] = st.session_state.backend
    backend_error: Optional[str] = st.session_state.backend_error

    # Backend status
    if backend_error:
        st.sidebar.error(f"❌ Backend Unavailable: {backend_error}")
    elif use_mock:
        st.sidebar.info("🔶 Backend: **Mock Engine** (In-Memory)")
    else:
        st.sidebar.success("🟢 Backend: **Live Local Engine**")

    st.sidebar.metric("Indexed Documents", len(st.session_state.indexed_docs))

    # ── Document Ingestion ─────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Document Ingestion")

    uploaded_pdf = st.sidebar.file_uploader(
        "Upload Equipment Manual or SOP",
        type=["pdf"],
        help="Upload a PDF. Processing only begins when 'Index Document' is clicked.",
        key="pdf_uploader",
    )

    equipment_model = st.sidebar.text_input(
        "Equipment Model (optional)",
        placeholder="e.g. S7-1200 CPU 1214C",
        help="Attach equipment model metadata to chunks. Leave blank if unknown.",
        key="equipment_model_input",
    )

    is_synthetic = st.sidebar.checkbox(
        "Synthetic test data",
        value=False,
        help="Mark chunks with synthetic=True for development/evaluation datasets.",
        key="synthetic_checkbox",
    )

    if st.sidebar.button("📥 Index Document", type="primary", key="btn_index_doc"):
        if uploaded_pdf is None:
            st.sidebar.error("⚠️ Please choose a PDF file to upload before indexing.")
        elif backend is None:
            st.sidebar.error("❌ Cannot index: backend service is unavailable.")
        else:
            with st.sidebar.status("Processing document...", expanded=True) as status:
                try:
                    suffix = Path(uploaded_pdf.name).suffix or ".pdf"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(uploaded_pdf.getbuffer())
                        tmp_path = tmp_file.name

                    status.write("Parsing pages and chunking text...")
                    ingestor = create_ingestor(mock=False)
                    raw_chunks = ingestor.ingest_pdf(
                        path=tmp_path,
                        equipment_model=equipment_model.strip() or None,
                        synthetic=is_synthetic,
                    )
                    # Restore original uploaded filename
                    from contracts import Chunk as ChunkClass
                    clean_chunks = [
                        ChunkClass(
                            chunk_id=c.chunk_id,
                            document_id=c.document_id,
                            filename=uploaded_pdf.name,
                            page=c.page,
                            text=c.text,
                            equipment_model=c.equipment_model,
                            synthetic=c.synthetic,
                        )
                        for c in raw_chunks
                    ]

                    status.write("Submitting chunks to vector store...")
                    summary: IndexingSummary = backend.index_chunks(clean_chunks)
                    st.session_state.last_indexing_summary = summary

                    st.session_state.indexed_docs[uploaded_pdf.name] = {
                        "document_id": clean_chunks[0].document_id if clean_chunks else "unknown",
                        "chunks_count": len(clean_chunks),
                        "equipment_model": equipment_model.strip() or None,
                        "synthetic": is_synthetic,
                    }

                    if summary.chunks_failed > 0:
                        status.update(
                            label=f"⚠️ Indexing completed with {summary.chunks_failed} failures",
                            state="error",
                        )
                    else:
                        status.update(
                            label=f"✅ Indexed {summary.chunks_indexed} chunks successfully",
                            state="complete",
                        )
                except ValueError as ve:
                    status.update(label="❌ Ingestion Error", state="error")
                    st.sidebar.error(f"Invalid PDF or unreadable input: {ve}")
                except Exception as ex:
                    status.update(label="❌ Indexing Failed", state="error")
                    st.sidebar.error(f"Error during ingestion: {ex}")

    if st.session_state.last_indexing_summary:
        s = st.session_state.last_indexing_summary
        st.sidebar.caption(
            f"Last Indexing: {s.chunks_indexed} indexed, "
            f"{s.chunks_skipped} skipped, {s.chunks_failed} failed."
        )

    # ── Vision Image Upload ────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("🖼️ Visual Inspection (Optional)")

    st.sidebar.caption(
        f"Supported formats: {', '.join(sorted(_SUPPORTED_IMAGE_EXTS))}  |  Max {_MAX_IMAGE_SIZE_MB} MB"
    )

    uploaded_image = st.sidebar.file_uploader(
        "Attach Equipment Image",
        type=_SUPPORTED_IMAGE_TYPES,
        help=(
            "Attach a photo of equipment for visual inspection alongside SOP retrieval. "
            "The image is sent with your next question. "
            "Vision model integration is pending (Member B); mock responses are used in Mock Mode."
        ),
        key="image_uploader",
    )

    vision_available = True
    vision_unavailable_reason: Optional[str] = None

    if uploaded_image is not None:
        # Format and size validation
        img_error = _validate_uploaded_image(uploaded_image)
        if img_error:
            st.sidebar.error(f"❌ Image rejected: {img_error}")
            st.session_state.vision_image_path = None
            st.session_state.vision_image_name = None
            st.session_state.vision_mode_active = False
        else:
            # Save image to temp file for this session
            suffix = Path(uploaded_image.name).suffix or ".png"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix, prefix="valence_img_"
            ) as tmp_img:
                tmp_img.write(uploaded_image.getbuffer())
                st.session_state.vision_image_path = tmp_img.name
                st.session_state.vision_image_name = uploaded_image.name
                st.session_state.vision_mode_active = True

            st.sidebar.success(
                f"✅ Image ready: `{uploaded_image.name}` "
                f"({uploaded_image.size / 1024:.0f} KB)"
            )
            st.sidebar.image(uploaded_image, caption=f"Preview: {uploaded_image.name}", width=200)
            if use_mock:
                st.sidebar.caption("🔶 Vision responses will use mock observations.")
    else:
        if st.session_state.vision_mode_active:
            if st.sidebar.button("🗑️ Clear Image", key="btn_clear_image"):
                st.session_state.vision_image_path = None
                st.session_state.vision_image_name = None
                st.session_state.vision_mode_active = False
                st.rerun()

    # Check whether the live backend supports vision
    if not use_mock and st.session_state.vision_mode_active:
        if not hasattr(backend, "answer_with_image"):
            vision_available = False
            vision_unavailable_reason = (
                "The connected backend does not expose answer_with_image. "
                "Visual inspection requires Member B's VLM integration."
            )

    # ── Clear Chat ─────────────────────────────────────────────────────────────
    if st.sidebar.button("🗑️ Clear Chat History", key="btn_clear_chat"):
        st.session_state.chat_history = []
        st.rerun()

    # ── Main Chat Area ─────────────────────────────────────────────────────────
    st.title("VALENCE: Offline Industrial Knowledge Assistant")

    # Mock mode banner
    if use_mock:
        st.warning(
            "🔶 **RUNNING IN MOCK BACKEND MODE**: Text retrieval and generation are simulated "
            "in-memory. Vision responses are also **mocked** — no actual image inference is performed."
        )

    if backend_error:
        st.error(
            f"❌ **BACKEND SERVICE UNAVAILABLE**: {backend_error}\n\n"
            "Queries cannot be answered until the backend is operational or Mock Mode is enabled."
        )

    # Vision mode status strip
    if st.session_state.vision_mode_active and st.session_state.vision_image_name:
        img_label = "🖼️ **Visual Inspection Mode Active**"
        if not vision_available:
            st.error(
                f"❌ {img_label} — Vision unavailable: {vision_unavailable_reason}\n\n"
                "Text-only queries remain functional."
            )
        elif use_mock:
            st.info(
                f"{img_label}: `{st.session_state.vision_image_name}` — "
                "🔶 Vision responses will use mock observations (no real inference)."
            )
        else:
            st.info(
                f"{img_label}: `{st.session_state.vision_image_name}` attached. "
                "Your next question will use multimodal inspection."
            )

    # Render conversation history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                if msg.get("image_name"):
                    st.caption(f"🖼️ With image: `{msg['image_name']}`")
                st.write(msg["content"])
        elif msg["role"] == "assistant":
            _render_assistant_message(msg, use_mock=use_mock)

    # ── Chat Input ─────────────────────────────────────────────────────────────
    query = st.chat_input(
        "Ask a question about equipment operation, troubleshooting, or SOPs..."
    )

    if query:
        vision_active = (
            st.session_state.vision_mode_active
            and st.session_state.vision_image_path is not None
            and vision_available
        )
        image_name = st.session_state.vision_image_name if vision_active else None

        st.session_state.chat_history.append({
            "role": "user",
            "content": query,
            "image_name": image_name,
        })

        if backend is None:
            ans = Answer(
                text="Cannot process query: Backend service is unavailable.",
                evidence=[],
                insufficient_evidence=True,
            )
        elif vision_active:
            try:
                ans = backend.answer_with_image(
                    question=query,
                    image_path=st.session_state.vision_image_path,
                    equipment_model=equipment_model.strip() or None,
                )
            except FileNotFoundError as e:
                logger.error("Vision image not found: %s", e)
                ans = Answer(
                    text=f"❌ Image file could not be located: {e}",
                    evidence=[],
                    insufficient_evidence=True,
                )
            except ValueError as e:
                logger.error("Vision validation error: %s", e)
                ans = Answer(
                    text=f"❌ Image validation error: {e}",
                    evidence=[],
                    insufficient_evidence=True,
                )
            except RuntimeError as e:
                # Missing vision model / model not loaded
                logger.error("Vision model failure: %s", e)
                ans = Answer(
                    text=(
                        f"❌ **Vision Model Unavailable**: {e}\n\n"
                        "The multimodal model could not be reached. "
                        "Check that the VLM is loaded in Ollama and retry, "
                        "or switch to Mock Mode for development."
                    ),
                    evidence=[],
                    insufficient_evidence=True,
                )
            except Exception as e:
                logger.error("Unexpected vision error: %s", e)
                ans = Answer(
                    text=f"❌ Unexpected vision interpretation failure: {e}",
                    evidence=[],
                    insufficient_evidence=True,
                )
        else:
            try:
                ans = backend.answer_question(
                    question=query,
                    equipment_model=equipment_model.strip() or None,
                )
            except Exception as e:
                logger.error("Text query failure: %s", e)
                ans = Answer(
                    text=f"Backend query failure: {e}",
                    evidence=[],
                    insufficient_evidence=True,
                )

        st.session_state.chat_history.append({
            "role": "assistant",
            "answer": ans,
            "image_name": image_name,
        })
        st.rerun()


if __name__ == "__main__":
    main()
