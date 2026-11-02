"""Main Streamlit application for VALENCE (Milestone 2A).

Provides text-only chat interface, document upload, explicit indexing,
evidence inspection drawers, insufficient evidence declarations, and mock mode indicators.
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
            return None, "Live backend is not implemented yet by Member B (create_backend raised NotImplementedError)."
        except RuntimeError as e:
            return None, f"Local backend connection failed: {e}"
        except Exception as e:
            return None, f"Backend unavailable: {e}"


def init_session_state() -> None:
    """Initializes persistent session state keys."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "indexed_docs" not in st.session_state:
        st.session_state.indexed_docs = {}
    if "backend" not in st.session_state:
        st.session_state.backend = None
    if "use_mock" not in st.session_state:
        st.session_state.use_mock = True
    if "last_indexing_summary" not in st.session_state:
        st.session_state.last_indexing_summary = None


def main() -> None:
    st.set_page_config(
        page_title="VALENCE - Industrial Knowledge Assistant",
        page_icon="⚙️",
        layout="wide",
    )
    init_session_state()

    # --- Sidebar Configuration ---
    st.sidebar.title("⚙️ System Control")

    use_mock = st.sidebar.checkbox(
        "Run in Mock Mode",
        value=st.session_state.use_mock,
        help="Simulates vector retrieval and local LLM generation in-memory without Ollama or Qdrant.",
        key="mock_mode_toggle",
    )

    # Re-initialize backend if mode toggled or uninitialized
    if st.session_state.backend is None or st.session_state.use_mock != use_mock:
        st.session_state.use_mock = use_mock
        backend_inst, err = get_or_create_backend(use_mock=use_mock)
        st.session_state.backend = backend_inst
        st.session_state.backend_error = err

    backend: Optional[BackendServiceProtocol] = st.session_state.backend
    backend_error: Optional[str] = st.session_state.get("backend_error")

    # Backend Status Indicator
    if backend_error:
        st.sidebar.error(f"❌ Backend Unavailable: {backend_error}")
    elif use_mock:
        st.sidebar.info("🔶 Backend: **Mock Engine** (In-Memory)")
    else:
        st.sidebar.success("🟢 Backend: **Live Local Engine**")

    # Display Indexed Corpus Metrics
    doc_count = len(st.session_state.indexed_docs)
    st.sidebar.metric("Indexed Documents", doc_count)

    # --- Document Upload & Indexing Section ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Document Ingestion")

    uploaded_file = st.sidebar.file_uploader(
        "Upload Equipment Manual or SOP",
        type=["pdf"],
        help="Upload a PDF manual or SOP. Document is processed only when 'Index Document' is clicked.",
        key="pdf_uploader",
    )

    equipment_model = st.sidebar.text_input(
        "Equipment Model (optional)",
        placeholder="e.g. S7-1200 CPU 1214C",
        help="Attach equipment model metadata to chunks. Leave blank if unknown or generic.",
        key="equipment_model_input",
    )

    is_synthetic = st.sidebar.checkbox(
        "Synthetic test data",
        value=False,
        help="Mark chunks with synthetic=True for development/evaluation datasets.",
        key="synthetic_checkbox",
    )

    index_button = st.sidebar.button("📥 Index Document", type="primary", key="btn_index_doc")

    if index_button:
        if uploaded_file is None:
            st.sidebar.error("⚠️ Please choose a PDF file to upload before indexing.")
        elif backend is None:
            st.sidebar.error("❌ Cannot index: backend service is unavailable.")
        else:
            with st.sidebar.status("Processing document...", expanded=True) as status:
                try:
                    # Save uploaded buffer to a temporary file
                    suffix = Path(uploaded_file.name).suffix or ".pdf"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getbuffer())
                        tmp_path = tmp_file.name

                    # Ingest PDF
                    status.write("Parsing pages and chunking text...")
                    ingestor = create_ingestor(mock=False)
                    chunks = ingestor.ingest_pdf(
                        path=tmp_path,
                        equipment_model=equipment_model.strip() or None,
                        synthetic=is_synthetic,
                    )

                    # Update filename to original uploaded name
                    clean_chunks = []
                    for c in chunks:
                        clean_chunks.append(
                            type(c)(
                                chunk_id=c.chunk_id,
                                document_id=c.document_id,
                                filename=uploaded_file.name,
                                page=c.page,
                                text=c.text,
                                equipment_model=c.equipment_model,
                                synthetic=c.synthetic,
                            )
                        )

                    # Index into backend
                    status.write("Submitting chunks to vector store...")
                    summary: IndexingSummary = backend.index_chunks(clean_chunks)
                    st.session_state.last_indexing_summary = summary

                    # Record indexed document metadata
                    st.session_state.indexed_docs[uploaded_file.name] = {
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

    # Display Indexing Summary Card if present
    if st.session_state.last_indexing_summary:
        sum_obj = st.session_state.last_indexing_summary
        st.sidebar.caption(
            f"Last Indexing: {sum_obj.chunks_indexed} indexed, "
            f"{sum_obj.chunks_skipped} skipped, {sum_obj.chunks_failed} failed."
        )

    # Clear Chat History Button
    if st.sidebar.button("🗑️ Clear Chat History", key="btn_clear_chat"):
        st.session_state.chat_history = []
        st.rerun()

    # --- Main Chat Area ---
    st.title("VALENCE: Offline Industrial Knowledge Assistant")

    # Conspicuous Banner when running Mock Backend (Task 6)
    if use_mock:
        st.warning(
            "🔶 **RUNNING IN MOCK BACKEND MODE**: Retrieval and generation are simulated in-memory "
            "with deterministic mock data. No live Ollama daemon or local Qdrant instance is connected."
        )

    if backend_error:
        st.error(
            f"❌ **BACKEND SERVICE UNAVAILABLE**: {backend_error}\n\n"
            "Queries cannot be answered until the backend service is operational or Mock Mode is enabled."
        )

    # Render Chat History (Task 3, 4, 5, 8)
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        elif msg["role"] == "assistant":
            answer: Answer = msg["answer"]
            with st.chat_message("assistant"):
                # Insufficient evidence alert (Task 5)
                if answer.insufficient_evidence:
                    st.warning(
                        "⚠️ **Insufficient Documentary Evidence**: The retrieved manuals and SOPs do not "
                        "substantiate an answer to this query."
                    )

                # Main answer text
                st.markdown(answer.text)

                # Supporting Evidence Drawer (Task 4)
                if answer.evidence:
                    with st.expander(f"📚 Supporting Evidence ({len(answer.evidence)} citations)", expanded=False):
                        for ev in answer.evidence:
                            st.markdown(f"**Source: `{ev.source_id}`** — File: `{ev.chunk.filename}` (Page {ev.chunk.page})")
                            meta_parts = []
                            if ev.chunk.equipment_model:
                                meta_parts.append(f"Model: `{ev.chunk.equipment_model}`")
                            if ev.chunk.synthetic:
                                meta_parts.append("`[Synthetic]`")
                            if meta_parts:
                                st.caption(" | ".join(meta_parts))
                            st.info(ev.chunk.text)

                # Multimodal visual observations if present
                if answer.observations:
                    with st.expander("👁️ Tentative Visual Observations", expanded=True):
                        for obs in answer.observations:
                            st.markdown(f"- {obs}")

    # Chat Input Box
    query = st.chat_input("Ask a question about equipment operation, troubleshooting, or SOPs...")

    if query:
        # Avoid resetting or re-indexing on ordinary chat input
        st.session_state.chat_history.append({"role": "user", "content": query})

        if backend is None:
            # Report backend unavailable state without fake success (Task 7)
            unavailable_answer = Answer(
                text="Cannot process query: Backend service is unavailable.",
                evidence=[],
                insufficient_evidence=True,
            )
            st.session_state.chat_history.append({"role": "assistant", "answer": unavailable_answer})
        else:
            try:
                # Query backend (Task 3)
                ans = backend.answer_question(
                    question=query,
                    equipment_model=equipment_model.strip() or None,
                )
                st.session_state.chat_history.append({"role": "assistant", "answer": ans})
            except Exception as e:
                logger.error("Error generating answer: %s", e)
                error_answer = Answer(
                    text=f"Backend query failure: {e}",
                    evidence=[],
                    insufficient_evidence=True,
                )
                st.session_state.chat_history.append({"role": "assistant", "answer": error_answer})

        st.rerun()


if __name__ == "__main__":
    main()
