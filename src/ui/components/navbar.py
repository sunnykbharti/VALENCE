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

    cols = st.columns([4, 2, 2, 3])

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
                    📄 {doc_count} Doc{'s' if doc_count != 1 else ''} Indexed
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[2]:
        use_mock = st.session_state.get("use_mock", True)
        if use_mock:
            pill_html = """
            <span style="background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.3); padding:0.25rem 0.6rem; border-radius:9999px; font-size:0.8rem; font-weight:600;">
                🔶 Dev Mock (Testing)
            </span>
            """
        else:
            pill_html = """
            <span style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); padding:0.25rem 0.6rem; border-radius:9999px; font-size:0.8rem; font-weight:600;">
                🟢 Live Engine
            </span>
            """
        st.markdown(f"<div style='padding-top:0.35rem;'>{pill_html}</div>", unsafe_allow_html=True)

    with cols[3]:
        # Universal backward-compatible view toggle between Classic and Modern
        options = ["🚀 Modern UI", "🏛️ Classic UI"]
        default_index = 0 if st.session_state["ui_view"] == "modern" else 1

        selected_view = st.radio(
            "Frontend View",
            options=options,
            index=default_index,
            horizontal=True,
            label_visibility="collapsed",
            key="ui_view_selector",
        )

        if selected_view == "🏛️ Classic UI":
            st.session_state["ui_view"] = "classic"
        else:
            st.session_state["ui_view"] = "modern"

    st.markdown("<hr style='margin-top:0.4rem; margin-bottom:1rem; border:0; border-top:1px solid #334155;'>", unsafe_allow_html=True)
    return st.session_state["ui_view"]

