"""Main entrypoint for VALENCE Frontend with Top Navbar View Toggle.

Supports seamless toggling between:
- 🚀 Modern UI: Tabbed industrial workspace (Chat, Document Ingestion, Vision Hub, System Control).
- 🏛️ Classic UI: Original sidebar-driven layout.
All document indexing, chat sessions, and inspection states are shared across both views.
"""

from __future__ import annotations

import importlib
import logging
from typing import Optional

import streamlit as st

import src.ui.styles.theme as theme_mod
import src.ui.views.modern_view as modern_view_mod
# Auto-reload view and theme modules so edits take effect immediately on browser refresh
importlib.reload(theme_mod)
importlib.reload(modern_view_mod)
# In-box microphone option active in chat input query box

from src.services import BackendServiceProtocol
from src.ui.state import get_or_create_backend, init_session_state
from src.ui.styles.theme import apply_theme
from src.ui.components.navbar import render_navbar
from src.ui.views.modern_view import render_modern_view
from src.ui.voice_installer import install_voice_assets

logger = logging.getLogger(__name__)


def main() -> None:
    # Ensure client voice assets are installed in Streamlit static assets
    install_voice_assets()

    st.set_page_config(
        page_title="VALENCE - Industrial Knowledge Assistant",
        page_icon="⚙️",
        layout="wide",
    )

    # Initialize shared state & apply custom styling
    init_session_state()
    apply_theme()

    # Re-initialize backend & incident service if mode toggled or uninitialized
    use_mock = st.session_state.get("use_mock", True)
    if st.session_state.get("backend") is None or st.session_state.get("backend_is_mock") != use_mock:
        backend_inst, err = get_or_create_backend(use_mock=use_mock)
        st.session_state["backend"] = backend_inst
        st.session_state["backend_is_mock"] = use_mock
        st.session_state["backend_error"] = err
        if backend_inst is not None and st.session_state.get("cached_chunks"):
            try:
                backend_inst.index_chunks(st.session_state["cached_chunks"])
            except Exception as e:
                logger.warning("Could not re-populate cached chunks: %s", e)

    if st.session_state.get("incident_service") is None or st.session_state.get("incident_service_is_mock") != use_mock:
        import sys
        is_testing = "unittest" in sys.modules or any("test" in arg.lower() for arg in sys.argv)
        from src.services import create_incident_service
        st.session_state["incident_service"] = create_incident_service(mock=use_mock, populate_defaults=is_testing)
        st.session_state["incident_service_is_mock"] = use_mock

    backend: Optional[BackendServiceProtocol] = st.session_state["backend"]
    backend_error: Optional[str] = st.session_state["backend_error"]

    # Render top navbar
    render_navbar()

    # Render Modern UI workspace
    render_modern_view(backend, backend_error)


if __name__ == "__main__":
    main()
