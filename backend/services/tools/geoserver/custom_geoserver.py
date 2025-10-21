"""
This tool is used to get data from a custom GeoServer instance.
It uses the GetCapabilities endpoint of a GeoServer to get a list of layers
and their descriptions across WMS, WFS, WCS, and WMTS services.
"""

import logging
import socket
import ssl
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlencode, urljoin

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

# OWSLib imports are done lazily to allow SSL patching before import
# DO NOT import owslib.wms, owslib.wfs, etc. at module level!
# They must be imported AFTER patching for allow_insecure to work
from pydantic import Field
from pydantic.fields import FieldInfo
from typing_extensions import Annotated

from core.config import get_filter_non_webmercator_wmts
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.settings_model import (
    GeoServerBackend,
    ModelSettings,
    SearchPortal,
    SettingsSnapshot,
    ToolConfig,
)
from models.states import GeoDataAgentState
from services.tools.geoserver.vector_store import (
    delete_layers,
    get_embedding_status,
    has_layers,
    is_fully_encoded,
)
from services.tools.geoserver.vector_store import list_layers as vector_list_layers
from services.tools.geoserver.vector_store import similarity_search as vector_similarity_search
from services.tools.geoserver.vector_store import store_layers

logger = logging.getLogger(__name__)


class GeoServerConnectionError(Exception):
    """Raised when unable to connect to GeoServer backend.

    Attributes:
        error_type: Category of error (ssl, dns, connection, timeout, http, unknown)
        message: Human-readable error message
        technical_details: Technical error details for debugging
    """

    def __init__(self, error_type: str, message: str, technical_details: str = ""):
        self.error_type = error_type
        self.message = message
        self.technical_details = technical_details
        super().__init__(message)


def classify_connection_error(exception: Exception) -> Tuple[str, str, str]:
    """Classify a connection exception into user-friendly categories.

    Returns:
        Tuple of (error_type, user_message, technical_details)

    Error types:
        - ssl_certificate: SSL certificate issues (expired, self-signed, invalid)
        - dns: Domain name resolution failures
        - connection: Connection refused, network unreachable
        - timeout: Connection or read timeout
        - http: HTTP error responses (404, 500, etc.)
        - auth: Authentication failures
        - unknown: Other errors
    """
    error_str = str(exception).lower()
    exc_type = type(exception).__name__

    # SSL Certificate Errors
    if isinstance(exception, ssl.SSLError) or "ssl" in error_str or "certificate" in error_str:
        if (
            "certificate verify failed" in error_str
            or "sslcertverificationerror" in exc_type.lower()
        ):
            return (
                "ssl_certificate",
                "SSL certificate verification failed. The server's certificate may be "
                "expired, self-signed, or invalid. Enable 'Allow Insecure' to bypass "
                "verification (not recommended for production).",
                str(exception),
            )
        elif "certificate has expired" in error_str:
            return (
                "ssl_certificate",
                "SSL certificate has expired. Contact the server administrator or enable "
                "'Allow Insecure' to bypass verification.",
                str(exception),
            )
        else:
            return (
                "ssl_certificate",
                "SSL/TLS connection error. The server may have an invalid or "
                "untrusted certificate.",
                str(exception),
            )

    # DNS Resolution Errors
    if (
        isinstance(exception, socket.gaierror)
        or "name or service not known" in error_str
        or "nodename nor servname provided" in error_str
        or "getaddrinfo failed" in error_str
    ):
        return (
            "dns",
            "Domain name resolution failed. The server address may be incorrect "
            "or DNS is unavailable.",
            str(exception),
        )

    # Connection Errors
    connection_error_types = (
        ConnectionRefusedError,
        ConnectionResetError,
        ConnectionAbortedError,
        ConnectionError,
    )
    if (
        isinstance(exception, connection_error_types)
        or "connection refused" in error_str
        or "connection reset" in error_str
    ):
        return (
            "connection",
            "Connection refused. The server may be down, firewalled, or the "
            "URL/port may be incorrect.",
            str(exception),
        )

    if "network is unreachable" in error_str or "no route to host" in error_str:
        return (
            "connection",
            "Network unreachable. Check your network connection or the server may "
            "be inaccessible.",
            str(exception),
        )

    # Timeout Errors
    if isinstance(exception, TimeoutError) or "timeout" in error_str or "timed out" in error_str:
        return (
            "timeout",
            "Connection timeout. The server took too long to respond. It may be "
            "slow or unreachable.",
            str(exception),
        )

    # HTTP Errors
    if hasattr(exception, "response"):
        status_code = getattr(exception.response, "status_code", None)
        if status_code:
            if status_code == 401:
                return (
                    "auth",
                    "Authentication required. Please provide valid username and password.",
                    f"HTTP {status_code}: {str(exception)}",
                )
            elif status_code == 403:
                return (
                    "auth",
                    "Access forbidden. Your credentials may not have sufficient permissions.",
                    f"HTTP {status_code}: {str(exception)}",
                )
            elif status_code == 404:
                return (
                    "http",
                    "GeoServer endpoint not found (404). The URL may be incorrect.",
                    f"HTTP {status_code}: {str(exception)}",
                )
            elif status_code >= 500:
                return (
                    "http",
                    f"Server error ({status_code}). The GeoServer may be misconfigured "
                    "or experiencing issues.",
                    f"HTTP {status_code}: {str(exception)}",
                )
            else:
                return (
                    "http",
                    f"HTTP error {status_code}. See technical details for more information.",
                    f"HTTP {status_code}: {str(exception)}",
                )

    # Authentication errors in exception message
    if "401" in error_str or "unauthorized" in error_str:
        return (
            "auth",
            "Authentication required. Please provide valid username and password.",
            str(exception),
        )

    if "403" in error_str or "forbidden" in error_str:
        return (
            "auth",
            "Access forbidden. Your credentials may not have sufficient permissions.",
            str(exception),
        )

    # Unknown errors
    return (
        "unknown",
        "An unexpected error occurred while connecting to the GeoServer. " "See technical details.",
        str(exception),
    )


def _sanitize_crs_list(crs_options: Any) -> List[str]:
    """Sanitize and filter CRS options to commonly used projections only.

    Many GeoServers report thousands of CRS codes, bloating responses.
    We filter to only include commonly used web mapping projections.
    """
    sanitized: List[str] = []
    try:
        from owslib.crs import Crs  # noqa: F401
    except Exception:  # pragma: no cover - ignore import failures
        pass

    # Common web mapping CRS codes (not thousands of obscure local projections)
    COMMON_CRS = {
        "4326",  # WGS84 - Standard lat/lon
        "3857",  # Web Mercator - Most web maps
        "900913",  # Google Web Mercator (old)
        "3395",  # World Mercator
        "4269",  # NAD83
        "3785",  # Popular Visualization CRS
        "102100",  # Web Mercator (ESRI)
        "102113",  # Web Mercator (ESRI old)
    }

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

    def _is_common(crs_str: str) -> bool:
        """Check if CRS code is in common list."""
        # Extract numeric code from formats like "EPSG:4326" or "4326"
        code = crs_str.upper().replace("EPSG:", "").replace("CRS:", "").replace("AUTO:", "")
        return code in COMMON_CRS

    # Normalize iterable
    if isinstance(crs_options, (list, tuple, set)):
        for c in crs_options:
            crs_str = _one(c)
            if _is_common(crs_str):
                sanitized.append(crs_str)
    else:
        crs_str = _one(crs_options)
        if _is_common(crs_str):
            sanitized.append(crs_str)

    # Ensure we always have at least EPSG:3857 (web mercator) if nothing matched
    if not sanitized:
        sanitized.append("EPSG:3857")

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
            str(_sanitize_properties(k, _depth + 1, _max_depth)): _sanitize_properties(
                v, _depth + 1, _max_depth
            )
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize_properties(v, _depth + 1, _max_depth) for v in obj]
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
            properties=_sanitize_properties(
                {
                    "srs": _sanitize_crs_list(getattr(layer, "crsOptions", None)),
                    "keywords": list(getattr(layer, "keywords", []) or []),
                }
            ),
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
            properties=_sanitize_properties(
                {
                    "srs": _sanitize_crs_list(getattr(ft, "crsOptions", None)),
                    "keywords": list(getattr(ft, "keywords", []) or []),
                }
            ),
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
    filter_non_webmerc = get_filter_non_webmercator_wmts()

    def _is_webmerc(name: Optional[str]) -> bool:
        if not name:
            return False
        import re

        pattern = r"3857|900913|googlemapscompatible|google|web ?mercator|mercatorquad"
        return bool(re.search(pattern, name, flags=re.IGNORECASE))

    def _pick_webmerc(candidates: List[str]) -> Optional[str]:
        if not candidates:
            return None
        # Prefer explicit EPSG:3857 first
        for pref in candidates:
            if "3857" in pref:
                return pref
        # Then other common aliases
        import re

        alias_pattern = r"900913|google|mercator"
        for pref in candidates:
            if re.search(alias_pattern, pref, flags=re.IGNORECASE):
                return pref
        return candidates[0]

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

        # Determine available TileMatrixSets and pick a preferred WebMercator one
        tile_matrix_sets = list(getattr(layer, "tilematrixsetlinks", {}).keys())
        webmerc_sets = [s for s in tile_matrix_sets if _is_webmerc(s)]
        preferred_webmerc = _pick_webmerc(webmerc_sets)

        # Attempt to construct a KVP GetTile template if we have a preferred WebMercator matrix set
        data_link = ""
        if preferred_webmerc:
            # Derive base GeoServer endpoint (strip trailing path after /gwc/service/wmts)
            # geoserver_url is expected like https://host/geoserver/gwc/service/wmts
            base_root = geoserver_url.split("/gwc/")[0].rstrip("/")
            # Standard KVP endpoint
            kvp_base = f"{base_root}/gwc/service/wmts"
            # Use style placeholder blank and image/png by default
            data_link = (
                f"{kvp_base}?service=WMTS&version=1.0.0&request=GetTile&layer={layer.id}"
                f"&style=&tilematrixset={preferred_webmerc}&format=image/png"
                f"&tilematrix={preferred_webmerc}:{{z}}&tilerow={{y}}&tilecol={{x}}"
            )
        else:
            # If filtering is enabled and there is no WebMercator matrix set,
            # skip this layer entirely
            if filter_non_webmerc:
                logger.debug(
                    "Skipping WMTS layer without WebMercator matrix set due to env filter: %s",
                    layer_id,
                )
                continue
            # Fallback to existing discovery logic for non-WebMercator sets
            try:
                if hasattr(layer, "resourceURLs") and layer.resourceURLs:
                    rr = layer.resourceURLs[0]
                    tmpl = None
                    if isinstance(rr, dict):
                        tmpl = rr.get("template") or rr.get("href")
                    else:
                        tmpl = getattr(rr, "template", None) or getattr(rr, "href", None)
                    if tmpl:
                        data_link = tmpl if isinstance(tmpl, str) else str(tmpl)
                if not data_link and getattr(layer, "tilematrixsetlinks", None):
                    first_link = next(iter(layer.tilematrixsetlinks.values()))
                    tmpl = getattr(first_link, "template", None) or getattr(
                        first_link, "href", None
                    )
                    if isinstance(tmpl, dict):
                        tmpl = tmpl.get("template") or tmpl.get("href")
                    if tmpl:
                        tmpl_str = tmpl if isinstance(tmpl, str) else str(tmpl)
                        if (
                            "{TileMatrix}" in tmpl_str
                            or "{TileRow}" in tmpl_str
                            or "{TileCol}" in tmpl_str
                        ):
                            data_link = tmpl_str
                        else:
                            try:
                                data_link = tmpl_str.format(
                                    TileMatrix="{TileMatrix}",
                                    TileRow="{TileRow}",
                                    TileCol="{TileCol}",
                                )
                            except Exception:
                                data_link = tmpl_str
            except Exception:
                logger.debug("Unexpected WMTS link structure; skipping tile template extraction.")

        if data_link:
            if "{style}" in data_link:
                data_link = data_link.replace("{style}", "default")
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
            properties=_sanitize_properties(
                {
                    "tile_matrix_sets": tile_matrix_sets,
                    "webmercator_matrix_sets": webmerc_sets,
                    "preferred_matrix_set": preferred_webmerc,
                    "has_webmercator": bool(preferred_webmerc),
                }
            ),
        )
        layers.append(geo_object)
    return layers


def fetch_all_service_capabilities_with_status(
    backend: GeoServerBackend, search_term: Optional[str] = None
) -> Tuple[List[GeoDataObject], Dict[str, bool], Dict[str, Dict[str, str]]]:
    """Fetch capabilities from all services and capture per-service success flags.

    Returns:
        Tuple of (layers, service_status, service_errors)
        - layers: List of discovered GeoDataObjects
        - service_status: Dict mapping service name to success boolean
        - service_errors: Dict mapping service name to error details
            {error_type, message, technical_details}
    """

    if not backend.enabled:
        return [], {}, {}

    base_url = backend.url
    username = backend.username
    password = backend.password
    allow_insecure = backend.allow_insecure

    # Log the allow_insecure setting for debugging
    logger.info(
        f"Processing backend {base_url}: allow_insecure={allow_insecure}, "
        f"enabled={backend.enabled}"
    )

    all_layers: List[GeoDataObject] = []
    service_status: Dict[str, bool] = {}
    service_errors: Dict[str, Dict[str, str]] = {}

    # Configure SSL verification for OWSLib
    import urllib3
    import ssl

    # Store original values for restoration
    original_ssl_context = None
    original_openURL = None

    if allow_insecure:
        # Suppress only the InsecureRequestWarning when explicitly allowed
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logger.warning(
            f"SSL verification disabled for {base_url} (allow_insecure=True). "
            "This is insecure and should only be used in development."
        )

        # Method 1: Patch SSL context globally - affects all SSL connections
        try:
            original_ssl_context = ssl._create_default_https_context
            ssl._create_default_https_context = ssl._create_unverified_context
            logger.info(f"Patched SSL context for {base_url}")
        except AttributeError as e:
            logger.warning(f"Could not patch SSL context: {e}")

        # Method 2: Patch OWSLib's openURL function to force verify=False
        # This must be done BEFORE importing OWSLib service classes
        try:
            # First, reload owslib.util to get a fresh module state
            import importlib
            import owslib.util
            importlib.reload(owslib.util)

            from owslib.util import openURL as orig_openURL

            original_openURL = orig_openURL

            def patched_openURL(
                url_base,
                data=None,
                method="Get",
                cookies=None,
                username=None,
                password=None,
                timeout=30,
                headers=None,
                verify=True,
                cert=None,
                auth=None,
            ):
                # Force verify=False regardless of what was passed
                logger.debug(
                    f"[PATCHED] openURL called: url={url_base}, "
                    f"verify={verify} -> forcing verify=False"
                )
                return original_openURL(
                    url_base,
                    data,
                    method,
                    cookies,
                    username,
                    password,
                    timeout,
                    headers,
                    verify=False,
                    cert=cert,
                    auth=auth,
                )

            owslib.util.openURL = patched_openURL
            logger.info(f"Patched owslib.util.openURL for {base_url}")
        except Exception as e:
            logger.warning(f"Could not patch owslib.util.openURL: {e}")

    # Re-import OWSLib services AFTER patching to ensure they use the patched openURL
    # This is critical: the classes must be imported AFTER we patch owslib.util.openURL
    if allow_insecure:
        # Force reload of OWSLib modules to pick up the patched openURL
        import importlib
        import owslib.wcs
        import owslib.wfs
        import owslib.wms
        import owslib.wmts

        importlib.reload(owslib.wcs)
        importlib.reload(owslib.wfs)
        importlib.reload(owslib.wms)
        importlib.reload(owslib.wmts)

        from owslib.wcs import WebCoverageService as WCS_Local
        from owslib.wfs import WebFeatureService as WFS_Local
        from owslib.wms import WebMapService as WMS_Local
        from owslib.wmts import WebMapTileService as WMTS_Local
        from owslib.util import Authentication  # Import after reload!

        logger.info("Reloaded OWSLib modules after patching")
    else:
        # Import normally when not bypassing SSL
        from owslib.wcs import WebCoverageService as WCS_Local
        from owslib.wfs import WebFeatureService as WFS_Local
        from owslib.wms import WebMapService as WMS_Local
        from owslib.wmts import WebMapTileService as WMTS_Local
        from owslib.util import Authentication

    # Ensure base_url ends with / for proper urljoin behavior
    # Without trailing slash:
    #   urljoin("https://example.com/geoserver", "wms")
    #   produces: "https://example.com/wms" (incorrect!)
    # With trailing slash:
    #   urljoin("https://example.com/geoserver/", "wms")
    #   produces: "https://example.com/geoserver/wms" (correct)
    if not base_url.endswith("/"):
        base_url = base_url + "/"

    # WMS
    wms_url = urljoin(base_url, "wms")
    logger.info(f"Fetching WMS capabilities from {wms_url} (allow_insecure={allow_insecure})")
    try:
        wms = WMS_Local(wms_url, version="1.3.0", username=username, password=password)
        all_layers.extend(parse_wms_capabilities(wms, wms_url, search_term))
        service_status["WMS"] = True
        logger.info(f"Successfully fetched WMS capabilities from {wms_url}")
    except Exception as e:
        logger.warning(f"Could not fetch WMS capabilities from {wms_url}: {e}")
        service_status["WMS"] = False
        error_type, message, technical = classify_connection_error(e)
        service_errors["WMS"] = {
            "error_type": error_type,
            "message": message,
            "technical_details": technical,
        }

    # WFS
    wfs_url = urljoin(base_url, "wfs")
    try:
        wfs = WFS_Local(wfs_url, version="2.0.0", username=username, password=password)
        all_layers.extend(parse_wfs_capabilities(wfs, wfs_url, search_term))
        service_status["WFS"] = True
    except Exception as e:
        logger.warning(f"Could not fetch WFS capabilities from {wfs_url}: {e}")
        service_status["WFS"] = False
        error_type, message, technical = classify_connection_error(e)
        service_errors["WFS"] = {
            "error_type": error_type,
            "message": message,
            "technical_details": technical,
        }

    # WCS
    wcs_url = urljoin(base_url, "wcs")
    try:
        wcs = WCS_Local(wcs_url, version="2.0.1")
        all_layers.extend(parse_wcs_capabilities(wcs, wcs_url, search_term))
        service_status["WCS"] = True
    except Exception as e:
        logger.warning(f"Could not fetch WCS capabilities from {wcs_url}: {e}")
        service_status["WCS"] = False
        error_type, message, technical = classify_connection_error(e)
        service_errors["WCS"] = {
            "error_type": error_type,
            "message": message,
            "technical_details": technical,
        }

    # WMTS
    wmts_url = urljoin(base_url, "gwc/service/wmts")
    try:
        # Create Authentication object with verify=False for insecure connections
        wmts_auth = Authentication(
            username=username,
            password=password,
            verify=(not allow_insecure)  # verify=False when allow_insecure=True
        )

        wmts = WMTS_Local(wmts_url, auth=wmts_auth)
        all_layers.extend(parse_wmts_capabilities(wmts, wmts_url, search_term))
        service_status["WMTS"] = True
    except Exception as e:
        logger.warning(f"Could not fetch WMTS capabilities from {wmts_url}: {e}")
        service_status["WMTS"] = False
        error_type, message, technical = classify_connection_error(e)
        service_errors["WMTS"] = {
            "error_type": error_type,
            "message": message,
            "technical_details": technical,
        }

    # Restore original SSL context and openURL if they were patched
    if original_ssl_context is not None:
        try:
            ssl._create_default_https_context = original_ssl_context
        except Exception:
            pass

    if original_openURL is not None:
        try:
            import owslib.util

            owslib.util.openURL = original_openURL
        except Exception:
            pass

    return all_layers, service_status, service_errors


def fetch_all_service_capabilities(
    backend: GeoServerBackend, search_term: Optional[str] = None
) -> List[GeoDataObject]:
    """Fetches capabilities from all services and returns a flat list."""

    layers, _, _ = fetch_all_service_capabilities_with_status(backend, search_term=search_term)
    return layers


def _annotate_layers_with_backend(
    layers: List[GeoDataObject], backend: GeoServerBackend
) -> List[GeoDataObject]:
    """Attach backend metadata to the layer properties so it survives persistence."""

    normalized_url = backend.url.rstrip("/")
    for layer in layers:
        props = layer.properties if isinstance(layer.properties, dict) else {}
        if not isinstance(props, dict):
            props = {}
        props.setdefault("_backend_url", normalized_url)
        if backend.name:
            props.setdefault("_backend_name", backend.name)
        if backend.description:
            props.setdefault("_backend_description", backend.description)
        layer.properties = props
    return layers


def preload_backend_layers_with_state(
    session_id: str, backend: GeoServerBackend, search_term: Optional[str] = None
) -> Dict[str, Any]:
    """Wrapper for preload_backend_layers that manages processing state.

    This function sets the state to 'processing', calls the actual preload,
    and sets the state to 'completed' or 'error' based on the result.
    """
    from services.tools.geoserver.vector_store import set_processing_state

    backend_url = backend.url.rstrip("/")

    try:
        # Processing happens in preload_backend_layers (sets to "processing")
        result = preload_backend_layers(session_id, backend, search_term)
        # State is set to "completed" in store_layers finally block
        return result
    except GeoServerConnectionError as exc:
        # Set error state with detailed information
        error_message = f"[{exc.error_type}] {exc.message}"
        set_processing_state(
            session_id,
            backend_url,
            "error",
            error=error_message,
            error_type=exc.error_type,
            error_details=exc.technical_details,
        )
        raise
    except Exception as exc:
        # Set generic error state
        set_processing_state(session_id, backend_url, "error", error=str(exc))
        raise
        raise


def preload_backend_layers(
    session_id: str, backend: GeoServerBackend, search_term: Optional[str] = None
) -> Dict[str, Any]:
    """Fetch and persist layers for a backend into the session-scoped vector store."""
    from services.tools.geoserver.vector_store import set_processing_state

    if not backend.enabled:
        raise ValueError("Backend must be enabled before preloading layers.")

    backend_url = backend.url.rstrip("/")

    # Set processing state before fetching - clear any previous errors
    set_processing_state(
        session_id,
        backend_url,
        "processing",
        total=0,
        error=None,
        error_type=None,
        error_details=None,
    )

    layers, status, errors = fetch_all_service_capabilities_with_status(
        backend, search_term=search_term
    )

    if not any(status.values()):
        # All services failed - raise detailed error
        if errors:
            # Get the first error (they're likely all the same root cause)
            first_error = next(iter(errors.values()))
            error_type = first_error["error_type"]
            error_msg = first_error["message"]
            technical = first_error["technical_details"]

            raise GeoServerConnectionError(
                error_type=error_type,
                message=f"Unable to reach GeoServer backend. {error_msg}",
                technical_details=technical,
            )
        else:
            raise ConnectionError(
                "Unable to reach the GeoServer backend. All capability requests failed."
            )

    annotated_layers = _annotate_layers_with_backend(layers, backend)
    delete_layers(session_id, [backend.url])

    # Update total count now that we know how many layers exist
    if annotated_layers:
        set_processing_state(session_id, backend_url, "processing", total=len(annotated_layers))

    stored_count = store_layers(session_id, backend.url, backend.name, annotated_layers)
    service_counts = Counter(layer.layer_type or "UNKNOWN" for layer in annotated_layers)
    return {
        "session_id": session_id,
        "backend_url": backend_url,
        "backend_name": backend.name,
        "total_layers": stored_count,
        "service_status": status,
        "service_counts": dict(service_counts),
        "service_errors": errors,  # Include error details in response
    }


def _get_custom_geoserver_data(
    state: GeoDataAgentState,
    tool_call_id: str,
    search_term: Optional[str] = None,
    max_results: Optional[int] = 10,
    backend_name: Optional[str] = None,
    backend_url: Optional[str] = None,
    bounding_box: Optional[str] = None,
) -> Union[Dict[str, Any], ToolMessage, Command]:
    """
    Core logic for fetching data from GeoServer backends.
    This function is wrapped by the @tool decorator.
    """
    settings = state.get("options")
    snapshot: Optional[SettingsSnapshot] = None
    if isinstance(settings, SettingsSnapshot):
        snapshot = settings
    elif isinstance(settings, dict):
        try:
            snapshot = SettingsSnapshot.model_validate(settings, strict=False)
        except Exception:
            snapshot = None

    if not snapshot or not snapshot.geoserver_backends:
        return ToolMessage(
            content="No GeoServer backends configured.",
            tool_call_id=tool_call_id,
        )

    session_id = snapshot.session_id
    if not session_id:
        return ToolMessage(
            content=(
                "Missing session identifier. Please reload the settings page to "
                "establish a session."
            ),
            tool_call_id=tool_call_id,
        )

    enabled_backends = [backend for backend in snapshot.geoserver_backends if backend.enabled]
    if backend_name:
        enabled_backends = [
            b for b in enabled_backends if (b.name or "").lower() == backend_name.lower()
        ]
    if backend_url:
        enabled_backends = [
            b for b in enabled_backends if b.url.rstrip("/") == backend_url.rstrip("/")
        ]
    if not enabled_backends:
        return ToolMessage(
            content="All configured GeoServer backends are disabled.",
            tool_call_id=tool_call_id,
        )

    backend_urls = [backend.url.rstrip("/") for backend in enabled_backends]
    if not has_layers(session_id, backend_urls):
        return ToolMessage(
            content=(
                "No prefetched GeoServer layers found for this session. Please preload the"
                " backend via the settings page before querying."
            ),
            tool_call_id=tool_call_id,
        )

    # Check if embedding is complete
    if not is_fully_encoded(session_id, backend_urls):
        embedding_status = get_embedding_status(session_id, backend_urls)
        incomplete_backends = [
            url
            for url, info in embedding_status.items()
            if info["total"] > 0 and not info["complete"]
        ]
        if incomplete_backends:
            return ToolMessage(
                content=(
                    "⚠️ Warning: GeoServer layer embedding is still in progress. "
                    f"Some layers may not be searchable yet. "
                    f"Incomplete backends: {', '.join(incomplete_backends)}. "
                    "Results may be incomplete. Please wait for embedding to complete."
                ),
                tool_call_id=tool_call_id,
            )

    limit = max_results or 10
    fetch_limit = max(limit * 5, limit)
    if search_term:
        search_hits = vector_similarity_search(
            session_id=session_id,
            backend_urls=backend_urls,
            query=search_term,
            limit=fetch_limit,
        )
        candidate_layers = [layer for layer, _distance in search_hits]
    else:
        candidate_layers = vector_list_layers(
            session_id=session_id,
            backend_urls=backend_urls,
            limit=fetch_limit,
        )

    if not candidate_layers:
        return ToolMessage(
            content="No matching layers found for the provided filters.",
            tool_call_id=tool_call_id,
        )

    all_layers: List[GeoDataObject] = candidate_layers

    # Optional bounding box filtering (WGS84 lon/lat)
    bbox_filter = None
    if bounding_box:
        try:
            parts = [float(p.strip()) for p in bounding_box.split(",")]
            if len(parts) != 4:
                raise ValueError
            minx, miny, maxx, maxy = parts
            if not (minx < maxx and miny < maxy):  # simple validity check
                raise ValueError
            bbox_filter = (minx, miny, maxx, maxy)
        except Exception:
            return ToolMessage(
                content=(
                    "Invalid bounding_box format. Expected 'min_lon,min_lat,max_lon,max_lat' "
                    "with valid floats."
                ),
                tool_call_id=tool_call_id,
            )

    if bbox_filter:

        def _parse_layer_bbox(wkt: Optional[str]):
            if not wkt or "POLYGON" not in wkt.upper():
                return None
            import re

            nums = re.findall(r"[-+]?[0-9]*\.?[0-9]+", wkt)
            if len(nums) < 8:
                return None
            coords = list(map(float, nums))
            lons = coords[0::2]
            lats = coords[1::2]
            return (min(lons), min(lats), max(lons), max(lats))

        def _intersects(a, b):
            return not (a[0] > b[2] or a[2] < b[0] or a[1] > b[3] or a[3] < b[1])

        filtered = []
        for lyr in all_layers:
            lyr_bbox = _parse_layer_bbox(getattr(lyr, "bounding_box", None))
            if not lyr_bbox or _intersects(lyr_bbox, bbox_filter):
                filtered.append(lyr)
        all_layers = filtered

    # Enforce max_results limit
    trim_limit = limit if max_results is not None else len(all_layers)
    if trim_limit is not None and len(all_layers) > trim_limit:
        all_layers = all_layers[:trim_limit]

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
            crs_summary += f" (+{len(distinct_crs) - 6} more)"

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
    max_results: Optional[int] = Field(10, description="The maximum number of results to return."),
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
    bounding_box: Optional[str] = Field(
        None,
        description=(
            "Optional WGS84 bounding box filter as 'min_lon,min_lat,max_lon,max_lat'. "
            "Only layers whose WGS84 extent intersects this box are returned."
        ),
    ),
) -> Union[Dict[str, Any], ToolMessage, Command]:
    """
    Searches for geospatial data layers across configured GeoServer instances (WMS, WFS, WCS, WMTS).
    Optional filters:
      - search_term: case-insensitive substring match on layer name/title/abstract.
      - backend_name/backend_url: restrict to a specific configured backend.
            - bounding_box: WGS84 'min_lon,min_lat,max_lon,max_lat' – returns layers whose WGS84
                extent intersects it.
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
    if isinstance(bounding_box, FieldInfo):  # type: ignore[unreachable]
        bounding_box = bounding_box.default

    return _get_custom_geoserver_data(
        actual_state,
        tool_call_id,
        search_term,
        max_results,
        backend_name,
        backend_url,
        bounding_box,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manual tester for custom_geoserver tool.")
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
