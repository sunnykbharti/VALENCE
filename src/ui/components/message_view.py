"""Reusable chat message renderer for user and assistant bubbles."""

from __future__ import annotations

from typing import Optional
import streamlit as st

from contracts import Answer
from src.ui.components.evidence_drawer import render_evidence_drawer
from src.ui.components.observations_panel import render_visual_observations
from src.ui.components.tts_player import render_tts_button


def render_assistant_message(msg: dict, use_mock: bool, msg_idx: int = 0) -> None:
    """Renders a complete assistant chat message including citations, observations, and TTS audio."""
    answer: Answer = msg["answer"]
    image_name: Optional[str] = msg.get("image_name")

    with st.chat_message("assistant"):
        if image_name:
            st.caption(f"🖼️ Image inspection: `{image_name}`")

        if answer.insufficient_evidence:
            st.warning(
                "⚠️ **Insufficient Documentary Evidence**: The retrieved manuals and SOPs do not "
                "substantiate an answer to this query."
            )

        st.markdown(answer.text)
        render_tts_button(answer.text, key_suffix=f"msg_{msg_idx}")
        render_evidence_drawer(answer)
        render_visual_observations(answer, use_mock)


def render_user_message(msg: dict) -> None:
    """Renders a user message bubble with optional image attachment indicator."""
    with st.chat_message("user"):
        if msg.get("image_name"):
            st.caption(f"🖼️ Attached inspection image: `{msg['image_name']}`")
        st.write(msg["content"])

