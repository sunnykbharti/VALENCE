"""SQLite persistence layer for VALENCE frontend session state.

Ensures that chat history, indexed documents, active incidents, and operator
settings persist across browser refreshes per user session.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from contracts import Answer, Chunk, Evidence

logger = logging.getLogger("valence.persistence")

DB_DIR = Path("data")
DB_PATH = DB_DIR / "user_state.db"


def _get_connection() -> sqlite3.Connection:
    """Returns a thread-safe connection to the user state SQLite database."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes tables for persistent user state."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        # Session state table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                active_incident_id TEXT,
                use_mock INTEGER DEFAULT 1,
                vision_image_name TEXT,
                vision_image_path TEXT,
                vision_mode_active INTEGER DEFAULT 0,
                updated_at TEXT
            )
            """
        )

        # Chat history table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                answer_text TEXT,
                evidence_json TEXT,
                insufficient_evidence INTEGER DEFAULT 0,
                observations_json TEXT,
                image_name TEXT,
                created_at TEXT
            )
            """
        )

        # Indexed documents metadata table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS indexed_documents (
                doc_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                page_count INTEGER DEFAULT 1,
                chunk_count INTEGER DEFAULT 0,
                equipment_model TEXT,
                synthetic INTEGER DEFAULT 0,
                indexed_at TEXT
            )
            """
        )

        # Cached chunks table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cached_chunks (
                chunk_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                page INTEGER NOT NULL,
                text TEXT NOT NULL,
                equipment_model TEXT,
                synthetic INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


# ── Chat History Persistence ──────────────────────────────────────────────────

def save_chat_message(session_id: str, msg: dict[str, Any]) -> None:
    """Appends a single chat message (user or assistant) to SQLite."""
    try:
        init_db()
        role = msg.get("role", "user")
        content = msg.get("content", "")
        image_name = msg.get("image_name")
        created_at = datetime.now(timezone.utc).isoformat()

        answer_text = None
        evidence_json = "[]"
        insufficient = 0
        observations_json = "[]"

        if role == "assistant" and "answer" in msg:
            ans: Answer = msg["answer"]
            answer_text = ans.text
            insufficient = 1 if ans.insufficient_evidence else 0
            observations_json = json.dumps(ans.observations)

            ev_list = []
            for ev in ans.evidence:
                ev_list.append({
                    "source_id": ev.source_id,
                    "chunk": {
                        "chunk_id": ev.chunk.chunk_id,
                        "document_id": ev.chunk.document_id,
                        "filename": ev.chunk.filename,
                        "page": ev.chunk.page,
                        "text": ev.chunk.text,
                        "equipment_model": ev.chunk.equipment_model,
                        "synthetic": ev.chunk.synthetic,
                    }
                })
            evidence_json = json.dumps(ev_list)

        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (
                    session_id, role, content, answer_text, evidence_json,
                    insufficient_evidence, observations_json, image_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, answer_text, evidence_json, insufficient, observations_json, image_name, created_at)
            )
            conn.commit()
    except Exception as e:
        logger.warning("Could not persist chat message to SQLite: %s", e)


def load_chat_history(session_id: str) -> list[dict[str, Any]]:
    """Loads reconstructed chat history for the user session."""
    try:
        init_db()
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content, answer_text, evidence_json, insufficient_evidence,
                       observations_json, image_name
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,)
            )
            rows = cursor.fetchall()

        history = []
        for r in rows:
            role = r["role"]
            image_name = r["image_name"]
            if role == "user":
                history.append({"role": "user", "content": r["content"], "image_name": image_name})
            else:
                # Reconstruct Evidence objects
                ev_data = json.loads(r["evidence_json"] or "[]")
                evidence_objs = []
                for item in ev_data:
                    c = item["chunk"]
                    chunk_obj = Chunk(
                        chunk_id=c["chunk_id"],
                        document_id=c["document_id"],
                        filename=c["filename"],
                        page=c["page"],
                        text=c["text"],
                        equipment_model=c.get("equipment_model"),
                        synthetic=bool(c.get("synthetic", False)),
                    )
                    evidence_objs.append(Evidence(source_id=item["source_id"], chunk=chunk_obj))

                ans = Answer(
                    text=r["answer_text"] or "",
                    evidence=evidence_objs,
                    insufficient_evidence=bool(r["insufficient_evidence"]),
                    observations=json.loads(r["observations_json"] or "[]"),
                )
                history.append({"role": "assistant", "answer": ans, "image_name": image_name})
        return history
    except Exception as e:
        logger.warning("Could not load chat history from SQLite: %s", e)
        return []


def clear_chat_history(session_id: str) -> None:
    """Wipes chat history for the given user session."""
    try:
        init_db()
        with _get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.commit()
    except Exception as e:
        logger.warning("Could not clear chat history in SQLite: %s", e)


# ── Documents & Chunks Persistence ────────────────────────────────────────────

def save_indexed_document(session_id: str, doc_id: str, meta: dict[str, Any], chunks: list[Chunk]) -> None:
    """Persists document metadata and chunks into SQLite."""
    try:
        init_db()
        now = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO indexed_documents (
                    doc_id, session_id, filename, page_count, chunk_count,
                    equipment_model, synthetic, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    session_id,
                    meta.get("filename", "document.pdf"),
                    meta.get("page_count", 1),
                    len(chunks),
                    meta.get("equipment_model"),
                    1 if meta.get("synthetic") else 0,
                    now,
                )
            )

            for c in chunks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cached_chunks (
                        chunk_id, session_id, doc_id, filename, page, text, equipment_model, synthetic
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c.chunk_id,
                        session_id,
                        c.document_id,
                        c.filename,
                        c.page,
                        c.text,
                        c.equipment_model,
                        1 if c.synthetic else 0,
                    )
                )
            conn.commit()
    except Exception as e:
        logger.warning("Could not persist indexed document to SQLite: %s", e)


def load_indexed_documents(session_id: str) -> tuple[dict[str, Any], list[Chunk]]:
    """Loads persistent indexed documents and chunks for this session."""
    try:
        init_db()
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT doc_id, filename, page_count, chunk_count, equipment_model, synthetic FROM indexed_documents WHERE session_id = ?",
                (session_id,)
            )
            doc_rows = cursor.fetchall()

            docs_dict = {}
            for d in doc_rows:
                fname = d["filename"] or d["doc_id"]
                docs_dict[fname] = {
                    "document_id": d["doc_id"],
                    "filename": fname,
                    "page_count": d["page_count"],
                    "chunk_count": d["chunk_count"],
                    "chunks_count": d["chunk_count"],
                    "equipment_model": d["equipment_model"],
                    "synthetic": bool(d["synthetic"]),
                }

            cursor.execute(
                "SELECT chunk_id, doc_id, filename, page, text, equipment_model, synthetic FROM cached_chunks WHERE session_id = ?",
                (session_id,)
            )
            chunk_rows = cursor.fetchall()

            chunks = []
            for c in chunk_rows:
                chunks.append(
                    Chunk(
                        chunk_id=c["chunk_id"],
                        document_id=c["doc_id"],
                        filename=c["filename"],
                        page=c["page"],
                        text=c["text"],
                        equipment_model=c["equipment_model"],
                        synthetic=bool(c["synthetic"]),
                    )
                )
        return docs_dict, chunks
    except Exception as e:
        logger.warning("Could not load indexed documents from SQLite: %s", e)
        return {}, []


def delete_indexed_document(session_id: str, identifier: str) -> None:
    """Removes an indexed document and its cached chunks from SQLite."""
    try:
        init_db()
        with _get_connection() as conn:
            conn.execute(
                "DELETE FROM indexed_documents WHERE session_id = ? AND (doc_id = ? OR filename = ?)",
                (session_id, identifier, identifier),
            )
            conn.execute(
                "DELETE FROM cached_chunks WHERE session_id = ? AND (doc_id = ? OR filename = ?)",
                (session_id, identifier, identifier),
            )
            conn.commit()
            logger.info("Deleted document %s from SQLite session %s", identifier, session_id)
    except Exception as e:
        logger.warning("Could not delete indexed document from SQLite: %s", e)


# ── Session Preferences Persistence ───────────────────────────────────────────

def save_user_session_state(
    session_id: str,
    active_incident_id: Optional[str] = None,
    use_mock: bool = True,
    vision_image_name: Optional[str] = None,
    vision_image_path: Optional[str] = None,
    vision_mode_active: bool = False,
) -> None:
    """Updates user session metadata in SQLite."""
    try:
        init_db()
        now = datetime.now(timezone.utc).isoformat()
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_sessions (
                    session_id, active_incident_id, use_mock, vision_image_name,
                    vision_image_path, vision_mode_active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    active_incident_id,
                    1 if use_mock else 0,
                    vision_image_name,
                    vision_image_path,
                    1 if vision_mode_active else 0,
                    now,
                )
            )
            conn.commit()
    except Exception as e:
        logger.warning("Could not persist session metadata: %s", e)


def load_user_session_state(session_id: str) -> Optional[dict[str, Any]]:
    """Loads user session metadata from SQLite."""
    try:
        init_db()
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT active_incident_id, use_mock, vision_image_name, vision_image_path, vision_mode_active FROM user_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "active_incident_id": row["active_incident_id"],
                    "use_mock": bool(row["use_mock"]),
                    "vision_image_name": row["vision_image_name"],
                    "vision_image_path": row["vision_image_path"],
                    "vision_mode_active": bool(row["vision_mode_active"]),
                }
        return None
    except Exception as e:
        logger.warning("Could not load session metadata: %s", e)
        return None

