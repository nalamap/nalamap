import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from core import config as core_config
from models.settings_model import GeoServerBackend
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS, DEFAULT_SYSTEM_PROMPT
from services.tools.geoserver.custom_geoserver import preload_backend_layers

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
    if not re.match(r'^[a-zA-Z0-9-]+$', session_id):
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


class SettingsOptions(BaseModel):
    system_prompt: str
    tool_options: Dict[str, ToolOption]  # per-tool settings
    search_portals: List[str]
    model_options: Dict[str, List[ModelOption]]  # per-provider model list
    session_id: str


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
    search_portals = [
        "FAO",
        "MapX",
    ]
    model_options: Dict[str, List[ModelOption]] = {
        "openai": [
            {"name": "gpt-4-nano", "max_tokens": 50000},
            {"name": "gpt-4-mini", "max_tokens": 100000},
        ],
    }

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
        search_portals=search_portals,
        model_options=model_options,
        session_id=session_id,
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

    try:
        result = await asyncio.to_thread(
            preload_backend_layers, session_id, normalized_backend, payload.search_term
        )
    except ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.exception("Failed to preload GeoServer backend", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preload GeoServer backend.",
        ) from exc

    return GeoServerPreloadResponse(**result)
