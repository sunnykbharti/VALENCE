# Project: Offline Industrial Knowledge Assistant (VALENCE)

## Objective
Build a hackathon prototype that answers questions from equipment manuals and SOPs, with supporting evidence.

## System Architecture & Constraints
- **Air-gapped Runtime**: All document processing, embeddings, retrieval, generation, and image interpretation must run locally.
- **No Remote Calls**: No hosted inference, hosted embeddings, hosted OCR, web search, cloud fallback, or automatic runtime downloads.
- **Localhost Allowed**: Localhost inter-process communication (e.g. to a local Ollama daemon or local Qdrant instance) is permitted.
- **Synthetic Data**: Public documents and clearly marked synthetic test data are used during development.

## Team Ownership & Responsibilities
This project is shared across two separate Antigravity workspaces:

### Member A (MacBook Air M1)
- Document ingestion & PDF parsing (`ingest_pdf`)
- User Interface (Streamlit)
- Evaluation harness (`evaluation/`)
- Demo scenario scripting and presentation

### Member B (MacBook Air M5)
- Local model management and embedding pipeline
- Vector indexing and retrieval (`index_chunks`, `retrieve`)
- Local LLM generation & local multimodal interpretation (`answer_question`, `answer_with_image`)
- System configuration and dependency management

## Shared Contracts & Conventions
- Shared contracts live in [`contracts.py`](file:///Users/sunnykumarbharti/Desktop/Desktop/Vikrant/contracts.py) and cannot be modified without mutual agreement.
- **Page Numbers**: 1-based original PDF page positions (`page >= 1`).
- **Data Validation**: Reject whitespace-only chunk text, empty document IDs, and empty source IDs.
- **Deterministic IDs**: Chunk and document IDs must be derived deterministically.
- **Insufficient Evidence**: Defined strictly by documentary support (retrieved context does not substantiate the answer), never by model confidence scores.
- **Citations**: `Answer.evidence` contains supporting evidence selected for the answer. Every citation identifier in `Answer.text` must map to an item in `Answer.evidence`.
- **Unknown Equipment**: If equipment model is unidentified or unspecified, it must remain `None`.
- **No Hallucination**: Do not invent maintenance instructions or technical values. State when evidence is insufficient.

## Verification & Handoff Rules
- Distinguish mocked unit tests from real model integration tests.
- Never claim a test passed unless it was actually executed.
- Report all blockers explicitly (e.g., missing dependencies or missing local models).
- Every handoff must report:
  1. Files changed.
  2. Commands executed.
  3. Tests run and actual results.
  4. Remaining limitations.
  5. The next smallest task.
