"""Utilities for persisting and querying prefetched GeoServer layers.

The vector store is backed by SQLite with the ``sqlite-vec`` extension and is used
to cache layer metadata per user session. The stored vectors are derived from a
light-weight hashing embedding to avoid heavyweight ML dependencies while still
enabling approximate semantic search. Set the ``NALAMAP_GEOSERVER_EMBEDDING_FACTORY``
environment variable to point to a callable that returns a ``langchain``
``Embeddings`` implementation if you need to plug in a different model.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import math
import re
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from langchain_community.vectorstores import SQLiteVec
from langchain_core.embeddings import Embeddings

from core.config import (
    GEOSERVER_EMBEDDING_FACTORY_ENV,
    get_geoserver_embedding_factory_path,
    get_geoserver_vector_db_path,
)
from models.geodata import GeoDataObject

_VECTOR_TABLE = "geoserver_layer_embeddings"


logger = logging.getLogger(__name__)


class _HashingEmbeddings(Embeddings):
    """Deterministic hashing-based embeddings.

    The implementation tokenizes the text into alphanumeric tokens and assigns each
    token to one of ``dimension`` buckets using SHA1. Term frequency weights are
    accumulated per bucket and the resulting vector is L2-normalized. The
    representation is simple yet effective enough for clustering similar layer
    descriptions without the heavy runtime dependency footprint of transformer
    models.
    """

    def __init__(self, dimension: int = 512) -> None:
        self._dimension = dimension
        self._token_pattern = re.compile(r"\w+", re.UNICODE)

    def _vectorize(self, text: str) -> List[float]:
        buckets = [0.0] * self._dimension
        tokens = self._token_pattern.findall(text.lower())
        if not tokens:
            return buckets

        for token in tokens:
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            # Use the first 4 bytes to derive a consistent bucket index
            bucket_idx = int.from_bytes(digest[:4], byteorder="big") % self._dimension
            buckets[bucket_idx] += 1.0

        norm = math.sqrt(sum(weight * weight for weight in buckets))
        if norm > 0.0:
            buckets = [weight / norm for weight in buckets]
        return buckets

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:  # type: ignore[override]
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:  # type: ignore[override]
        return self._vectorize(text)


_vector_store_lock = threading.Lock()
_vector_store: Optional[SQLiteVec] = None
_embedding_model: Optional[Embeddings] = None
_use_fallback_store = False
_fallback_documents: List[dict] = []


def _get_db_path() -> Path:
    return get_geoserver_vector_db_path()


def _load_custom_embeddings() -> Optional[Embeddings]:
    factory_path = get_geoserver_embedding_factory_path()
    if not factory_path:
        return None

    module_name: Optional[str]
    attribute_name: Optional[str]

    if ":" in factory_path:
        module_name, attribute_name = factory_path.split(":", 1)
    else:
        module_name, _, attribute_name = factory_path.rpartition(".")

    if not module_name or not attribute_name:
        logger.warning(
            "Ignoring %s because it must be in 'module:callable' or 'module.callable' format.",
            GEOSERVER_EMBEDDING_FACTORY_ENV,
        )
        return None

    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute_name)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to import custom GeoServer embedding factory '%s': %s",
            factory_path,
            exc,
        )
        return None

    try:
        instance = factory()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Custom GeoServer embedding factory '%s' raised an exception: %s",
            factory_path,
            exc,
        )
        return None

    if not isinstance(instance, Embeddings):
        logger.warning(
            "Custom GeoServer embedding factory '%s' returned %s instead of an "
            "Embeddings instance.",
            factory_path,
            type(instance).__name__,
        )
        return None

    return instance


def _get_embedding_model() -> Embeddings:
    global _embedding_model
    if _embedding_model is None:
        custom = _load_custom_embeddings()
        if custom is not None:
            _embedding_model = custom
        else:
            _embedding_model = _HashingEmbeddings()
    return _embedding_model


def _create_vector_store() -> Optional[SQLiteVec]:
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = SQLiteVec.create_connection(str(db_path))
    except AttributeError:
        import sqlite_vec  # type: ignore

        connection = sqlite_vec.Connection(str(db_path))
    # Ensure we always return rows as dictionaries so json_extract calls work predictably
    connection.row_factory = sqlite3.Row
    try:
        return SQLiteVec(
            table=_VECTOR_TABLE,
            connection=connection,
            embedding=_get_embedding_model(),
        )
    except sqlite3.OperationalError:
        global _use_fallback_store

        _use_fallback_store = True
        return None


def get_vector_store() -> Optional[SQLiteVec]:
    """Return a lazily-instantiated shared vector store instance."""

    global _vector_store
    with _vector_store_lock:
        if _use_fallback_store:
            return None
        if _vector_store is None:
            _vector_store = _create_vector_store()
    return _vector_store


def reset_vector_store_for_tests() -> None:
    """Reset cached handles so tests can operate on isolated temporary databases."""

    global _vector_store
    global _embedding_model
    global _use_fallback_store
    global _fallback_documents
    with _vector_store_lock:
        if _vector_store is not None:
            try:
                _vector_store._connection.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        _vector_store = None
        _embedding_model = None
        _use_fallback_store = False
        _fallback_documents = []


def _layer_to_text(layer: GeoDataObject) -> str:
    """Create a textual representation used for embedding generation."""

    parts: List[str] = []
    for candidate in (
        layer.name,
        layer.title,
        layer.description,
        json.dumps(layer.properties or {}, sort_keys=True),
    ):
        if candidate:
            parts.append(candidate)
    return " \n".join(parts)


def _metadata_payload(
    session_id: str, backend_url: str, backend_name: Optional[str], layer: GeoDataObject
) -> dict:
    payload = layer.model_dump(mode="json")
    return {
        "session_id": session_id,
        "backend_url": backend_url,
        "backend_name": backend_name,
        "layer_id": layer.id,
        "layer_type": layer.layer_type,
        "layer": payload,
    }


def delete_layers(session_id: str, backend_urls: Sequence[str]) -> None:
    """Remove cached layers for the given session/backends."""

    if not backend_urls:
        return
    if _use_fallback_store:
        global _fallback_documents
        normalized = {url.rstrip("/") for url in backend_urls}
        _fallback_documents = [
            doc
            for doc in _fallback_documents
            if not (doc["session_id"] == session_id and doc["backend_url"] in normalized)
        ]
        return

    store = get_vector_store()
    if store is None:
        return
    conn = store._connection  # type: ignore[attr-defined]
    normalized = [url.rstrip("/") for url in backend_urls]
    placeholders = ",".join(["?"] * len(normalized))
    conn.execute(
        f"""
        DELETE FROM {_VECTOR_TABLE}
        WHERE json_extract(metadata, '$.session_id') = ?
          AND json_extract(metadata, '$.backend_url') IN ({placeholders})
        """,
        (session_id, *normalized),
    )
    conn.execute(
        f"DELETE FROM {_VECTOR_TABLE}_vec WHERE rowid NOT IN (SELECT rowid FROM {_VECTOR_TABLE})"
    )
    conn.commit()


def store_layers(
    session_id: str,
    backend_url: str,
    backend_name: Optional[str],
    layers: Sequence[GeoDataObject],
) -> int:
    """Persist a collection of layers for later retrieval.

    Returns the number of stored layers.
    """

    if not layers:
        return 0

    normalized_backend = backend_url.rstrip("/")
    texts = [_layer_to_text(layer) for layer in layers]
    metadatas = [
        _metadata_payload(session_id, normalized_backend, backend_name, layer) for layer in layers
    ]

    if _use_fallback_store:
        embedding_model = _get_embedding_model()
        for text, metadata in zip(texts, metadatas):
            vector = embedding_model.embed_query(text)
            _fallback_documents.append(
                {
                    "session_id": session_id,
                    "backend_url": normalized_backend,
                    "backend_name": backend_name,
                    "layer": metadata["layer"],
                    "metadata": metadata,
                    "text": text,
                    "vector": vector,
                }
            )
        return len(layers)

    store = get_vector_store()
    if store is None:
        return 0
    store.add_texts(texts=texts, metadatas=metadatas)
    return len(layers)


def _rows_to_layers(rows: Iterable[sqlite3.Row]) -> List[GeoDataObject]:
    results: List[GeoDataObject] = []
    for row in rows:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        layer_payload = metadata.get("layer")
        if not layer_payload:
            continue
        layer = GeoDataObject.model_validate(layer_payload)
        results.append(layer)
    return results


def list_layers(
    session_id: str,
    backend_urls: Sequence[str],
    limit: int,
) -> List[GeoDataObject]:
    """Return the most recently stored layers for the given session/backends."""

    normalized = [url.rstrip("/") for url in backend_urls]

    if _use_fallback_store:
        filtered = [
            doc
            for doc in reversed(_fallback_documents)
            if doc["session_id"] == session_id
            and (not normalized or doc["backend_url"] in normalized)
        ]
        return [GeoDataObject.model_validate(doc["layer"]) for doc in filtered[:limit]]

    store = get_vector_store()
    if store is None:
        return []
    conn = store._connection  # type: ignore[attr-defined]

    params: List[object] = [session_id]
    filters = ""
    if normalized:
        placeholders = ",".join(["?"] * len(normalized))
        filters = f" AND json_extract(metadata, '$.backend_url') IN ({placeholders})"
        params.extend(normalized)

    params.append(limit)
    cursor = conn.execute(
        f"""
        SELECT text, metadata
        FROM {_VECTOR_TABLE}
        WHERE json_extract(metadata, '$.session_id') = ?{filters}
        ORDER BY rowid DESC
        LIMIT ?
        """,
        params,
    )
    return _rows_to_layers(cursor.fetchall())


def similarity_search(
    session_id: str,
    backend_urls: Sequence[str],
    query: str,
    limit: int,
) -> List[Tuple[GeoDataObject, float]]:
    """Return layers ordered by vector similarity for the provided query."""

    if _use_fallback_store:
        embedding = _get_embedding_model().embed_query(query)
        normalized = {url.rstrip("/") for url in backend_urls if url}
        scored: List[Tuple[GeoDataObject, float]] = []
        for doc in _fallback_documents:
            if doc["session_id"] != session_id:
                continue
            if normalized and doc["backend_url"] not in normalized:
                continue
            vector = doc["vector"]
            denom = math.sqrt(sum(v * v for v in vector)) * math.sqrt(sum(v * v for v in embedding))
            similarity = 0.0
            if denom:
                similarity = sum(a * b for a, b in zip(vector, embedding)) / denom
            layer = GeoDataObject.model_validate(doc["layer"])
            layer.score = similarity
            scored.append((layer, 1.0 - similarity))
        scored.sort(key=lambda item: item[1])
        return scored[:limit]

    store = get_vector_store()
    if store is None:
        return []
    candidate_multiplier = max(2, len(backend_urls) or 1)
    fetch_k = max(limit * candidate_multiplier, limit)
    documents = store.similarity_search_with_score(query=query, k=fetch_k)

    normalized = {url.rstrip("/") for url in backend_urls if url}
    results: List[Tuple[GeoDataObject, float]] = []
    for doc, distance in documents:
        metadata = doc.metadata or {}
        if metadata.get("session_id") != session_id:
            continue
        backend_url = metadata.get("backend_url")
        if normalized and backend_url not in normalized:
            continue
        payload = metadata.get("layer")
        if not payload:
            continue
        layer = GeoDataObject.model_validate(payload)
        layer.score = max(0.0, 1.0 - float(distance))
        results.append((layer, distance))
        if len(results) >= limit:
            break
    return results


def has_layers(session_id: str, backend_urls: Sequence[str]) -> bool:
    if _use_fallback_store:
        normalized = {url.rstrip("/") for url in backend_urls if url}
        for doc in _fallback_documents:
            if doc["session_id"] != session_id:
                continue
            if normalized and doc["backend_url"] not in normalized:
                continue
            return True
        return False

    store = get_vector_store()
    if store is None:
        return False
    conn = store._connection  # type: ignore[attr-defined]
    normalized = [url.rstrip("/") for url in backend_urls]
    params: List[object] = [session_id]
    filters = ""
    if normalized:
        placeholders = ",".join(["?"] * len(normalized))
        filters = f" AND json_extract(metadata, '$.backend_url') IN ({placeholders})"
        params.extend(normalized)
    cursor = conn.execute(
        f"""
        SELECT 1 FROM {_VECTOR_TABLE}
        WHERE json_extract(metadata, '$.session_id') = ?{filters}
        LIMIT 1
        """,
        params,
    )
    return cursor.fetchone() is not None
