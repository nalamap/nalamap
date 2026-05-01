"""
Tool for searching geospatial collections on configured OGC API servers.

Queries each enabled OGC API backend for collections matching a natural-language
query string.  The server-side ``q=`` parameter (see nala-ogcapi-server#18) is
used when available; on HTTP 400 or any 4xx response the tool falls back to
fetching all collections and filtering client-side.

Returned collections are mapped to GeoDataObject items that NaLaMap can display
on the map.  The pattern mirrors services/tools/geoserver/custom_geoserver.py.
"""

from __future__ import annotations

import logging
import ssl
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlencode

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic.fields import FieldInfo
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import OGCAPIBackend, SettingsSnapshot
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)

# Request timeout in seconds for each OGC API backend call
_TIMEOUT = 15.0


def _build_http_client(allow_insecure: bool):
    """Return a configured httpx.AsyncClient for an OGC API backend."""
    import httpx  # lazy import – not available at module load for type checking

    if allow_insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return httpx.AsyncClient(verify=False, timeout=_TIMEOUT)
    return httpx.AsyncClient(timeout=_TIMEOUT)


async def _fetch_collections(
    base_url: str,
    query: str,
    max_results: int,
    allow_insecure: bool,
) -> List[Dict[str, Any]]:
    """
    Fetch matching collections from a single OGC API backend.

    Tries ``GET /collections?q=<query>&limit=<max_results>`` first.
    Falls back to ``GET /collections?limit=<max_results>`` and filters
    client-side if the server responds with a 4xx status.
    """
    import httpx

    collections_url = urljoin(base_url.rstrip("/") + "/", "collections")
    headers = {"Accept": "application/json"}

    async with _build_http_client(allow_insecure) as client:
        # Attempt server-side search
        try:
            params = urlencode({"q": query, "limit": max_results, "f": "json"})
            resp = await client.get(f"{collections_url}?{params}", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("collections", [])
            # Server does not support q= (400) or other 4xx → fallback
            if resp.status_code >= 400:
                logger.debug(
                    "OGC API backend %s returned %s for q= search; "
                    "falling back to client-side filter",
                    base_url,
                    resp.status_code,
                )
        except (httpx.TimeoutException, httpx.ConnectError, ssl.SSLError) as exc:
            logger.warning(
                "OGC API backend %s connection error during q= search: %s", base_url, exc
            )
            raise

        # Fallback: list all collections and filter client-side
        params_fb = urlencode({"limit": max_results, "f": "json"})
        resp_fb = await client.get(f"{collections_url}?{params_fb}", headers=headers)
        resp_fb.raise_for_status()
        all_collections: List[Dict[str, Any]] = resp_fb.json().get("collections", [])

    q_lower = query.lower()
    return [
        c
        for c in all_collections
        if q_lower in (c.get("title") or "").lower()
        or q_lower in (c.get("description") or "").lower()
    ]


def _extract_access_url(collection: Dict[str, Any], base_url: str) -> str:
    """
    Derive the best access URL from the collection's links array.

    Priority: items link → tiles link → self link → constructed /collections/{id} URL.
    """
    links: List[Dict[str, Any]] = collection.get("links") or []
    for rel in ("items", "tiles", "self"):
        for link in links:
            if link.get("rel") == rel and link.get("href"):
                return link["href"]
    col_id = collection.get("id", "")
    return urljoin(base_url.rstrip("/") + "/", f"collections/{col_id}/items")


def _extract_bbox(collection: Dict[str, Any]) -> Optional[str]:
    """Return a WKT POLYGON bounding box from the collection extent, or None."""
    try:
        bbox_list = collection["extent"]["spatial"]["bbox"]
        if bbox_list and len(bbox_list[0]) == 4:
            minx, miny, maxx, maxy = bbox_list[0]
            return (
                f"POLYGON(({minx} {miny}, {maxx} {miny}, {maxx} {maxy}, "
                f"{minx} {maxy}, {minx} {miny}))"
            )
    except (KeyError, TypeError, IndexError):
        pass
    return None


def _collection_to_geodata(
    collection: Dict[str, Any],
    backend: OGCAPIBackend,
) -> GeoDataObject:
    """Map an OGC API collection dict to a GeoDataObject."""
    dataset_type = collection.get("datasetType") or collection.get("dataset_type") or "vector"
    data_type = DataType.LAYER if dataset_type in ("coverage", "raster") else DataType.LAYER

    title = collection.get("title") or collection.get("id") or "Untitled"
    description = collection.get("description") or ""
    access_url = _extract_access_url(collection, backend.url)
    bbox_wkt = _extract_bbox(collection)

    obj = GeoDataObject(
        id=collection.get("id") or title,
        data_source_id=f"ogcapi:{backend.url.rstrip('/')}",
        data_type=data_type,
        data_origin=DataOrigin.TOOL,
        data_source="ogcapi",
        data_link=access_url,
        name=title,
        title=title,
        description=description,
        bounding_box=bbox_wkt,
    )
    return obj


def _search_ogcapi_layers(
    state: GeoDataAgentState,
    tool_call_id: str,
    query: str,
    max_results: int = 20,
) -> Union[Dict[str, Any], Command]:
    """Core (sync-wrapper) implementation used by the @tool below."""
    import asyncio

    # Resolve settings snapshot from agent state
    options = state.get("options")
    snapshot: Optional[SettingsSnapshot] = None
    if isinstance(options, SettingsSnapshot):
        snapshot = options
    elif isinstance(options, dict):
        try:
            snapshot = SettingsSnapshot.model_validate(options, strict=False)
        except Exception:
            snapshot = None

    enabled_backends: List[OGCAPIBackend] = []
    if snapshot:
        enabled_backends = [b for b in (snapshot.ogcapi_backends or []) if b.enabled]

    if not enabled_backends:
        return ToolMessage(
            content="No OGC API backends configured or all are disabled.",
            tool_call_id=tool_call_id,
        )

    async def _gather() -> List[GeoDataObject]:
        results: List[GeoDataObject] = []
        for backend in enabled_backends:
            try:
                collections = await _fetch_collections(
                    base_url=backend.url,
                    query=query,
                    max_results=max_results,
                    allow_insecure=backend.allow_insecure,
                )
                for col in collections:
                    results.append(_collection_to_geodata(col, backend))
            except Exception as exc:
                logger.warning(
                    "OGC API backend '%s' (%s) error during search: %s",
                    backend.name or backend.url,
                    backend.url,
                    exc,
                )
        return results

    try:
        import concurrent.futures

        try:
            asyncio.get_running_loop()
            # We are inside a running event loop (e.g. FastAPI); run in a thread
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _gather())
                all_layers = future.result(timeout=60)
        except RuntimeError:
            # No running event loop – run directly (e.g. pytest, CLI)
            all_layers = asyncio.run(_gather())
    except Exception as exc:
        logger.exception("Unexpected error querying OGC API backends")
        return ToolMessage(
            content=f"Error querying OGC API backends: {exc}",
            tool_call_id=tool_call_id,
        )

    if not all_layers:
        return ToolMessage(
            content=f"No OGC API collections found matching '{query}'.",
            tool_call_id=tool_call_id,
        )

    # Deduplicate by access_url
    seen: set = set()
    unique_layers: List[GeoDataObject] = []
    for layer in all_layers:
        key = layer.data_link or layer.id
        if key not in seen:
            seen.add(key)
            unique_layers.append(layer)

    unique_layers = unique_layers[:max_results]

    tool_message = ToolMessage(
        content=f"Found {len(unique_layers)} OGC API collection(s) matching '{query}'.",
        tool_call_id=tool_call_id,
    )

    current_messages = state.get("messages", [])
    if not isinstance(current_messages, list):
        current_messages = []

    return Command(
        update={
            "messages": current_messages + [tool_message],
            "geodata_results": unique_layers,
            "geodata_last_results": unique_layers,
        }
    )


@tool
def search_ogcapi_layers(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    max_results: int = 20,
) -> Union[Dict[str, Any], Command]:
    """
    Search for geospatial layers on configured OGC API servers.
    Use this when the user asks for layers or datasets from an OGC API endpoint or
    when other data-discovery tools have not found relevant results.
    Searches collection title and description for the given query.
    Results are returned as map layers ready to be displayed.
    query: natural-language search string, e.g. "rivers Germany" or "land cover Africa"
    max_results: maximum number of results per search (default 20)
    """
    # Coerce FieldInfo defaults (LangChain may inject them for unset optional args)
    if isinstance(max_results, FieldInfo):
        max_results = max_results.default or 20

    actual_state = state.get("state", state)
    return _search_ogcapi_layers(
        state=actual_state,
        tool_call_id=tool_call_id,
        query=query,
        max_results=int(max_results),
    )
