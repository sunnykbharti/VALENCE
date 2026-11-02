"""Session state initialization and backend factory for VALENCE frontend."""

from __future__ import annotations

import logging
from typing import Optional
import streamlit as st
from src.services import BackendServiceProtocol

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
            return None, (
                "Live backend is not implemented yet by Member B "
                "(create_backend raised NotImplementedError)."
            )
        except RuntimeError as e:
            return None, f"Local backend connection failed: {e}"
        except Exception as e:
            return None, f"Backend unavailable: {e}"


def init_session_state() -> None:
    """Initializes persistent session state keys."""
    defaults: dict = {
        "chat_history": [],
        "indexed_docs": {},
        "backend": None,
        "use_mock": False,  # Default to Live Engine for presentation path
        "last_indexing_summary": None,
        "backend_error": None,
        "ui_view": "modern",  # "modern" or "classic"
        # Vision state
        "vision_image_path": None,
        "vision_image_name": None,
        "vision_mode_active": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

