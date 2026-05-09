"""OGC API Layer Search Tool.

Queries one or more configured OGC API – Features/Tiles servers for collections
matching a natural-language query, and returns them as GeoDataObject items that
NaLaMap can display on the map.

Server-side ``q=`` full-text search is attempted first (OGC API – Common Part 2
conformance).  When the server returns HTTP 400 or yields no results, the tool
falls back to listing all collections and filtering client-side via substring
match on ``title`` and ``description``.
"""

import hashlib
import logging
import ssl
import uuid
from typing import Any, Dict, List, Optional, Union

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


def _make_client(allow_insecure: bool) -> httpx.Client:
    """Return a synchronous httpx client, optionally skipping TLS verification."""
    if allow_insecure:
        return httpx.Client(verify=False, timeout=_DEFAULT_TIMEOUT)
    return httpx.Client(timeout=_DEFAULT_TIMEOUT)


def _pick_access_url(collection: Dict[str, Any], base_url: str) -> str:
    """Extract the best access URL from a collection's links array.

    Preference order: tiles link → items link → self link → base_url/collection_id.
    """
    links: List[Dict[str, Any]] = collection.get("links", [])
    for rel in ("tiles", "items", "self"):
        for link in links:
            if link.get("rel") == rel and link.get("href"):
                return link["href"]
    col_id = collection.get("id", "")
    return f"{base_url.rstrip('/')}/collections/{col_id}/items" if col_id else base_url


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
            # --- Attempt 1: server-side q= search ---
            try:
                resp = client.get(
                    f"{base}/collections",
                    params={"q": query, "limit": min(max_results, _MAX_RESULTS)},
                )
                if resp.status_code == 400:
                    raise ValueError("Server does not support q= parameter")
                resp.raise_for_status()
                data = resp.json()
                collections = data.get("collections", data if isinstance(data, list) else [])
                results = [_collection_to_geodata(c, backend) for c in collections[:max_results]]
                if results:
                    return results
                # Zero server-side results — fall through to client-side fallback
            except (ValueError, httpx.HTTPStatusError):
                pass

            # --- Attempt 2: client-side substring filter ---
            resp = client.get(f"{base}/collections", params={"limit": _MAX_RESULTS})
            resp.raise_for_status()
            data = resp.json()
            all_collections = data.get("collections", data if isinstance(data, list) else [])
            q = query.lower()
            matched = [
                c
                for c in all_collections
                if q in (c.get("title") or "").lower()
                or q in (c.get("description") or "").lower()
                or q in (c.get("id") or "").lower()
            ]
            return [_collection_to_geodata(c, backend) for c in matched[:max_results]]

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
