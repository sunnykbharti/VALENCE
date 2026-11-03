"""Persistent vector store for VALENCE (Member B).

Implements persistent local indexing with idempotent re-indexing.
Supports local persistent Qdrant with a self-contained local storage fallback
for environments where qdrant-client C-extensions are not yet compiled.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Optional, Sequence

from contracts import Chunk, IndexingSummary

logger = logging.getLogger("valence.vector_store")

_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "let's", "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    "often", "check", "please", "tell",
}


def _content_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if t not in _STOPWORDS and len(t) > 2}


def _bm25_score(
    query_text: str,
    doc_text: str,
    doc_freqs: dict[str, int],
    total_docs: int,
) -> float:
    """Computes BM25 term frequency saturation score with exact phrase matching boost."""
    q_tokens = _content_tokens(query_text)
    if not q_tokens:
        return 0.0

    doc_words = [t for t in re.findall(r"\w+", doc_text.lower()) if t not in _STOPWORDS and len(t) > 2]
    doc_counts = Counter(doc_words)
    score = 0.0

    for t in q_tokens:
        if t in doc_counts:
            tf = doc_counts[t]
            df = doc_freqs.get(t, 1)
            idf = math.log((total_docs + 1) / (df + 1)) + 1.0
            score += (tf / (tf + 1.2)) * idf

    # Exact bigram phrase match bonus (e.g. "solid yellow", "run stop")
    clean_q = re.sub(r"[^\w\s]", " ", query_text.lower())
    q_words = [w for w in clean_q.split() if w not in _STOPWORDS and len(w) > 2]
    doc_lower = doc_text.lower()
    for i in range(len(q_words) - 1):
        phrase = f"{q_words[i]} {q_words[i+1]}"
        if phrase in doc_lower:
            score += 5.0

    return score


def _compute_chunk_hash(chunk: Chunk) -> str:
    """Computes a deterministic hash of chunk content and metadata."""
    payload_str = f"{chunk.text}|{chunk.document_id}|{chunk.page}|{chunk.equipment_model}|{chunk.synthetic}"
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculates cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class PersistentVectorStore:
    """Persistent vector store for local chunk indexing and similarity retrieval.

    Uses persistent disk storage to preserve vectors and metadata across sessions.
    Guarantees idempotence: re-indexing identical chunks is safely skipped.
    """

    def __init__(
        self,
        storage_path: Path | str,
        collection_name: str = "industrial_docs",
        vector_dim: int = 384,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._qdrant_client = None
        self._db_path = self.storage_path / f"{self.collection_name}.db"
        self._init_storage()

    def _init_storage(self) -> None:
        """Initializes storage backend."""
        # Check for qdrant_client
        try:
            import qdrant_client
            from qdrant_client.http import models

            self._qdrant_client = qdrant_client.QdrantClient(path=str(self.storage_path))
            collections = [c.name for c in self._qdrant_client.get_collections().collections]
            if self.collection_name not in collections:
                self._qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_dim,
                        distance=models.Distance.COSINE,
                    ),
                )
            logger.info("Initialized Qdrant local persistent storage at %s", self.storage_path)
        except ImportError:
            logger.info("qdrant-client not installed; using persistent SQLite vector store at %s", self._db_path)
        except Exception as e:
            logger.warning("Qdrant initialization error (%s); falling back to SQLite vector store", e)
            self._qdrant_client = None

        # Always initialize SQLite schema for local persistence / fallback / hash tracking
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT,
                    filename TEXT,
                    page INTEGER,
                    text TEXT,
                    equipment_model TEXT,
                    synthetic INTEGER,
                    payload_hash TEXT,
                    vector_json TEXT
                )
                """
            )
            conn.commit()

    def index_chunks_with_embeddings(
        self,
        chunks: Sequence[Chunk],
        embeddings: Sequence[list[float]],
    ) -> IndexingSummary:
        """Indexes chunks with their corresponding embedding vectors into persistent storage.

        Idempotent: Identical chunks (matching hash) are skipped.
        Updated chunks: Overwritten in-place.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")

        indexed = 0
        skipped = 0
        failed = 0
        errors: list[str] = []

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            for chunk, vec in zip(chunks, embeddings):
                try:
                    payload_hash = _compute_chunk_hash(chunk)

                    # Check existing record
                    cursor.execute(
                        "SELECT payload_hash FROM chunks WHERE chunk_id = ?",
                        (chunk.chunk_id,),
                    )
                    row = cursor.fetchone()

                    if row is not None:
                        existing_hash = row[0]
                        if existing_hash == payload_hash:
                            # Identical chunk -> Idempotent skip
                            skipped += 1
                            continue

                    # Insert or update
                    cursor.execute(
                        """
                        INSERT INTO chunks (
                            chunk_id, document_id, filename, page, text,
                            equipment_model, synthetic, payload_hash, vector_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(chunk_id) DO UPDATE SET
                            document_id = excluded.document_id,
                            filename = excluded.filename,
                            page = excluded.page,
                            text = excluded.text,
                            equipment_model = excluded.equipment_model,
                            synthetic = excluded.synthetic,
                            payload_hash = excluded.payload_hash,
                            vector_json = excluded.vector_json
                        """,
                        (
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.filename,
                            chunk.page,
                            chunk.text,
                            chunk.equipment_model,
                            1 if chunk.synthetic else 0,
                            payload_hash,
                            json.dumps(vec),
                        ),
                    )

                    # If Qdrant client is active, sync point to Qdrant
                    if self._qdrant_client is not None:
                        from qdrant_client.http import models

                        # Deterministic integer/uuid ID for Qdrant point
                        point_id = int(hashlib.md5(chunk.chunk_id.encode()).hexdigest()[:15], 16)
                        self._qdrant_client.upsert(
                            collection_name=self.collection_name,
                            points=[
                                models.PointStruct(
                                    id=point_id,
                                    vector=vec,
                                    payload={
                                        "chunk_id": chunk.chunk_id,
                                        "document_id": chunk.document_id,
                                        "filename": chunk.filename,
                                        "page": chunk.page,
                                        "text": chunk.text,
                                        "equipment_model": chunk.equipment_model,
                                        "synthetic": chunk.synthetic,
                                    },
                                )
                            ],
                        )

                    indexed += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Failed to index chunk {chunk.chunk_id}: {e}")

            conn.commit()

        total = len(chunks)
        return IndexingSummary(
            total_chunks_received=total,
            chunks_indexed=indexed,
            chunks_skipped=skipped,
            chunks_failed=failed,
            collection_name=self.collection_name,
            errors=errors,
        )

    def search_similar(
        self,
        query_vector: list[float],
        top_k: int = 5,
        equipment_model: Optional[str] = None,
        query_text: Optional[str] = None,
    ) -> list[tuple[float, Chunk]]:
        """Searches persistent storage for most similar chunks, respecting equipment_model filter."""
        # Query local SQLite persistent records
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            if equipment_model is not None:
                cursor.execute(
                    "SELECT chunk_id, document_id, filename, page, text, equipment_model, synthetic, vector_json "
                    "FROM chunks WHERE equipment_model = ?",
                    (equipment_model,),
                )
            else:
                cursor.execute(
                    "SELECT chunk_id, document_id, filename, page, text, equipment_model, synthetic, vector_json "
                    "FROM chunks"
                )

            rows = cursor.fetchall()

        if not rows:
            return []

        # Precompute document frequencies if query_text is provided
        doc_freqs: dict[str, int] = {}
        total_docs = len(rows)
        if query_text:
            for r in rows:
                tokens = _content_tokens(r[4])
                for t in tokens:
                    doc_freqs[t] = doc_freqs.get(t, 0) + 1

        scored_chunks: list[tuple[float, Chunk]] = []
        for r in rows:
            chunk = Chunk(
                chunk_id=r[0],
                document_id=r[1],
                filename=r[2],
                page=r[3],
                text=r[4],
                equipment_model=r[5],
                synthetic=bool(r[6]),
            )
            vec = json.loads(r[7])
            cos_score = _cosine_similarity(query_vector, vec)
            if query_text:
                bm_score = _bm25_score(query_text, chunk.text, doc_freqs, total_docs)
                final_score = cos_score + bm_score
            else:
                final_score = cos_score
            scored_chunks.append((final_score, chunk))

        # Sort descending by similarity score, then deterministically by chunk_id
        scored_chunks.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return scored_chunks[:top_k]

    def count(self) -> int:
        """Returns total number of chunks currently indexed in persistent storage."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chunks")
            return int(cursor.fetchone()[0])

    def delete_document_chunks(
        self,
        filename: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> int:
        """Deletes all chunks belonging to a document from persistent vector store and Qdrant.

        Returns:
            Number of chunks removed.
        """
        if not filename and not document_id:
            return 0

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            conditions = []
            params = []
            if filename:
                conditions.append("filename = ?")
                params.append(filename)
            if document_id:
                conditions.append("document_id = ?")
                params.append(document_id)

            where_clause = " OR ".join(conditions)
            cursor.execute(f"SELECT COUNT(*) FROM chunks WHERE {where_clause}", tuple(params))
            deleted_count = int(cursor.fetchone()[0])

            cursor.execute(f"DELETE FROM chunks WHERE {where_clause}", tuple(params))
            conn.commit()

        if self._qdrant_client is not None:
            try:
                from qdrant_client.http import models
                filters = []
                if filename:
                    filters.append(models.FieldCondition(key="filename", match=models.MatchValue(value=filename)))
                if document_id:
                    filters.append(models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)))
                if filters:
                    self._qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.FilterSelector(
                            filter=models.Filter(should=filters)
                        ),
                    )
            except Exception as e:
                logger.warning("Error deleting points from Qdrant: %s", e)

        logger.info("Deleted %d chunks for document filename=%s doc_id=%s", deleted_count, filename, document_id)
        return deleted_count

