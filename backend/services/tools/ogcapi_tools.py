"""OGC API Layer Search Tool.

Queries one or more configured OGC API – Features/Tiles servers for collections
matching a natural-language query, and returns them as GeoDataObject items that
NaLaMap can display on the map.

Server-side ``q=`` full-text search is attempted first (OGC API – Common Part 2
conformance) and compared with the unfiltered listing.  If the server rejected
``q`` (HTTP 400), returned nothing, or returned the same collections as the
unfiltered listing (i.e. it ignored ``q``), the tool filters the listing
client-side via substring match on ``title``, ``description`` and ``id``.

Results are exposed as GeoJSON feature layers (``layer_type="WFS"`` with an
``/items?f=json&limit=...`` URL) because that is what the map renderer supports.
"""

import hashlib
import logging
import ssl
import uuid
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import OGCAPIBackend, SettingsSnapshot
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0  # seconds
_MAX_RESULTS = 50  # upper bound to avoid oversized ToolMessage
_ITEMS_LIMIT = 1000  # max features requested per layer when displaying on the map


def _make_client(allow_insecure: bool) -> httpx.Client:
    """Return a synchronous httpx client, optionally skipping TLS verification."""
    if allow_insecure:
        return httpx.Client(verify=False, timeout=_DEFAULT_TIMEOUT)
    return httpx.Client(timeout=_DEFAULT_TIMEOUT)


def _with_query_params(url: str, params: Dict[str, Any]) -> str:
    """Return ``url`` with ``params`` set (overriding existing keys of the same name)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: str(v) for k, v in params.items()})
    return urlunsplit(parts._replace(query=urlencode(query)))


def _pick_access_url(collection: Dict[str, Any], base_url: str) -> str:
    """Return a GeoJSON ``/items`` URL for the collection, renderable by the map.

    The Leaflet renderer fetches ``data_link`` as GeoJSON, so MVT/tiles links are
    intentionally ignored.  Preference: ``rel="items"`` link whose type is GeoJSON,
    then any ``rel="items"`` link, then ``{base}/collections/{id}/items``.  The URL
    always carries ``f=json`` and ``limit`` so the server answers with GeoJSON.
    """
    links: List[Dict[str, Any]] = collection.get("links", []) or []
    items_links = [lk for lk in links if lk.get("rel") == "items" and lk.get("href")]
    chosen: Optional[str] = None
    for link in items_links:
        if "json" in (link.get("type") or "").lower():
            chosen = link["href"]
            break
    if chosen is None and items_links:
        chosen = items_links[0]["href"]
    if chosen is None:
        col_id = collection.get("id", "")
        if not col_id:
            return base_url
        chosen = f"{base_url.rstrip('/')}/collections/{col_id}/items"
    chosen = urljoin(base_url.rstrip("/") + "/", chosen)
    return _with_query_params(chosen, {"f": "json", "limit": _ITEMS_LIMIT})


def _extract_bbox_wkt(collection: Dict[str, Any]) -> Optional[str]:
    """Return a WKT POLYGON bbox string from the collection's spatial extent, if present."""
    try:
        bbox = collection.get("extent", {}).get("spatial", {}).get("bbox", [[]])[0]
        if bbox and len(bbox) >= 4:
            min_lon, min_lat, max_lon, max_lat = (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )
            return (
                f"POLYGON(("
                f"{max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, "
                f"{max_lon} {min_lat}"
                f"))"
            )
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return None


def _collection_to_geodata(
    collection: Dict[str, Any],
    backend: OGCAPIBackend,
) -> GeoDataObject:
    """Map an OGC API collection dict to a GeoDataObject."""
    col_id = collection.get("id", "")
    access_url = _pick_access_url(collection, backend.url)
    bbox_wkt = _extract_bbox_wkt(collection)
    # Stable deterministic ID so the same collection is deduplicated in agent state.
    stable_id = str(uuid.UUID(hashlib.sha1(f"{backend.name}:{col_id}".encode()).hexdigest()[:32]))
    return GeoDataObject(
        id=stable_id,
        name=col_id,
        title=collection.get("title") or col_id or "Untitled",
        description=collection.get("description") or "",
        data_type=DataType.LAYER,
        data_source="ogcapi",
        data_source_id=backend.name,
        data_origin=DataOrigin.TOOL.value,
        data_link=access_url,
        layer_type="WFS",  # renderer treats this as a GeoJSON feature layer
        bounding_box=bbox_wkt,
        properties={
            "collection_id": col_id,
            "backend_name": backend.name,
            "backend_url": backend.url,
        },
    )


def _search_backend(
    backend: OGCAPIBackend,
    query: str,
    max_results: int,
) -> List[GeoDataObject]:
    """Query a single OGC API backend and return matching GeoDataObjects.

    Tries server-side ``?q=`` search first; falls back to client-side filtering
    if the server returns HTTP 400 or does not support the parameter.
    """
    base = backend.url.rstrip("/")

    try:
        with _make_client(backend.allow_insecure) as client:

            def _list(params: Dict[str, Any]) -> List[Dict[str, Any]]:
                resp = client.get(f"{base}/collections", params=params)
                resp.raise_for_status()
                data = resp.json()
                return data.get("collections", data if isinstance(data, list) else [])

            def _local_matches(cols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                q = query.lower()
                return [
                    c
                    for c in cols
                    if q in (c.get("title") or "").lower()
                    or q in (c.get("description") or "").lower()
                    or q in (c.get("id") or "").lower()
                ]

            # Same limit for both requests so their results are comparable.
            base_params: Dict[str, Any] = {"limit": _MAX_RESULTS}

            # --- Attempt 1: server-side q= search ---
            searched: List[Dict[str, Any]] = []
            try:
                searched = _list({**base_params, "q": query})
            except (ValueError, httpx.HTTPStatusError):
                searched = []  # e.g. HTTP 400: q= unsupported

            all_collections = _list(base_params)

            # A server that does not implement q= typically ignores it and returns its
            # normal listing with HTTP 200.  We only trust the server-side result when
            # it demonstrably narrowed the listing, i.e. the set of collection ids
            # differs from the unfiltered listing.  Otherwise (identical, empty or
            # failed) the local title/description/id predicate is applied.
            searched_ids = {c.get("id") for c in searched}
            all_ids = {c.get("id") for c in all_collections}
            if searched and searched_ids != all_ids:
                chosen = searched
            else:
                chosen = _local_matches(all_collections)
            return [_collection_to_geodata(c, backend) for c in chosen[:max_results]]

    except httpx.ConnectError as exc:
        logger.warning("OGC API backend %s: connection error — %s", backend.name, exc)
        raise
    except ssl.SSLError as exc:
        logger.warning("OGC API backend %s: SSL error — %s", backend.name, exc)
        raise
    except httpx.TimeoutException as exc:
        logger.warning("OGC API backend %s: timeout — %s", backend.name, exc)
        raise
    except Exception as exc:
        logger.warning("OGC API backend %s: unexpected error — %s", backend.name, exc)
        raise


@tool
def search_ogcapi_layers(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    max_results: int = 20,
) -> Union[Dict[str, Any], Command, ToolMessage]:
    """Search for geospatial layers on configured OGC API servers.

    Use this when the user asks for layers or datasets from an OGC API endpoint.
    Searches collection title, description, and id for the given query.

    query: natural-language search string, e.g. "rivers Germany"
    max_results: maximum number of results to return per backend (default 20)
    """
    return _search_ogcapi_layers_impl(
        state=state, tool_call_id=tool_call_id, query=query, max_results=max_results
    )


def _search_ogcapi_layers_impl(
    state: GeoDataAgentState,
    tool_call_id: str,
    query: str,
    max_results: int = 20,
) -> Union[Dict[str, Any], Command, ToolMessage]:
    settings = state.get("options")
    snapshot: Optional[SettingsSnapshot] = None
    if isinstance(settings, SettingsSnapshot):
        snapshot = settings
    elif isinstance(settings, dict):
        try:
            snapshot = SettingsSnapshot.model_validate(settings, strict=False)
        except Exception:
            snapshot = None

    if not snapshot or not snapshot.ogcapi_backends:
        return ToolMessage(
            content="No OGC API backends configured. Add at least one backend in the settings.",
            tool_call_id=tool_call_id,
        )

    enabled_backends = [b for b in snapshot.ogcapi_backends if b.enabled]
    if not enabled_backends:
        return ToolMessage(
            content="All configured OGC API backends are disabled.",
            tool_call_id=tool_call_id,
        )

    all_results: List[GeoDataObject] = []
    errors: List[str] = []

    for backend in enabled_backends:
        try:
            results = _search_backend(backend, query, max_results)
            all_results.extend(results)
        except Exception as exc:
            errors.append(f"{backend.name}: {exc}")

    if not all_results and errors:
        return ToolMessage(
            content=(
                "Could not reach any OGC API backend. Errors:\n"
                + "\n".join(f"- {e}" for e in errors)
            ),
            tool_call_id=tool_call_id,
        )

    if not all_results:
        msg = f'No collections found matching "{query}"'
        if errors:
            msg += f" (some backends unreachable: {', '.join(errors)})"
        return ToolMessage(content=msg + ".", tool_call_id=tool_call_id)

    summary_lines = [f'Found {len(all_results)} collection(s) matching "{query}":']
    for obj in all_results:
        summary_lines.append(f"- **{obj.title}**: {obj.description or '(no description)'}")
    if errors:
        summary_lines.append(f"\n⚠️ Could not reach: {', '.join(errors)}")

    return Command(
        update={
            "geodata_last_results": all_results,
            "messages": [
                ToolMessage(
                    content="\n".join(summary_lines),
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
