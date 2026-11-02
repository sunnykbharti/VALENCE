# Project: Offline Industrial Knowledge Assistant

## Objective
Build a hackathon prototype that answers questions from equipment
manuals and SOPs, with supporting evidence.

## Runtime constraints
- All document processing and inference must run locally.
- No hosted inference, hosted embeddings, hosted OCR, or web search.
- No runtime downloads, cloud fallback, or remote UI assets.
- Localhost communication between components is permitted.
- Separate online preparation from offline operation.
- Do not introduce external services without explicit approval.

## Initial architecture
- Python and Streamlit.
- Local PDF extraction.
- Sentence Transformers loaded from a local model directory.
- Qdrant local mode with persistent storage.
- Ollama using locally installed models.
- Model names and paths must be configurable.

## Implementation rules
- Implement only the current milestone.
- Prefer simple modules over agent frameworks.
- Keep extraction, retrieval, generation, and UI separate.
- Preserve document ID, equipment model, page, and source text.
- Construct source references from stored metadata.
- Clearly mark synthetic documents.
- Do not invent maintenance instructions or technical values.
- State when retrieved evidence is insufficient.

## Verification rules
- Add tests for new behavior.
- Distinguish mocked tests from real model integration tests.
- Never claim a test passed unless it was executed.
- If a model or dependency is unavailable, report the blocker.
- Do not silently download a replacement.

## Handoff
Report:
1. Files changed.
2. Commands executed.
3. Tests run and actual results.
4. Remaining limitations.
5. The next smallest task.