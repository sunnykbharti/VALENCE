"""Reusable component for rendering tentative visual observations."""

from __future__ import annotations

import streamlit as st
from contracts import Answer


def render_visual_observations(answer: Answer, use_mock: bool) -> None:
    """Renders visual observations clearly separated from documented guidance."""
    if not answer.observations:
        return

    with st.expander("👁️ Tentative Visual Observations", expanded=True):
        if use_mock:
            st.caption(
                "🔶 **[MOCK VISION RESPONSE]** — These observations are simulated. "
                "No actual image inference has been performed."
            )
        st.warning(
            "⚠️ Visual observations are **tentative** and must not be used as confirmed diagnoses. "
            "Always verify against physical inspection and official documentation."
        )
        for obs in answer.observations:
            st.markdown(f"- {obs}")

