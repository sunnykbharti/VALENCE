"""Classic / Old UI view for VALENCE.

Preserves the original sidebar-centric layout with chat stream.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
from contracts import Answer, IndexingSummary
from src.services import BackendServiceProtocol, create_ingestor
from src.ui.components.message_view import render_assistant_message, render_user_message
from src.ui.components.incident_panel import render_incident_controls

logger = logging.getLogger(__name__)

_SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp", "tiff", "webp"]
_SUPPORTED_IMAGE_EXTS = {f".{t}" for t in _SUPPORTED_IMAGE_TYPES}
_MAX_IMAGE_SIZE_MB = 20


def _validate_uploaded_image(uploaded_file) -> Optional[str]:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in _SUPPORTED_IMAGE_EXTS:
        return f"Unsupported image format `{suffix}`. Accepted: {', '.join(sorted(_SUPPORTED_IMAGE_EXTS))}"
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > _MAX_IMAGE_SIZE_MB:
        return f"Image file size {size_mb:.1f} MB exceeds {_MAX_IMAGE_SIZE_MB} MB limit."
    return None


def render_classic_view(backend: Optional[BackendServiceProtocol], backend_error: Optional[str]) -> None:
    """Renders the original sidebar-based interface."""
    use_mock = st.session_state.get("use_mock", True)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    st.sidebar.title("⚙️ System Control")

    new_mock = st.sidebar.checkbox(
        "Run in Mock Mode",
        value=use_mock,
        help="Simulates vector retrieval and LLM generation in-memory.",
        key="classic_mock_mode_toggle",
    )
    if new_mock != use_mock:
        st.session_state.use_mock = new_mock
        st.rerun()

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
        key="classic_pdf_uploader",
    )

    equipment_model = st.sidebar.text_input(
        "Equipment Model (optional)",
        placeholder="e.g. S7-1200 CPU 1214C",
        key="classic_equipment_model_input",
    )

    is_synthetic = st.sidebar.checkbox(
        "Synthetic test data",
        value=False,
        key="classic_synthetic_checkbox",
    )

    if st.sidebar.button("📥 Index Document", type="primary", key="classic_btn_index_doc"):
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
                    if "cached_chunks" not in st.session_state:
                        st.session_state["cached_chunks"] = []
                    st.session_state["cached_chunks"].extend(clean_chunks)

                    st.session_state.indexed_docs[uploaded_pdf.name] = {
                        "document_id": clean_chunks[0].document_id if clean_chunks else "unknown",
                        "chunks_count": len(clean_chunks),
                        "equipment_model": equipment_model.strip() or None,
                        "synthetic": is_synthetic,
                    }

                    if summary.chunks_failed > 0:
                        status.update(label=f"⚠️ Indexing completed with {summary.chunks_failed} failures", state="error")
                    else:
                        status.update(label=f"✅ Indexed {summary.chunks_indexed} chunks successfully", state="complete")
                except Exception as ex:
                    status.update(label="❌ Indexing Failed", state="error")
                    st.sidebar.error(f"Error during ingestion: {ex}")

    if st.session_state.last_indexing_summary:
        s = st.session_state.last_indexing_summary
        st.sidebar.caption(
            f"Last Indexing: {s.chunks_indexed} indexed, {s.chunks_skipped} skipped, {s.chunks_failed} failed."
        )

    # ── Vision Image Upload ────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("🖼️ Visual Inspection (Optional)")

    uploaded_image = st.sidebar.file_uploader(
        "Attach Equipment Image",
        type=_SUPPORTED_IMAGE_TYPES,
        key="classic_image_uploader",
    )

    vision_available = True
    vision_unavailable_reason: Optional[str] = None

    if uploaded_image is not None:
        img_error = _validate_uploaded_image(uploaded_image)
        if img_error:
            st.sidebar.error(f"❌ Image rejected: {img_error}")
            st.session_state.vision_image_path = None
            st.session_state.vision_image_name = None
            st.session_state.vision_mode_active = False
        else:
            suffix = Path(uploaded_image.name).suffix or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="valence_img_") as tmp_img:
                tmp_img.write(uploaded_image.getbuffer())
                st.session_state.vision_image_path = tmp_img.name
                st.session_state.vision_image_name = uploaded_image.name
                st.session_state.vision_mode_active = True

            st.sidebar.success(f"✅ Image ready: `{uploaded_image.name}` ({uploaded_image.size / 1024:.0f} KB)")
            st.sidebar.image(uploaded_image, caption=f"Preview: {uploaded_image.name}", width=200)
    else:
        if st.session_state.vision_mode_active:
            if st.sidebar.button("🗑️ Clear Image", key="classic_btn_clear_image"):
                st.session_state.vision_image_path = None
                st.session_state.vision_image_name = None
                st.session_state.vision_mode_active = False
                st.rerun()

    if not use_mock and st.session_state.vision_mode_active:
        if not hasattr(backend, "answer_with_image"):
            vision_available = False
            vision_unavailable_reason = "Backend does not expose answer_with_image."

    # ── Clear Chat ─────────────────────────────────────────────────────────────
    if st.sidebar.button("🗑️ Clear Chat History", key="classic_btn_clear_chat"):
        st.session_state.chat_history = []
        st.rerun()

    # ── Main Area ──────────────────────────────────────────────────────────────
    st.title("VALENCE: Offline Industrial Knowledge Assistant")

    if use_mock:
        st.warning(
            "🔶 **RUNNING IN MOCK BACKEND MODE**: Text retrieval and generation are simulated in-memory. "
            "Vision responses are also **mocked** — no actual image inference is performed."
        )

    if backend_error:
        st.error(f"❌ **BACKEND SERVICE UNAVAILABLE**: {backend_error}")

    if st.session_state.vision_mode_active and st.session_state.vision_image_name:
        img_label = "🖼️ **Visual Inspection Mode Active**"
        if not vision_available:
            st.error(f"❌ {img_label} — Vision unavailable: {vision_unavailable_reason}")
        else:
            st.info(f"{img_label}: `{st.session_state.vision_image_name}` attached.")

    # Phase 2: Operational Incident Workspace
    incident_service = st.session_state.get("incident_service")
    if incident_service:
        with st.container():
            render_incident_controls(incident_service, backend=backend)

    # Render conversation history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            render_user_message(msg)
        elif msg["role"] == "assistant":
            render_assistant_message(msg, use_mock=use_mock)

    # Chat Input
    query = st.chat_input("Ask a question about equipment operation, troubleshooting, or SOPs...", key="classic_chat_input")
    if query:
        _handle_query(query, backend, equipment_model, vision_available)


def _handle_query(query: str, backend, equipment_model: str, vision_available: bool) -> None:
    vision_active = (
        st.session_state.vision_mode_active
        and st.session_state.vision_image_path is not None
        and vision_available
    )
    image_name = st.session_state.vision_image_name if vision_active else None

    st.session_state.chat_history.append({"role": "user", "content": query, "image_name": image_name})

    if backend is None:
        ans = Answer(text="Cannot process query: Backend service is unavailable.", evidence=[], insufficient_evidence=True)
    elif vision_active:
        try:
            ans = backend.answer_with_image(
                question=query,
                image_path=st.session_state.vision_image_path,
                equipment_model=equipment_model.strip() or None,
            )
        except Exception as e:
            ans = Answer(text=f"❌ Vision interpretation error: {e}", evidence=[], insufficient_evidence=True)
    else:
        try:
            ans = backend.answer_question(
                question=query,
                equipment_model=equipment_model.strip() or None,
            )
        except Exception as e:
            ans = Answer(text=f"❌ Backend query error: {e}", evidence=[], insufficient_evidence=True)

    st.session_state.chat_history.append({"role": "assistant", "answer": ans, "image_name": image_name})
    st.rerun()

