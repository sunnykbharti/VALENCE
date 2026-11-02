# VALENCE: Live Demonstration Script & Presentation Sequence

This document provides the step-by-step walkthrough script for the Hackathon demonstration.
All interactions operate strictly offline and air-gapped on the local machine.

---

## Pre-Demo Setup Checklist (1 Minute)

1. Ensure the local Ollama daemon is active:
   ```bash
   ollama list
   ```
2. Verify local configuration is targeting the real backend:
   ```bash
   cat .env
   # Ensure VALENCE_MOCK_MODE=0
   ```
3. Start the application:
   ```bash
   export PYTHONPATH=.
   streamlit run src/ui/app.py
   ```
4. Confirm the top navbar pill displays: **🟢 Live Engine**.

---

## 4-Step Demo Presentation Sequence

### Step 1: Grounded Document Question
*Objective*: Demonstrate fast, factual retrieval from indexed equipment documentation.

1. In the chat console (Tab 1), enter the question:
   ```text
   What is the procedure and authorization required to change the operating state of the Filler Cell PLC?
   ```
2. **Observe**:
   - The assistant answers within 1–2 seconds.
   - The answer text cites the exact source identifier: e.g. `[doc_...#p1#c0]`.
   - The response states that only *authorized personnel* are permitted to start, stop, monitor, and safely change operating states.

---

### Step 2: Source Evidence Inspection
*Objective*: Show that every factual claim is traceable to the exact physical page and chunk.

1. Underneath the assistant's response, click to expand:
   👉 **`📚 Supporting Evidence (1 citations)`**
2. **Highlight to Evaluators**:
   - The physical file lineage: `01_Standard_Operating_Procedure.pdf`.
   - The 1-based page number: `Page 1`.
   - The equipment model metadata: `Model: S7-1200 CPU 1214C`.
   - The exact verbatim text excerpt stored in the local vector database.

---

### Step 3: Multimodal Image Inspection
*Objective*: Demonstrate local visual interpretation combined with SOP retrieval while keeping observations tentative.

1. Switch to **Tab 3: 🖼️ Visual Inspection** (or use the sidebar in Classic view).
2. Attach the inspection image fixture:
   ```text
   tests/fixtures/synthetic_plc_leds_normal.png
   ```
3. Return to **Tab 1: 💬 Assistant Console** and ask:
   ```text
   Inspect the attached photo of the PLC indicator LEDs. What is the current operating state shown and does any LED indicate a fault?
   ```
4. **Highlight to Evaluators**:
   - **Tentative Visual Observations Panel**: Rendered separately with clear warning badges:
     - *"Tentative observation: RUN/STOP indicator is green; ERROR and MAINT LEDs are dark."*
     - *"CPU is in normal RUN operating state with no active fault."*
   - **Grounded Technical Guidance**: The text below cites `01_Standard_Operating_Procedure.pdf` confirming normal operating protocol.

---

### Step 4: Negative Test / Unsupported Question (Zero Hallucination)
*Objective*: Prove the system never invents technical values when evidence is lacking.

1. Ask an out-of-scope question about absent equipment:
   ```text
   What is the exact torque specification for the cylinder head bolts on the high-pressure air compressor?
   ```
2. **Observe**:
   - The assistant displays the prominent warning banner:
     > ⚠️ **Insufficient Documentary Evidence**: The retrieved manuals and SOPs do not substantiate an answer to this query.
   - The answer text confirms: *"Insufficient documentary evidence found to answer..."*
   - No torque values, bolt sizes, or maintenance instructions are hallucinated.

