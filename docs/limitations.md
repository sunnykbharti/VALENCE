# VALENCE: System Limitations & Unfinished Features

In accordance with `AGENTS.md` verification guidelines, this document explicitly records all known technical boundaries, operational limitations, and unfinished prototype features. No unsupported claims are made.

---

## 1. Technical Limitations

### 1.1 Scanned PDF Extraction & OCR
- **Current Capability**: The ingestion engine extracts digital text streams directly from vector and searchable PDFs using pure-Python parsing and `pypdf`.
- **Limitation**: Purely scanned, rasterized, or photocopy-style PDFs contain no extractable character streams. In accordance with contract rules, these pages are omitted and logged as warnings (`Page X has no extractable text`).
- **Required Enhancement**: Integration of an air-gapped, on-device OCR engine (such as local Tesseract or Surya OCR) for scanned legacy manuals.

### 1.2 Memory Headroom on 16 GB Unified RAM
- **Current Strategy**: Sequential model execution. The vision engine passes `"keep_alive": "0m"` to Ollama upon visual inspection completion to immediately unload the ~7.9 GB VLM weights from unified memory before loading the text LLM (`qwen2.5:latest` or `llama3.2:3b`).
- **Limitation**: Multimodal queries incur a model swap latency of ~2.5–4.0 seconds as weights transfer across Metal unified memory buffers.

### 1.3 Complex Multi-Column Engineering Tables
- **Current Capability**: Extracts sequential text strings and chunks them respecting paragraph and line breaks.
- **Limitation**: Heavily nested tables with merged headers and cross-column cells can lose spatial column associations when linearized into flat text chunks.

### 1.4 Vector Storage Concurrency
- **Current Capability**: Embedded on-disk local persistent storage (`data/qdrant_storage/`) with transactional SQLite indexing and payload hashing.
- **Limitation**: Optimized for single-technician offline workstations. Multi-client concurrent write transactions across multiple workstations require running the standalone Qdrant server daemon.

---

## 2. Unfinished Features & Future Roadmap

1. **Hands-Free Speech Interface**:
   - *Status*: Not implemented.
   - *Plan*: Local on-device Whisper (`whisper.cpp`) for voice-activated technician inquiries in industrial environments.

2. **Before-and-After Image Comparison**:
   - *Status*: Prototype accepts single inspection photographs.
   - *Plan*: Side-by-side comparison of baseline reference diagrams against current technician wear photos.

3. **Automated Folder Watcher**:
   - *Status*: Document indexing is initiated via the UI or CLI script.
   - *Plan*: Background filesystem watcher automatically indexing new SOP revisions dropped into `data/documents/manuals/`.

