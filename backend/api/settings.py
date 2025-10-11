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
    input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    cache_cost_per_million: Optional[float] = None
    description: Optional[str] = None
    supports_tools: bool = True
    supports_vision: bool = False


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

    primary: ColorScale  # Main neutral/text colors
    second_primary: ColorScale  # Main action buttons
    secondary: ColorScale  # Supporting accents
    tertiary: ColorScale  # Success states
    danger: ColorScale  # Error/delete actions
    warning: ColorScale  # Warning states
    info: ColorScale  # Informational states
    neutral: ColorScale  # Pure neutral (white/black/gray)
    corporate_1: ColorScale  # Corporate brand color 1
    corporate_2: ColorScale  # Corporate brand color 2
    corporate_3: ColorScale  # Corporate brand color 3


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
    """Get available settings options including dynamically discovered LLM providers and models."""
    # Get available tools
    tool_options = {
        available_tool_name: {"default_prompt": available_tool.description, "settings": {}}
        for available_tool_name, available_tool in DEFAULT_AVAILABLE_TOOLS.items()
    }

    # Example GeoServer backends
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

    # Dynamically discover available LLM providers and models
    from services.ai.provider_interface import get_all_providers

    providers_info = get_all_providers()

    # Convert provider info to model_options format
    model_options: Dict[str, List[ModelOption]] = {}
    for provider_name, provider_info in providers_info.items():
        if provider_info.available and provider_info.models:
            model_options[provider_name] = [
                ModelOption(
                    name=model.name,
                    max_tokens=model.max_tokens,
                    input_cost_per_million=model.input_cost_per_million,
                    output_cost_per_million=model.output_cost_per_million,
                    cache_cost_per_million=model.cache_cost_per_million,
                    description=model.description,
                    supports_tools=model.supports_tools,
                    supports_vision=model.supports_vision,
                )
                for model in provider_info.models
            ]

    # If no providers are available, fall back to minimal OpenAI options for UI testing
    if not model_options:
        logger.warning("No LLM providers available, using fallback model options")
        model_options = {
            "openai": [
                ModelOption(
                    name="gpt-5-mini",
                    max_tokens=100000,
                    input_cost_per_million=0.25,
                    output_cost_per_million=0.025,
                    description="GPT-5 Mini (fallback - configure API key)",
                ),
            ],
        }

    # Default color settings matching globals.css
    # IUCN Green List–matched color settings (tuned to NalaMap usage)
    default_color_settings = ColorSettings(
        # Neutral greys (text, borders, light backgrounds)
        primary=ColorScale(
            shade_50="#FAFBFA",  # app backgrounds (very light)
            shade_100="#E3E7E4",  # light panels / chat backgrounds
            shade_200="#DEE1DF",  # light dividers / subtle fills
            shade_300="#C9CECC",  # borders (maps to your primary-300 use)
            shade_400="#9F9F9F",  # disabled text, handles
            shade_500="#7D807E",  # secondary text / metadata
            shade_600="#646464",  # interactive icons/links (default)
            shade_700="#545454",  # hover/darker interactive
            shade_800="#3B3E3C",  # sidebar bg / section headings (slate)
            shade_900="#2F3530",  # main text / strong emphasis
            shade_950="#181B19",
        ),
        # Main accent (buttons, active states, progress) — leaf green
        second_primary=ColorScale(
            shade_50="#F3FAF3",
            shade_100="#E6F3E6",
            shade_200="#D5E8D3",  # user message bg
            shade_300="#B9D8B8",
            shade_400="#96C691",
            shade_500="#79B472",
            shade_600="#66A660",  # ACTION BUTTONS / active — your 600
            shade_700="#4F8E4F",  # button hover — your 700
            shade_800="#3D7040",
            shade_900="#2F5732",
            shade_950="#1D3820",
        ),
        # Supporting accent (focus rings, subtle highlights, hovers) — seafoam/teal
        secondary=ColorScale(
            shade_50="#F0F5F2",
            shade_100="#E3EDE8",
            shade_200="#CDE1D8",
            shade_300="#B6D5C9",  # textarea/input focus ring
            shade_400="#9EC9B9",
            shade_500="#86BEAA",  # waiting progress bar
            shade_600="#6BAE97",  # waiting status text / send button
            shade_700="#559D85",  # send hover
            shade_800="#3C8C74",  # sidebar item hover bg
            shade_900="#2F6F5C",
            shade_950="#204F42",
        ),
        # Success / confirmations — deeper forest green
        tertiary=ColorScale(
            shade_50="#EAF4ED",
            shade_100="#D8E8DE",
            shade_200="#B9D5C4",
            shade_300="#99C2AA",
            shade_400="#79AE90",
            shade_500="#5D9A7A",
            shade_600="#477951",  # success text, checkboxes, completed
            shade_700="#3D6948",  # export hover (darker success)
            shade_800="#32573C",
            shade_900="#284832",
            shade_950="#1A2F22",
        ),
        # Danger / error states — red
        danger=ColorScale(
            shade_50="#FEF2F2",
            shade_100="#FEE2E2",
            shade_200="#FECACA",
            shade_300="#FCA5A5",
            shade_400="#F87171",
            shade_500="#EF4444",
            shade_600="#DC2626",  # main error/delete color
            shade_700="#B91C1C",  # hover state
            shade_800="#991B1B",
            shade_900="#7F1D1D",
            shade_950="#450A0A",
        ),
        # Warning states — amber/orange
        warning=ColorScale(
            shade_50="#FFFBEB",
            shade_100="#FEF3C7",
            shade_200="#FDE68A",
            shade_300="#FCD34D",
            shade_400="#FBBF24",
            shade_500="#F59E0B",
            shade_600="#D97706",  # main warning color
            shade_700="#B45309",
            shade_800="#92400E",
            shade_900="#78350F",
            shade_950="#451A03",
        ),
        # Info states — blue
        info=ColorScale(
            shade_50="#EFF6FF",
            shade_100="#DBEAFE",
            shade_200="#BFDBFE",
            shade_300="#93C5FD",
            shade_400="#60A5FA",
            shade_500="#3B82F6",
            shade_600="#2563EB",  # main info color
            shade_700="#1D4ED8",
            shade_800="#1E40AF",
            shade_900="#1E3A8A",
            shade_950="#172554",
        ),
        # Neutral (pure white/black/grays) for backgrounds and overlays
        neutral=ColorScale(
            shade_50="#FFFFFF",  # pure white
            shade_100="#F9FAFB",
            shade_200="#F3F4F6",
            shade_300="#E5E7EB",
            shade_400="#D1D5DB",
            shade_500="#9CA3AF",
            shade_600="#6B7280",
            shade_700="#4B5563",
            shade_800="#374151",
            shade_900="#1F2937",
            shade_950="#000000",  # pure black
        ),
        # Corporate Color 1 - for layer type styling (rose)
        corporate_1=ColorScale(
            shade_50="#FFF1F2",
            shade_100="#FFE4E6",
            shade_200="#FECDD3",
            shade_300="#FDA4AF",
            shade_400="#FB7185",
            shade_500="#F43F5E",
            shade_600="#E11D48",
            shade_700="#BE123C",
            shade_800="#9F1239",
            shade_900="#881337",
            shade_950="#4C0519",
        ),
        # Corporate Color 2 - for layer type styling (sky)
        corporate_2=ColorScale(
            shade_50="#F0F9FF",
            shade_100="#E0F2FE",
            shade_200="#BAE6FD",
            shade_300="#7DD3FC",
            shade_400="#38BDF8",
            shade_500="#0EA5E9",
            shade_600="#0284C7",
            shade_700="#0369A1",
            shade_800="#075985",
            shade_900="#0C4A6E",
            shade_950="#082F49",
        ),
        # Corporate Color 3 - for layer type styling (purple)
        corporate_3=ColorScale(
            shade_50="#FAF5FF",
            shade_100="#F3E8FF",
            shade_200="#E9D5FF",
            shade_300="#D8B4FE",
            shade_400="#C084FC",
            shade_500="#A855F7",
            shade_600="#9333EA",
            shade_700="#7E22CE",
            shade_800="#6B21A8",
            shade_900="#581C87",
            shade_950="#3B0764",
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
