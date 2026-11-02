"""Streamlit user interface package (Member A)."""

from src.ui.mock_backend import MockBackendService


def main() -> None:
    from src.ui.app import main as app_main
    app_main()


__all__ = ["main", "MockBackendService"]



