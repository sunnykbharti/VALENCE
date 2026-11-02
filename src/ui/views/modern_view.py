"""Modern frontend view for VALENCE.

Provides an industrial dashboard layout with tabs for Assistant Chat,
Knowledge Base Indexing, Visual Inspection, and System Control.
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


def render_modern_view(backend: Optional[BackendServiceProtocol], backend_error: Optional[str]) -> None:
    """Renders the modern industrial workspace layout with top tabs."""
    use_mock = st.session_state.get("use_mock", True)

    tab_chat, tab_incident, tab_docs, tab_vision, tab_settings = st.tabs([
        "💬 Assistant Console",
        "🚨 Incident Operations",
        "📚 Knowledge Base & Indexing",
        "🖼️ Visual Inspection",
        "⚙️ System & Model Control",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1: ASSISTANT CONSOLE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_chat:
        # Status header strip
        cols = st.columns([6, 2])
        with cols[0]:
            if use_mock:
                st.caption("🔶 **Running in Mock Backend Mode** (Simulated retrieval and responses)")
            elif backend_error:
                st.error(f"❌ Backend Unavailable: {backend_error}")
            else:
                st.caption("🟢 **Live Air-Gapped Engine Active** (Local Vector RAG & LLM)")

        with cols[1]:
            if st.button("🗑️ Clear Chat", key="modern_clear_chat", help="Wipe conversation history"):
                st.session_state.chat_history = []
                st.rerun()

        # Active incident alert (Phase 2)
        active_id = st.session_state.get("active_incident_id")
        if active_id and st.session_state.get("incident_service"):
            active_inc = st.session_state.incident_service.get_incident(active_id)
            if active_inc:
                confirmed_badge = "✅ Confirmed" if active_inc.equipment_confirmed else "⚠️ Unconfirmed"
                eq_text = f" | Equipment: `{active_inc.equipment_model}` ({confirmed_badge})" if active_inc.equipment_model else ""
                st.info(f"🚨 **Active Incident Context:** `{active_inc.incident_id}`: **{active_inc.title}** [{active_inc.status.upper()}]{eq_text}")

                # Notification for pending operator clarification
                exec_key = f"active_execution_{active_inc.incident_id}"
                active_exec = st.session_state.get(exec_key)
                if active_exec and active_exec.state == "waiting" and active_exec.clarification:
                    st.warning(f"⏳ **Clarification Required for Incident `{active_inc.incident_id}`:** {active_exec.clarification.question} (Switch to '🚨 Incident Operations' to respond)")

        # Image attachment alert
        if st.session_state.get("vision_mode_active") and st.session_state.get("vision_image_name"):
            st.info(
                f"🖼️ **Attached for inspection:** `{st.session_state.vision_image_name}` "
                "| Your next prompt will execute multimodal analysis."
            )

        # Chat message stream
        if not st.session_state.chat_history:
            st.markdown(
                """
                <div style="text-align: center; padding: 2.5rem 1rem; color: #94a3b8; background: #0f172a; border-radius: 12px; border: 1px dashed #334155; margin-bottom: 1rem;">
                    <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚙️</div>
                    <h3 style="color: #f8fafc; margin-bottom: 0.5rem;">VALENCE Industrial Knowledge Assistant</h3>
                    <p style="font-size: 0.95rem; max-width: 500px; margin: 0 auto 1rem auto;">
                        Ask technical questions from indexed equipment manuals, troubleshooting guides, and SOPs with grounded citations.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Quick prompt suggestions
            quick_cols = st.columns(3)
            with quick_cols[0]:
                if st.button("🔍 Operating Pressure Limits", use_container_width=True):
                    _process_query("What is the normal operating pressure range?", backend)
            with quick_cols[1]:
                if st.button("🚨 Emergency Shutdown", use_container_width=True):
                    _process_query("What is the emergency shutdown sequence?", backend)
            with quick_cols[2]:
                if st.button("🔧 Lubrication Schedule", use_container_width=True):
                    _process_query("What are the lubrication and maintenance intervals?", backend)

        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                render_user_message(msg)
            elif msg["role"] == "assistant":
                render_assistant_message(msg, use_mock=use_mock)

        # Chat Input
        prompt = st.chat_input("Ask a question about equipment operation, troubleshooting, or SOPs...", key="modern_chat_input")
        if prompt:
            _process_query(prompt, backend)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2: INCIDENT OPERATIONS (PHASE 2)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_incident:
        incident_service = st.session_state.get("incident_service")
        if incident_service:
            render_incident_controls(incident_service, backend=backend)
        else:
            st.error("Incident service unavailable in session state.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3: KNOWLEDGE BASE & INDEXING
    # ══════════════════════════════════════════════════════════════════════════
    with tab_docs:
        st.subheader("📄 Document Ingestion & Vector Indexing")
        st.caption("Upload technical manuals or SOPs in PDF format and index them into the local vector store.")

        col_upload, col_meta = st.columns([5, 4])
        with col_upload:
            uploaded_pdf = st.file_uploader(
                "Select Equipment Manual (PDF)",
                type=["pdf"],
                help="PDF documents are processed locally; text is chunked and stored in local vector index.",
                key="modern_pdf_uploader",
            )

        with col_meta:
            equipment_model = st.text_input(
                "Target Equipment Model (Optional)",
                placeholder="e.g. S7-1200 or Compressor-X1",
                help="Tags extracted chunks with this equipment model for precise filtered retrieval.",
                key="modern_equip_model",
            )
            is_synthetic = st.checkbox(
                "Synthetic / Test Benchmark Data",
                value=False,
                key="modern_synth_check",
            )

        # Indexing Action Button
        if st.button("📥 Index Document into Vector Store", type="primary", key="modern_btn_index", use_container_width=True):
            if uploaded_pdf is None:
                st.error("⚠️ Please select a PDF file to upload before indexing.")
            elif backend is None:
                st.error("❌ Cannot index: Backend service is unavailable.")
            else:
                with st.status("Indexing document...", expanded=True) as status:
                    try:
                        suffix = Path(uploaded_pdf.name).suffix or ".pdf"
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                            tmp_file.write(uploaded_pdf.getbuffer())
                            tmp_path = tmp_file.name

                        status.write("Parsing pages and extracting text...")
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

                        status.write("Generating local embeddings & storing vectors...")
                        summary: IndexingSummary = backend.index_chunks(clean_chunks)
                        st.session_state.last_indexing_summary = summary

                        st.session_state.indexed_docs[uploaded_pdf.name] = {
                            "document_id": clean_chunks[0].document_id if clean_chunks else "unknown",
                            "chunks_count": len(clean_chunks),
                            "equipment_model": equipment_model.strip() or None,
                            "synthetic": is_synthetic,
                        }

                        if summary.chunks_failed > 0:
                            status.update(label=f"⚠️ Indexing finished with {summary.chunks_failed} errors", state="error")
                        else:
                            status.update(label=f"✅ Successfully indexed {summary.chunks_indexed} chunks!", state="complete")
                    except Exception as ex:
                        status.update(label="❌ Indexing Failed", state="error")
                        st.error(f"Ingestion error: {ex}")

        # Summary Metrics
        st.markdown("---")
        st.subheader("📚 Indexed Manuals Overview")
        if st.session_state.last_indexing_summary:
            s = st.session_state.last_indexing_summary
            stat_cols = st.columns(4)
            stat_cols[0].metric("Total Received", s.total_chunks_received)
            stat_cols[1].metric("Chunks Indexed", s.chunks_indexed)
            stat_cols[2].metric("Duplicates Skipped", s.chunks_skipped)
            stat_cols[3].metric("Errors / Failed", s.chunks_failed)

        # List of indexed docs
        if st.session_state.indexed_docs:
            for fname, meta in st.session_state.indexed_docs.items():
                with st.container():
                    st.markdown(
                        f"""
                        <div style="background:#1e293b; padding:0.75rem 1rem; border-radius:8px; border:1px solid #334155; margin-bottom:0.5rem; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-weight:600; color:#f8fafc;">📄 {fname}</span>
                                <span style="font-size:0.8rem; color:#94a3b8; margin-left:0.5rem;">({meta['document_id']})</span>
                            </div>
                            <div>
                                <span style="background:rgba(59,130,246,0.2); color:#60a5fa; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.8rem;">
                                    {meta['chunks_count']} chunks
                                </span>
                                {'<span style="background:rgba(16,185,129,0.2); color:#34d399; padding:0.2rem 0.6rem; border-radius:4px; font-size:0.8rem; margin-left:0.3rem;">Model: ' + meta["equipment_model"] + '</span>' if meta["equipment_model"] else ''}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("No documents indexed yet. Upload a PDF manual above to begin.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3: VISUAL INSPECTION
    # ══════════════════════════════════════════════════════════════════════════
    with tab_vision:
        st.subheader("🖼️ Multimodal Equipment Visual Inspection")
        st.caption("Upload equipment photographs, nameplates, or gauge readings for visual diagnosis.")

        v_col1, v_col2 = st.columns([5, 4])
        with v_col1:
            uploaded_image = st.file_uploader(
                "Attach Equipment Inspection Photo",
                type=_SUPPORTED_IMAGE_TYPES,
                key="modern_image_uploader",
            )

            if uploaded_image is not None:
                suffix = Path(uploaded_image.name).suffix or ".png"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="valence_img_") as tmp_img:
                    tmp_img.write(uploaded_image.getbuffer())
                    st.session_state.vision_image_path = tmp_img.name
                    st.session_state.vision_image_name = uploaded_image.name
                    st.session_state.vision_mode_active = True

                st.success(f"✅ Image Attached: `{uploaded_image.name}` ({uploaded_image.size / 1024:.0f} KB)")
                if st.button("🗑️ Remove Attached Image", key="modern_clear_img"):
                    st.session_state.vision_image_path = None
                    st.session_state.vision_image_name = None
                    st.session_state.vision_mode_active = False
                    st.rerun()

        with v_col2:
            if st.session_state.get("vision_mode_active") and uploaded_image:
                st.image(uploaded_image, caption=f"Inspection Target: {uploaded_image.name}", use_container_width=True)
            else:
                st.markdown(
                    """
                    <div style="border: 2px dashed #334155; border-radius: 8px; padding: 2rem; text-align: center; color: #64748b;">
                        📷 No inspection image attached.<br>Upload a photo on the left to activate visual diagnosis.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4: SYSTEM & MODEL CONTROL
    # ══════════════════════════════════════════════════════════════════════════
    with tab_settings:
        st.subheader("⚙️ System Configuration & Diagnostics")

        set_col1, set_col2 = st.columns(2)
        with set_col1:
            st.markdown("#### Execution Engine")
            if hasattr(st, "toggle"):
                new_mock = st.toggle(
                    "Run in Mock Backend Mode",
                    value=use_mock,
                    help="Toggle between in-memory simulation and live local Ollama/Qdrant execution.",
                    key="modern_mock_toggle",
                )
            else:
                new_mock = st.checkbox(
                    "Run in Mock Backend Mode",
                    value=use_mock,
                    help="Toggle between in-memory simulation and live local Ollama/Qdrant execution.",
                    key="modern_mock_toggle",
                )
            if new_mock != use_mock:
                st.session_state.use_mock = new_mock
                st.rerun()

            if use_mock:
                st.warning("🔶 In-Memory Mock Active — Deterministic simulation without local models.")
            else:
                st.success("🟢 Live Engine Active — Connecting to local Ollama and Qdrant.")

        with set_col2:
            st.markdown("#### Offline Diagnostics")
            if st.button("🩺 Run Environment Diagnostics", use_container_width=True):
                try:
                    from backend.diagnostics import run_diagnostics
                    report = run_diagnostics()
                    st.code(report.summary(), language="text")
                except Exception as e:
                    st.error(f"Diagnostics error: {e}")


def _process_query(query: str, backend) -> None:
    """Processes user query and appends assistant answer."""
    vision_active = (
        st.session_state.get("vision_mode_active")
        and st.session_state.get("vision_image_path") is not None
    )
    image_name = st.session_state.get("vision_image_name") if vision_active else None

    st.session_state.chat_history.append({"role": "user", "content": query, "image_name": image_name})

    if backend is None:
        ans = Answer(text="Cannot process query: Backend service is unavailable.", evidence=[], insufficient_evidence=True)
    elif vision_active:
        try:
            ans = backend.answer_with_image(
                question=query,
                image_path=st.session_state.vision_image_path,
                equipment_model=None,
            )
        except Exception as e:
            ans = Answer(text=f"❌ Vision interpretation error: {e}", evidence=[], insufficient_evidence=True)
    else:
        try:
            ans = backend.answer_question(question=query, equipment_model=None)
        except Exception as e:
            ans = Answer(text=f"❌ Backend query error: {e}", evidence=[], insufficient_evidence=True)

    st.session_state.chat_history.append({"role": "assistant", "answer": ans, "image_name": image_name})
    st.rerun()

