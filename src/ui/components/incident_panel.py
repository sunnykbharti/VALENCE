"""Incident-oriented UI component for Phase 2 Milestone 1A.

Displays and manages industrial incidents:
- Controls to create, open, select, and inspect incidents
- Clear display of symptom, equipment identity, confirmation state,
  tentative observations, documentary evidence, and status
- Strict visual separation between:
    1. Confirmed equipment details (green / verified badge)
    2. Tentative observations (amber / warning badge)
    3. Document evidence (navy / official citations)
- Seamless integration with IncidentServiceProtocol
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import streamlit as st
from src.incidents.schema import Incident, VALID_INCIDENT_STATUSES
from src.incidents.protocol import IncidentServiceProtocol
from src.ui.components.activity_panel import render_activity_panel

logger = logging.getLogger(__name__)


def render_incident_controls(
    service: IncidentServiceProtocol,
    backend=None,
) -> Optional[Incident]:
    """Renders incident selector and create/open controls.

    Returns:
        The currently active Incident object, or None if none selected.
    """
    if backend is None:
        backend = st.session_state.get("backend")

    st.markdown("### 🚨 Incident Management & Workspace")
    st.caption("🔶 **[MOCK INCIDENT SERVICE ACTIVE]** — In-memory incident tracking and state management.")

    incidents = service.list_incidents()
    active_id = st.session_state.get("active_incident_id")

    # Build options
    options = ["-- None (General Assistant) --"]
    id_map = {}
    for inc in incidents:
        label = f"{inc.incident_id}: {inc.title} [{inc.status.upper()}]"
        options.append(label)
        id_map[label] = inc.incident_id
    options.append("➕ Create New Incident...")

    # Determine default index
    default_idx = 0
    if active_id:
        for idx, (lbl, iid) in enumerate(id_map.items(), start=1):
            if iid == active_id:
                default_idx = idx
                break

    selected_option = st.selectbox(
        "Select Active Incident or Action",
        options=options,
        index=default_idx,
        key="incident_selector_widget",
    )

    if selected_option == "➕ Create New Incident...":
        _render_create_incident_form(service)
        return None
    elif selected_option == "-- None (General Assistant) --":
        if st.session_state.get("active_incident_id") is not None:
            st.session_state["active_incident_id"] = None
        return None
    else:
        chosen_id = id_map.get(selected_option)
        st.session_state["active_incident_id"] = chosen_id
        active_inc = service.get_incident(chosen_id)
        if active_inc:
            _render_active_incident_details(service, active_inc, backend=backend)
        return active_inc


def _render_create_incident_form(service: IncidentServiceProtocol) -> None:
    """Renders the form to create a new incident."""
    with st.form("create_incident_form", clear_on_submit=False):
        st.subheader("➕ Open New Operational Incident")
        title = st.text_input("Incident Title *", placeholder="e.g. S7-1200 Comm Fault on Line 3")
        symptom = st.text_area(
            "Observed Symptom / Error Code *",
            placeholder="e.g. PLC rack diagnostic LED flashing red. Error code 0x8081 reported on HMI.",
            help="Describe the symptom or physical alert in detail.",
        )
        col1, col2 = st.columns(2)
        with col1:
            equipment_model = st.text_input(
                "Equipment Model (Optional)",
                placeholder="e.g. S7-1200 CPU 1214C",
                help="Leave blank if equipment identity is unknown.",
            )
        with col2:
            equipment_confirmed = st.checkbox(
                "Equipment Model Confirmed by Operator",
                value=False,
                help="Check only if physically verified by nameplate or authorized schematics.",
            )
        initial_obs = st.text_input(
            "Initial Tentative Observation (Optional)",
            placeholder="e.g. Blinking RED fault LED; cooling fan running at high pitch.",
            help="Tentative visual or auditory observations.",
        )

        submitted = st.form_submit_button("🚨 Open Incident", type="primary")
        if submitted:
            if not title or not title.strip():
                st.error("Please enter a non-empty incident title.")
                return
            if not symptom or not symptom.strip():
                st.error("Please describe the incident symptom.")
                return
            if equipment_confirmed and (not equipment_model or not equipment_model.strip()):
                st.error("Cannot confirm equipment model without entering an equipment model identifier.")
                return

            obs_list = [initial_obs.strip()] if initial_obs and initial_obs.strip() else []
            try:
                new_inc = service.create_incident(
                    title=title,
                    symptom=symptom,
                    equipment_model=equipment_model if equipment_model and equipment_model.strip() else None,
                    equipment_confirmed=equipment_confirmed,
                    observations=obs_list,
                )
                st.session_state["active_incident_id"] = new_inc.incident_id
                st.success(f"Incident `{new_inc.incident_id}` opened successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to create incident: {e}")


def _render_active_incident_details(
    service: IncidentServiceProtocol,
    inc: Incident,
    backend=None,
) -> None:
    """Renders full details of an active incident with strict visual separation."""
    if backend is None:
        backend = st.session_state.get("backend")
    # Top Status Bar
    status_colors = {
        "open": ("#fee2e2", "#ef4444", "🚨 OPEN"),
        "investigating": ("#e0e7ff", "#4338ca", "🔍 INVESTIGATING"),
        "mitigated": ("#fef3c7", "#d97706", "🛡️ MITIGATED"),
        "resolved": ("#dcfce7", "#15803d", "✅ RESOLVED"),
        "closed": ("#f3f4f6", "#4b5563", "🔒 CLOSED"),
    }
    bg, fg, label = status_colors.get(inc.status, ("#f3f4f6", "#4b5563", inc.status.upper()))

    st.markdown(
        f"""
        <div style="background:rgba(30,41,59,0.7); border:1px solid #334155; border-radius:10px; padding:1rem; margin-bottom:1rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h4 style="margin:0; color:#f8fafc;">{inc.incident_id}: {inc.title}</h4>
                <span style="background:{bg}; color:{fg}; font-weight:700; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.85rem;">
                    {label}
                </span>
            </div>
            <p style="margin:0.5rem 0 0 0; color:#94a3b8; font-size:0.85rem;">
                Created: {inc.created_at[:19]} UTC | Last Updated: {inc.updated_at[:19]} UTC
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Symptom Section
    with st.container():
        st.markdown("#### ⚡ Reported Symptom / Condition")
        st.info(f"**Description:** {inc.symptom}")

    # Task 3: Equipment/manual mismatch and missing-evidence alert banners
    from backend.applicability import validate_equipment_applicability, detect_contradictions
    if not inc.evidence:
        st.markdown(
            """
            <div style="background:rgba(245, 158, 11, 0.12); border-left:4px solid #f59e0b; padding:0.75rem 1rem; border-radius:4px; margin:0.75rem 0;">
                <strong style="color:#fbbf24;">⚠️ MISSING DOCUMENTARY EVIDENCE</strong>
                <div style="color:#fde68a; font-size:0.85rem; margin-top:0.25rem;">
                    No documentary evidence or equipment manuals are attached to this incident. Grounded troubleshooting procedures cannot be certified.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        is_app, r_code, r_details, blocking = validate_equipment_applicability(
            target_equipment=inc.equipment_model,
            target_revision=inc.firmware_revision or inc.hardware_revision,
            evidence=inc.evidence,
        )
        if not is_app:
            if r_code == "EQUIPMENT_MISMATCH":
                st.markdown(
                    f"""
                    <div style="background:rgba(239, 68, 68, 0.15); border-left:4px solid #ef4444; padding:0.75rem 1rem; border-radius:4px; margin:0.75rem 0;">
                        <strong style="color:#f87171;">🚨 EQUIPMENT / MANUAL MISMATCH</strong>
                        <div style="color:#fca5a5; font-size:0.85rem; margin-top:0.25rem;">
                            Target equipment <code>{inc.equipment_model}</code> does not match the retrieved document metadata. {r_details}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif r_code == "UNKNOWN_EQUIPMENT":
                st.markdown(
                    """
                    <div style="background:rgba(245, 158, 11, 0.12); border-left:4px solid #f59e0b; padding:0.75rem 1rem; border-radius:4px; margin:0.75rem 0;">
                        <strong style="color:#fbbf24;">❓ UNCONFIRMED / UNKNOWN EQUIPMENT IDENTITY</strong>
                        <div style="color:#fde68a; font-size:0.85rem; margin-top:0.25rem;">
                            Target equipment model is unconfirmed or unknown. Verify physical nameplate before applying documented procedures.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif r_code == "MISSING_REVISION":
                st.markdown(
                    f"""
                    <div style="background:rgba(245, 158, 11, 0.12); border-left:4px solid #f59e0b; padding:0.75rem 1rem; border-radius:4px; margin:0.75rem 0;">
                        <strong style="color:#fbbf24;">⚠️ MISSING REVISION DATA</strong>
                        <div style="color:#fde68a; font-size:0.85rem; margin-top:0.25rem;">
                            {r_details}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        contradictions = detect_contradictions(inc.evidence)
        if contradictions:
            st.markdown(
                f"""
                <div style="background:rgba(220, 38, 38, 0.2); border-left:4px solid #dc2626; padding:0.75rem 1rem; border-radius:4px; margin:0.75rem 0;">
                    <strong style="color:#fca5a5;">🚨 CONTRADICTORY DOCUMENTARY INSTRUCTIONS</strong>
                    <div style="color:#fed7aa; font-size:0.85rem; margin-top:0.25rem;">
                        {contradictions[0]['description']} Silent resolution is prohibited.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 2. Status Transition Controls
    c1, c2 = st.columns([3, 1])
    with c1:
        new_status = st.selectbox(
            "Update Incident Status",
            options=VALID_INCIDENT_STATUSES,
            index=VALID_INCIDENT_STATUSES.index(inc.status) if inc.status in VALID_INCIDENT_STATUSES else 0,
            key=f"status_select_{inc.incident_id}",
        )
    with c2:
        st.write("")
        st.write("")
        if st.button("Apply Status", key=f"apply_status_{inc.incident_id}"):
            if new_status != inc.status:
                service.update_status(inc.incident_id, new_status)
                st.success(f"Status updated to '{new_status}'")
                st.rerun()

    st.markdown("---")

    # 3. Confirmed Equipment Details (VISIBLY SEPARATE - SECTION A)
    st.markdown("#### 🏷️ Equipment Identity & Confirmation")
    if inc.equipment_model and inc.equipment_confirmed:
        st.markdown(
            f"""
            <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:0.85rem; margin-bottom:0.75rem;">
                <span style="color:#34d399; font-weight:700;">✅ CONFIRMED EQUIPMENT MODEL</span>:
                <code style="font-size:1rem; color:#f8fafc; margin-left:0.5rem;">{inc.equipment_model}</code>
                <div style="font-size:0.8rem; color:#a7f3d0; margin-top:0.25rem;">
                    Verified by operator inspection. Grounded retrieval will prioritize this exact equipment model.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif inc.equipment_model and not inc.equipment_confirmed:
        st.markdown(
            f"""
            <div style="background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); border-radius:8px; padding:0.85rem; margin-bottom:0.75rem;">
                <span style="color:#fbbf24; font-weight:700;">⚠️ TENTATIVE / UNCONFIRMED MODEL</span>:
                <code style="font-size:1rem; color:#f8fafc; margin-left:0.5rem;">{inc.equipment_model}</code>
                <div style="font-size:0.8rem; color:#fde68a; margin-top:0.25rem;">
                    Identified from tentative observations or image cues. Requires operator confirmation before strict filtering.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Confirm Equipment Model as Verified", key=f"confirm_eq_{inc.incident_id}"):
            service.confirm_equipment(inc.incident_id, inc.equipment_model)
            st.success("Equipment model confirmed!")
            st.rerun()
    else:
        st.markdown(
            """
            <div style="background:rgba(100,116,139,0.1); border:1px solid rgba(100,116,139,0.3); border-radius:8px; padding:0.85rem; margin-bottom:0.75rem;">
                <span style="color:#94a3b8; font-weight:700;">❓ EQUIPMENT UNIDENTIFIED (None)</span>
                <div style="font-size:0.8rem; color:#cbd5e1; margin-top:0.25rem;">
                    No equipment model has been associated with this incident yet.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Assign & Confirm Equipment Model"):
            manual_model = st.text_input("Equipment Model Identifier", key=f"manual_model_{inc.incident_id}")
            if st.button("Assign & Confirm", key=f"btn_manual_model_{inc.incident_id}"):
                if manual_model and manual_model.strip():
                    service.confirm_equipment(inc.incident_id, manual_model.strip())
                    st.success(f"Equipment model set to '{manual_model}' and confirmed.")
                    st.rerun()
                else:
                    st.error("Please enter a valid equipment model string.")

    st.markdown("---")

    # 4. Tentative Observations (VISIBLY SEPARATE - SECTION B)
    st.markdown("#### 👁️ Tentative Visual Observations")
    st.markdown(
        """
        <div style="background:rgba(217,119,6,0.08); border-left:4px solid #f59e0b; padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.75rem;">
            <strong style="color:#fbbf24;">⚠️ TENTATIVE FINDINGS (UNCONFIRMED)</strong>
            <div style="color:#fcd34d; font-size:0.85rem; margin-top:0.25rem;">
                Observations listed here are tentative visual or sensory observations. They do NOT constitute confirmed diagnoses or certified operating specs.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if inc.observations:
        for idx, obs in enumerate(inc.observations, start=1):
            st.markdown(f"**{idx}.** `{obs}`")
    else:
        st.caption("No visual observations recorded yet for this incident.")

    with st.expander("➕ Append Visual Observation to Incident"):
        new_obs = st.text_input("New Observation", placeholder="e.g. Amber DIAG LED blinking at 2Hz", key=f"new_obs_{inc.incident_id}")
        if st.button("Record Observation", key=f"btn_add_obs_{inc.incident_id}"):
            if new_obs and new_obs.strip():
                service.add_observations(inc.incident_id, [new_obs.strip()])
                st.success("Observation appended.")
                st.rerun()
            else:
                st.error("Please enter observation text.")

    st.markdown("---")

    # 5. Documentary Evidence (VISIBLY SEPARATE - SECTION C)
    st.markdown("#### 📚 Attached Documentary Evidence")
    if inc.evidence:
        st.caption(f"{len(inc.evidence)} verified excerpts from equipment manuals & SOPs:")
        for ev in inc.evidence:
            st.markdown(f"- **`{ev.source_id}`** — File: `{ev.chunk.filename}` (Page {ev.chunk.page})")
            st.info(ev.chunk.text)
    else:
        st.info(
            "ℹ️ No documentary evidence attached yet. "
            "Ask technical questions in the Assistant Console to retrieve and verify guidance from official manuals."
        )

    st.markdown("---")

    # 5B. Proposed Documented Checks & Field Technician Findings (Phase 2 Milestone 3A Tasks 1 & 2)
    st.markdown("#### 🛠️ Proposed Documented Checks (Evidence-Grounded)")
    st.caption("Operational steps derived strictly from attached equipment documentation. Each check is substantiated by specific source citations.")

    from backend.applicability import extract_proposed_checks
    proposed_checks = extract_proposed_checks(inc.evidence) if inc.evidence else []

    if not proposed_checks:
        st.info("No proposed checks available. Attach equipment documentation or manual excerpts to generate grounded checks.")
    else:
        for chk in proposed_checks:
            with st.container():
                st.markdown(
                    f"""
                    <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:0.85rem 1rem; margin-bottom:0.75rem;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                            <span style="color:#60a5fa; font-weight:700;">Step {chk.step_number}: <code>{chk.check_id}</code></span>
                            {'<span style="background:rgba(245, 158, 11, 0.2); color:#fbbf24; font-size:0.75rem; padding:0.15rem 0.5rem; border-radius:4px;">' + chk.safety_precaution + '</span>' if chk.safety_precaution else ''}
                        </div>
                        <div style="color:#f8fafc; font-size:0.95rem; margin-bottom:0.5rem;">
                            <strong>Instruction:</strong> {chk.instruction}
                        </div>
                        <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.25rem;">
                            <strong>Linked Evidence Source:</strong> <code>{', '.join(chk.evidence_ids)}</code>
                        </div>
                        <div style="font-size:0.75rem; color:#94a3b8; margin-top:0.4rem; padding-top:0.4rem; border-top:1px dashed #334155;">
                            ℹ️ <strong>Physical Check Disclaimer</strong>: Field inspection must be executed physically by an authorized human technician. VALENCE does not perform physical actions.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Expandable Source Evidence details (Task 1)
                matching_ev = [e for e in inc.evidence if e.source_id in chk.evidence_ids]
                if matching_ev:
                    with st.expander(f"📖 View Source Evidence for {chk.check_id}", expanded=False):
                        for mev in matching_ev:
                            st.caption(f"Source: `{mev.source_id}` | Manual: `{mev.chunk.filename}` (Page {mev.chunk.page})")
                            st.info(mev.chunk.text)

                # Technician Finding Recording form (Task 2)
                # Note: Explicit disclaimer that application does NOT perform the check
                with st.expander(f"📝 Record Field Inspection Finding for Step {chk.step_number} (Human-Verified)", expanded=False):
                    st.caption(
                        "ℹ️ **Physical Check Disclaimer**: This check must be performed physically by an authorized technician. "
                        "The application does not perform or automate physical actions."
                    )
                    c_f1, c_f2 = st.columns([4, 1])
                    with c_f1:
                        f_input = st.text_input(
                            f"Technician Finding for {chk.check_id}",
                            placeholder="e.g. Resistance reads 4.2 ohms (within spec); no physical damage.",
                            key=f"finding_input_{inc.incident_id}_{chk.check_id}",
                        )
                    with c_f2:
                        st.write("")
                        st.write("")
                        if st.button("Save Finding", key=f"btn_save_finding_{inc.incident_id}_{chk.check_id}"):
                            if f_input and f_input.strip():
                                formatted_finding = f"[{chk.check_id} Physical Finding]: {f_input.strip()}"
                                service.add_technician_findings(inc.incident_id, [formatted_finding])
                                st.success("Physical inspection finding recorded.")
                                st.rerun()
                            else:
                                st.error("Please enter finding description.")

    # List recorded technician findings distinctly (Task 2 & 7)
    st.markdown("##### 🟢 Recorded Field Technician Findings")
    st.caption("Human-verified physical inspection results. Kept strictly distinct from tentative observations and unreviewed hypotheses.")
    if inc.technician_findings:
        for idx, finding in enumerate(inc.technician_findings, start=1):
            st.markdown(f"**{idx}.** `{finding}`")
    else:
        st.caption("No human technician findings recorded yet.")

    with st.expander("➕ Append General Technician Finding"):
        st.caption("ℹ️ Recorded as a human physical observation. VALENCE does not perform physical actions.")
        gen_finding = st.text_input("Physical Inspection Finding", placeholder="e.g. Cleaned fan filter; motor rotor turns freely by hand.", key=f"gen_finding_{inc.incident_id}")
        if st.button("Record General Finding", key=f"btn_gen_finding_{inc.incident_id}"):
            if gen_finding and gen_finding.strip():
                service.add_technician_findings(inc.incident_id, [gen_finding.strip()])
                st.success("Technician finding saved.")
                st.rerun()
            else:
                st.error("Please enter finding text.")

    st.markdown("---")

    # 6. Applicability & Escalation Governance (Phase 2 Milestone 3B)
    st.markdown("#### ⚖️ Applicability & Escalation Governance")
    with st.expander("🔍 Pre-Flight Applicability & Escalation Evaluation", expanded=False):
        st.caption("Verifies documentation compatibility, checks for revision requirements, and detects contradictions.")
        if st.button("Evaluate Applicability & Contradictions", key=f"btn_eval_app_{inc.incident_id}"):
            from backend.applicability import evaluate_incident_applicability
            decision = evaluate_incident_applicability(inc)
            st.session_state[f"escalation_{inc.incident_id}"] = decision

        saved_decision = st.session_state.get(f"escalation_{inc.incident_id}")
        if saved_decision:
            if saved_decision.escalate:
                st.error(
                    f"🚨 **ESCALATION REQUIRED [{saved_decision.reason}]**\n\n"
                    f"**Details**: {saved_decision.details}\n\n"
                    f"**Action Required**: {saved_decision.action_required}"
                )
                if saved_decision.blocking_sources:
                    st.caption(f"Blocking Sources: `{', '.join(saved_decision.blocking_sources)}`")
            else:
                st.success(
                    f"✅ **PROCEDURE CERTIFIED [{saved_decision.reason}]**\n\n"
                    f"{saved_decision.details}\n\n"
                    f"**Next Action**: {saved_decision.action_required}"
                )

    # 7. Shift Handover Staging, Review & Export (Phase 2 Milestone 3A Tasks 4, 5, 6, 7)
    with st.expander("📋 Shift Handover Staging, Review & Export", expanded=False):
        st.caption("Compiles persisted incident facts into an auditable handover preview. Review all uncertainty and unresolved items before saving or exporting.")

        escalation_dec = st.session_state.get(f"escalation_{inc.incident_id}")
        review_notes_key = f"handover_review_notes_{inc.incident_id}"

        # Review notes input (Task 5)
        user_notes = st.text_area(
            "Shift Reviewer Notes / Addendum (Optional)",
            value=st.session_state.get(review_notes_key, ""),
            placeholder="e.g. Handing off to Shift 2. Replacement fan blade on order (PO #4412). Breaker locked out.",
            key=f"textarea_notes_{inc.incident_id}",
            help="Review and supplement the handover before exporting or saving.",
        )
        st.session_state[review_notes_key] = user_notes

        from backend.handover import generate_handover
        report = generate_handover(inc, escalation=escalation_dec, user_review_notes=user_notes)
        st.session_state[f"handover_{inc.incident_id}"] = report

        # Task 6 & 7: Prominent Labels and Separation
        st.markdown(
            """
            <div style="background:rgba(59, 130, 246, 0.1); border:1px solid #3b82f6; border-radius:6px; padding:0.6rem 0.9rem; margin-bottom:0.75rem;">
                <span style="color:#60a5fa; font-weight:700;">🤖 [GENERATED SUMMARY - REQUIRES HUMAN REVIEW]</span>
                <div style="font-size:0.8rem; color:#94a3b8; margin-top:0.25rem;">
                    Generated from persisted facts and documentary citations. Verify all items before shift transfer.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if report.is_synthetic:
            st.markdown(
                """
                <div style="background:rgba(245, 158, 11, 0.1); border:1px solid #f59e0b; border-radius:6px; padding:0.6rem 0.9rem; margin-bottom:0.75rem;">
                    <span style="color:#fbbf24; font-weight:700;">🔶 [SYNTHETIC TEST BENCHMARK DATA - NOT FOR PRODUCTION DISPATCH]</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Task 7: Unreviewed outcome disclaimer
        if not report.is_reviewed:
            st.markdown(
                """
                <div style="background:rgba(239, 68, 68, 0.1); border:1px solid #ef4444; border-radius:6px; padding:0.6rem 0.9rem; margin-bottom:0.75rem;">
                    <span style="color:#f87171; font-weight:700;">⚠️ [UNREVIEWED OUTCOME - NO AUTHORITATIVE SIGN-OFF]</span>
                    <div style="font-size:0.8rem; color:#fca5a5; margin-top:0.25rem;">
                        Authentication and authorization mechanisms are not implemented in this offline runtime.
                        No reviewer approval is certified or implied; this outcome remains unreviewed.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Completeness Badge
        if report.is_complete:
            st.success("✅ **Handover Complete**: All operational fields are verified.")
        else:
            st.warning(f"⚠️ **Incomplete Handover**: Missing fields: `{', '.join(report.missing_fields)}`")

        # Knowledge promotion guard badge
        if report.authoritative_knowledge_eligible:
            st.success(f"🟢 **Authoritative Knowledge Promotion**: {report.knowledge_guard_reason}")
        else:
            st.error(f"🛑 **Authoritative Knowledge Promotion**: {report.knowledge_guard_reason}")

        # Render structured preview markdown
        st.markdown(report.markdown_text)

        # Action Buttons: Save & Export (Task 5)
        st.markdown("---")
        st.markdown("##### 💾 Save & Export Handover")
        c_exp1, c_exp2, c_exp3 = st.columns(3)
        with c_exp1:
            if st.button("💾 Save Handover to Incident", key=f"btn_save_handover_{inc.incident_id}"):
                st.session_state[f"saved_handover_{inc.incident_id}"] = report
                st.success("Handover report saved to incident record.")

        with c_exp2:
            st.download_button(
                label="📥 Export Handover (Markdown)",
                data=report.markdown_text,
                file_name=f"handover_{inc.incident_id.lower().replace('-', '_')}.md",
                mime="text/markdown",
                key=f"download_md_{inc.incident_id}",
            )

        with c_exp3:
            report_json = json.dumps(report.to_dict(), indent=2)
            st.download_button(
                label="📥 Export Handover (JSON)",
                data=report_json,
                file_name=f"handover_{inc.incident_id.lower().replace('-', '_')}.json",
                mime="application/json",
                key=f"download_json_{inc.incident_id}",
            )

    # 8. Autonomous Agent Troubleshooting & Real Activity Stream (Phase 2 Milestone 2A)
    st.markdown("---")
    st.markdown("#### 🤖 Autonomous Agent Troubleshooting")
    st.caption("Executes real diagnostic tools across indexed manuals, checks applicability, and prompts for clarification.")

    exec_key = f"active_execution_{inc.incident_id}"
    active_execution = st.session_state.get(exec_key)

    is_executing = st.session_state.get("is_executing", False)
    btn_disabled = is_executing or (active_execution is not None and active_execution.state == "running")

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        if st.button(
            "🚀 Run Automated Agent Investigation",
            key=f"btn_start_agent_{inc.incident_id}",
            disabled=btn_disabled,
            type="primary",
            use_container_width=True,
            help="Executes retrieval, applicability check, operator clarification, and synthesis tools.",
        ):
            if backend is None:
                st.error("Backend service is unavailable.")
            else:
                st.session_state["is_executing"] = True
                try:
                    with st.spinner("Agent running real diagnostic tools..."):
                        execution = backend.start_investigation(
                            incident_id=inc.incident_id,
                            query=inc.symptom,
                            incident_service=service,
                        )
                        st.session_state[exec_key] = execution
                except Exception as e:
                    st.error(f"Investigation error: {e}")
                finally:
                    st.session_state["is_executing"] = False
                    st.rerun()

    with col_btn2:
        if active_execution is not None:
            if st.button("🔄 Reset Run", key=f"btn_reset_exec_{inc.incident_id}", disabled=is_executing):
                st.session_state[exec_key] = None
                st.rerun()

    if active_execution is not None and backend is not None:
        render_activity_panel(active_execution, backend=backend, incident_service=service)



