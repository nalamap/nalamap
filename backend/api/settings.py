import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from models.settings_model import GeoServerBackend
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS, DEFAULT_SYSTEM_PROMPT
from services.tools.geoserver.custom_geoserver import preload_backend_layers

router = APIRouter(prefix="/settings", tags=["settings"])

logger = logging.getLogger(__name__)


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
    if not session_id:
        session_id = uuid4().hex
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=False,
            samesite="lax",
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

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )

    try:
        result = await asyncio.to_thread(
            preload_backend_layers, session_id, payload.backend, payload.search_term
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
