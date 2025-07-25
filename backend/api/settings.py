from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Any
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS, DEFAULT_SYSTEM_PROMPT

router = APIRouter(prefix="/settings", tags=["settings"])


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


@router.get("/options", response_model=SettingsOptions)
async def get_settings_options():
    # TODO: replace hardcoded with dynamics calls to the different tools and providers
    tool_options = {
        available_tool_name: {"default_prompt": available_tool.description, "settings": {}}
        for available_tool_name, available_tool in DEFAULT_AVAILABLE_TOOLS.items()
    }
    search_portals = [
        "FAO",
        "MapX",
    ]
    model_options = {
        "openai": [
            {"name": "gpt-4-nano", "max_tokens": 50000},
            {"name": "gpt-4-mini", "max_tokens": 100000},
        ],
    }
    return SettingsOptions(
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tool_options=tool_options,
        search_portals=search_portals,
        model_options=model_options,
    )
