"""Activity Panel Component for Phase 2 Milestone 2A.

Renders real agent tool events, clarification requests, and execution states.
Invariants:
- Only events supplied by the backend are rendered; no synthetic activity is invented in the UI.
- Private chain-of-thought is never displayed; only structured actions and concise user-facing outcomes.
- Duplicate submissions are prevented while execution is active.
- Displays all states: waiting, completed, failed, cancelled, and escalated.
"""

from __future__ import annotations

import logging
from typing import Optional

import streamlit as st
from contracts import Answer
from src.incidents.agent_schema import AgentExecution, ToolEvent
from src.incidents.protocol import IncidentServiceProtocol

logger = logging.getLogger(__name__)

# State visual presentation config
_STATE_CONFIG = {
    "waiting": {
        "label": "⏳ WAITING FOR OPERATOR CLARIFICATION",
        "bg": "rgba(245, 158, 11, 0.15)",
        "fg": "#fbbf24",
        "border": "#f59e0b",
    },
    "completed": {
        "label": "✅ EXECUTION COMPLETED",
        "bg": "rgba(16, 185, 129, 0.15)",
        "fg": "#34d399",
        "border": "#10b981",
    },
    "failed": {
        "label": "❌ EXECUTION FAILED",
        "bg": "rgba(239, 68, 68, 0.15)",
        "fg": "#f87171",
        "border": "#ef4444",
    },
    "cancelled": {
        "label": "⏹️ EXECUTION CANCELLED",
        "bg": "rgba(148, 163, 184, 0.15)",
        "fg": "#cbd5e1",
        "border": "#64748b",
    },
    "escalated": {
        "label": "🚨 ESCALATION REQUIRED",
        "bg": "rgba(220, 38, 38, 0.2)",
        "fg": "#fca5a5",
        "border": "#dc2626",
    },
    "running": {
        "label": "🔄 INVESTIGATION RUNNING",
        "bg": "rgba(59, 130, 246, 0.15)",
        "fg": "#60a5fa",
        "border": "#3b82f6",
    },
}

_TOOL_ICONS = {
    "retrieve_evidence": "🔍",
    "validate_applicability": "⚖️",
    "request_clarification": "❓",
    "apply_clarification": "✍️",
    "synthesize_guidance": "🛠️",
    "cancel_investigation": "⏹️",
}


def render_activity_panel(
    execution: AgentExecution,
    backend,
    incident_service: IncidentServiceProtocol,
) -> None:
    """Renders the auditable Agent Activity Panel and real tool timeline."""
    st.markdown("---")
    st.markdown("### 🤖 Agent Troubleshooting Activity & Audit Stream")

    cfg = _STATE_CONFIG.get(
        execution.state,
        {
            "label": execution.state.upper(),
            "bg": "rgba(100, 116, 139, 0.15)",
            "fg": "#94a3b8",
            "border": "#475569",
        },
    )

    # 1. Execution Header and Status Banner
    col_status, col_cancel = st.columns([4, 2])
    with col_status:
        st.markdown(
            f"""
            <div style="background:{cfg['bg']}; border:1px solid {cfg['border']}; border-radius:8px; padding:0.6rem 1rem; display:flex; align-items:center; gap:0.75rem;">
                <span style="font-size:1.1rem; font-weight:700; color:{cfg['fg']};">
                    {cfg['label']}
                </span>
                <span style="font-size:0.8rem; color:#94a3b8; margin-left:auto;">
                    ID: <code>{execution.execution_id}</code> | Incident: <code>{execution.incident_id}</code>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_cancel:
        # Cancel / Pause control using backend's supported behavior
        if execution.state in ("running", "waiting"):
            is_executing = st.session_state.get("is_executing", False)
            if st.button(
                "⏹️ Cancel / Pause Execution",
                key=f"btn_cancel_{execution.execution_id}",
                disabled=is_executing,
                use_container_width=True,
                help="Cancels or pauses active troubleshooting execution via backend command.",
            ):
                updated = backend.cancel_execution(execution.execution_id)
                st.session_state[f"active_execution_{execution.incident_id}"] = updated
                st.toast("Execution paused/cancelled by operator.")
                st.rerun()

    # 2. Real Tool Events Timeline (Backend Supplied Only)
    st.markdown("#### 📋 Real Tool Execution Timeline")
    st.caption("Auditable record of backend tool actions, purposes, outcomes, and statuses. No private chain-of-thought is displayed.")

    if not execution.events:
        st.info("No tool events recorded yet.")
    else:
        for idx, event in enumerate(execution.events, start=1):
            _render_single_tool_event(idx, event)

    # 3. Clarification Questions & User Response Submission (if waiting)
    if execution.state == "waiting" and execution.clarification:
        _render_clarification_section(execution, backend, incident_service)

    # 4. Terminal State Summaries
    if execution.state == "completed" and execution.answer:
        st.markdown("#### 💡 Synthesized Maintenance Guidance")
        st.success(execution.answer.text)
        if execution.answer.evidence:
            with st.expander(f"📚 Grounded Document Citations ({len(execution.answer.evidence)})", expanded=True):
                for ev in execution.answer.evidence:
                    st.markdown(f"**`{ev.source_id}`** — *{ev.chunk.filename}* (Page {ev.chunk.page}):")
                    st.info(ev.chunk.text)

    elif execution.state == "escalated" and execution.escalation:
        st.markdown(
            f"""
            <div style="background:rgba(220, 38, 38, 0.15); border:1px solid #ef4444; border-radius:8px; padding:1rem; margin-top:1rem;">
                <h4 style="color:#f87171; margin:0 0 0.5rem 0;">🚨 Escalation Required: {execution.escalation.reason}</h4>
                <p style="color:#fca5a5; margin:0 0 0.5rem 0;">{execution.escalation.details}</p>
                <div style="background:#1e1e2e; padding:0.5rem 0.75rem; border-radius:4px; font-weight:600; color:#fed7aa;">
                    Mandatory Next Action: {execution.escalation.action_required}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif execution.state == "failed" and execution.error_message:
        st.error(f"Execution Error: {execution.error_message}")


def _render_single_tool_event(idx: int, event: ToolEvent) -> None:
    """Renders a single backend tool event with purpose, outcome, and status."""
    status_badges = {
        "completed": ("#dcfce7", "#15803d", "COMPLETED"),
        "waiting": ("#fef3c7", "#d97706", "WAITING"),
        "running": ("#e0e7ff", "#4338ca", "RUNNING"),
        "failed": ("#fee2e2", "#dc2626", "FAILED"),
        "cancelled": ("#f1f5f9", "#64748b", "CANCELLED"),
        "escalated": ("#fee2e2", "#b91c1c", "ESCALATED"),
        "pending": ("#f3f4f6", "#4b5563", "PENDING"),
    }
    bg, fg, text = status_badges.get(event.status, ("#f3f4f6", "#4b5563", event.status.upper()))
    icon = _TOOL_ICONS.get(event.tool_name, "⚙️")

    st.markdown(
        f"""
        <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:0.85rem 1rem; margin-bottom:0.6rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                <div style="font-weight:700; color:#f8fafc; display:flex; align-items:center; gap:0.4rem;">
                    <span>{icon}</span>
                    <span style="color:#60a5fa;">Step {idx}:</span>
                    <code>{event.tool_name}</code>
                </div>
                <div style="display:flex; align-items:center; gap:0.6rem;">
                    <span style="font-size:0.75rem; color:#94a3b8;">{event.timestamp[11:19]} UTC</span>
                    <span style="background:{bg}; color:{fg}; font-weight:700; font-size:0.75rem; padding:0.15rem 0.5rem; border-radius:9999px;">
                        {text}
                    </span>
                </div>
            </div>
            <div style="font-size:0.85rem; color:#cbd5e1; margin-bottom:0.25rem;">
                <strong style="color:#94a3b8;">Purpose:</strong> {event.short_purpose}
            </div>
            <div style="font-size:0.85rem; color:#e2e8f0;">
                <strong style="color:#94a3b8;">Outcome:</strong> {event.outcome or 'Executing...'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_clarification_section(
    execution: AgentExecution,
    backend,
    incident_service: IncidentServiceProtocol,
) -> None:
    """Renders the clarification question and user response submission with duplicate prevention."""
    clarif = execution.clarification
    if clarif is None:
        return

    st.markdown(
        f"""
        <div style="background:rgba(245, 158, 11, 0.12); border:1px solid #f59e0b; border-radius:8px; padding:1rem; margin:1rem 0;">
            <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                <span style="font-size:1.25rem;">❓</span>
                <strong style="color:#fbbf24; font-size:1rem;">Operator Clarification Required</strong>
            </div>
            <p style="color:#fde68a; font-size:0.95rem; margin:0 0 0.5rem 0;">
                {clarif.question}
            </p>
            <div style="font-size:0.8rem; color:#fcd34d;">
                Target Parameter: <code>{clarif.parameter}</code> | Request ID: <code>{clarif.clarification_id}</code>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Concurrency and duplicate submission guard
    is_executing = st.session_state.get("is_executing", False)

    # Pre-fill response key
    resp_key = f"clarif_resp_{execution.execution_id}"
    if resp_key not in st.session_state:
        st.session_state[resp_key] = clarif.options[0] if clarif.options else ""

    # Option quick buttons
    if clarif.options:
        st.markdown("**Suggested Options:**")
        cols = st.columns(min(len(clarif.options), 4))
        for o_idx, opt in enumerate(clarif.options[:4]):
            with cols[o_idx]:
                if st.button(
                    f"👉 {opt}",
                    key=f"opt_btn_{execution.execution_id}_{o_idx}",
                    disabled=is_executing,
                ):
                    st.session_state[resp_key] = opt
                    st.rerun()

    # Response Input Field
    user_input = st.text_input(
        f"Enter or confirm {clarif.parameter}:",
        value=st.session_state.get(resp_key, ""),
        key=f"text_input_{execution.execution_id}",
        disabled=is_executing,
        placeholder="e.g. S7-1200 CPU 1214C",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        submit_btn = st.button(
            "✅ Submit Clarification & Resume Investigation",
            type="primary",
            key=f"btn_resume_{execution.execution_id}",
            disabled=is_executing,
            use_container_width=True,
        )

    if submit_btn:
        if not user_input or not user_input.strip():
            st.error("Please enter a non-empty clarification response.")
            return

        # Enforce duplicate submission prevention
        if st.session_state.get("is_executing", False):
            st.warning("Execution is already in progress. Please wait.")
            return

        st.session_state["is_executing"] = True
        try:
            with st.spinner("Applying clarification and resuming investigation on the same incident..."):
                updated_execution = backend.resume_investigation(
                    execution_id=execution.execution_id,
                    user_response=user_input.strip(),
                    incident_service=incident_service,
                )
                st.session_state[f"active_execution_{execution.incident_id}"] = updated_execution
                st.toast("Clarification applied. Investigation resumed.")
        except Exception as e:
            st.error(f"Failed to resume investigation: {e}")
        finally:
            st.session_state["is_executing"] = False
            st.rerun()

