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
import ipaddress
import json
import logging
import re
import socket
import ssl
import uuid
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpcore
import httpx
from fastapi import HTTPException
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import Field
from typing_extensions import Annotated

from api.proxy import validate_url as _proxy_validate_url
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import OGCAPIBackend, SettingsSnapshot
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0  # seconds
_MAX_RESULTS = 50  # upper bound to avoid oversized ToolMessage
_ITEMS_LIMIT = 1000  # max features requested per layer when displaying on the map


_MAX_PAGES = 10  # cap on followed pagination links per backend
_MAX_REDIRECTS = 3
_MAX_BODY_BYTES = 5 * 1024 * 1024  # cap on any single response body


class UnsafeURLError(Exception):
    """Raised when a configured/followed URL targets a disallowed destination."""


def _resolve_host(host: str) -> List[str]:
    """Resolve ``host`` to all of its IP addresses (patched in tests)."""
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


def _assert_public(host: str, addresses: List[str]) -> None:
    """Raise UnsafeURLError unless every address is a public unicast address."""
    if not addresses:
        raise UnsafeURLError(f"Host {host!r} did not resolve")
    for addr in addresses:
        ip = ipaddress.ip_address(addr.split("%")[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURLError(f"Host {host!r} resolves to a non-public address ({ip})")


def _resolve_public(host: str) -> List[str]:
    """Resolve ``host`` (or accept an IP literal) and require only public addresses."""
    try:
        addresses = [str(ipaddress.ip_address(host.strip("[]")))]
    except ValueError:
        try:
            addresses = _resolve_host(host)
        except OSError as exc:
            raise UnsafeURLError(f"Cannot resolve host {host!r}: {exc}") from exc
    _assert_public(host, addresses)
    return addresses


def _validate_outbound_url(url: str) -> None:
    """Early SSRF check (scheme, host, resolved addresses) with a clear error.

    Reuses the proxy's scheme/host validation, then rejects hosts resolving to
    private, loopback, link-local (incl. cloud metadata), multicast or reserved
    addresses.  This pre-check is advisory: the authoritative enforcement happens at
    connect time in :class:`_PinnedNetworkBackend`, which closes the DNS-rebinding
    window between validation and connection.
    """
    try:
        _proxy_validate_url(url)
    except HTTPException as exc:
        raise UnsafeURLError(str(exc.detail)) from exc
    _resolve_public(urlsplit(url).hostname or "")


class _PinnedNetworkBackend(httpcore.SyncBackend):
    """httpcore backend that resolves, validates and connects to the *same* IP.

    TLS SNI / certificate verification and the Host header still use the original
    hostname because httpcore derives them from the request origin, not from the
    address passed to ``connect_tcp``.
    """

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = _resolve_public(host)
        last_exc: Optional[Exception] = None
        for addr in addresses:
            try:
                return super().connect_tcp(
                    addr,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore.ConnectError as exc:
                last_exc = exc
        raise last_exc or UnsafeURLError(f"Host {host!r} did not resolve")


def _safe_get(
    client: httpx.Client, url: str, params: Optional[Dict[str, Any]] = None
) -> Tuple[httpx.Response, bytes]:
    """GET ``url`` with SSRF validation per hop and a bounded, streamed body.

    Redirects are followed manually (each hop re-validated).  The body is read in
    chunks and rejected once it exceeds ``_MAX_BODY_BYTES`` (also checked up front
    against Content-Length).  HTTP error statuses raise ``httpx.HTTPStatusError``.
    """
    for _ in range(_MAX_REDIRECTS + 1):
        _validate_outbound_url(url)
        # Merge params into the URL ourselves: httpx's ``params=`` would replace any
        # query string already present (e.g. an api_key on the configured base URL).
        request_url = _with_query_params(url, params) if params else url
        with client.stream("GET", request_url, follow_redirects=False) as resp:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location")
                if location:
                    url = urljoin(url, location)
                    params = None
                    continue
            resp.raise_for_status()
            declared = resp.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > _MAX_BODY_BYTES:
                raise ValueError(f"Response too large ({declared} bytes)")
            body = bytearray()
            for chunk in resp.iter_bytes():
                body.extend(chunk)
                if len(body) > _MAX_BODY_BYTES:
                    raise ValueError(f"Response exceeds {_MAX_BODY_BYTES} bytes")
            return resp, bytes(body)
    raise UnsafeURLError("Too many redirects")


_URL_RE = re.compile(r"https?://[^\s'\"<>)]+")


def _redact_urls(text: str) -> str:
    """Strip userinfo, query strings and fragments from any URL inside ``text``."""

    def _clean(match: "re.Match[str]") -> str:
        parts = urlsplit(match.group(0))
        host = parts.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parts.scheme, host, parts.path, "", ""))

    return _URL_RE.sub(_clean, text)


def _describe_error(exc: BaseException) -> str:
    """Short, credential-free description of a request failure."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "request timed out"
    if isinstance(exc, (ssl.SSLError, httpx.ConnectError)):
        return "connection failed"
    if isinstance(exc, (UnsafeURLError, ValueError)):
        return _redact_urls(str(exc))
    return type(exc).__name__


def _normalize_backend_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, "")
    )


def _backend_key(backend: OGCAPIBackend) -> str:
    """Stable identifier of an endpoint (hash of its normalized URL), independent of name."""
    return hashlib.sha1(_normalize_backend_url(backend.url).encode()).hexdigest()[:16]


def _make_client(allow_insecure: bool) -> httpx.Client:
    """Return a synchronous httpx client, optionally skipping TLS verification."""
    transport = httpx.HTTPTransport(verify=not allow_insecure)
    # Pin connections to validated public IPs (DNS-rebinding safe).  Passing an explicit
    # transport also disables environment proxies, which would bypass the guard.
    transport._pool._network_backend = _PinnedNetworkBackend()
    return httpx.Client(transport=transport, timeout=_DEFAULT_TIMEOUT)


def _join_path(base_url: str, *segments: str) -> str:
    """Append path segments to ``base_url`` while preserving its query string."""
    parts = urlsplit(base_url.strip())
    path = "/".join([parts.path.rstrip("/"), *[seg.strip("/") for seg in segments]])
    return urlunsplit(parts._replace(path=path, fragment=""))


def _with_query_params(url: str, params: Dict[str, Any]) -> str:
    """Return ``url`` with ``params`` set (overriding existing keys of the same name)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({k: str(v) for k, v in params.items()})
    return urlunsplit(parts._replace(query=urlencode(query)))


def _resolve_link(base_url: str, href: str) -> str:
    """Resolve ``href`` against the parsed base URL (path joined, query preserved).

    Plain ``urljoin`` against the raw base would drop the base path (when it has no
    trailing slash) and any query credentials.  Absolute hrefs are returned as-is;
    relative ones are resolved under the base path and, being same-origin, inherit
    the base query parameters (e.g. an api key) unless they set their own.
    """
    if urlsplit(href).scheme:
        return href
    base = urlsplit(base_url.strip())
    anchor = urlunsplit(base._replace(path=base.path.rstrip("/") + "/", query="", fragment=""))
    resolved = urljoin(anchor, href)
    base_query = dict(parse_qsl(base.query, keep_blank_values=True))
    return _merge_query(resolved, base_query) if base_query else resolved


def _merge_query(url: str, defaults: Dict[str, str]) -> str:
    """Add ``defaults`` to ``url``'s query without overriding keys it already has."""
    parts = urlsplit(url)
    query = dict(defaults)
    query.update(dict(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def _is_public_http_url(url: str) -> bool:
    """True if ``url`` is http(s) and resolves only to public addresses."""
    try:
        _validate_outbound_url(url)
    except UnsafeURLError:
        return False
    return True


def _pick_access_url(collection: Dict[str, Any], base_url: str) -> str:
    """Return a GeoJSON ``/items`` URL for the collection, renderable by the map.

    The Leaflet renderer fetches ``data_link`` as GeoJSON, so MVT/tiles links are
    intentionally ignored.  Preference: ``rel="items"`` link whose type is GeoJSON,
    then any ``rel="items"`` link, then ``{base}/collections/{id}/items``.  The URL
    always carries ``f=json`` and ``limit`` so the server answers with GeoJSON.

    Catalog-provided links are untrusted (the browser fetches the result): links
    that are not http(s) or that point at private/local/link-local hosts are dropped.
    """
    links: List[Dict[str, Any]] = collection.get("links", []) or []
    items_links = [lk for lk in links if lk.get("rel") == "items" and lk.get("href")]
    items_links.sort(key=lambda lk: "json" not in (lk.get("type") or "").lower())
    for link in items_links:
        candidate = _resolve_link(base_url, str(link["href"]))
        if _is_public_http_url(candidate):
            return _with_query_params(candidate, {"f": "json", "limit": _ITEMS_LIMIT})
        logger.warning("OGC API: dropping unsafe items link from catalog")
    col_id = collection.get("id", "")
    if not col_id:
        return base_url
    constructed = _join_path(base_url, "collections", col_id, "items")
    return _with_query_params(constructed, {"f": "json", "limit": _ITEMS_LIMIT})


_CRS84_EQUIVALENTS = {
    "http://www.opengis.net/def/crs/ogc/1.3/crs84",
    "http://www.opengis.net/def/crs/ogc/0/crs84h",
    "http://www.opengis.net/def/crs/epsg/0/4326",
    "urn:ogc:def:crs:ogc:1.3:crs84",
    "ogc:crs84",
    "epsg:4326",
}


def _bbox_to_crs84(
    bbox_xy: Tuple[float, float, float, float], crs: Optional[str]
) -> Optional[Tuple[float, float, float, float]]:
    """Return (minx, miny, maxx, maxy) in CRS84, or None if it cannot be determined."""
    if not crs or str(crs).strip().lower() in _CRS84_EQUIVALENTS:
        return bbox_xy
    try:
        from pyproj import CRS, Transformer

        transformer = Transformer.from_crs(CRS.from_user_input(crs), "OGC:CRS84", always_xy=True)
        minx, miny, maxx, maxy = transformer.transform_bounds(*bbox_xy, densify_pts=21)
        if not all(map(lambda v: v == v and abs(v) != float("inf"), (minx, miny, maxx, maxy))):
            return None
        return minx, miny, maxx, maxy
    except Exception:
        return None


def _extract_bbox_wkt(collection: Dict[str, Any]) -> Optional[str]:
    """Return a WKT POLYGON bbox string from the collection's spatial extent, if present."""
    try:
        spatial = collection.get("extent", {}).get("spatial", {})
        bbox = spatial.get("bbox", [[]])[0]
        if bbox and len(bbox) >= 4:
            # 2D: minX,minY,maxX,maxY; 3D: minX,minY,minZ,maxX,maxY,maxZ
            hi = (3, 4) if len(bbox) >= 6 else (2, 3)
            converted = _bbox_to_crs84(
                (float(bbox[0]), float(bbox[1]), float(bbox[hi[0]]), float(bbox[hi[1]])),
                spatial.get("crs"),
            )
            if converted is None:
                return None  # unknown/untransformable CRS: omit rather than mislocate
            min_lon, min_lat, max_lon, max_lat = converted
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
    stable_id = str(
        uuid.UUID(hashlib.sha1(f"{_backend_key(backend)}:{col_id}".encode()).hexdigest()[:32])
    )
    return GeoDataObject(
        id=stable_id,
        name=col_id,
        title=collection.get("title") or col_id or "Untitled",
        description=collection.get("description") or "",
        data_type=DataType.LAYER,
        data_source="ogcapi",
        data_source_id=f"ogcapi:{_backend_key(backend)}",
        data_origin=DataOrigin.TOOL.value,
        data_link=access_url,
        layer_type="WFS",  # renderer treats this as a GeoJSON feature layer
        bounding_box=bbox_wkt,
        properties={
            "collection_id": col_id,
            "backend_name": backend.name,
            "backend_key": _backend_key(backend),
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
    try:
        with _make_client(backend.allow_insecure) as client:

            def _pages(params: Dict[str, Any]) -> Iterator[List[Dict[str, Any]]]:
                """Yield collection pages, following rel=next links (or offset)."""
                url = _join_path(backend.url, "collections")
                page_params: Optional[Dict[str, Any]] = params
                fetched = 0
                for _ in range(_MAX_PAGES):
                    _, body = _safe_get(client, url, page_params)
                    data = json.loads(body)
                    if isinstance(data, list):
                        yield data
                        return
                    if not isinstance(data, dict):
                        return
                    cols = data.get("collections", [])
                    yield cols
                    fetched += len(cols)
                    next_href = next(
                        (
                            lk.get("href")
                            for lk in data.get("links", []) or []
                            if lk.get("rel") == "next" and lk.get("href")
                        ),
                        None,
                    )
                    if next_href:
                        url, page_params = urljoin(url, next_href), None
                    elif cols and fetched < (data.get("numberMatched") or 0):
                        url = _join_path(backend.url, "collections")
                        page_params = {**params, "offset": fetched}
                    else:
                        return

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

            # --- Attempt 1: server-side q= search (first page only) ---
            searched: List[Dict[str, Any]] = []
            searched_pages = _pages({**base_params, "q": query})
            try:
                searched = next(searched_pages, [])
            except (ValueError, httpx.HTTPStatusError):
                searched = []  # e.g. HTTP 400: q= unsupported, or non-JSON body

            unfiltered_pages = _pages(base_params)
            first_page = next(unfiltered_pages, [])

            # A server that does not implement q= typically ignores it and returns its
            # normal listing with HTTP 200.  We only trust the server-side result when
            # it demonstrably narrowed the listing, i.e. the set of collection ids
            # differs from the unfiltered first page.  Otherwise (identical, empty or
            # failed) the local predicate is applied, following pagination until
            # max_results matches are found or the catalog (or page cap) is exhausted.
            searched_ids = {c.get("id") for c in searched}
            first_ids = {c.get("id") for c in first_page}
            if searched and searched_ids != first_ids:
                chosen = list(searched)
                # Server honored q: keep paging while it returns fewer than we need.
                try:
                    while len(chosen) < max_results:
                        page = next(searched_pages, None)
                        if page is None:
                            break
                        chosen.extend(page)
                except (ValueError, httpx.HTTPStatusError):
                    pass
            else:
                chosen = _local_matches(first_page)
                while len(chosen) < max_results:
                    page = next(unfiltered_pages, None)
                    if page is None:
                        break
                    chosen.extend(_local_matches(page))
            return [_collection_to_geodata(c, backend) for c in chosen[:max_results]]

    except Exception as exc:
        logger.warning("OGC API backend %s: %s", backend.name, _describe_error(exc))
        raise


@tool
def search_ogcapi_layers(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    max_results: Annotated[int, Field(ge=1, le=_MAX_RESULTS)] = 20,
) -> Union[Dict[str, Any], Command, ToolMessage]:
    """Search for geospatial layers on configured OGC API servers.

    Use this when the user asks for layers or datasets from an OGC API endpoint.
    Searches collection title, description, and id for the given query.

    query: natural-language search string, e.g. "rivers Germany"
    max_results: maximum number of results per backend (1-50, default 20)
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
    try:
        max_results = max(1, min(int(max_results), _MAX_RESULTS))
    except (TypeError, ValueError):
        max_results = 20
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
            errors.append(f"{backend.name}: {_describe_error(exc)}")

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
            "geodata_results": all_results,
            "messages": [
                ToolMessage(
                    content="\n".join(summary_lines),
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
