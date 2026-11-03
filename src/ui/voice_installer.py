"""Automated installer for VALENCE Voice Dictation script in Streamlit."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
import streamlit

logger = logging.getLogger("valence.voice")

_SCRIPT_NAME = "valence_voice.js"
_SCRIPT_TAG = f'<script src="./{_SCRIPT_NAME}" defer></script>'


def install_voice_assets() -> bool:
    """Installs the voice script into Streamlit's static folder and patches index.html.

    Returns:
        True if installed/verified successfully, False otherwise.
    """
    try:
        source_js = Path(__file__).parent / "static" / _SCRIPT_NAME
        if not source_js.exists():
            logger.warning("Voice asset source not found at %s", source_js)
            return False

        static_dir = Path(streamlit.__file__).parent / "static"
        if not static_dir.exists():
            return False

        target_js = static_dir / _SCRIPT_NAME
        shutil.copyfile(source_js, target_js)

        index_html_path = static_dir / "index.html"
        if index_html_path.exists():
            content = index_html_path.read_text(encoding="utf-8")
            if _SCRIPT_TAG not in content and _SCRIPT_NAME not in content:
                if "</head>" in content:
                    new_content = content.replace("</head>", f"{_SCRIPT_TAG}</head>")
                    index_html_path.write_text(new_content, encoding="utf-8")
                    logger.info("Successfully patched Streamlit index.html with VALENCE voice script.")
                elif "</body>" in content:
                    new_content = content.replace("</body>", f"{_SCRIPT_TAG}</body>")
                    index_html_path.write_text(new_content, encoding="utf-8")
                    logger.info("Successfully patched Streamlit index.html with VALENCE voice script.")

        return True
    except Exception as e:
        logger.warning("Could not auto-install voice script into Streamlit static dir: %s", e)
        return False

