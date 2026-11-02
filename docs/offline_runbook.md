# VALENCE: Air-Gapped Offline Runbook & Verification Manual

This runbook defines the exact preparation, verification, and execution procedures required to run VALENCE in a strictly air-gapped, offline environment with **zero runtime package downloads or external API calls**.

---

## 1. Online Preparation Phase (One-Time Setup)

Perform these steps while connected to the network before entering the air-gapped evaluation environment:

### Step 1: Environment & Virtualenv
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Download Model Weights to Local Cache
```bash
# Pull local LLM & VLM models into local Ollama storage
ollama pull qwen2.5:latest            # Primary text model (or llama3.2:3b)
ollama pull llama3.2-vision:11b       # Local multimodal inspection model

# Download local embedding model weights into the explicit models/ directory
mkdir -p models
git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 models/all-MiniLM-L6-v2
```

### Step 3: Configure Local Environment
```bash
cat << 'EOF' > .env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:latest
OLLAMA_VLM_MODEL=llama3.2-vision:11b
EMBEDDING_MODEL_DIR=models/all-MiniLM-L6-v2
QDRANT_STORAGE_PATH=data/qdrant_storage
QDRANT_COLLECTION_NAME=industrial_docs
VALENCE_MOCK_MODE=0
EOF
```

---

## 2. Air-Gap Transition & Verification Checklist

Before starting the demo or production operation, sever all outbound connectivity (disable Wi-Fi / disconnect Ethernet).

### Check 1: Zero Outbound Endpoints Audit
Run the codebase audit to verify that no external URLs exist in runtime code:
```bash
grep -rn "https://" backend/ src/ config.py
# Must return ZERO runtime endpoints (only localhost:11434 is permitted)
```

### Check 2: Streamlit Analytics Telemetry Block
Verify that `.streamlit/config.toml` has disabled telemetry:
```toml
[browser]
gatherUsageStats = false
```

### Check 3: Run the Environment Readiness Doctor
Execute the read-only pre-flight doctor:
```bash
export PYTHONPATH=.
python3 scripts/doctor.py
```
*Expected Output*:
- Endpoint: strictly loopback (`localhost:11434`)
- Local weights: present in `models/all-MiniLM-L6-v2`
- Vector index path: writable
- All checks: `[PASS]`

---

## 3. Air-Gapped Offline Startup Sequence

### Step 1: Start the Local Ollama Daemon
Ensure Ollama is running locally:
```bash
ollama list
```
*(Confirms `qwen2.5:latest` and `llama3.2-vision:11b` are available locally).*

### Step 2: Launch Application via Offline Runner
```bash
./scripts/run_app.sh
```
*(Or manually via: `streamlit run src/ui/app.py`).*

Access the interface in your browser:
👉 **`http://localhost:8501`**

---

## 4. End-to-End Offline Workflow Verification

Execute these four verification workflows to prove 100% offline functionality:

| Workflow | Action | Expected Offline Verification Observation |
|---|---|---|
| **1. Ingestion & Persistence** | In Tab 2, upload `01_Standard_Operating_Procedure.pdf` and click **"Index Document"**. | Chunks are parsed and vectors stored in `data/qdrant_storage/`. Counter updates to `1 Doc Indexed`. |
| **2. Restart Persistence** | Terminate the application (`Ctrl+C`), restart it, and query indexed SOP. | System retains all chunks and answers without needing re-uploading or re-indexing. |
| **3. Grounded Question** | Ask: *"What is the procedure to change operating state?"* | Returns factual answer citing `[doc_...#p1#c0]`. Source evidence drawer expands to show exact chunk text. |
| **4. Negative Query (No Hallucination)** | Ask: *"What is the torque specification for the compressor cylinder head bolts?"* | Prominently displays: **⚠️ Insufficient Documentary Evidence**. No values are invented. |
| **5. Visual Inspection** | In Tab 3, attach `tests/fixtures/synthetic_plc_leds_normal.png` and ask: *"Inspect the PLC status."* | Observations panel displays tentative LED status (*"RUN indicator green, no fault"*). |

---

## 5. Offline Emergency Procedures & Fallback

- **If Ollama Daemon Crashes or Is Terminated**:
  - The application does not crash.
  - Queries return clear error reporting: `Cannot connect to local Ollama daemon on localhost:11434`.
  - In Tab 4 (System Control), toggle **"Run in Mock Backend Mode"** to continue presentation in simulated mode with zero models required.
- **If Image Inference Is Unclear**:
  - System flags ambiguity explicitly: *"Equipment model could not be unambiguously confirmed"*.
  - General SOP guidance is presented without silently misapplying wrong manuals.

