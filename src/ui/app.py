"""Main entrypoint for VALENCE Frontend with Top Navbar View Toggle.

Supports seamless toggling between:
- 🚀 Modern UI: Tabbed industrial workspace (Chat, Document Ingestion, Vision Hub, System Control).
- 🏛️ Classic UI: Original sidebar-driven layout.
All document indexing, chat sessions, and inspection states are shared across both views.
"""

from __future__ import annotations

import logging
from typing import Optional

import streamlit as st

from src.services import BackendServiceProtocol
from src.ui.state import get_or_create_backend, init_session_state
from src.ui.styles.theme import apply_theme
from src.ui.components.navbar import render_navbar
from src.ui.views.classic_view import render_classic_view
from src.ui.views.modern_view import render_modern_view

logger = logging.getLogger(__name__)


def main() -> None:
    st.set_page_config(
        page_title="VALENCE - Industrial Knowledge Assistant",
        page_icon="⚙️",
        layout="wide",
    )

    # Initialize shared state & apply custom styling
    init_session_state()
    apply_theme()

    # Re-initialize backend if mode toggled or uninitialized
    use_mock = st.session_state.get("use_mock", True)
    if st.session_state.backend is None:
        backend_inst, err = get_or_create_backend(use_mock=use_mock)
        st.session_state.backend = backend_inst
        st.session_state.backend_error = err

    backend: Optional[BackendServiceProtocol] = st.session_state.backend
    backend_error: Optional[str] = st.session_state.backend_error

    # Render top navbar with view toggle
    current_view = render_navbar()

    # Render selected view
    if current_view == "classic":
        render_classic_view(backend, backend_error)
    else:
        render_modern_view(backend, backend_error)


if __name__ == "__main__":
    main()
