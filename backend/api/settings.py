import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from core import config as core_config
from models.settings_model import GeoServerBackend
from services.background_tasks import TaskPriority, get_task_manager
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS, DEFAULT_SYSTEM_PROMPT
from services.tools.geoserver.custom_geoserver import preload_backend_layers_with_state
from services.tools.geoserver.vector_store import set_processing_state

router = APIRouter(prefix="/settings", tags=["settings"])

logger = logging.getLogger(__name__)


def validate_session_id(session_id: str) -> bool:
    """Validate that session_id is safe to use in cookies.

    Only allows alphanumeric characters and hyphens, with reasonable length.
    This prevents cookie injection attacks where malicious values could be
    used to manipulate cookie behavior.

    Args:
        session_id: The session identifier to validate

    Returns:
        True if session_id is valid and safe to use

    Examples:
        >>> validate_session_id("abc123def456")
        True
        >>> validate_session_id("session-id-123")
        True
        >>> validate_session_id("bad;value=malicious")
        False
        >>> validate_session_id("a" * 200)
        False
    """
    if not session_id or not isinstance(session_id, str):
        return False

    # Length check: reasonable session ID length (8-128 characters)
    if len(session_id) < 8 or len(session_id) > 128:
        return False

    # Only allow alphanumeric characters and hyphens (safe for cookies)
    # This matches UUID hex strings and similar safe formats
    if not re.match(r"^[a-zA-Z0-9-]+$", session_id):
        return False

    return True


def normalize_geoserver_url(url: str) -> str:
    """Normalize GeoServer URL by ensuring it has a protocol.

    If the URL is missing a protocol (http:// or https://), prepends https://.
    This prevents connection errors that result in 503 responses.

    Args:
        url: The GeoServer URL to normalize

    Returns:
        The normalized URL with protocol

    Examples:
        >>> normalize_geoserver_url("example.com/geoserver")
        "https://example.com/geoserver"
        >>> normalize_geoserver_url("http://example.com/geoserver")
        "http://example.com/geoserver"
        >>> normalize_geoserver_url("https://example.com/geoserver")
        "https://example.com/geoserver"
    """
    url = url.strip()

    # Check if URL starts with a protocol (case-insensitive)
    if not (url.lower().startswith("http://") or url.lower().startswith("https://")):
        url = f"https://{url}"
        logger.info(f"Added https:// protocol to GeoServer URL: {url}")

    return url


class ToolOption(BaseModel):
    default_prompt: str
    settings: Dict[str, Any] = {}  # additional tool-specific settings


class ModelOption(BaseModel):
    name: str
    max_tokens: int


class ExampleGeoServer(BaseModel):
    url: str
    name: str
    description: str
    username: Optional[str] = None
    password: Optional[str] = None


class ColorScale(BaseModel):
    """Represents a color scale with 11 shades (50-950)"""

    shade_50: str
    shade_100: str
    shade_200: str
    shade_300: str
    shade_400: str
    shade_500: str
    shade_600: str
    shade_700: str
    shade_800: str
    shade_900: str
    shade_950: str


class ColorSettings(BaseModel):
    """User-customizable color settings for the UI"""

    primary: ColorScale
    second_primary: ColorScale
    secondary: ColorScale
    tertiary: ColorScale


class SettingsOptions(BaseModel):
    system_prompt: str
    tool_options: Dict[str, ToolOption]  # per-tool settings
    example_geoserver_backends: List[ExampleGeoServer]
    model_options: Dict[str, List[ModelOption]]  # per-provider model list
    session_id: str
    color_settings: ColorSettings  # default color settings


class GeoServerPreloadRequest(BaseModel):
    backend: GeoServerBackend
    search_term: Optional[str] = None
    session_id: Optional[str] = None


class GeoServerPreloadResponse(BaseModel):
    session_id: str
    backend_url: str
    backend_name: Optional[str] = None
    total_layers: int
    service_status: Dict[str, bool]
    service_counts: Dict[str, int]


@router.get("/options", response_model=SettingsOptions)
async def get_settings_options(request: Request, response: Response):
    # TODO: replace hardcoded with dynamic calls to the different tools and providers
    tool_options = {
        available_tool_name: {"default_prompt": available_tool.description, "settings": {}}
        for available_tool_name, available_tool in DEFAULT_AVAILABLE_TOOLS.items()
    }
    example_geoserver_backends = [
        ExampleGeoServer(
            url="https://geoserver.mapx.org/geoserver/",
            name="MapX",
            description=(
                "MapX is an open-source, web-based platform developed by UNEP/GRID-Geneva for "
                "managing, visualizing, and analyzing geospatial data on natural resources and "
                "environmental issues. It supports a wide range of applications such as "
                "biodiversity planning, disaster risk reduction, and sustainable land-use "
                "management. Designed for both experts and non-specialists, MapX offers intuitive "
                "tools like dashboards and story maps to communicate data effectively. Built on "
                "open standards, it ensures interoperability through OGC services and APIs, "
                "allowing seamless integration with other geospatial systems. Overall, MapX "
                "provides an accessible and collaborative environment to support evidence-based "
                "environmental decision-making."
            ),
        ),
        ExampleGeoServer(
            url="https://ogc.worldpop.org/geoserver/",
            name="WorldPop",
            description=(
                "WorldPop is a research-based geospatial platform developed at the University of "
                "Southampton that provides high-resolution, open-access data on population "
                "distribution, structure, and dynamics, with a focus on low- and middle-income "
                "countries. Its datasets support applications in public health, disaster "
                "management, development planning, and monitoring of the Sustainable Development "
                "Goals. The platform ensures interoperability through REST APIs and OGC services, "
                "enabling seamless integration with other GIS systems. WorldPop hosts an extensive "
                "and regularly updated data repository, offering tools for visualization, "
                "querying, and downloading. Its mission is to ensure that everyone, everywhere is "
                "counted by filling demographic data gaps with transparent, fine-scale modelling "
                "in collaboration with national partners."
            ),
        ),
    ]
    model_options: Dict[str, List[ModelOption]] = {
        "openai": [
            ModelOption(name="gpt-4-nano", max_tokens=50000),
            ModelOption(name="gpt-4-mini", max_tokens=100000),
        ],
    }

    # Default color settings matching globals.css
    default_color_settings = ColorSettings(
        primary=ColorScale(
            shade_50="#f7f7f8",
            shade_100="#eeeef0",
            shade_200="#d8d8df",
            shade_300="#b7b9c2",
            shade_400="#8f91a1",
            shade_500="#717386",
            shade_600="#5b5c6e",
            shade_700="#505160",
            shade_800="#40414c",
            shade_900="#383842",
            shade_950="#25252c",
        ),
        second_primary=ColorScale(
            shade_50="#f5f8f9",
            shade_100="#e8eef1",
            shade_200="#d6e1e7",
            shade_300="#baccd6",
            shade_400="#99b2c1",
            shade_500="#809bb1",
            shade_600="#68829e",
            shade_700="#627793",
            shade_800="#546279",
            shade_900="#465262",
            shade_950="#2e343d",
        ),
        secondary=ColorScale(
            shade_50="#fafaeb",
            shade_100="#f2f4d3",
            shade_200="#e6eaac",
            shade_300="#d3db7b",
            shade_400="#bec952",
            shade_500="#aebd38",
            shade_600="#7e8b25",
            shade_700="#606a21",
            shade_800="#4c551f",
            shade_900="#41491e",
            shade_950="#22270c",
        ),
        tertiary=ColorScale(
            shade_50="#f4f8ed",
            shade_100="#e5f0d7",
            shade_200="#cde2b4",
            shade_300="#adcf87",
            shade_400="#8eba61",
            shade_500="#719f43",
            shade_600="#598234",
            shade_700="#43612a",
            shade_800="#394e26",
            shade_900="#324324",
            shade_950="#18240f",
        ),
    )

    session_id = request.cookies.get("session_id")

    # Validate existing session_id from cookie, or generate a new one
    if not session_id or not validate_session_id(session_id):
        session_id = uuid4().hex
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=core_config.COOKIE_HTTPONLY,
            secure=core_config.COOKIE_SECURE,
            samesite=core_config.COOKIE_SAMESITE,
            max_age=60 * 60 * 24 * 30,
        )

    return SettingsOptions(
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tool_options=tool_options,
        example_geoserver_backends=example_geoserver_backends,
        model_options=model_options,
        session_id=session_id,
        color_settings=default_color_settings,
    )


@router.post("/geoserver/preload", response_model=GeoServerPreloadResponse)
async def preload_geoserver_backend(
    payload: GeoServerPreloadRequest, request: Request, response: Response
):
    session_id = request.cookies.get("session_id") or payload.session_id
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session identifier is required to preload GeoServer backends.",
        )

    # Validate session_id to prevent cookie injection attacks
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session identifier format. Session ID must be alphanumeric.",
        )

    # Normalize the backend URL to ensure it has a protocol
    normalized_backend = payload.backend.model_copy()
    normalized_backend.url = normalize_geoserver_url(payload.backend.url)

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=core_config.COOKIE_HTTPONLY,
        secure=core_config.COOKIE_SECURE,
        samesite=core_config.COOKIE_SAMESITE,
        max_age=60 * 60 * 24 * 30,
    )

    # Immediately set state to "waiting" and return response
    # This prevents 504 timeouts for long-running preloads
    backend_url = normalized_backend.url.rstrip("/")

    try:
        set_processing_state(session_id, backend_url, "waiting", total=0)
    except Exception as exc:
        logger.exception("Failed to set processing state", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize backend processing state.",
        ) from exc

    # Submit preload task to low-priority thread pool (runs in background)
    try:
        task_manager = get_task_manager()
    except Exception as exc:
        logger.exception("Failed to get task manager", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize background task manager.",
        ) from exc

    task_id = f"preload_{session_id}_{backend_url}"

    # Submit the task with low priority (won't block user queries)
    try:
        task_manager.submit_task(
            preload_backend_layers_with_state,
            session_id,
            normalized_backend,
            payload.search_term,
            priority=TaskPriority.LOW,
            task_id=task_id,
        )
    except Exception as exc:
        logger.exception("Failed to submit preload task", exc_info=exc)
        set_processing_state(session_id, backend_url, "error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit backend preload task.",
        ) from exc

    # Return immediately with "waiting" state
    # Frontend will poll embedding-status endpoint to track progress
    return GeoServerPreloadResponse(
        session_id=session_id,
        backend_url=backend_url,
        backend_name=normalized_backend.name,
        total_layers=0,  # Will be updated once processing starts
        service_status={},  # Will be populated during processing
        service_counts={},  # Will be populated during processing
    )


@router.get("/geoserver/embedding-status")
async def get_geoserver_embedding_status(request: Request, backend_urls: Optional[str] = None):
    """Get the embedding progress status for GeoServer backends in the current session.

    Returns the total number of layers and how many have been encoded for each backend.

    Query parameters:
        backend_urls: Comma-separated list of backend URLs to check (optional).
                     If not provided, will return empty status.
    """
    from services.tools.geoserver import vector_store

    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session identifier is required.",
        )

    # Validate session_id
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session identifier format.",
        )

    # Parse backend URLs from query parameter
    urls = []
    if backend_urls:
        urls = [
            normalize_geoserver_url(url.strip()) for url in backend_urls.split(",") if url.strip()
        ]

    # Get embedding status from vector store
    try:
        status_dict = vector_store.get_embedding_status(session_id, urls)

        return {
            "session_id": session_id,
            "backends": status_dict,
        }
    except Exception as exc:
        logger.exception("Failed to get embedding status", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get embedding status.",
        ) from exc
