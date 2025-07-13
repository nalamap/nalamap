from typing import List, Optional
from pydantic import BaseModel, Field


class GeoServerBackend(BaseModel):
    url: str = Field(..., description="GeoServer endpoint URL")
    username: Optional[str] = Field(None, description="Basic auth username")
    password: Optional[str] = Field(None, description="Basic auth password")
    enabled: bool = Field(True, description="Enable or disable this backend")


class SearchPortal(BaseModel):
    url: str = Field(..., description="Geodata portal URL")
    enabled: bool = Field(True, description="Enable or disable this portal")


class ModelSettings(BaseModel):
    model_provider: str = Field(..., description="Provider name, e.g., openai, anthropic")
    model_name: str = Field(..., description="Model identifier, e.g., gpt-4")
    max_tokens: int = Field(..., ge=1, description="Maximum tokens to generate")
    system_prompt: str = Field("", description="System-level prompt override")


class ToolConfig(BaseModel):
    name: str = Field(..., description="Tool name as referenced in settings")
    enabled: bool = Field(True, description="Enable or disable this tool")
    prompt_override: str = Field("", description="Custom prompt to override default tool behavior")


class SettingsSnapshot(BaseModel):
    search_portals: List[SearchPortal] = Field(..., description="Configured data portal endpoints")
    geoserver_backends: List[GeoServerBackend] = Field(
        ..., description="Configured GeoServer backends"
    )
    model_settings: ModelSettings = Field(..., description="Configuration for LLM model usage")
    tools: List[ToolConfig] = Field(..., description="Per-tool configuration overrides")
