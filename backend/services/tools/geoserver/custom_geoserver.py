"""
This tool is used to get data from a custom GeoServer instance.
It uses the GetCapabilities endpoint of a GeoServer to get a list of layers
and their descriptions across WMS, WFS, WCS, and WMTS services.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode, urljoin

from owslib.wcs import WebCoverageService
from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from pydantic import Field
from pydantic.fields import FieldInfo
from typing_extensions import Annotated
from langgraph.types import Command

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import (
    GeoServerBackend,
    SettingsSnapshot,
    SearchPortal,
    ModelSettings,
    ToolConfig,
)
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)


def _sanitize_crs_list(crs_options: Any) -> List[str]:
    """Return a list of stringifiable CRS identifiers.

    owslib may return a heterogeneous container (set/list) including
    owslib.crs.Crs objects which FastAPI/Pydantic cannot serialize directly.
    We defensively cast each entry to a readable string, preferring an explicit
    code attribute when present.
    """
    sanitized: List[str] = []
    if not crs_options:
        return sanitized
    try:  # pragma: no cover - optional import safety
        from owslib.crs import Crs  # noqa: F401
    except Exception:  # pragma: no cover - ignore import failures
        pass

    def _one(item: Any) -> str:
        try:
            if hasattr(item, "code") and getattr(item, "code"):
                return str(getattr(item, "code"))
            # Some Crs objects expose proj4 / urn / srs codes via attributes
            for attr in ("srs", "urn", "proj4", "id"):
                if hasattr(item, attr) and getattr(item, attr):
                    return str(getattr(item, attr))
        except Exception:
            pass
        try:
            return str(item)
        except Exception:
            return repr(item)

    # Normalize iterable
    if isinstance(crs_options, (list, tuple, set)):
        for c in crs_options:
            sanitized.append(_one(c))
    else:
        sanitized.append(_one(crs_options))
    return sanitized


def _sanitize_properties(obj: Any, _depth: int = 0, _max_depth: int = 5) -> Any:
    """Recursively sanitize a properties structure for JSON/Pydantic serialization.

    - Basic JSON-compatible scalars are returned as-is.
    - Enums are converted to their value.
    - Objects without a simple representation are converted via str().
    - Depth is limited to avoid pathological recursion.
    """
    if _depth > _max_depth:
        return str(obj)
    # Primitives
    if obj is None or isinstance(obj, (int, float, bool, str)):
        return obj
    # Enums
    try:  # pragma: no cover - defensive
        from enum import Enum
        if isinstance(obj, Enum):
            return obj.value
    except Exception:  # pragma: no cover
        pass
    # Containers
    if isinstance(obj, dict):
        return {
            str(_sanitize_properties(k, _depth + 1, _max_depth)):
            _sanitize_properties(v, _depth + 1, _max_depth)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple, set)):
        return [
            _sanitize_properties(v, _depth + 1, _max_depth) for v in obj
        ]
    # Fallback: best-effort string
    try:
        return str(obj)
    except Exception:  # pragma: no cover
        return repr(obj)


def parse_wms_capabilities(
    wms, geoserver_url: str, search_term: Optional[str] = None
) -> List[GeoDataObject]:
    """Parses WMS GetCapabilities and returns a list of GeoDataObjects."""
    layers: List[GeoDataObject] = []
    base_url = geoserver_url.split("?")[0]

    for layer_name, layer in wms.contents.items():
        title = layer.title or layer.name
        abstract = layer.abstract or ""
        if search_term and not (
            search_term.lower() in title.lower()
            or search_term.lower() in abstract.lower()
            or search_term.lower() in layer_name.lower()
        ):
            continue

        bounding_box = None
        if layer.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = layer.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        params = {
            "service": "WMS",
            "request": "GetMap",
            "layers": layer.name,
            "format": "image/png",
            "transparent": "true",
            "width": 256,
            "height": 256,
            "bbox": "{bbox-epsg-3857}",
            "srs": "EPSG:3857",
        }
        data_link = f"{base_url}?{urlencode(params)}"

        geo_object = GeoDataObject(
            id=f"wms_{layer.name}",
            data_source_id=f"geoserver_{layer.name}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wms.provider.contact.organization or "Unknown",
            data_link=data_link,
            name=layer.name,
            title=title,
            description=abstract,
            bounding_box=bounding_box,
            layer_type="WMS",
            properties=_sanitize_properties({
                "srs": _sanitize_crs_list(getattr(layer, "crsOptions", None)),
                "keywords": list(getattr(layer, "keywords", []) or []),
            }),
        )
        layers.append(geo_object)
    return layers


def parse_wfs_capabilities(
    wfs, geoserver_url: str, search_term: Optional[str] = None
) -> List[GeoDataObject]:
    """Parses WFS GetCapabilities and returns a list of GeoDataObjects."""
    layers: List[GeoDataObject] = []
    base_url = geoserver_url.split("?")[0]

    for ft_name, ft in wfs.contents.items():
        title = ft.title or ft.id
        abstract = ft.abstract or ""
        if search_term and not (
            search_term.lower() in title.lower()
            or search_term.lower() in abstract.lower()
            or search_term.lower() in ft_name.lower()
        ):
            continue

        bounding_box = None
        if ft.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = ft.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": ft.id,
            "outputFormat": "application/json",
        }
        data_link = f"{base_url}?{urlencode(params)}"

        geo_object = GeoDataObject(
            id=f"wfs_{ft.id}",
            data_source_id=f"geoserver_{ft.id}",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL.value,
            data_source=wfs.provider.name or "Unknown",
            data_link=data_link,
            name=ft.id,
            title=title,
            description=abstract,
            bounding_box=bounding_box,
            layer_type="WFS",
            properties=_sanitize_properties({
                "srs": _sanitize_crs_list(getattr(ft, "crsOptions", None)),
                "keywords": list(getattr(ft, "keywords", []) or []),
            }),
        )
        layers.append(geo_object)
    return layers


def parse_wcs_capabilities(
    wcs, geoserver_url: str, search_term: Optional[str] = None
) -> List[GeoDataObject]:
    """Parses WCS GetCapabilities and returns a list of GeoDataObjects."""
    layers: List[GeoDataObject] = []
    base_url = geoserver_url.split("?")[0]

    for cov_id, cov in wcs.contents.items():
        title = cov.title or cov.id
        abstract = cov.abstract or ""
        if search_term and not (
            search_term.lower() in title.lower()
            or search_term.lower() in abstract.lower()
            or search_term.lower() in cov_id.lower()
        ):
            continue

        bounding_box = None
        if cov.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = cov.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "coverageId": cov.id,
        }
        data_link = f"{base_url}?{urlencode(params)}"

        geo_object = GeoDataObject(
            id=f"wcs_{cov.id}",
            data_source_id=f"geoserver_{cov.id}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wcs.provider.name or "Unknown",
            data_link=data_link,
            name=cov.id,
            title=title,
            description=abstract,
            bounding_box=bounding_box,
            layer_type="WCS",
            properties=_sanitize_properties(
                {"supported_formats": getattr(cov, "supportedFormats", [])}
            ),
        )
        layers.append(geo_object)
    return layers


def parse_wmts_capabilities(
    wmts, geoserver_url: str, search_term: Optional[str] = None
) -> List[GeoDataObject]:
    """Parses WMTS GetCapabilities and returns a list of GeoDataObjects."""
    layers: List[GeoDataObject] = []

    for layer_id, layer in wmts.contents.items():
        title = layer.title or layer.id
        abstract = layer.abstract or ""
        if search_term and not (
            search_term.lower() in title.lower()
            or search_term.lower() in abstract.lower()
            or search_term.lower() in layer_id.lower()
        ):
            continue

        bounding_box = None
        if layer.boundingBoxWGS84:
            min_lon, min_lat, max_lon, max_lat = layer.boundingBoxWGS84
            bounding_box = (
                f"POLYGON(({max_lon} {min_lat}, {max_lon} {max_lat}, "
                f"{min_lon} {max_lat}, {min_lon} {min_lat}, {max_lon} {min_lat}))"
            )

        # Be defensive: different WMTS responses may expose link templates in
        # different attributes (resourceURLs, TileMatrixSetLink objects, href, etc.).
        data_link = ""
        try:
            # resourceURLs (preferred if present)
            if hasattr(layer, "resourceURLs") and layer.resourceURLs:
                rr = layer.resourceURLs[0]
                # rr might be a dict or an object
                tmpl = None
                if isinstance(rr, dict):
                    tmpl = rr.get("template") or rr.get("href")
                else:
                    tmpl = getattr(rr, "template", None) or getattr(rr, "href", None)
                if tmpl:
                    data_link = tmpl if isinstance(tmpl, str) else str(tmpl)
            # fall back to tilematrixsetlinks
            if not data_link and getattr(layer, "tilematrixsetlinks", None):
                first_link = next(iter(layer.tilematrixsetlinks.values()))
                tmpl = getattr(first_link, "template", None) or getattr(first_link, "href", None)
                # Some objects may wrap resource info in dict-like attrs
                if isinstance(tmpl, dict):
                    tmpl = tmpl.get("template") or tmpl.get("href")
                if tmpl:
                    # Work with a string representation
                    tmpl_str = tmpl if isinstance(tmpl, str) else str(tmpl)
                    # If the template contains placeholders, keep them formatted
                    if (
                        "{TileMatrix}" in tmpl_str
                        or "{TileRow}" in tmpl_str
                        or "{TileCol}" in tmpl_str
                    ):
                        data_link = tmpl_str
                    else:
                        # try naive formatting if it's a python-style template
                        try:
                            data_link = tmpl_str.format(
                                TileMatrix="{TileMatrix}", TileRow="{TileRow}", TileCol="{TileCol}"
                            )
                        except Exception:
                            data_link = tmpl_str
        except Exception:
            logger.debug("Unexpected WMTS link structure; skipping tile template extraction.")

        # Post-process template for frontend safety: remove unsupported {style} placeholder
        if data_link:
            if "{style}" in data_link:
                data_link = data_link.replace("{style}", "default")
            # Prefer image/png over utfgrid JSON for rendering base tiles
            if "application/json;type=utfgrid" in data_link:
                data_link = data_link.replace("application/json;type=utfgrid", "image/png")

        geo_object = GeoDataObject(
            id=f"wmts_{layer.id}",
            data_source_id=f"geoserver_{layer.id}",
            data_type=DataType.RASTER,
            data_origin=DataOrigin.TOOL.value,
            data_source=wmts.provider.name or "Unknown",
            data_link=data_link,
            name=layer.id,
            title=title,
            description=abstract,
            bounding_box=bounding_box,
            layer_type="WMTS",
            properties=_sanitize_properties({
                "tile_matrix_sets": list(getattr(layer, "tilematrixsetlinks", {}).keys())
            }),
        )
        layers.append(geo_object)
    return layers


def fetch_all_service_capabilities(
    backend: GeoServerBackend, search_term: Optional[str] = None
) -> List[GeoDataObject]:
    """Fetches capabilities from all services and returns a flat list."""
    if not backend.enabled:
        return []

    base_url = backend.url
    username = backend.username
    password = backend.password
    all_layers: List[GeoDataObject] = []

    # WMS
    wms_url = urljoin(base_url, "wms")
    try:
        wms = WebMapService(
            wms_url, version="1.3.0", username=username, password=password
        )
        all_layers.extend(parse_wms_capabilities(wms, wms_url, search_term))
    except Exception as e:
        logger.warning(f"Could not fetch WMS capabilities from {wms_url}: {e}")

    # WFS
    wfs_url = urljoin(base_url, "wfs")
    try:
        wfs = WebFeatureService(
            wfs_url, version="2.0.0", username=username, password=password
        )
        all_layers.extend(parse_wfs_capabilities(wfs, wfs_url, search_term))
    except Exception as e:
        logger.warning(f"Could not fetch WFS capabilities from {wfs_url}: {e}")

    # WCS
    wcs_url = urljoin(base_url, "wcs")
    try:
        wcs = WebCoverageService(wcs_url, version="2.0.1")
        all_layers.extend(parse_wcs_capabilities(wcs, wcs_url, search_term))
    except Exception as e:
        logger.warning(f"Could not fetch WCS capabilities from {wcs_url}: {e}")

    # WMTS
    wmts_url = urljoin(base_url, "gwc/service/wmts")
    try:
        wmts = WebMapTileService(wmts_url, username=username, password=password)
        all_layers.extend(parse_wmts_capabilities(wmts, wmts_url, search_term))
    except Exception as e:
        logger.warning(f"Could not fetch WMTS capabilities from {wmts_url}: {e}")

    return all_layers


def _get_custom_geoserver_data(
    state: GeoDataAgentState,
    tool_call_id: str,
    search_term: Optional[str] = None,
    max_results: Optional[int] = 10,
    backend_name: Optional[str] = None,
    backend_url: Optional[str] = None,
) -> Union[Dict[str, Any], ToolMessage, Command]:
    """
    Core logic for fetching data from GeoServer backends.
    This function is wrapped by the @tool decorator.
    """
    settings = state.get("options")
    if (
        not settings
        or not isinstance(settings, SettingsSnapshot)
        or not settings.geoserver_backends
    ):
        return ToolMessage(
            content="No GeoServer backends configured.",
            tool_call_id=tool_call_id,
        )

    enabled_backends = [backend for backend in settings.geoserver_backends if backend.enabled]
    if backend_name:
        enabled_backends = [
            b
            for b in enabled_backends
            if (b.name or "").lower() == backend_name.lower()
        ]
    if backend_url:
        enabled_backends = [
            b
            for b in enabled_backends
            if b.url.rstrip("/") == backend_url.rstrip("/")
        ]
    if not enabled_backends:
        return ToolMessage(
            content="All configured GeoServer backends are disabled.",
            tool_call_id=tool_call_id,
        )

    all_layers: List[GeoDataObject] = []
    for backend in enabled_backends:
        try:
            fetched_layers = fetch_all_service_capabilities(
                backend, search_term=search_term
            )
            # annotate with backend metadata (non-invasive; add to properties if dict-like)
            for lyr in fetched_layers:
                try:
                    props = getattr(lyr, 'properties', None)
                    if isinstance(props, dict):
                        props.setdefault('_backend_url', backend.url)
                        if backend.name:
                            props.setdefault('_backend_name', backend.name)
                        if backend.description:
                            props.setdefault('_backend_description', backend.description)
                except Exception:
                    pass
            all_layers.extend(fetched_layers)
        except Exception as e:
            logger.error(f"Error fetching from backend {backend.url}: {e}")
            # Optionally, add a message to the state indicating partial failure
            # For now, we just log and continue
            pass

    # Enforce max_results limit
    if max_results is not None and len(all_layers) > max_results:
        all_layers = all_layers[:max_results]

    # Summarize distinct CRS codes across collected layers (if available)
    crs_codes = []
    for lyr in all_layers:
        try:
            props = getattr(lyr, "properties", {}) or {}
            if isinstance(props, dict):
                srs_list = props.get("srs")
                if isinstance(srs_list, (list, tuple, set)):
                    for c in srs_list:
                        if isinstance(c, str):
                            crs_codes.append(c)
        except Exception:
            pass
    distinct_crs = sorted({c for c in crs_codes if c})
    crs_summary = ""
    if distinct_crs:
        crs_summary = f" Distinct CRS: {', '.join(distinct_crs[:6])}"
        if len(distinct_crs) > 6:
            crs_summary += f" (+{len(distinct_crs)-6} more)"

    tool_message = ToolMessage(
        content=f"Found {len(all_layers)} layers.{crs_summary}", tool_call_id=tool_call_id
    )

    current_messages = state.get("messages", [])
    if not isinstance(current_messages, list):
        current_messages = []

    # Update messages; DO NOT overwrite geodata_layers or geodata_last_results here.
    state["messages"] = current_messages + [tool_message]

    # Prepare new geodata_results (replace previous search results with current set)
    new_results = all_layers

    return Command(
        update={
            "messages": state["messages"],
            "geodata_results": new_results,
        }
    )


@tool
def get_custom_geoserver_data(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    search_term: Optional[str] = Field(
        None, description="An optional search term to filter layer names, titles, and abstracts."
    ),
    max_results: Optional[int] = Field(
        10, description="The maximum number of results to return."
    ),
    backend_name: Optional[str] = Field(
        None,
        description=(
            "Optional exact name of a configured GeoServer backend to query only that backend."
        ),
    ),
    backend_url: Optional[str] = Field(
        None,
        description=(
            "Optional exact URL of a configured GeoServer backend to query only that backend."
        ),
    ),
) -> Union[Dict[str, Any], ToolMessage, Command]:
    """
    Searches for geospatial data layers across all configured GeoServer instances.
    It queries WMS, WFS, WCS, and WMTS services for available layers.
    """
    # The input to a tool is a dict, but the InjectedState logic passes the whole state
    # We need to handle both cases. If 'state' is in the input, we use that.
    actual_state = state.get("state", state)
    # Tool runners may pass the pydantic Field objects (FieldInfo) as defaults
    # when args are not provided. Coerce FieldInfo to their default values so
    # downstream code receives plain Python types (e.g., int or None).
    if isinstance(max_results, FieldInfo):
        max_results = max_results.default
    if isinstance(search_term, FieldInfo):
        search_term = search_term.default
    # Newly added optional filters may also arrive as FieldInfo objects
    if isinstance(backend_name, FieldInfo):  # type: ignore[unreachable]
        backend_name = backend_name.default
    if isinstance(backend_url, FieldInfo):  # type: ignore[unreachable]
        backend_url = backend_url.default

    return _get_custom_geoserver_data(
        actual_state,
        tool_call_id,
        search_term,
        max_results,
        backend_name,
        backend_url,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Manual tester for custom_geoserver tool."
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default="https://development.demo.geonode.org/geoserver/",
        help=(
            "Base URL of the GeoServer instance. "
            "Example: https://development.demo.geonode.org/geoserver/"
        ),
    )
    parser.add_argument("--search", "-s", help="Optional search term to filter layers.")
    parser.add_argument("--max", "-m", type=int, default=20, help="Maximum results to print.")

    args = parser.parse_args()

    # Build a minimal backend config and settings snapshot to pass into the tool
    backend = GeoServerBackend(
        url=args.base_url,
        name="CLI Backend",
        description="Ad-hoc CLI invocation",
        enabled=True,
        username=None,
        password=None,
    )

    settings_snapshot = SettingsSnapshot(
        search_portals=[SearchPortal(url=args.base_url, enabled=True)],
        geoserver_backends=[backend],
        model_settings=ModelSettings(
            model_provider="local",
            model_name="none",
            max_tokens=1,
            system_prompt="",
        ),
        tools=[ToolConfig(name="get_custom_geoserver_data", enabled=True, prompt_override="")],
    )

    initial_state = {
        "options": settings_snapshot,
        "geodata_layers": [],
        "messages": [],
        "results_title": "",
        "geodata_last_results": [],
        "geodata_results": [],
        "remaining_steps": 0,
    }

    print(f"Querying GeoServer at: {args.base_url} using the tool wrapper\n")

    # Call the LangChain tool wrapper via its invoke method
    tool_call_id = "cli_call"
    result = get_custom_geoserver_data.invoke(
        {
            "state": initial_state,
            "tool_call_id": tool_call_id,
            "search_term": args.search,
            "max_results": args.max,
        }
    )

    # Handle ToolMessage (error/info) vs successful dict or Command(update=...) result
    if isinstance(result, ToolMessage):
        print(f"Tool message: {result.content}\n")
        print("No layers returned from tool.")
    else:
        # Support Command(update=...) or plain dict
        if hasattr(result, "update") and isinstance(result.update, dict):
            result_dict = result.update
        else:
            result_dict = result

        layers = result_dict.get("geodata_layers", []) or []
        print(f"Found total layers: {len(layers)}\n")

        # Print a summary by service
        from collections import Counter

        svc_counts = Counter(getattr(layer, "layer_type", "UNKNOWN") for layer in layers)
        for svc, cnt in svc_counts.items():
            print(f"  {svc}: {cnt}")

        print("\nSample layers:")
        for layer in layers[: args.max]:
            lid = getattr(layer, "id", repr(layer))
            ltitle = getattr(layer, "title", "")
            lsource = getattr(layer, "data_source", getattr(layer, "data_source_id", ""))
            ltype = getattr(layer, "layer_type", "")
            print(f"- [{ltype}] {lid} | {ltitle} | source={lsource}")

        # Quick verification that all four services are handled
        expected = {"WMS", "WFS", "WCS", "WMTS"}
        present = set(getattr(layer, "layer_type", "UNKNOWN") for layer in layers)
        missing = expected - present
        if missing:
            print(f"\nWarning: Missing expected services: {', '.join(sorted(missing))}")
        else:
            print("\nAll expected services found: WMS, WFS, WCS, WMTS")
