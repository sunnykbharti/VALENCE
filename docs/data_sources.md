# Data Sources & Manufacturer Manual Guidelines

This document provides instructions on how users supply public manufacturer equipment manuals and synthetic operating procedures to VALENCE.

---

## 1. Air-Gapped Ingestion Principles

In accordance with system constraints (`AGENTS.md`):
- **Zero Runtime Downloads**: VALENCE does **not** download, crawl, or scrape manuals from the internet at runtime.
- **Local Storage**: All source documents must be placed on the local filesystem before ingestion.
- **Deterministic Processing**: All documents generate stable deterministic identifiers (`doc_<hash>`) based strictly on their binary content.

---

## 2. Document Locations

The repository organizes documents into two dedicated directories:

| Directory | Purpose | Handling |
|---|---|---|
| `data/raw_docs/` | Authentic, publicly available manufacturer manuals and technical specifications. | Manually placed by the user. Not modified by code. |
| `data/synthetic/` | Synthetic demonstration SOPs, inspection sheets, and escalation policies. | Clearly marked with `synthetic=True` flag in contracts. |

---

## 3. How to Supply a Manufacturer Manual

1. **Obtain Official Documentation**:
   - Download the official PDF manual directly from the equipment manufacturer's customer portal (e.g., Siemens Industry Online Support, Festo Didactic, ABB Library, Schneider Electric).
   - Ensure the document is a public manual or authorized technical SOP.

2. **Place File into Local Repository**:
   - Copy the PDF manual into `data/raw_docs/`:
     ```bash
     cp /path/to/downloaded/manual.pdf data/raw_docs/S7-1200_System_Manual.pdf
     ```

3. **Verify Text Layer (Non-OCR)**:
   - VALENCE Milestone 1 parses native PDF text layers.
   - If a manual is a flat scanned image without an embedded OCR text layer, the ingestor will report pages with no extractable text as warnings and omit them from the chunk index.

4. **Associate Equipment Model**:
   - When ingesting the document through the ingestion service, specify the equipment identifier:
     ```python
     from src.services import create_ingestor

     ingestor = create_ingestor(mock=False)
     chunks = ingestor.ingest_pdf(
         path="data/raw_docs/S7-1200_System_Manual.pdf",
         equipment_model="S7-1200 CPU 1214C",
         synthetic=False,
     )
     ```
   - If the manual covers multiple pieces of equipment or the model is unknown, set `equipment_model=None`.

---

## 4. Ingestion Verification

To verify that a supplied manual parses cleanly:

```bash
python3 -c "
from src.services import create_ingestor
ingestor = create_ingestor(mock=False)
chunks = ingestor.ingest_pdf('data/raw_docs/S7-1200_System_Manual.pdf')
print(f'Successfully parsed {len(chunks)} chunks across pages')
"
```

---

## 5. Dependency Recommendation for Member B

- For standard and synthetic documents, the built-in pure-Python parser handles Flate, ASCII85, and text stream decompression without third-party dependencies.
- For large, complex linearized manufacturer manuals (e.g., `data/raw_docs/MANNUAL.pdf` exceeding 800 pages with complex font cross-reference tables), adding `pypdf>=4.0.0` is recommended. `pypdf` is a pure-Python library with zero native C dependencies and operates entirely offline.

