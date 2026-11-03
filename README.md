# VALENCE: Offline Industrial Knowledge & Visual Inspection Assistant

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Runtime: Air-Gapped](https://img.shields.io/badge/Runtime-100%25%20Air--Gapped-success.svg)](docs/offline_runbook.md)
[![Tests: 172 Passed](https://img.shields.io/badge/Tests-172%20Passed-brightgreen.svg)](tests/)
[![Models: Local Ollama](https://img.shields.io/badge/Inference-Local%20Ollama-orange.svg)](https://ollama.com/)

**VALENCE** is an air-gapped multimodal industrial assistant designed for shop-floor technicians, field operators, and maintenance engineers. It answers technical questions from equipment manuals, standard operating procedures (SOPs), and maintenance logs with verifiable documentary evidence, while supporting targeted visual inspection of machinery.

---

## Key Capabilities

### 1. Air-Gapped Document Ingestion & Vector Retrieval
- **1-Based Page Lineage**: Deterministic chunk extraction (`[doc_id#pX#cY]`) linking every excerpt directly to original manual pages.
- **Embedded Local Vector Search**: Embedded disk-backed Qdrant store with automatic SQLite fallback, powered by offline `FastEmbed` embeddings.
- **Strict Documentary Grounding**: Answers cite exact source chunks. If the retrieved context does not substantiate the answer, the assistant reports insufficient documentary evidence rather than guessing or hallucinating.

### 2. “Point, Inspect, Ask” (Multimodal Region Inspection)
- **User-Selected Region**: Technicians isolate equipment components (indicators, nameplates, gauges) using crop percentage sliders.
- **Strict Negative Constraints**: Local vision models (`qwen2.5vl:7b` or `llama3.2-vision:11b` on local Ollama) report visible text, indicator states, and physical wear with explicit uncertainty.
  - *No Hallucinated Safety*: Never assumes operational safety or electrical correctness from visual appearance alone.
  - *No Out-of-Crop Inferences*: Explicitly reports when text is unreadable or blurry without autocompleting model numbers.
- **Operator Confirmation Gate**: Detected terms and readings are displayed to the operator for verification before initiating documentation retrieval.
- **Four-Part Separated Display**:
  1. *User-Confirmed Information* (Operator-editable terms)
  2. *Tentative Visual Observations* (Model findings with explicit uncertainty)
  3. *Retrieved Documentary Evidence* (Citations and excerpts)
  4. *Unresolved Questions & Follow-Up* (Targeted requests for closer/sharper views)

### 3. Industrial Incident Operations & Shift Handover
- **Structured Incident Lifecycle**: Tracks operational symptoms, equipment models, and diagnostic progress across `open`, `investigating`, `mitigated`, `resolved`, and `closed` states.
- **Rules-Based Escalation**: Automated evaluation against plant escalation rules (e.g., pressure thresholds, vibration limits).
- **Shift Handover Synthesis**: Generates structured shift transition briefs with verified technician findings and pending maintenance checks.

### 4. Dual Execution Engines
- **Live Local Engine**: Connects to local Ollama (`localhost:11434`) and local vector storage with zero external network access.
- **In-Memory Mock Mode**: Deterministic simulation mode for instantaneous offline testing, CI, and decoupled UI development.

---

## System Architecture

```
                       ┌───────────────────────────────────────────────┐
                       │          VALENCE User Interface               │
                       │     (Modern Industrial Tabbed Dashboard)       │
                       └───────┬───────────────────────────────┬───────┘
                               │                               │
                [Document Q&A / Incidents]          [Point, Inspect, Ask]
                               │                               │
                               ▼                               ▼
                       ┌──────────────┐                ┌──────────────┐
                       │ Industrial   │                │ Local Vision │
                       │ Service      │                │ Engine       │
                       └───────┬──────┘                └───────┬──────┘
                               │                               │
                ┌──────────────┴──────────────┐                │
                ▼                             ▼                ▼
     ┌────────────────────┐        ┌──────────────────┐  ┌───────────┐
     │ Local Vector Store │        │ Local Generator  │  │ Local VLM │
     │ (FastEmbed/Qdrant) │        │ (Ollama LLM)     │  │ (Ollama)  │
     └────────────────────┘        └──────────────────┘  └───────────┘
```

---

## Team Ownership & Repository Division

VALENCE is maintained collaboratively across two distinct development environments:

| Area | Member A (MacBook Air M1) | Member B (MacBook Air M5) |
|---|---|---|
| **Document Ingestion** | Ingestion pipeline & PDF chunking (`src/ingestion/`) | Schema definitions & lineage invariants |
| **Search & Retrieval** | — | Embedding pipeline, vector storage, and hybrid retrieval (`backend/`) |
| **Generation & Vision** | Confirmation UI & visual display widgets | Local LLM generation, VLM crop inspection adapter (`backend/vision.py`) |
| **Incidents & Handover** | Incident UI panels (`src/ui/components/`) | Incident schema & escalation engine (`backend/applicability.py`) |
| **Testing & Evaluation** | UI smoke tests & scenario evaluations (`evaluation/`) | Unit test battery (172 tests) & offline air-gap audits |

---

## Shared Contracts & Architectural Invariants

All shared interfaces live in [`contracts.py`](contracts.py) and enforce strict invariants:
- **1-Based Page Numbers**: All chunk page positions are 1-based (`page >= 1`).
- **Data Validation**: Whitespace-only text, empty document IDs, or blank source IDs are rejected.
- **Deterministic Identifiers**: Chunk IDs (`doc_...#pX#cY`) and crop IDs (`img_crop_<sha256[:12]>`) are derived deterministically.
- **Grounding & Citations**: Every citation token `[source_id]` in an answer must strictly resolve to an item in `Answer.evidence`.
- **Refusal Semantics**: `insufficient_evidence` is strictly determined by documentary support, never by model confidence scores.

---

## Project Layout

```
VALENCE/
├── contracts.py              # Shared immutable data contracts and protocols
├── config.py                 # Loopback-only runtime configuration
├── README.md                 # Project documentation and architecture guide
├── AGENTS.md                 # Air-gapped invariants and team conventions
├── requirements.txt          # Python dependencies
│
├── backend/                  # Member B: Core offline backend services
│   ├── service.py            # Unified IndustrialService coordinator
│   ├── vision.py             # LocalVisionEngine & crop inspection adapter
│   ├── vector_store.py       # Qdrant and SQLite vector database engine
│   ├── generator.py          # Evidence-grounded response generator
│   ├── applicability.py      # Plant escalation & applicability engine
│   └── mock_backend.py       # Deterministic backend simulation
│
├── src/                      # Member A: UI and application layer
│   ├── ui/                   # Streamlit UI implementation
│   │   ├── app.py            # Streamlit application entry point
│   │   ├── mock_backend.py   # In-memory mock backend for UI
│   │   ├── components/       # Message view, incident panel, status pills
│   │   └── views/            # Modern tabbed dashboard & Classic layout
│   ├── ingestion/            # PDF ingestion, text extraction, chunking
│   ├── incidents/            # Incident schema, storage protocol, mock service
│   ├── utils/                # Image cropping and region overlay utilities
│   └── api_server.py         # REST API server (port 8000)
│
├── data/                     # Offline data store
│   ├── raw_docs/             # Technical equipment manuals (PDF)
│   ├── synthetic/            # Synthetic benchmark SOPs and equipment cards
│   └── qdrant_storage/       # Local disk-backed vector store
│
├── docs/                     # Operational runbooks and guides
│   ├── offline_runbook.md    # Air-gapped verification procedures
│   ├── local_setup.md        # Model sizing and preparation guide
│   └── hackathon_presentation_and_qa.md # Presentation pitch & Q&A prep
│
├── evaluation/               # Scenario evaluation battery and reports
├── scripts/                  # Standalone verification and capability spikes
└── tests/                    # 172-test automated unit test suite
```

---

## Quickstart Guide

### 1. Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Local Model Preparation (Ollama)
Ensure the local Ollama daemon is active (`ollama serve`). Pull the approved local models:
```bash
# Text generation LLM
ollama pull llama3.2:3b

# Vision-Language Model for Point, Inspect, Ask
ollama pull qwen2.5vl:7b
```

### 3. Launching the Assistant

#### Option A: Streamlit Web Dashboard (Recommended)
```bash
# Run Streamlit dashboard (defaults to Mock Mode for instant evaluation)
streamlit run src/ui/app.py
```
*Toggle between **In-Memory Mock Mode** and **Live Local Engine** anytime in the System Control tab.*

#### Option B: REST API Backend
```bash
# Launch FastAPI backend on http://localhost:8000
python -m src.api_server
```

---

## Running Automated Tests

VALENCE includes a comprehensive 172-test unit test battery validating ingestion, retrieval, chunking invariants, citation verification, incident state, and crop inspection:

```bash
# Run full unit test suite
./env/bin/python -m unittest discover -s tests

# Run dedicated Point, Inspect, Ask tests
./env/bin/python -m unittest tests/test_point_inspect_ask.py
```

---

## Air-Gapped Verification Audit

VALENCE enforces a strict zero-outbound-network policy:
- **No Remote Endpoints**: Outbound requests are blocked; only loopback (`127.0.0.1` / `localhost:11434`) is permitted.
- **Telemetry Disabled**: Streamlit analytics telemetry is disabled in `.streamlit/config.toml`.
- **Zero Runtime Downloads**: Embeddings and models run strictly from local disk.

To audit runtime code for zero external endpoints:
```bash
grep -rn "https://" backend/ src/ config.py
# Must return ZERO runtime endpoints
```

---

## License & Usage

Developed as an industrial hackathon prototype. All synthetic documentation and test benchmarks are created exclusively for validation purposes. Technical equipment manuals belong to their respective manufacturers.
