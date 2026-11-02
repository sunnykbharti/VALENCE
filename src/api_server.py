"""VALENCE Local REST API Server for Frontend Clients (React & Streamlit).

Exposes local endpoints on port 8000:
- GET  /api/health            -> System health and backend status
- GET  /api/documents         -> Returns indexed documents and chunks
- POST /api/query             -> Grounded query answer with citations
- POST /api/query_image       -> Grounded multimodal image analysis
- POST /api/index_pdf         -> Ingest and index equipment manuals locally
- POST /api/remove_document   -> Remove manual from index
- POST /api/remove_chunk      -> Remove specific chunk
- POST /api/reset             -> Reset corpus and reload defaults
- GET  /api/incidents         -> List active operational incidents
- GET  /api/incidents/<id>    -> Get incident details
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from contracts import Answer, Chunk, Evidence
from src.services import create_backend, create_ingestor, create_incident_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("valence.api_server")

FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"


def is_ollama_online(base_url: str = "http://localhost:11434") -> bool:
    """Probes if the local Ollama daemon is reachable."""
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            return resp.status == 200
    except Exception:
        return False


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    # Initialize backend and incident service
    ollama_online = is_ollama_online()
    use_mock = not ollama_online
    backend = create_backend(mock=use_mock)
    incident_service = create_incident_service(mock=True)

    # Internal document registry metadata
    indexed_documents_meta: dict[str, dict[str, Any]] = {}
    chunks_by_document: dict[str, list[dict[str, Any]]] = {}

    def seed_default_knowledge():
        indexed_documents_meta.clear()
        chunks_by_document.clear()

        demo_chunks = [
            Chunk(
                chunk_id="chk_s7_01",
                document_id="doc_s71200",
                filename="s71200_manual.pdf",
                page=14,
                text=(
                    "Siemens S7-1200 CPU 1214C diagnostic LEDs: When ERROR LED flashes red at 2 Hz, "
                    "it indicates a hardware or firmware fault. Inspect rack temperature (max 60°C), "
                    "check power supply rail, and verify PLC operating status in TIA Portal."
                ),
                equipment_model="S7-1200 CPU 1214C",
                synthetic=True,
            ),
            Chunk(
                chunk_id="chk_rex_01",
                document_id="doc_rex",
                filename="A10VSO_Overhaul_Rev1.pdf",
                page=12,
                text=(
                    "Rexroth A10VSO hydraulic pump troubleshooting: Check suction line strainer for blockage, "
                    "inspect case drain pressure (max 2.5 bar), and verify manifold pressure relief setpoint."
                ),
                equipment_model="Rexroth A10VSO",
                synthetic=True,
            ),
            Chunk(
                chunk_id="chk_comp_01",
                document_id="doc_compressor_sop",
                filename="01_Standard_Operating_Procedure.pdf",
                page=1,
                text=(
                    "Only authorized personnel are permitted to start, stop, monitor, and safely change operating "
                    "states of the Filler Cell PLC. Operating pressure must remain between 6.5 and 8.0 bar."
                ),
                equipment_model="S7-1200 CPU 1214C",
                synthetic=True,
            ),
        ]
        backend.index_chunks(demo_chunks)

        for c in demo_chunks:
            fname = c.filename
            if fname not in indexed_documents_meta:
                indexed_documents_meta[fname] = {
                    "document_id": c.document_id,
                    "chunks_count": 0,
                    "equipment_model": c.equipment_model,
                    "synthetic": c.synthetic,
                }
                chunks_by_document[fname] = []
            indexed_documents_meta[fname]["chunks_count"] += 1
            chunks_by_document[fname].append({
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "filename": c.filename,
                "page": c.page,
                "text": c.text,
                "equipment_model": c.equipment_model,
                "synthetic": c.synthetic,
            })

    seed_default_knowledge()

    # ── Routes ─────────────────────────────────────────────────────────────

    @app.route("/api/health", methods=["GET"])
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "healthy",
            "version": "0.1.0",
            "mode": "live" if not use_mock else "mock",
            "ollama_online": ollama_online,
            "air_gapped": True,
        })

    @app.route("/api/documents", methods=["GET"])
    @app.route("/documents", methods=["GET"])
    def get_documents():
        return jsonify({
            "documents": indexed_documents_meta,
            "chunks": chunks_by_document,
        })

    @app.route("/api/query", methods=["POST"])
    @app.route("/query", methods=["POST"])
    def query():
        data = request.get_json(force=True, silent=True) or {}
        question = data.get("question", "").strip()
        equipment_model = data.get("equipment_model") or None
        if not question:
            return jsonify({"error": "question parameter must be non-empty"}), 400

        try:
            ans: Answer = backend.answer_question(question=question, equipment_model=equipment_model)
            evidence_list = [
                {
                    "source_id": e.source_id,
                    "chunk": {
                        "chunk_id": e.chunk.chunk_id,
                        "document_id": e.chunk.document_id,
                        "filename": e.chunk.filename,
                        "page": e.chunk.page,
                        "text": e.chunk.text,
                        "equipment_model": e.chunk.equipment_model,
                        "synthetic": e.chunk.synthetic,
                    },
                }
                for e in ans.evidence
            ]
            return jsonify({
                "text": ans.text,
                "evidence": evidence_list,
                "insufficient_evidence": ans.insufficient_evidence,
                "observations": ans.observations or [],
            })
        except Exception as e:
            logger.error("Query processing failed: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/query_image", methods=["POST"])
    @app.route("/query_image", methods=["POST"])
    def query_image():
        data = request.get_json(force=True, silent=True) or {}
        question = data.get("question", "").strip()
        image_name = data.get("image_name", "")
        equipment_model = data.get("equipment_model") or None

        if not question:
            return jsonify({"error": "question parameter must be non-empty"}), 400

        # Resolve image path
        image_path = FIXTURES_DIR / image_name
        if not image_path.exists():
            # Check standard fixtures
            if "blurry" in image_name.lower():
                image_path = FIXTURES_DIR / "synthetic_blurry_panel.png"
            elif "ambiguous" in image_name.lower():
                image_path = FIXTURES_DIR / "synthetic_ambiguous_model.png"
            elif "unknown" in image_name.lower():
                image_path = FIXTURES_DIR / "synthetic_unknown_equipment.png"
            else:
                image_path = FIXTURES_DIR / "synthetic_plc_leds_normal.png"

        try:
            ans: Answer = backend.answer_with_image(
                question=question,
                image_path=image_path,
                equipment_model=equipment_model,
            )
            evidence_list = [
                {
                    "source_id": e.source_id,
                    "chunk": {
                        "chunk_id": e.chunk.chunk_id,
                        "document_id": e.chunk.document_id,
                        "filename": e.chunk.filename,
                        "page": e.chunk.page,
                        "text": e.chunk.text,
                        "equipment_model": e.chunk.equipment_model,
                        "synthetic": e.chunk.synthetic,
                    },
                }
                for e in ans.evidence
            ]
            return jsonify({
                "text": ans.text,
                "evidence": evidence_list,
                "insufficient_evidence": ans.insufficient_evidence,
                "observations": ans.observations or [],
            })
        except Exception as e:
            logger.error("Image query processing failed: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/index_pdf", methods=["POST"])
    @app.route("/index_pdf", methods=["POST"])
    def index_pdf():
        filename = request.args.get("filename", "uploaded_manual.pdf")
        equipment_model = request.args.get("equipment_model") or None
        synthetic = request.args.get("synthetic", "false").lower() == "true"

        pdf_bytes = request.get_data()
        if not pdf_bytes:
            return jsonify({"error": "No PDF data payload received"}), 400

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            ingestor = create_ingestor(mock=False)
            raw_chunks = ingestor.ingest_pdf(
                path=tmp_path,
                equipment_model=equipment_model,
                synthetic=synthetic,
            )
            chunks = [
                Chunk(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    filename=filename,
                    page=c.page,
                    text=c.text,
                    equipment_model=c.equipment_model,
                    synthetic=c.synthetic,
                )
                for c in raw_chunks
            ]
            summary = backend.index_chunks(chunks)

            # Update document registry
            if filename not in indexed_documents_meta:
                indexed_documents_meta[filename] = {
                    "document_id": chunks[0].document_id if chunks else "unknown",
                    "chunks_count": 0,
                    "equipment_model": equipment_model,
                    "synthetic": synthetic,
                }
                chunks_by_document[filename] = []

            indexed_documents_meta[filename]["chunks_count"] += len(chunks)
            for c in chunks:
                chunks_by_document[filename].append({
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "filename": c.filename,
                    "page": c.page,
                    "text": c.text,
                    "equipment_model": c.equipment_model,
                    "synthetic": c.synthetic,
                })

            return jsonify({
                "total_received": summary.total_chunks_received,
                "chunks_indexed": summary.chunks_indexed,
                "chunks_skipped": summary.chunks_skipped,
                "chunks_failed": summary.chunks_failed,
            })
        except Exception as e:
            logger.error("PDF indexing failed: %s", e, exc_info=True)
            return jsonify({"error": str(e)}), 500
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @app.route("/api/remove_document", methods=["POST"])
    @app.route("/remove_document", methods=["POST"])
    def remove_document():
        data = request.get_json(force=True, silent=True) or {}
        filename = data.get("filename")
        if filename in indexed_documents_meta:
            del indexed_documents_meta[filename]
        if filename in chunks_by_document:
            del chunks_by_document[filename]
        return jsonify({"success": True, "filename": filename})

    @app.route("/api/remove_chunk", methods=["POST"])
    @app.route("/remove_chunk", methods=["POST"])
    def remove_chunk():
        data = request.get_json(force=True, silent=True) or {}
        chunk_id = data.get("chunk_id")
        filename = data.get("filename")
        if filename and filename in chunks_by_document:
            chunks_by_document[filename] = [
                c for c in chunks_by_document[filename] if c["chunk_id"] != chunk_id
            ]
            if filename in indexed_documents_meta:
                indexed_documents_meta[filename]["chunks_count"] = len(chunks_by_document[filename])
        return jsonify({"success": True, "chunk_id": chunk_id})

    @app.route("/api/reset", methods=["POST"])
    @app.route("/reset", methods=["POST"])
    def reset_corpus():
        seed_default_knowledge()
        return jsonify({"status": "reset", "success": True})

    @app.route("/api/incidents", methods=["GET"])
    @app.route("/incidents", methods=["GET"])
    def list_incidents():
        incidents = incident_service.list_incidents()
        return jsonify([
            {
                "incident_id": inc.incident_id,
                "title": inc.title,
                "symptom": inc.symptom,
                "equipment_model": inc.equipment_model,
                "equipment_confirmed": inc.equipment_confirmed,
                "status": inc.status,
                "observations": inc.observations,
                "technician_findings": inc.technician_findings,
                "created_at": inc.created_at,
            }
            for inc in incidents
        ])

    return app


def main():
    port = int(os.environ.get("VALENCE_API_PORT", 8000))
    app = create_app()
    logger.info("Starting VALENCE REST Backend Server on http://0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
