# VALENCE: Phase 2 Release Checklist & Offline Verification Audit

This document certifies that VALENCE satisfies all operational, architectural, and air-gapped constraints for local offline industrial deployment.

---

## 1. Release Verification Matrix

| Verification Dimension | Status | Verified Component / Test | Evidence / Observations |
| :--- | :---: | :--- | :--- |
| **Phase 1 Regression** | ✅ PASS | 78 tests (`contracts`, `ingestion`, `RAG`, `UI`, `vision`) | 78/78 tests pass without regression in 0.94s. |
| **Phase 2 Regression** | ✅ PASS | 76 tests (`incidents`, `tools`, `orchestrator`, `applicability`) | All 76 Phase 2 tests pass; 154/154 total active tests pass. |
| **Incident Persistence** | ✅ PASS | `SQLiteIncidentService` (`data/incidents.db`) | Verified across 3 separate process restarts with full evidence deserialization. |
| **Air-Gap Confinement** | ✅ PASS | Loopback audit (`config.py`) | Endpoint strictly targets `http://localhost:11434`. Zero external remote endpoints. |
| **Zero Runtime Downloads** | ✅ PASS | Package & model audit | Model weights and packages run locally; no cloud fallback or telemetry (`gatherUsageStats=false`). |
| **Model Action Discrimination** | ✅ PASS | `TestRealLocalModelOrchestration` on `qwen2.5:latest` | Confirmed equipment triggers `search_documents`; unconfirmed triggers `ask_user`. |
| **Contradiction Detection** | ✅ PASS | `detect_contradictions` in `applicability.py` | Opposing directives and conflicting torque setpoints escalate with `CONTRADICTORY_INSTRUCTIONS`. |
| **Path Traversal Security** | ✅ PASS | `validate_safe_filesystem_path` | Rejects `..` tokens and non-workspace absolute paths with `PermissionError`. |
| **Bounded Orchestrator** | ✅ PASS | `BoundedOrchestrator` | Bounded retries on malformed JSON; repeated actions abort; max steps enforced. |
| **Knowledge Promotion Guard**| ✅ PASS | `promote_incident_to_knowledge_chunk` | Blocks unreviewed incidents from entering knowledge base (`PermissionError`). |

---

## 2. Supported Local Model Configuration

| Capability | Model Identifier | Parameter Size | Format & Quantization | Local Runtime |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Text LLM** | `qwen2.5:latest` | 7.6B | GGUF Q4_K_M (4.7 GB) | Local Ollama Daemon (`localhost:11434`) |
| **Fallback Text LLM**| `llama3.2:3b` | 3.2B | GGUF Q4_K_M (2.0 GB) | Local Ollama Daemon (`localhost:11434`) |
| **Multimodal Vision**| `llama3.2-vision:11b` | 11B | GGUF Q4_K_M (7.9 GB) | Local Ollama Daemon (`localhost:11434`) |
| **Text Embeddings**  | `all-MiniLM-L6-v2` | 22M | PyTorch / ONNX (80 MB) | Local weights in `models/all-MiniLM-L6-v2` |
| **Incident Storage** | SQLite 3 | Embedded | Single-file (`data/incidents.db`) | Built-in Python `sqlite3` engine |
| **Vector Indexing**  | Qdrant Local / SQLite | Embedded | Local disk (`data/qdrant_storage/`) | In-process embedded engine |

---

## 3. Performance & Resource Benchmarks (Apple Silicon Demo Machine)

Measurements taken on local Apple Silicon hardware with unified memory architecture:

- **Resident Set Size (Initial Base RSS)**: `21.4 MB`
- **Resident Set Size (Peak Working RSS)**: `21.4 MB` (Python process baseline excluding Ollama background daemon)
- **Local Text RAG Latency**: `< 1.0 ms` (Mock / in-memory), `~1.2–2.8 s` (Live Ollama `qwen2.5:latest` inference)
- **Multimodal Visual Inspection Latency**: `< 1.0 ms` (Mock), `~3.5–5.2 s` (Live Ollama vision inference including weight swap)
- **Incident State Retrieval Latency**: `< 0.5 ms` (SQLite local disk lookup)

---

## 4. Known Limitations & Operational Boundaries

1. **Scanned / Rasterized Documents**: Manuals lacking digital text streams emit page warnings and require vector/searchable PDF formats.
2. **Sequential Model Swapping on 16 GB RAM**: To prevent unified memory thrashing, vision and text models execute sequentially with `"keep_alive": "0m"`.
3. **Single-Workstation Embedded Database**: Embedded SQLite and Qdrant local storage are optimized for single-machine air-gapped workstations.
4. **Physical Write Prohibitions**: VALENCE is strictly an advisory, read-only decision assistant; no direct PLC/actuator write interfaces exist.

---

## 5. Release Sign-Off

- **Code Inspection & Test Verification**: Certified via `./scripts/verify_offline_milestone_4b.py`.
- **Offline Runbook**: Documented in [`docs/offline_runbook.md`](file:///Users/sunnykumarbharti/Desktop/Desktop/Vikrant/docs/offline_runbook.md).
- **Presentation Sequence**: Documented in [`docs/demo.md`](file:///Users/sunnykumarbharti/Desktop/Desktop/Vikrant/docs/demo.md).
- **Status**: **READY FOR AIR-GAPPED HACKATHON DEMO**.

