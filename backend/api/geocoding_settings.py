"""API endpoints for OSM tag embedding management.

Allows admins to trigger population of the tag vector store and poll
its status.  Follows the same background-task pattern as the GeoServer
preload in api/settings.py.
"""

import logging
import threading
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings/geocoding", tags=["settings"])

# ---------------------------------------------------------------------------
# In-memory status tracker (module-level, shared across requests)
# ---------------------------------------------------------------------------

_status_lock = threading.Lock()
_populate_status: dict = {
    "state": "idle",  # idle | waiting | processing | completed | error
    "total": 0,
    "encoded": 0,
    "error_message": None,
}


def _update_status(**kwargs) -> None:
    with _status_lock:
        _populate_status.update(kwargs)


def get_tag_store_status() -> dict:
    """Return the current tag vector store status (store + in-memory tracker merged)."""
    from services.tools.geocoding.tag_vector_store import TagVectorStore

    store = TagVectorStore()
    store_status = store.get_status()  # {count, last_updated, state}

    with _status_lock:
        tracker = dict(_populate_status)

    # If the background task has finished or never ran, use the persistent store state.
    if tracker["state"] in ("idle", "completed"):
        state = "populated" if store_status["state"] == "populated" else "empty"
    else:
        state = tracker["state"]

    return {
        "state": state,
        "total": tracker["total"],
        "encoded": tracker["encoded"],
        "tag_count": store_status["count"],
        "last_updated": store_status["last_updated"],
        "error_message": tracker["error_message"],
    }


def submit_populate_task(
    fetch_descriptions: bool,
    min_count: int,
    force_refresh: bool,
) -> str:
    """Submit the background tag population task. Returns task_id."""
    from services.background_tasks import TaskPriority, get_task_manager

    task_id = "populate_osm_tags"
    task_manager = get_task_manager()
    task_manager.submit_task(
        _run_populate,
        fetch_descriptions,
        min_count,
        force_refresh,
        priority=TaskPriority.LOW,
        task_id=task_id,
    )
    return task_id


def _run_populate(fetch_descriptions: bool, min_count: int, force_refresh: bool) -> None:
    """Background worker: fetch tags from TagInfo and store embeddings."""
    from services.tools.geocoding.tag_vector_store import TagVectorStore
    from services.tools.geocoding.taginfo_fetcher import fetch_popular_tags

    store = TagVectorStore()

    try:
        _update_status(state="processing", total=0, encoded=0, error_message=None)

        if force_refresh:
            store.clear()
            logger.info("Tag vector store cleared for refresh")

        def _progress(fetched: int, total: int) -> None:
            _update_status(total=total, encoded=fetched)

        logger.info(
            "Starting TagInfo fetch (fetch_descriptions=%s, min_count=%d)",
            fetch_descriptions,
            min_count,
        )
        tags = fetch_popular_tags(
            min_count=min_count,
            fetch_descriptions=fetch_descriptions,
            progress_callback=_progress if fetch_descriptions else None,
        )
        logger.info("Fetched %d tags from TagInfo", len(tags))

        _update_status(state="processing", total=len(tags), encoded=0)

        tag_dicts = [
            {
                "key": t.key,
                "value": t.value,
                "description": t.description,
                "count_all": t.count_all,
                "count_nodes": t.count_nodes,
                "count_ways": t.count_ways,
                "count_relations": t.count_relations,
            }
            for t in tags
        ]
        stored = store.store_tags(tag_dicts)

        _update_status(state="completed", total=stored, encoded=stored, error_message=None)
        logger.info("Tag vector store populated with %d tags", stored)

    except Exception as exc:
        logger.exception("Tag embedding population failed: %s", exc)
        _update_status(state="error", error_message=str(exc))


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PopulateTagsRequest(BaseModel):
    scope: str = "popular"  # "popular" (wiki-documented) or "extended"
    force_refresh: bool = False
    fetch_descriptions: bool = True
    min_count: int = 100


class PopulateTagsResponse(BaseModel):
    task_id: Optional[str] = None
    state: str  # "waiting" | "already_populated"
    message: str = ""


class TagEmbeddingStatusResponse(BaseModel):
    state: str  # "empty" | "waiting" | "processing" | "completed" | "error" | "populated"
    total: int = 0
    encoded: int = 0
    percentage: float = 0.0
    tag_count: int = 0
    last_updated: Optional[str] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/populate-tags", response_model=PopulateTagsResponse)
async def populate_tag_embeddings(request: PopulateTagsRequest) -> PopulateTagsResponse:
    """Trigger population of the OSM tag embedding store.

    Fetches tags from TagInfo API, generates embeddings, and stores them
    in the local SQLite vector DB. Runs as a background task.

    If the store is already populated and force_refresh is False,
    returns immediately with state='already_populated'.
    """
    status = get_tag_store_status()

    if status["tag_count"] > 0 and not request.force_refresh:
        return PopulateTagsResponse(
            task_id=None,
            state="already_populated",
            message=f"Tag store already contains {status['tag_count']} tags. "
            "Use force_refresh=true to rebuild.",
        )

    _update_status(state="waiting", total=0, encoded=0, error_message=None)
    task_id = submit_populate_task(
        fetch_descriptions=request.fetch_descriptions,
        min_count=request.min_count,
        force_refresh=request.force_refresh,
    )

    return PopulateTagsResponse(
        task_id=task_id,
        state="waiting",
        message="Tag embedding population started in the background.",
    )


@router.get("/embedding-status", response_model=TagEmbeddingStatusResponse)
async def get_tag_embedding_status() -> TagEmbeddingStatusResponse:
    """Get the current status of the tag embedding store.

    Used by the frontend settings page for polling during population.
    """
    status = get_tag_store_status()

    total = status["total"]
    encoded = status["encoded"]
    percentage = round((encoded / total * 100) if total > 0 else 0.0, 1)

    return TagEmbeddingStatusResponse(
        state=status["state"],
        total=total,
        encoded=encoded,
        percentage=percentage,
        tag_count=status["tag_count"],
        last_updated=status["last_updated"],
        error_message=status["error_message"],
    )
