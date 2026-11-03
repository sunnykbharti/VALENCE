# VALENCE: Offline Industrial Knowledge & Visual Inspection Assistant

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Runtime: Air-Gapped](https://img.shields.io/badge/Runtime-100%25%20Air--Gapped-success.svg)](docs/offline_runbook.md)
[![Tests: 179 Passed](https://img.shields.io/badge/Tests-179%20Passed-brightgreen.svg)](tests/)
[![Models: Local Ollama](https://img.shields.io/badge/Inference-Local%20Ollama-orange.svg)](https://ollama.com/)
[![Speech: Web Speech API](https://img.shields.io/badge/Voice-Client--Native%20STT%2FTTS-blueviolet.svg)](#voice-dictation--industrial-text-to-speech)

**VALENCE** is an air-gapped multimodal industrial knowledge and diagnostic assistant engineered for factory-floor technicians, field operators, and reliability engineers. It answers technical inquiries from equipment manuals, standard operating procedures (SOPs), and maintenance logs with verifiable 1-based page citations, executes targeted visual inspection of machinery, and orchestrates incident troubleshooting workflows—all running **100% locally and completely disconnected from the cloud**.

---

## Key Capabilities

### 1. Air-Gapped Document Ingestion & Hybrid Vector Retrieval
- **1-Based Physical Page Citations**: Deterministic chunk extraction (`[doc_id#pX#cY]`) linking every excerpt directly to physical manual pages.
- **Embedded Local Vector Search**: Disk-backed local Qdrant vector database paired with an automatic SQLite fallback, powered by offline `FastEmbed` embeddings.
- **Strict Documentary Grounding**: Every answer is substantiated 1:1 against retrieved chunks. If evidence is lacking, the assistant strictly outputs `insufficient_evidence=True` rather than guessing.
- **Dynamic Document De-Indexing & Cache Purge**: Immediate removal of manuals and SOPs from the vector store and SQLite registry, purging all in-memory caches and halting retrieval for deleted files.

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

### 3. Voice Dictation & Industrial Text-to-Speech (STT / TTS)
- **Embedded Microphone Query Input**: Voice dictation button (`🎙️`) embedded directly inside the chat input box using browser-native Web Speech API. Transcribes technician speech in real-time with zero external network transmission.
- **Industrial Technical Acronym Normalizer**: Expands shop-floor jargon (`SOP` -> `S.O.P.`, `PLC` -> `P.L.C.`, `CPU` -> `C.P.U.`, `LED` -> `L.E.D.`, `RPM` -> `R.P.M.`, `PSI` -> `P.S.I.`, `°C` -> `degrees Celsius`) for natural technical pronunciation.
- **Sentence-Queued Playback**: Eliminates browser speech synthesis timeout bugs by chunking speech into atomic sentences with sequential playback.
- **Audio Controls**: Inline playback bar featuring Play, Pause, Resume, Stop, live sentence tracking, and speed selection (`0.9x`, `1.0x`, `1.2x`).

### 4. Industrial Incident Operations & State Persistence
- **Structured Incident Lifecycle**: Tracks operational symptoms, equipment models, and diagnostic progress across `open`, `investigating`, `mitigated`, `resolved`, and `closed` states.
- **Auditable Tool Timeline**: Real backend tool execution events (actions, purposes, outputs, statuses) displayed without private chain-of-thought exposure.
- **Interactive Clarification Workflow**: Automatically halts and prompts the technician when equipment model or operating context is ambiguous.
- **Per-User SQLite Persistence**: Chat histories, incident states, and indexed document registries persist automatically across browser refreshes and session restarts.
- **Clean Production Runtime**: Zero hardcoded or pre-seeded dummy incidents/prompts. All analytics and telemetry reflect live user-uploaded manuals and real incidents.

### 5. Dual Execution Engines
- **Live Local Engine**: Connects to local Ollama (`localhost:11434`) and local vector storage with zero external network access.
- **In-Memory Mock Mode**: Deterministic simulation mode for instantaneous offline testing, CI, and decoupled UI development.

---

## System Architecture

```
                       ┌───────────────────────────────────────────────┐
                       │          VALENCE Modern Dashboard             │
                       │   (Chat, Incidents, KB, Vision, Analytics)    │
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
                 │                             │                │
                 ▼                             ▼                ▼
      ┌───────────────────────────────────────────────────────────────┐
      │         SQLite Persistence Layer (user_state.db)              │
      │   (Sessions, Chat History, Chunks, Documents, Incidents)      │
      └───────────────────────────────────────────────────────────────┘
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
| **Testing & Evaluation** | UI smoke tests & scenario evaluations (`evaluation/`) | Unit test battery (179 tests) & offline air-gap audits |

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
│   ├── vector_store.py       # Qdrant and SQLite persistent vector database engine
│   ├── generation.py         # Evidence-grounded response generator
│   ├── applicability.py      # Plant escalation & applicability engine
│   ├── orchestrator/         # Bounded coordinator with explicit tool allowlist
│   └── mock_backend.py       # Deterministic backend simulation
│
├── src/                      # Member A: UI and application layer
│   ├── ui/                   # Streamlit industrial dashboard
│   │   ├── app.py            # Streamlit application entry point
│   │   ├── persistence.py    # SQLite state persistence (sessions, chat, docs)
│   │   ├── voice_installer.py# Automatic installer for native voice assets
│   │   ├── mock_backend.py   # In-memory mock backend for UI
│   │   ├── static/           # Client-side assets (valence_voice.js)
│   │   ├── components/       # TTS player, message view, activity panel, incident panel
│   │   └── views/            # Modern industrial tabbed workspace
│   ├── ingestion/            # PDF ingestion, text extraction, chunking
│   ├── incidents/            # Incident schema, SQLite service, mock service
│   ├── utils/                # Image cropping and region overlay utilities
│   └── api_server.py         # REST API server (port 8000)
│
├── data/                     # Offline data store
│   ├── raw_docs/             # Technical equipment manuals (PDF)
│   ├── synthetic/            # Synthetic benchmark SOPs and equipment cards
│   ├── qdrant_storage/       # Local disk-backed vector store
│   └── user_state.db         # Persistent SQLite database
│
├── docs/                     # Operational runbooks and guides
│   ├── offline_runbook.md    # Air-gapped verification procedures
│   ├── local_setup.md        # Model sizing and preparation guide
│   └── hackathon_presentation_and_qa.md # Presentation pitch & Q&A defense
│
├── evaluation/               # Scenario evaluation battery and reports
├── scripts/                  # Standalone verification and capability spikes
└── tests/                    # 179-test automated unit and integration suite
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
*Access the workspace at `http://localhost:8501`. Toggle between **In-Memory Mock Mode** and **Live Local Engine** anytime in the top bar or System Control tab.*

#### Option B: REST API Backend
```bash
# Launch FastAPI backend on http://localhost:8000
python -m src.api_server
```

---

## Running Automated Tests

VALENCE includes a comprehensive 179-test automated test suite validating ingestion, retrieval, chunking invariants, citation verification, incident state, and crop inspection:

```bash
# Run full unit and integration test battery
./env/bin/python -m unittest discover -s tests

# Run dedicated Point, Inspect, Ask tests
./env/bin/python -m unittest tests/test_point_inspect_ask.py

# Run SQLite persistence and state tests
./env/bin/python -m unittest tests/test_persistence.py
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
# Must return ZERO runtime network endpoints
```

---

## License & Usage

Developed as an industrial hackathon prototype. All synthetic documentation and test benchmarks are created exclusively for validation purposes. Technical equipment manuals belong to their respective manufacturers.
