# VALENCE Local Setup & Air-Gapped Operation Guide (Member B)

VALENCE operates in an air-gapped environment. To maintain compliance with `AGENTS.md`, system operations are strictly split into two phases:
1. **Online Preparation**: Performed once while connected to download model weights and dependencies.
2. **Offline Runtime**: Performed strictly air-gapped with zero remote calls and loopback-only communication.

---

## Hardware Suitability & Model Sizing Analysis

Target Machine: **Apple Silicon MacBook Air (M5, 16 GB Unified Memory)**

- **Memory Architecture**: CPU and GPU share the 16 GB unified RAM pool.
- **System Overhead**: macOS WindowServer, buffers, and system caches require ~3.5 GB.
- **Available Unified Memory**: ~12.5 GB.
- **Model Allocation Strategy**:
  - **Embedding Engine**: `all-MiniLM-L6-v2` (~120 MB RAM) or `bge-small-en-v1.5` (~133 MB RAM). Extremely fast, negligible memory consumption.
  - **Vector Database**: Qdrant embedded mode with disk-backed storage (~200 MB memory footprint).
  - **Local Text LLM**: `llama3.2:3b` (~2.0 GB VRAM at 4-bit quantization). Leaves ~10 GB headroom, preventing swapping during large multi-page SOP retrieval contexts.
  - **Local Multimodal VLM**: `llama3.2-vision:11b` (~7.9 GB VRAM at 4-bit quantization). Fits comfortably within memory budget when operated sequentially with the text model (total model footprint: 2.0 + 7.9 = 9.9 GB <= 12.5 GB available).

---

## Phase 1: Online Preparation (Run Once With Internet)

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export PYTHONPATH=.
```

### 2. Pull Local Models into Ollama
Ensure the Ollama application or daemon is active:
```bash
# Text generation LLM (fast, concise SOP answers)
ollama pull llama3.2:3b

# Vision-Language Model for equipment inspection
ollama pull llama3.2-vision:11b
```

### 3. Prepare Local Embedding Weights
Clone or copy the sentence-transformer weights locally so no runtime HuggingFace calls occur:
```bash
mkdir -p models
git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 models/all-MiniLM-L6-v2
```

### 4. Verify Preparation via Diagnostics
Run the diagnostic suite to confirm all offline assets are present:
```bash
python3 -c "import backend; print(backend.run_diagnostics().summary())"
```

---

## Phase 2: Offline Runtime (Air-Gapped Operation)

In this phase, remote network connections must be severed. Only loopback calls (`localhost` / `127.0.0.1`) are permitted.

### 1. Air-Gap Safety Rules
- `config.py` automatically rejects non-loopback URLs.
- No network requests, hosted APIs, or automatic model downloads will be initiated.
- All documents, indexes, and models are read from local disk.

### 2. Start the Local Ollama Daemon
```bash
ollama serve
```

### 3. Verify Offline Diagnostics & Smoke Suite
Run the diagnostic check and test suite to ensure the system is operational:
```bash
export PYTHONPATH=.
python3 -c "import backend; print(backend.run_diagnostics().summary())"
python3 -m unittest discover -s tests
```

### 4. Launch the Application
```bash
streamlit run src/ui/app.py
```
*(During development, mock mode is active by default. Set `VALENCE_MOCK_MODE=0` in `.env` to engage real local inference once models are indexed.)*
