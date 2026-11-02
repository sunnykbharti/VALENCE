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
            backend = create_backend(mock=True)
            if st.session_state.get("cached_chunks"):
                try:
                    backend.index_chunks(st.session_state["cached_chunks"])
                except Exception:
                    pass
            return backend, None
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
    import os
    import sys
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    is_testing = "unittest" in sys.modules or any("test" in arg.lower() for arg in sys.argv)
    raw_mock = os.getenv("VALENCE_MOCK_MODE", "0").lower().strip()
    if is_testing:
        default_mock = True
    else:
        default_mock = raw_mock in ("1", "true", "yes")

    defaults: dict = {
        "chat_history": [],
        "indexed_docs": {},
        "backend": None,
        "use_mock": default_mock,
        "last_indexing_summary": None,
        "backend_error": None,
        "ui_view": "classic",  # Default to classic for backward compatibility, toggleable via navbar
        # Vision state
        "vision_image_path": None,
        "vision_image_name": None,
        "vision_mode_active": False,
        "cached_chunks": [],
        # Phase 2: Incident-oriented workflow
        "active_incident_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "incident_service" not in st.session_state or st.session_state.get("incident_service_is_mock") != default_mock:
        from src.services import create_incident_service
        st.session_state["incident_service"] = create_incident_service(mock=default_mock)
        st.session_state["incident_service_is_mock"] = default_mock


