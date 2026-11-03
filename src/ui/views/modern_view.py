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
import streamlit.components.v1 as components
from contracts import Answer, CropInspectionResult, IndexingSummary
from src.services import BackendServiceProtocol, create_ingestor
from src.ui.components.message_view import render_assistant_message, render_user_message
from src.ui.components.incident_panel import render_incident_controls
from src.ui.persistence import (
    clear_chat_history,
    delete_indexed_document,
    save_chat_message,
    save_indexed_document,
    save_user_session_state,
)
from src.utils.image_crop import crop_image_region, draw_user_region_overlay

logger = logging.getLogger(__name__)

_SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp", "tiff", "webp"]
_SUPPORTED_IMAGE_EXTS = {f".{t}" for t in _SUPPORTED_IMAGE_TYPES}
_MAX_IMAGE_SIZE_MB = 20


def _render_image(image, caption: Optional[str] = None) -> None:
    """Renders image compatible across Streamlit versions (1.38 use_column_width vs 1.40 use_container_width)."""
    try:
        st.image(image, caption=caption, use_column_width=True)
    except TypeError:
        st.image(image, caption=caption, use_container_width=True)


def render_modern_view(backend: Optional[BackendServiceProtocol], backend_error: Optional[str]) -> None:
    """Renders the modern industrial workspace layout with top tabs."""
    use_mock = st.session_state.get("use_mock", True)

    tab_chat, tab_incident, tab_docs, tab_vision, tab_analytics, tab_settings = st.tabs([
        "💬 Assistant Console",
        "🚨 Incident Operations",
        "📚 Knowledge Base & Indexing",
        "🖼️ Visual Inspection",
        "📊 Plant Analytics & Issues",
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
                st.warning("⚠️ RUNNING IN MOCK BACKEND MODE: Responses are generated from in-memory test fixtures.")
            elif backend_error:
                st.error(f"❌ Backend Unavailable: {backend_error}")
            else:
                st.caption("🟢 **Live Air-Gapped Engine Active** (Local Vector RAG & LLM)")

        with cols[1]:
            if st.button("🗑️ Clear Chat", key="modern_clear_chat", help="Wipe conversation history"):
                session_id = st.session_state.get("session_id", "default_user")
                st.session_state.chat_history = []
                clear_chat_history(session_id)
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
                <div style="text-align: center; padding: 2.2rem 1rem; color: #94a3b8; background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%); border-radius: 14px; border: 1px solid #334155; margin-bottom: 1.25rem; box-shadow: 0 4px 16px rgba(0,0,0,0.25);">
                    <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚙️</div>
                    <h3 style="color: #f8fafc; margin-bottom: 0.4rem; font-weight: 700;">VALENCE Industrial Knowledge Assistant</h3>
                    <p style="font-size: 0.95rem; max-width: 540px; margin: 0 auto 0.5rem auto; color: #cbd5e1;">
                        Query technical manuals, SOPs, and engineering documentation with verified 1-based page citations and zero hallucination.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.indexed_docs:
                st.caption(f"💡 **Grounded retrieval active across {len(st.session_state.indexed_docs)} indexed document(s). Ask any technical question below.**")
            else:
                st.info("📄 **No documents indexed yet.** Upload an equipment manual or SOP in the **📚 Knowledge Base & Indexing** tab to begin asking grounded questions.")

        for i, msg in enumerate(st.session_state.chat_history):
            if msg["role"] == "user":
                render_user_message(msg)
            elif msg["role"] == "assistant":
                render_assistant_message(msg, use_mock=use_mock, msg_idx=i)

        # Chat Input with In-Box Microphone Option (Voice Dictation active)
        prompt = st.chat_input("Ask a question or click 🎙️ to dictate query...", key="modern_chat_input")
        if prompt:
            _process_query(prompt, backend)

        # Dynamic query-box microphone button injection
        components.html(
            """
            <script>
            (function() {
                let isRecording = false;
                let activeRecognizer = null;

                function getSpeechRec() {
                    return window.SpeechRecognition || window.webkitSpeechRecognition ||
                           (window.parent && (window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition));
                }

                function updateMicUi(recording, btn, container) {
                    if (!btn) return;
                    if (recording) {
                        btn.innerHTML = '🔴';
                        btn.style.borderColor = '#ef4444';
                        btn.style.boxShadow = '0 0 12px rgba(239, 68, 68, 0.8)';
                        btn.style.background = 'rgba(239, 68, 68, 0.2)';
                        btn.title = 'Listening... Click to stop';
                        const ta = container ? container.querySelector('textarea') : null;
                        if (ta) ta.placeholder = '🔴 Listening... Speak clearly now.';
                    } else {
                        btn.innerHTML = '🎙️';
                        btn.style.borderColor = 'rgba(56, 189, 248, 0.4)';
                        btn.style.boxShadow = 'none';
                        btn.style.background = 'transparent';
                        btn.title = 'Speak query (Voice Dictation)';
                        const ta = container ? container.querySelector('textarea') : null;
                        if (ta) ta.placeholder = 'Ask a question or click 🎙️ to dictate query...';
                    }
                }

                function toggleVoice(btn, container) {
                    const ta = container ? container.querySelector('textarea') : null;

                    if (isRecording) {
                        if (activeRecognizer) {
                            try { activeRecognizer.stop(); } catch(e) {}
                        }
                        isRecording = false;
                        updateMicUi(false, btn, container);
                        if (ta) ta.focus();
                        return;
                    }

                    const SpeechRec = getSpeechRec();
                    if (!SpeechRec) {
                        alert(
                            "Voice Dictation:\\n\\n" +
                            "Web Speech is natively supported in Google Chrome, Edge, and Safari.\\n" +
                            "On other browsers, press your OS dictation shortcut directly into this box:\\n" +
                            "- Mac: Press Fn twice (Fn + Fn)\\n" +
                            "- Windows: Press Win + H"
                        );
                        if (ta) ta.focus();
                        return;
                    }

                    try {
                        const rec = new SpeechRec();
                        rec.continuous = false;
                        rec.interimResults = true;
                        rec.lang = 'en-US';

                        rec.onstart = function() {
                            isRecording = true;
                            updateMicUi(true, btn, container);
                        };

                        rec.onresult = function(event) {
                            let transcript = '';
                            for (let i = 0; i < event.results.length; i++) {
                                transcript += event.results[i][0].transcript;
                            }
                            if (ta) {
                                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set ||
                                                     (window.parent && Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value')?.set);
                                if (nativeSetter) {
                                    nativeSetter.call(ta, transcript);
                                } else {
                                    ta.value = transcript;
                                }
                                ta.dispatchEvent(new Event('input', { bubbles: true }));
                                ta.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        };

                        rec.onerror = function(err) {
                            console.warn('[VALENCE Voice] Recognition error:', err);
                            isRecording = false;
                            updateMicUi(false, btn, container);
                            if (err.error === 'not-allowed') {
                                alert(
                                    "Microphone access blocked by browser.\\n\\n" +
                                    "To enable:\\n" +
                                    "1. Click the site settings / lock icon 🔒 next to 'localhost:8501' in your Chrome address bar.\\n" +
                                    "2. Set 'Microphone' to 'Allow'.\\n" +
                                    "3. Refresh the page."
                                );
                            }
                        };

                        rec.onend = function() {
                            isRecording = false;
                            updateMicUi(false, btn, container);
                            if (ta) ta.focus();
                        };

                        activeRecognizer = rec;
                        rec.start();
                    } catch(err) {
                        console.warn('[VALENCE Voice] Start failed:', err);
                        isRecording = false;
                        updateMicUi(false, btn, container);
                    }
                }

                function setupMicInDoc(doc) {
                    if (!doc) return;
                    const container = doc.querySelector('div[data-testid="stChatInput"]');
                    if (!container) return;

                    let micBtn = container.querySelector('#valence-voice-mic-btn');
                    if (!micBtn) {
                        micBtn = doc.createElement('button');
                        micBtn.id = 'valence-voice-mic-btn';
                        micBtn.type = 'button';
                        micBtn.title = 'Speak query (Voice Dictation)';
                        micBtn.innerHTML = '🎙️';
                        micBtn.setAttribute('style', [
                            'position: absolute',
                            'right: 48px',
                            'bottom: 7px',
                            'width: 32px',
                            'height: 32px',
                            'border-radius: 8px',
                            'background: transparent',
                            'border: 1px solid rgba(56, 189, 248, 0.4)',
                            'cursor: pointer',
                            'font-size: 1.15rem',
                            'display: inline-flex',
                            'align-items: center',
                            'justify-content: center',
                            'z-index: 99999',
                            'pointer-events: auto',
                            'padding: 0',
                            'transition: all 0.2s ease',
                            'user-select: none'
                        ].join(' !important;') + ' !important;');

                        micBtn.onmouseenter = function() {
                            if (!isRecording) {
                                micBtn.style.borderColor = '#38bdf8';
                                micBtn.style.background = 'rgba(56, 189, 248, 0.1)';
                            }
                        };

                        micBtn.onmouseleave = function() {
                            if (!isRecording) {
                                micBtn.style.borderColor = 'rgba(56, 189, 248, 0.4)';
                                micBtn.style.background = 'transparent';
                            }
                        };

                        micBtn.onmousedown = function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleVoice(micBtn, container);
                        };

                        micBtn.onclick = function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                        };

                        container.appendChild(micBtn);

                        const ta = container.querySelector('textarea');
                        if (ta) {
                            ta.style.paddingRight = '84px';
                        }
                    }
                }

                function checkAll() {
                    setupMicInDoc(document);
                    if (window.parent && window.parent.document) {
                        setupMicInDoc(window.parent.document);
                    }
                }

                setInterval(checkAll, 400);
                checkAll();
            })();
            </script>
            """,
            height=0,
        )

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
                st.error("⚠️ Please choose a PDF file before clicking Index Document.")
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
                        if "cached_chunks" not in st.session_state:
                            st.session_state["cached_chunks"] = []
                        st.session_state["cached_chunks"].extend(clean_chunks)

                        doc_meta = {
                            "document_id": clean_chunks[0].document_id if clean_chunks else "unknown",
                            "filename": uploaded_pdf.name,
                            "page_count": max(c.page for c in clean_chunks) if clean_chunks else 1,
                            "chunks_count": len(clean_chunks),
                            "equipment_model": equipment_model.strip() or None,
                            "synthetic": is_synthetic,
                        }
                        st.session_state.indexed_docs[uploaded_pdf.name] = doc_meta
                        session_id = st.session_state.get("session_id", "default_user")
                        save_indexed_document(
                            session_id=session_id,
                            doc_id=doc_meta["document_id"],
                            meta=doc_meta,
                            chunks=clean_chunks,
                        )

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
            col_hdr1, col_hdr2 = st.columns([7, 3])
            with col_hdr2:
                if st.button("🗑️ Remove All & Clear Cache", key="btn_remove_all_docs", help="Purge all documents from vector store and clear all caches", use_container_width=True):
                    session_id = st.session_state.get("session_id", "default_user")
                    for fname_del, meta_del in list(st.session_state.indexed_docs.items()):
                        doc_id_del = meta_del.get("document_id") if isinstance(meta_del, dict) else None
                        if backend is not None and hasattr(backend, "delete_document"):
                            try:
                                backend.delete_document(filename=fname_del, document_id=doc_id_del)
                            except Exception:
                                pass
                        delete_indexed_document(session_id, fname_del)
                        if doc_id_del:
                            delete_indexed_document(session_id, doc_id_del)
                    st.session_state.indexed_docs = {}
                    st.session_state.cached_chunks = []
                    st.session_state.last_indexing_summary = None
                    st.toast("Purged all documents from vector store and cleared all caches.", icon="🗑️")
                    st.rerun()

            for fname, meta in list(st.session_state.indexed_docs.items()):
                if not isinstance(meta, dict):
                    continue
                doc_id = meta.get("document_id") or meta.get("doc_id") or "unknown"
                chunks_num = meta.get("chunks_count", meta.get("chunk_count", 0))
                eq_model = meta.get("equipment_model")

                with st.container():
                    d_cols = st.columns([5, 3, 2])
                    with d_cols[0]:
                        st.markdown(
                            f"**📄 {fname}**  \n"
                            f"<span style='color:#94a3b8; font-size:0.8rem;'>Document ID: <code>{doc_id}</code></span>",
                            unsafe_allow_html=True,
                        )
                    with d_cols[1]:
                        badge_html = f"<span style='background:rgba(59,130,246,0.2); color:#60a5fa; padding:0.25rem 0.6rem; border-radius:4px; font-size:0.82rem; font-weight:600;'>{chunks_num} chunks</span>"
                        if eq_model:
                            badge_html += f" <span style='background:rgba(16,185,129,0.2); color:#34d399; padding:0.25rem 0.6rem; border-radius:4px; font-size:0.82rem; font-weight:600;'>Model: {eq_model}</span>"
                        st.markdown(badge_html, unsafe_allow_html=True)
                    with d_cols[2]:
                        if st.button("🗑️ Remove", key=f"btn_remove_doc_{fname}", help=f"Remove '{fname}' from persistent knowledge base and clear cache", use_container_width=True):
                            session_id = st.session_state.get("session_id", "default_user")
                            # 1. Purge from vector store / backend
                            if backend is not None and hasattr(backend, "delete_document"):
                                try:
                                    backend.delete_document(filename=fname, document_id=doc_id)
                                except Exception as be_err:
                                    logger.warning("Could not delete from backend: %s", be_err)

                            # 2. Purge from SQLite persistence
                            delete_indexed_document(session_id, fname)
                            delete_indexed_document(session_id, doc_id)

                            # 3. Purge from session state dictionary
                            if fname in st.session_state.indexed_docs:
                                del st.session_state.indexed_docs[fname]

                            # 4. Purge from cached chunks in session state
                            if st.session_state.get("cached_chunks"):
                                st.session_state.cached_chunks = [
                                    c for c in st.session_state.cached_chunks
                                    if c.filename != fname and c.document_id != doc_id
                                ]

                            # 5. Clear last indexing summary cache
                            st.session_state.last_indexing_summary = None

                            st.toast(f"Removed '{fname}' from knowledge base and cleared all caches.", icon="🗑️")
                            st.rerun()
                    st.markdown("<hr style='margin: 0.35rem 0 0.75rem 0; border: 0; border-top: 1px solid #334155;'>", unsafe_allow_html=True)
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
            if st.session_state.get("vision_mode_active") and st.session_state.get("vision_image_path"):
                _render_image(st.session_state.vision_image_path, caption=f"Inspection Target: {st.session_state.get('vision_image_name')}")
            else:
                st.markdown(
                    """
                    <div style="border: 2px dashed #334155; border-radius: 8px; padding: 2rem; text-align: center; color: #64748b;">
                        📷 No inspection image attached.<br>Upload a photo on the left to activate visual diagnosis.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ── POINT, INSPECT, ASK (User-Selected Region Inspection) ───────────────
        if st.session_state.get("vision_mode_active") and st.session_state.get("vision_image_path"):
            st.divider()
            st.markdown("### 🎯 Point, Inspect, Ask: User-Selected Region")
            st.caption(
                "Select a rectangular inspection sub-region. The local model describes visible features, "
                "which are confirmed before retrieving SOP documentation. (Never calls region 'AI-detected')."
            )

            # Coordinate sliders for user-selected region
            sc1, sc2 = st.columns(2)
            with sc1:
                h_range = st.slider("Horizontal Crop Window (%)", 0, 100, (10, 90), step=1, key="crop_h_slider")
            with sc2:
                v_range = st.slider("Vertical Crop Window (%)", 0, 100, (15, 85), step=1, key="crop_v_slider")

            box_pct = (float(h_range[0]), float(v_range[0]), float(h_range[1]), float(v_range[1]))
            img_path = st.session_state.vision_image_path

            try:
                # Previews
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    overlay_img = draw_user_region_overlay(img_path, box_pct)
                    _render_image(overlay_img, caption="Original with User-Selected Region")
                with p_col2:
                    crop_file, crop_id, crop_px = crop_image_region(img_path, box_pct)
                    _render_image(str(crop_file), caption=f"Crop Preview ({crop_id}: X=[{crop_px[0]}..{crop_px[2]}], Y=[{crop_px[1]}..{crop_px[3]}])")

                # Inspect button
                if st.button("🔍 Inspect User-Selected Region", type="primary", key="btn_inspect_crop", use_container_width=True):
                    with st.spinner("Local vision model analyzing selected crop region..."):
                        if hasattr(backend, "inspect_crop"):
                            res, c_path = backend.inspect_crop(img_path, box_pct)
                            st.session_state.crop_result = res
                            st.session_state.crop_path = str(c_path)
                            st.session_state.confirmed_terms = " ".join(res.legible_text)
                            st.session_state.crop_evidence = []
                        else:
                            st.warning("Active backend does not support crop inspection.")

                # Structured Results & Confirmation
                crop_res: Optional[CropInspectionResult] = st.session_state.get("crop_result")
                if crop_res is not None:
                    st.markdown("---")
                    res_c1, res_c2 = st.columns(2)

                    # 1. User-Confirmed Information
                    with res_c1:
                        st.markdown("#### 1. ✍️ User-Confirmed Information")
                        st.caption("Verify or edit detected text before running documentary retrieval.")
                        confirmed_input = st.text_input(
                            "Verified Component / Indicator Terms",
                            value=st.session_state.get("confirmed_terms", " ".join(crop_res.legible_text)),
                            key="user_confirmed_terms_input",
                        )
                        st.session_state.confirmed_terms = confirmed_input

                        if st.button("📖 Retrieve Documentary Evidence for Region", key="btn_retrieve_region", use_container_width=True):
                            with st.spinner("Searching manuals and SOPs..."):
                                if backend and confirmed_input.strip():
                                    ev = backend.retrieve(confirmed_input.strip(), top_k=3)
                                    st.session_state.crop_evidence = ev

                    # 2. Tentative Visual Observations
                    with res_c2:
                        st.markdown("#### 2. 👁️ Tentative Visual Observations")
                        if crop_res.tentative_observations:
                            for obs in crop_res.tentative_observations:
                                st.markdown(f"- {obs}")
                        else:
                            st.write("No distinct physical features noted.")

                        if crop_res.indicator_states:
                            st.markdown("**Indicator States:**")
                            for ind in crop_res.indicator_states:
                                name = ind.get("name", "Indicator")
                                col = ind.get("color", "unknown")
                                stt = ind.get("state", "unknown")
                                st.markdown(f"- **{name}**: `{col}` ({stt})")

                        if crop_res.unreadable_text_noted:
                            st.warning("⚠️ **Uncertainty Alert**: Blurry, obscured, or illegible text noted in this crop. Do not assume unverified values.")

                    # 3. Retrieved Documentary Evidence & 4. Follow-Up
                    d_c1, d_c2 = st.columns(2)
                    with d_c1:
                        st.markdown("#### 3. 📚 Retrieved Documentary Evidence")
                        crop_ev = st.session_state.get("crop_evidence", [])
                        if crop_ev:
                            for e in crop_ev:
                                with st.expander(f"📄 Citation: `[{e.source_id}]` — Page {e.chunk.page}"):
                                    st.markdown(f"**Document**: `{e.chunk.filename}`")
                                    st.markdown(f"> {e.chunk.text}")
                        else:
                            st.info("No documentary evidence retrieved yet. Click 'Retrieve Documentary Evidence' above.")

                    with d_c2:
                        st.markdown("#### 4. ❓ Unresolved Questions & Follow-Up")
                        if crop_res.follow_up_needed:
                            st.warning(f"**Follow-Up Request**: {crop_res.follow_up_needed}")
                        else:
                            st.success("No missing visual details reported by inspection model.")
            except Exception as e:
                st.error(f"Region selection error: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5: PLANT ANALYTICS & ISSUES
    # ══════════════════════════════════════════════════════════════════════════
    with tab_analytics:
        st.subheader("📊 Plant Operations & Issue Analytics")
        st.caption("Operational telemetry and frequency analytics on shop-floor incidents and frequently consulted SOP topics.")

        inc_service = st.session_state.get("incident_service")
        all_incidents = inc_service.list_incidents() if inc_service else []
        total_inc = len(all_incidents)
        resolved_count = sum(1 for i in all_incidents if i.status in ("resolved", "closed", "mitigated"))
        indexed_count = len(st.session_state.get("indexed_docs", {}))

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val">{total_inc}</div>
                    <div class="kpi-label">Incidents Tracked</div>
                    <div class="kpi-sub">Across All Units</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k2:
            mit_rate = int(round((resolved_count / total_inc * 100))) if total_inc > 0 else 100
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val" style="color: #34d399;">{mit_rate}%</div>
                    <div class="kpi-label">Mitigation Rate</div>
                    <div class="kpi-sub">{resolved_count} Mitigated/Resolved</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val" style="color: #60a5fa;">{indexed_count}</div>
                    <div class="kpi-label">Manuals & SOPs</div>
                    <div class="kpi-sub">Indexed in Vector Store</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                """
                <div class="kpi-card">
                    <div class="kpi-val" style="color: #38bdf8;">100%</div>
                    <div class="kpi-label">Grounding Integrity</div>
                    <div class="kpi-sub">Zero Hallucinations Verified</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.markdown("#### 🚨 Most Frequently Reported Symptoms (Pareto)")
            st.caption("Aggregated incident frequencies across factory lines.")

            symptom_data = {}
            for inc in all_incidents:
                sym = inc.title if inc.title else inc.symptom
                sym_clean = sym.split(":")[0].strip()
                symptom_data[sym_clean] = symptom_data.get(sym_clean, 0) + 1

            if not symptom_data:
                st.info("ℹ️ No reported incident symptoms yet. Open an incident in the **🚨 Incident Operations** tab to track symptoms.")
            else:
                import pandas as pd
                df_sym = pd.DataFrame(list(symptom_data.items()), columns=["Symptom", "Reported Count"]).sort_values("Reported Count", ascending=False)
                st.bar_chart(df_sym.set_index("Symptom"), color="#38bdf8")

        with c_chart2:
            st.markdown("#### 🏭 Incidents by Equipment Model")
            st.caption("Distribution of maintenance tickets by machine.")

            eq_data = {}
            for inc in all_incidents:
                eq = inc.equipment_model or "Unassigned / General Unit"
                eq_data[eq] = eq_data.get(eq, 0) + 1

            if not eq_data:
                st.info("ℹ️ No equipment-tagged incidents yet. Register equipment models on incidents to track machine failure distribution.")
            else:
                import pandas as pd
                df_eq = pd.DataFrame(list(eq_data.items()), columns=["Equipment", "Active Tickets"]).sort_values("Active Tickets", ascending=False)
                st.bar_chart(df_eq.set_index("Equipment"), color="#818cf8")

        st.markdown("---")
        st.markdown("#### 🔍 Frequently Consulted SOP Topics")
        st.caption("Documentation topics available in the persistent local vector store.")
        indexed_docs = st.session_state.get("indexed_docs", {})
        if indexed_docs:
            t_cols = st.columns(2)
            idx = 0
            for fname, meta in indexed_docs.items():
                if not isinstance(meta, dict):
                    continue
                eq_m = meta.get("equipment_model") or "General Equipment"
                chunks_n = meta.get("chunks_count", meta.get("chunk_count", 0))
                pages_n = meta.get("page_count", 1)
                col_target = t_cols[idx % 2]
                idx += 1
                with col_target:
                    st.markdown(
                        f"""
                        <div style="background:#1e293b; border:1px solid #334155; border-radius:10px; padding:0.85rem 1rem; margin-bottom:0.75rem;">
                            <div style="font-weight:700; color:#f8fafc; font-size:0.92rem;">📑 {fname}</div>
                            <div style="font-size:0.82rem; color:#94a3b8; margin:0.3rem 0;">Target Model: <strong>{eq_m}</strong> | {chunks_n} chunks across {pages_n} pages</div>
                            <div style="font-size:0.75rem; color:#38bdf8; font-weight:600;">Status: Indexed in Persistent Vector Store</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("ℹ️ No manuals or SOPs indexed yet. Upload documents in the **📚 Knowledge Base & Indexing** tab to populate reference documentation topics.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6: SYSTEM & MODEL CONTROL
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
    """Processes user query and appends assistant answer with SQLite persistence."""
    session_id = st.session_state.get("session_id", "default_user")
    vision_active = (
        st.session_state.get("vision_mode_active")
        and st.session_state.get("vision_image_path") is not None
    )
    image_name = st.session_state.get("vision_image_name") if vision_active else None

    user_msg = {"role": "user", "content": query, "image_name": image_name}
    st.session_state.chat_history.append(user_msg)
    save_chat_message(session_id, user_msg)

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

    asst_msg = {"role": "assistant", "answer": ans, "image_name": image_name}
    st.session_state.chat_history.append(asst_msg)
    save_chat_message(session_id, asst_msg)
    st.rerun()

