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
            from contracts import Chunk
            backend = create_backend(mock=True)
            # Seed default demonstration chunks for offline demo and UI testing
            default_chunks = [
                Chunk(
                    chunk_id="chk_s7_01",
                    document_id="doc_s71200",
                    filename="s71200_manual.pdf",
                    page=14,
                    text="Siemens S7-1200 CPU 1214C overheating procedure: Inspect cabinet ventilation fan and verify intake airflow. If rack temperature exceeds 60°C, de-energize module before servicing.",
                    equipment_model="S7-1200 CPU 1214C",
                    synthetic=True,
                ),
                Chunk(
                    chunk_id="chk_rex_01",
                    document_id="doc_rex",
                    filename="A10VSO_Overhaul_Rev1.pdf",
                    page=12,
                    text="Rexroth A10VSO hydraulic pump troubleshooting: Check suction line strainer for blockage, inspect case drain pressure (max 2.5 bar), and verify manifold pressure relief setpoint.",
                    equipment_model="Rexroth A10VSO",
                    synthetic=True,
                ),
                Chunk(
                    chunk_id="chk_comp_01",
                    document_id="doc_compressor_sop",
                    filename="01_Standard_Operating_Procedure.pdf",
                    page=1,
                    text="Only authorized personnel are permitted to start, stop, monitor, and safely change operating states of the Filler Cell PLC. Operating pressure must remain between 6.5 and 8.0 bar.",
                    equipment_model="S7-1200 CPU 1214C",
                    synthetic=True,
                ),
            ]
            backend.index_chunks(default_chunks)
            if "indexed_docs" in st.session_state and not st.session_state["indexed_docs"]:
                st.session_state["indexed_docs"]["s71200_manual.pdf"] = {
                    "document_id": "doc_s71200",
                    "chunks_count": 1,
                    "equipment_model": "S7-1200 CPU 1214C",
                    "synthetic": True,
                }
                st.session_state["indexed_docs"]["A10VSO_Overhaul_Rev1.pdf"] = {
                    "document_id": "doc_rex",
                    "chunks_count": 1,
                    "equipment_model": "Rexroth A10VSO",
                    "synthetic": True,
                }
                st.session_state["indexed_docs"]["01_Standard_Operating_Procedure.pdf"] = {
                    "document_id": "doc_compressor_sop",
                    "chunks_count": 1,
                    "equipment_model": "S7-1200 CPU 1214C",
                    "synthetic": True,
                }
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
    defaults: dict = {
        "chat_history": [],
        "indexed_docs": {},
        "backend": None,
        "use_mock": True,  # Default to Mock for unit tests and safety fallback
        "last_indexing_summary": None,
        "backend_error": None,
        "ui_view": "classic",  # Default to classic for backward compatibility, toggleable via navbar
        # Vision state
        "vision_image_path": None,
        "vision_image_name": None,
        "vision_mode_active": False,
        # Phase 2: Incident-oriented workflow
        "active_incident_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "incident_service" not in st.session_state:
        from src.services import create_incident_service
        st.session_state["incident_service"] = create_incident_service(mock=True)


