# VALENCE Phase 2: Live Demonstration Walkthrough Script

This guide outlines a concise 3-act live demonstration showcasing **adaptivity**, **source inspection**, and a **well-handled failure** (not just successful answers).
All operations run strictly offline and air-gapped on the local machine.

---

## Pre-Demo Setup Checklist (1 Minute)

1. Launch the VALENCE application:
   ```bash
   cd VALENCE
   export PYTHONPATH=.
   streamlit run src/ui/app.py
   ```
2. In the top navigation bar, select **📋 Incidents** (or toggle to Phase 2 Incident Management View).
3. Ensure mock mode or local Ollama backend is active. The navbar displays **🟡 Mock / Sandbox Engine** or **🟢 Live Engine**.

---

## Act 1: Adaptivity (Ambiguity Resolution & Idempotent Resumption)

*Objective*: Demonstrate that VALENCE refuses to guess when equipment identity is ambiguous, halts cleanly for operator input, and resumes the exact same incident without duplicated tool execution.

1. Select **Incident INC-2026-002: Hydraulic Infeed Pressure Drop** from the Incident List.
2. Note that the equipment model is currently unconfirmed: `None (Unconfirmed)`.
3. Click **🚀 Investigate with Agent**.
4. **Observe the Activity Panel (Real Tool Events)**:
   - Event 1: `retrieve_evidence` (Status: `completed`) — Retrieves relevant hydraulic excerpts.
   - Event 2: `validate_applicability` (Status: `waiting`) — Identifies unconfirmed equipment model.
   - Execution State transitions to: **🟡 Waiting for Clarification**.
5. **Operator Clarification Prompt**:
   - The UI displays an amber clarification question card:
     > *"Equipment model for incident 'Hydraulic Infeed Pressure Drop' is unconfirmed. Please confirm the exact equipment model identifier to ensure safe and applicable troubleshooting."*
6. Submit clarification response:
   - Type or select: `Rexroth A10VSO`
   - Click **Submit Clarification Response**.
7. **Highlight to Evaluators (Seamless Resumption)**:
   - The same incident record is updated in-place (`apply_clarification`).
   - The activity panel records:
     - Event 3: `apply_clarification` (Status: `completed`).
     - Event 4: `validate_applicability` (Status: `completed` — Certified for `Rexroth A10VSO`).
     - Event 5: `synthesize_guidance` (Status: `completed`).
   - No past steps were repeated or duplicated.

---

## Act 2: Source Inspection & Grounded Human Findings

*Objective*: Prove that every recommended check is directly substantiated by verified documentation, safety boundaries are explicit, and human physical actions are cleanly recorded without implying automated execution.

1. Under **Grounded Diagnostic Guidance**, review the authored checklist.
2. Expand **🔍 Proposed Technical Checks (Grounded in Verified Evidence)**:
   - **Step 1 (`CHK-01`)**: *"Check inlet strainer for particulate accumulation and verify case drain pressure."*
     - Linked Evidence: `[doc_rex#p12#c01]`
     - Safety Precaution: `⚠️ Mandatory electrical/pneumatic isolation or PPE required prior to inspection.`
3. Expand **📚 Supporting Documentary Evidence**:
   - Inspect the exact citation lineage:
     - Document: `A10VSO_Overhaul_Rev1.pdf`
     - Page: `Page 12`
     - Target Equipment: `Rexroth A10VSO`
     - Verbatim excerpt matching the local indexed vector chunk.
4. **Record Technician Finding**:
   - In the **Record Technician Finding** input box, enter:
     ```text
     Technician inspected inlet strainer; mesh was 40% obstructed with varnish. Cleaned with solvent.
     ```
   - Click **Add Finding**.
   - **Highlight to Evaluators**: The finding is recorded distinctly as `[VERIFIED TECHNICIAN FINDING]`. The UI clearly distinguishes human physical observations from tentative visual cues and system diagnostic interpretations.

---

## Act 3: A Well-Handled Failure (Equipment Mismatch & Auditable Handover)

*Objective*: Demonstrate safety-critical boundary refusal when documentation does not match equipment, avoiding dangerous parameter hallucinations and generating an auditable shift handover.

1. Create a new incident or select an incident with an equipment mismatch:
   - Title: `Inverter Drive Overcurrent Fault`
   - Target Equipment: `Danfoss VLT FC 302` (Confirmed)
   - Retrieved Document: Attached `Micromaster_440_Manual.pdf` (`Siemens Micromaster 440`).
2. Click **🚀 Investigate with Agent**.
3. **Observe the Refusal & Escalation**:
   - The system executes `validate_applicability`.
   - Applicability engine detects that `Danfoss VLT FC 302` does not match `Siemens Micromaster 440`.
   - The system **REFUSES** to output Micromaster parameters (e.g. `P0305`), which could destroy a Danfoss motor.
   - Activity Panel displays:
     - Event: `validate_applicability` (Status: `escalated`).
     - Escalation Badge: **🚨 Escalation Required [EQUIPMENT_MISMATCH]**.
     - Details: *"Target equipment 'Danfoss VLT FC 302' does not match retrieved document equipment model. Sources apply to incompatible models."*
4. **Review Shift Handover Preview**:
   - Under **📋 Shift Handover & Knowledge Governance**, click **Generate Handover Preview**.
   - Notice the structured handover preview:
     - **Symptom**: Inverter overcurrent trip during motor acceleration.
     - **Equipment Confirmation**: `Danfoss VLT FC 302` (Confirmed).
     - **Unresolved Escalations**: Active escalation `[EQUIPMENT_MISMATCH]`.
     - **Authoritative Knowledge Promotion**: `Blocked (Ineligible)` — Unresolved escalations cannot be promoted to SOPs.
     - **Review Disclaimer**:
       > *"Authentication/authorization is not implemented in this offline runtime. Reviewer approval cannot be certified; outcomes remain strictly unreviewed."*
5. Click **💾 Export Handover Report (JSON)** to download the auditable handoff file for the incoming maintenance shift.

