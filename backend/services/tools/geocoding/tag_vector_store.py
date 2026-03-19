"""Persistent SQLite + sqlite-vec vector store for OSM tag embeddings.

Stores ~14K OSM tags with their embeddings for semantic similarity search.
Follows the same patterns as geoserver/vector_store.py: thread-local
connections, autocommit mode, pluggable embedding provider.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import struct
import threading
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

OSM_TAG_VECTOR_DB_PATH = os.getenv("NALAMAP_OSM_TAG_VECTOR_DB", "data/osm_tag_vectors.db")
OSM_TAG_VECTOR_TABLE = "osm_tag_embeddings"


class TagVectorStore:
    """SQLite + sqlite-vec vector store for OSM tag embeddings.

    Follows the same pattern as geoserver/vector_store.py:
    - Thread-local sqlite3 connections
    - Autocommit isolation level
    - Pluggable embedding provider (hashing/OpenAI/Azure)
    - Lazy initialization
    """

    def __init__(self, db_path: str = OSM_TAG_VECTOR_DB_PATH) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._embeddings = None  # lazy init
        self._embedding_dim: int | None = None  # detected from model

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local SQLite connection (same pattern as GeoServer)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = self._open_connection()
        return self._local.conn

    def _open_connection(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            # Try SQLiteVec helper first (handles extension loading portably)
            from langchain_community.vectorstores import SQLiteVec

            conn = SQLiteVec.create_connection(str(self._db_path))
        except Exception:
            # Fallback: load sqlite-vec manually
            import sqlite_vec  # type: ignore

            conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

        conn.isolation_level = None  # autocommit
        conn.row_factory = sqlite3.Row
        self._ensure_table(conn)
        return conn

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _get_existing_vec_dim(self, conn: sqlite3.Connection) -> int | None:
        """Return the dimension of the existing vec0 table, or None if it doesn't exist."""
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name=?",
                (f"{OSM_TAG_VECTOR_TABLE}_vec",),
            ).fetchone()
            if row is None:
                return None
            # Parse "float[768]" from the CREATE VIRTUAL TABLE statement
            match = re.search(r"float\[(\d+)\]", row["sql"])
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def _get_embedding_dim(self) -> int:
        """Detect embedding dimension from the configured model."""
        if self._embedding_dim is None:
            embeddings = self._get_embeddings()
            probe = embeddings.embed_query("dimension probe")
            self._embedding_dim = len(probe)
            logger.info("Detected embedding dimension: %d", self._embedding_dim)
        return self._embedding_dim

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        """Create the tag embeddings table and vec0 virtual table if they don't exist."""
        dim = self._get_embedding_dim()

        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {OSM_TAG_VECTOR_TABLE} (
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                tag TEXT NOT NULL,
                description TEXT DEFAULT '',
                count_all INTEGER DEFAULT 0,
                count_nodes INTEGER DEFAULT 0,
                count_ways INTEGER DEFAULT 0,
                count_relations INTEGER DEFAULT 0,
                text TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """)

        # Check if existing vec table has a different dimension
        existing_dim = self._get_existing_vec_dim(conn)
        if existing_dim is not None and existing_dim != dim:
            logger.warning(
                "Embedding dimension changed (%d -> %d). "
                "Dropping existing vector table and clearing tag data.",
                existing_dim,
                dim,
            )
            conn.execute(f"DROP TABLE IF EXISTS {OSM_TAG_VECTOR_TABLE}_vec")
            conn.execute(f"DELETE FROM {OSM_TAG_VECTOR_TABLE}")

        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {OSM_TAG_VECTOR_TABLE}_vec
            USING vec0(embedding float[{dim}])
            """)

    # ------------------------------------------------------------------
    # Embedding provider
    # ------------------------------------------------------------------

    def _get_embeddings(self):
        """Get the embedding provider (reuses GeoServer factory)."""
        if self._embeddings is None:
            from services.tools.geoserver.vector_store import _get_embedding_model

            self._embeddings = _get_embedding_model()
        return self._embeddings

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def store_tags(self, tags: List[Dict]) -> int:
        """Store tags with their embeddings. Returns count stored.

        Args:
            tags: List of dicts with keys: key, value, description,
                  count_all, count_nodes, count_ways, count_relations.
        """
        if not tags:
            return 0

        texts = [_tag_to_text(t) for t in tags]
        embeddings = self._get_embeddings().embed_documents(texts)

        conn = self._get_connection()
        stored = 0
        for tag, text, emb in zip(tags, texts, embeddings):
            key = tag.get("key", "")
            value = tag.get("value", "")
            tag_str = f"{key}={value}"

            cursor = conn.execute(
                f"""
                INSERT INTO {OSM_TAG_VECTOR_TABLE}
                    (key, value, tag, description, count_all,
                     count_nodes, count_ways, count_relations, text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    value,
                    tag_str,
                    tag.get("description", ""),
                    tag.get("count_all", 0),
                    tag.get("count_nodes", 0),
                    tag.get("count_ways", 0),
                    tag.get("count_relations", 0),
                    text,
                ),
            )
            rowid = cursor.lastrowid
            emb_blob = _pack_vector(emb)
            conn.execute(
                f"INSERT INTO {OSM_TAG_VECTOR_TABLE}_vec(rowid, embedding) VALUES (?, ?)",
                (rowid, emb_blob),
            )
            stored += 1

        return stored

    def clear(self) -> None:
        """Clear all tags (for rebuild)."""
        conn = self._get_connection()
        conn.execute(f"DELETE FROM {OSM_TAG_VECTOR_TABLE}")
        conn.execute(f"DELETE FROM {OSM_TAG_VECTOR_TABLE}_vec")

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def similarity_search(self, query: str, k: int = 20, min_count: int = 100) -> List[Dict]:
        """Search for tags similar to the query text.

        Returns list of dicts: {key, value, tag, description, count_all, score}
        Filtered by min_count to exclude rarely-used tags.
        """
        emb = self._get_embeddings().embed_query(query)
        emb_blob = _pack_vector(emb)

        # Fetch more candidates from vec to allow for min_count post-filtering.
        # We request k * 10 candidates so that after the count filter there are
        # still (likely) k results.  Cap at a reasonable upper bound.
        fetch_k = min(k * 10, 5000)

        conn = self._get_connection()
        # sqlite-vec KNN: ORDER BY distance is implicit for MATCH queries
        rows = conn.execute(
            f"""
            SELECT m.key, m.value, m.tag, m.description,
                   m.count_all, m.count_nodes, m.count_ways, m.count_relations,
                   v.distance
            FROM {OSM_TAG_VECTOR_TABLE}_vec v
            JOIN {OSM_TAG_VECTOR_TABLE} m ON v.rowid = m.rowid
            WHERE v.embedding MATCH ? AND k = ?
              AND m.count_all >= ?
            ORDER BY v.distance
            LIMIT ?
            """,
            (emb_blob, fetch_k, min_count, k),
        ).fetchall()

        results = []
        for row in rows:
            distance = row["distance"]
            score = max(0.0, 1.0 - float(distance))
            results.append(
                {
                    "key": row["key"],
                    "value": row["value"],
                    "tag": row["tag"],
                    "description": row["description"],
                    "count_all": row["count_all"],
                    "count_nodes": row["count_nodes"],
                    "count_ways": row["count_ways"],
                    "count_relations": row["count_relations"],
                    "score": score,
                }
            )
        return results

    def get_all_tag_labels(self) -> List[str]:
        """Return all tag strings ('key=value') for fuzzy matching."""
        conn = self._get_connection()
        rows = conn.execute(f"SELECT tag FROM {OSM_TAG_VECTOR_TABLE}").fetchall()
        return [row["tag"] for row in rows]

    def get_status(self) -> Dict:
        """Return store status: {count, last_updated, state}.

        state: 'empty' | 'populated'
        """
        conn = self._get_connection()
        row = conn.execute(
            f"SELECT COUNT(*) as cnt, MAX(updated_at) as last_updated FROM {OSM_TAG_VECTOR_TABLE}"
        ).fetchone()
        count = row["cnt"] if row else 0
        last_updated = row["last_updated"] if row else None
        return {
            "count": count,
            "last_updated": last_updated,
            "state": "populated" if count > 0 else "empty",
        }

    def is_initialized(self) -> bool:
        """Check if the store has any tags."""
        return self.get_status()["state"] == "populated"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _tag_to_text(tag: Dict) -> str:
    """Build the composite text used for embedding generation."""
    key = tag.get("key", "")
    value = tag.get("value", "")
    description = tag.get("description", "")
    count = tag.get("count_all", 0)

    if description:
        return f"{key}={value}: {description}. Used on {count} objects."
    return f"{key}={value}"


def _pack_vector(vec: List[float]) -> bytes:
    """Serialize a float list as little-endian float32 bytes for sqlite-vec."""
    return struct.pack(f"{len(vec)}f", *vec)
