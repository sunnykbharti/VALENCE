"""Top navigation bar component with UI view toggle and system status indicators."""

from __future__ import annotations

import streamlit as st


def render_navbar() -> str:
    """Renders the top navbar with frontend view toggle and status pills.

    Returns:
        The selected view string ("classic" or "modern").
    """
    if "ui_view" not in st.session_state:
        st.session_state["ui_view"] = "modern"

    cols = st.columns([4, 3, 2, 3])

    with cols[0]:
        st.markdown(
            """
            <div style="display:flex; align-items:center; gap:0.6rem; padding-top:0.25rem;">
                <span style="font-size:1.4rem;">⚙️</span>
                <span style="font-size:1.15rem; font-weight:700; color:#f8fafc; letter-spacing:-0.02em;">
                    VALENCE
                </span>
                <span style="font-size:0.75rem; background:#3b82f6; color:white; padding:0.15rem 0.5rem; border-radius:4px; font-weight:600;">
                    AIR-GAPPED
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        doc_count = len(st.session_state.get("indexed_docs", {}))
        st.markdown(
            f"""
            <div style="padding-top:0.35rem;">
                <span style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); padding:0.25rem 0.6rem; border-radius:9999px; font-size:0.8rem; font-weight:600;">
                    📄 {doc_count} Doc{'s' if doc_count != 1 else ''} Indexed (SQLite Persistent)
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[2]:
        sess_name = st.session_state.get("session_id", "default_user")
        st.markdown(
            f"""
            <div style="padding-top:0.35rem;">
                <span style="background:rgba(148,163,184,0.15); color:#94a3b8; border:1px solid rgba(148,163,184,0.3); padding:0.25rem 0.6rem; border-radius:9999px; font-size:0.8rem; font-weight:600;">
                    👤 {sess_name}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[3]:
        use_mock = st.session_state.get("use_mock", False)
        if hasattr(st, "toggle"):
            new_mock = st.toggle(
                "🔶 Mock Mode" if use_mock else "🟢 Live Engine",
                value=use_mock,
                key="navbar_mock_toggle",
                help="Switch between Live Local Ollama and Dev Mock simulation.",
            )
        else:
            new_mock = st.checkbox(
                "🔶 Mock Mode" if use_mock else "🟢 Live Engine",
                value=use_mock,
                key="navbar_mock_toggle",
                help="Switch between Live Local Ollama and Dev Mock simulation.",
            )
        if new_mock != use_mock:
            st.session_state["use_mock"] = new_mock
            st.session_state["backend"] = None
            st.session_state["incident_service"] = None
            from src.ui.persistence import save_user_session_state
            save_user_session_state(
                session_id=sess_name,
                active_incident_id=st.session_state.get("active_incident_id"),
                use_mock=new_mock,
                vision_image_name=st.session_state.get("vision_image_name"),
                vision_image_path=st.session_state.get("vision_image_path"),
                vision_mode_active=st.session_state.get("vision_mode_active", False),
            )
            st.rerun()

    st.markdown("<hr style='margin-top:0.4rem; margin-bottom:1rem; border:0; border-top:1px solid #334155;'>", unsafe_allow_html=True)
    st.session_state["ui_view"] = "modern"
    return "modern"

