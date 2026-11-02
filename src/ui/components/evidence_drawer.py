"""Reusable component for rendering supporting evidence citations."""

from __future__ import annotations

import streamlit as st
from contracts import Answer


def render_evidence_drawer(answer: Answer) -> None:
    """Renders the Supporting Evidence collapsible drawer from Answer.evidence."""
    if not answer.evidence:
        return

    with st.expander(
        f"📚 Supporting Evidence ({len(answer.evidence)} citations)",
        expanded=False,
    ):
        for ev in answer.evidence:
            st.markdown(
                f"**Source: `{ev.source_id}`** — File: `{ev.chunk.filename}` (Page {ev.chunk.page})"
            )
            meta_parts: list[str] = []
            if ev.chunk.equipment_model:
                meta_parts.append(f"Model: `{ev.chunk.equipment_model}`")
            if ev.chunk.synthetic:
                meta_parts.append("`[Synthetic]`")
            if meta_parts:
                st.caption(" | ".join(meta_parts))
            st.info(ev.chunk.text)

