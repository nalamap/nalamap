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

from core.config import (GEOSERVER_EMBEDDING_FACTORY_ENV, OPENAI_API_KEY,
                         OPENAI_EMBEDDING_MODEL, USE_OPENAI_EMBEDDINGS,
                         get_geoserver_embedding_factory_path,
                         get_geoserver_vector_db_path)
from models.geodata import GeoDataObject

_VECTOR_TABLE = "geoserver_layer_embeddings"


logger = logging.getLogger(__name__)


class _HashingEmbeddings(Embeddings):
    """Enhanced hashing-based embeddings with TF-IDF and n-gram support.

    Improvements over simple hashing:
    1. TF-IDF inspired weighting: rare terms get higher weight
    2. Stopword filtering: common words like "the", "a" are ignored
    3. N-gram support: captures character and word patterns
    4. Sublinear TF scaling: log(1+tf) reduces impact of repetition
    5. Higher dimension: 768 instead of 512 for better separation

    This provides better semantic similarity without heavy ML dependencies.
    """

    # Common English stopwords to filter out
    _STOPWORDS = frozenset(
        [
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "that",
            "the",
            "to",
            "was",
            "will",
            "with",
            "the",
            "this",
            "but",
            "they",
            "have",
            "had",
            "what",
            "when",
            "where",
            "who",
            "which",
            "why",
            "how",
        ]
    )

    def __init__(self, dimension: int = 768, use_ngrams: bool = True) -> None:
        self._dimension = dimension
        self._use_ngrams = use_ngrams
        # Match word tokens (alphanumeric sequences)
        self._token_pattern = re.compile(r"\w+", re.UNICODE)
        # Document frequency cache for IDF weighting
        self._doc_freq: dict = {}
        self._total_docs = 0

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract tokens from text with preprocessing."""
        tokens = []
        words = self._token_pattern.findall(text.lower())

        for word in words:
            # Skip stopwords
            if word in self._STOPWORDS:
                continue
            # Skip very short tokens
            if len(word) < 2:
                continue

            tokens.append(word)

            # Add character n-grams for partial matching
            if self._use_ngrams and len(word) >= 4:
                # Add character trigrams from longer words
                for i in range(len(word) - 2):
                    ngram = word[i : i + 3]
                    tokens.append(f"#{ngram}")

        return tokens

    def _get_idf_weight(self, token: str) -> float:
        """Get IDF-like weight for token (higher for rarer terms).

        Uses a simplified IDF approximation without requiring
        a full document corpus.
        """
        if not self._doc_freq:
            # No corpus stats yet, use uniform weight
            return 1.0

        df = self._doc_freq.get(token, 0)
        if df == 0:
            # Rare token, high weight
            return 2.0

        # IDF = log(N / df)
        idf = math.log((self._total_docs + 1) / (df + 1)) + 1.0
        return idf

    def _vectorize(self, text: str) -> List[float]:
        buckets = [0.0] * self._dimension
        tokens = self._extract_tokens(text)

        if not tokens:
            return buckets

        # Count term frequencies
        term_freq = {}
        for token in tokens:
            term_freq[token] = term_freq.get(token, 0) + 1

        # Apply sublinear TF scaling and IDF weighting
        for token, tf in term_freq.items():
            # Sublinear TF: log(1 + tf) instead of raw tf
            tf_weight = math.log(1.0 + tf)

            # IDF-like weight for rare terms
            idf_weight = self._get_idf_weight(token)

            # Combined TF-IDF weight
            weight = tf_weight * idf_weight

            # Hash to bucket
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            bucket_idx = int.from_bytes(digest[:4], byteorder="big") % self._dimension
            buckets[bucket_idx] += weight

        # L2 normalization
        norm = math.sqrt(sum(w * w for w in buckets))
        if norm > 0.0:
            buckets = [w / norm for w in buckets]

        return buckets

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:  # type: ignore[override]
        """Embed multiple documents and update IDF statistics."""
        texts_list = list(texts)

        # Update document frequency statistics
        self._total_docs += len(texts_list)
        for text in texts_list:
            tokens = set(self._extract_tokens(text))
            for token in tokens:
                self._doc_freq[token] = self._doc_freq.get(token, 0) + 1

        return [self._vectorize(text) for text in texts_list]

    def embed_query(self, text: str) -> List[float]:  # type: ignore[override]
        """Embed a query using the current IDF statistics."""
        return self._vectorize(text)


class _OpenAIEmbeddings(Embeddings):
    """OpenAI embeddings wrapper with automatic fallback.

    Uses OpenAI's text-embedding models (e.g., text-embedding-3-small,
    text-embedding-3-large, text-embedding-ada-002) for high-quality semantic
    embeddings. Falls back to _HashingEmbeddings if OpenAI is unavailable
    or encounters errors.

    Configuration via environment variables:
    - OPENAI_API_KEY: Your OpenAI API key
    - OPENAI_EMBEDDING_MODEL: Model name (default: text-embedding-3-small)
    """

    def __init__(self) -> None:
        self._openai_embeddings: Optional[Embeddings] = None
        self._fallback_embeddings = _HashingEmbeddings()
        self._use_fallback = False

        # Try to initialize OpenAI embeddings
        if self._should_use_openai():
            try:
                from langchain_openai import OpenAIEmbeddings

                self._openai_embeddings = OpenAIEmbeddings(
                    model=OPENAI_EMBEDDING_MODEL,
                    openai_api_key=OPENAI_API_KEY,
                )
                logger.info(
                    f"OpenAI embeddings initialized with model: " f"{OPENAI_EMBEDDING_MODEL}"
                )
            except ImportError:
                logger.warning(
                    "langchain_openai not installed. Install with: pip install langchain-openai. "
                    "Falling back to lightweight hashing embeddings."
                )
                self._use_fallback = True
            except Exception as e:
                logger.warning(
                    f"Failed to initialize OpenAI embeddings: {e}. "
                    "Falling back to lightweight hashing embeddings."
                )
                self._use_fallback = True
        else:
            logger.info("OpenAI embeddings not configured. Using lightweight hashing embeddings.")
            self._use_fallback = True

    def _should_use_openai(self) -> bool:
        """Check if OpenAI should be used based on configuration."""
        return bool(USE_OPENAI_EMBEDDINGS and OPENAI_API_KEY)

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:  # type: ignore[override]
        """Embed documents using OpenAI or fallback."""
        texts_list = list(texts)

        if self._use_fallback or not self._openai_embeddings:
            return self._fallback_embeddings.embed_documents(texts_list)

        try:
            return self._openai_embeddings.embed_documents(texts_list)
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}. Falling back to hashing embeddings.")
            self._use_fallback = True
            return self._fallback_embeddings.embed_documents(texts_list)

    def embed_query(self, text: str) -> List[float]:  # type: ignore[override]
        """Embed a query using OpenAI or fallback."""
        if self._use_fallback or not self._openai_embeddings:
            return self._fallback_embeddings.embed_query(text)

        try:
            return self._openai_embeddings.embed_query(text)
        except Exception as e:
            logger.error(f"OpenAI query embedding failed: {e}. Falling back to hashing embeddings.")
            self._use_fallback = True
            return self._fallback_embeddings.embed_query(text)


_vector_store_lock = threading.Lock()
_thread_local = threading.local()
_embedding_model: Optional[Embeddings] = None
_use_fallback_store = False
_fallback_documents: List[dict] = []

# Progress tracking for embedding status
# Key: (session_id, backend_url), Value: {"total": int, "encoded": int, "in_progress": bool}
_embedding_progress: dict[Tuple[str, str], dict] = {}
_progress_lock = threading.Lock()


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
        elif USE_OPENAI_EMBEDDINGS:
            _embedding_model = _OpenAIEmbeddings()
        else:
            _embedding_model = _HashingEmbeddings()
    return _embedding_model


def _create_vector_store() -> Optional[SQLiteVec]:
    global _use_fallback_store

    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Try using SQLiteVec's create_connection first
        try:
            connection = SQLiteVec.create_connection(str(db_path), check_same_thread=False)
        except (AttributeError, TypeError):
            # Fallback: create connection with sqlite-vec pre-loaded
            import sqlite_vec  # type: ignore

            # sqlite_vec.Connection creates a SQLite connection with vec extension pre-loaded
            connection = sqlite_vec.Connection(str(db_path), check_same_thread=False)
            # Enable thread-safe access for SQLite
            connection.isolation_level = None  # autocommit mode

        # Ensure we always return rows as dictionaries so json_extract calls work predictably
        connection.row_factory = sqlite3.Row

        return SQLiteVec(
            table=_VECTOR_TABLE,
            connection=connection,
            embedding=_get_embedding_model(),
        )
    except sqlite3.OperationalError as e:
        logger.warning(f"Failed to initialize SQLite vector store: {e}. Using in-memory fallback.")
        _use_fallback_store = True
        return None
    except Exception as e:
        logger.warning(
            f"Unexpected error initializing SQLite vector store: {e}. Using in-memory fallback."
        )
        _use_fallback_store = True
        return None


def get_vector_store() -> Optional[SQLiteVec]:
    """Return a thread-local vector store instance.

    Each thread gets its own SQLite connection to avoid threading issues.
    The connection is created lazily on first access per thread.
    """

    if _use_fallback_store:
        return None

    # Check if this thread already has a vector store
    if not hasattr(_thread_local, "vector_store"):
        # Create a new vector store for this thread
        _thread_local.vector_store = _create_vector_store()

    return _thread_local.vector_store


def reset_vector_store_for_tests() -> None:
    """Reset cached handles so tests can operate on isolated temporary databases."""

    global _embedding_model
    global _use_fallback_store
    global _fallback_documents

    # Close thread-local vector store if it exists
    if hasattr(_thread_local, "vector_store"):
        if _thread_local.vector_store is not None:
            try:
                _thread_local.vector_store._connection.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        delattr(_thread_local, "vector_store")

    # Reset global state
    _embedding_model = None
    _use_fallback_store = False
    _fallback_documents = []

    # Reset progress tracking
    with _progress_lock:
        _embedding_progress.clear()


def _layer_to_text(layer: GeoDataObject) -> str:
    """Create a textual representation used for embedding generation.

    The text is structured to prioritize important fields:
    1. Title (repeated 3x for higher weight in similarity)
    2. Name (repeated 2x)
    3. Description (full text)
    4. Layer type and data source
    5. Keywords from properties

    This weighting helps match user queries to layer titles/names more effectively.
    """
    parts: List[str] = []

    # Title gets highest weight (repeated 3 times)
    if layer.title:
        parts.extend([layer.title] * 3)

    # Name gets medium weight (repeated 2 times)
    if layer.name:
        parts.extend([layer.name] * 2)

    # Description gets full weight (once)
    if layer.description:
        parts.append(layer.description)

    # Add layer type and data source for context
    if layer.layer_type:
        parts.append(f"type:{layer.layer_type}")
    if layer.data_source:
        parts.append(f"source:{layer.data_source}")

    # Extract keywords from properties if available
    if layer.properties:
        props = layer.properties
        if isinstance(props, dict):
            # Add keywords if present
            if "keywords" in props and isinstance(props["keywords"], list):
                parts.extend(props["keywords"])
            # Add other string values (avoid large nested structures)
            for key, value in props.items():
                if isinstance(value, str) and len(value) < 100:
                    parts.append(value)

    return " ".join(parts)


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

    Returns the number of stored layers. Also tracks progress for embedding status.
    """

    if not layers:
        return 0

    normalized_backend = backend_url.rstrip("/")
    progress_key = (session_id, normalized_backend)

    # Initialize or update progress tracking
    with _progress_lock:
        if progress_key not in _embedding_progress:
            _embedding_progress[progress_key] = {
                "total": len(layers),
                "encoded": 0,
                "in_progress": True,
            }
        else:
            _embedding_progress[progress_key]["total"] = len(layers)
            _embedding_progress[progress_key]["in_progress"] = True

    try:
        texts = [_layer_to_text(layer) for layer in layers]
        metadatas = [
            _metadata_payload(session_id, normalized_backend, backend_name, layer)
            for layer in layers
        ]

        if _use_fallback_store:
            embedding_model = _get_embedding_model()
            for i, (text, metadata) in enumerate(zip(texts, metadatas)):
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
                # Update progress after each embedding
                with _progress_lock:
                    _embedding_progress[progress_key]["encoded"] = i + 1
            return len(layers)

        store = get_vector_store()
        if store is None:
            return 0

        # For SQLite store, add all at once (LangChain handles batching internally)
        store.add_texts(texts=texts, metadatas=metadatas)

        # Mark as complete
        with _progress_lock:
            _embedding_progress[progress_key]["encoded"] = len(layers)

        return len(layers)
    finally:
        # Mark embedding as complete (not in progress)
        with _progress_lock:
            if progress_key in _embedding_progress:
                _embedding_progress[progress_key]["in_progress"] = False


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


def get_embedding_status(session_id: str, backend_urls: Sequence[str]) -> dict[str, dict[str, int]]:
    """Get embedding progress status for given session and backend URLs.

    Returns a dictionary with backend URLs as keys and status info as values.
    Status info includes: total layers, encoded layers, and completion percentage.
    """
    normalized = [url.rstrip("/") for url in backend_urls if url]
    status = {}

    with _progress_lock:
        for backend_url in normalized:
            progress_key = (session_id, backend_url)
            if progress_key in _embedding_progress:
                info = _embedding_progress[progress_key]
                total = info["total"]
                encoded = info["encoded"]
                percentage = int((encoded / total * 100) if total > 0 else 0)

                status[backend_url] = {
                    "total": total,
                    "encoded": encoded,
                    "percentage": percentage,
                    "in_progress": info["in_progress"],
                    "complete": encoded >= total and not info["in_progress"],
                }
            else:
                # No progress data means not started or already cleaned up
                status[backend_url] = {
                    "total": 0,
                    "encoded": 0,
                    "percentage": 0,
                    "in_progress": False,
                    "complete": False,
                }

    return status


def is_fully_encoded(session_id: str, backend_urls: Sequence[str]) -> bool:
    """Check if all backends for a session have been fully encoded.

    Returns True if all backends are complete or have no progress data.
    Returns False if any backend is incomplete or in progress.
    """
    status = get_embedding_status(session_id, backend_urls)

    for backend_url, info in status.items():
        # If there's progress data and it's not complete, return False
        if info["total"] > 0 and not info["complete"]:
            return False

    return True
