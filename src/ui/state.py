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
    """Initializes persistent session state keys with SQLite recovery across refreshes."""
    import os
    import sys
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from src.ui.persistence import (
        load_chat_history,
        load_indexed_documents,
        load_user_session_state,
    )

    is_testing = "unittest" in sys.modules or any("test" in arg.lower() for arg in sys.argv)
    raw_mock = os.getenv("VALENCE_MOCK_MODE", "0").lower().strip()
    if is_testing:
        default_mock = True
    else:
        default_mock = raw_mock in ("1", "true", "yes")

    # Per-user persistent session identifier (customizable via URL ?user=operator1)
    session_id = "default_user"
    try:
        if hasattr(st, "query_params") and "user" in st.query_params:
            session_id = str(st.query_params["user"]).strip() or "default_user"
    except Exception:
        pass

    # Attempt to load persistent state from SQLite for this user
    saved_meta = load_user_session_state(session_id) if not is_testing else None
    saved_chat = load_chat_history(session_id) if not is_testing else []
    saved_docs, saved_chunks = load_indexed_documents(session_id) if not is_testing else ({}, [])

    active_inc = saved_meta["active_incident_id"] if saved_meta else None
    restored_mock = saved_meta["use_mock"] if saved_meta is not None else default_mock

    defaults: dict = {
        "session_id": session_id,
        "chat_history": saved_chat,
        "indexed_docs": saved_docs,
        "backend": None,
        "use_mock": restored_mock,
        "last_indexing_summary": None,
        "backend_error": None,
        "ui_view": "modern",  # Only 1 view: Modern UI
        # Vision state
        "vision_image_path": saved_meta["vision_image_path"] if saved_meta else None,
        "vision_image_name": saved_meta["vision_image_name"] if saved_meta else None,
        "vision_mode_active": saved_meta["vision_mode_active"] if saved_meta else False,
        "cached_chunks": saved_chunks,
        # Phase 2: Incident-oriented workflow
        "active_incident_id": active_inc,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "incident_service" not in st.session_state or st.session_state.get("incident_service_is_mock") != restored_mock:
        from src.services import create_incident_service
        st.session_state["incident_service"] = create_incident_service(mock=restored_mock, populate_defaults=is_testing)
        st.session_state["incident_service_is_mock"] = restored_mock


