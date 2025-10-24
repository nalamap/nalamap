from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class GeoServerBackend(BaseModel):
    url: str = Field(..., description="GeoServer endpoint URL")
    name: Optional[str] = Field(None, description="Human-friendly name for this backend")
    description: Optional[str] = Field(None, description="Optional description / purpose notes")
    username: Optional[str] = Field(None, description="Basic auth username")
    password: Optional[str] = Field(None, description="Basic auth password")
    enabled: bool = Field(True, description="Enable or disable this backend")
    allow_insecure: bool = Field(
        False,
        description=(
            "Allow insecure connections (e.g., expired/self-signed SSL certificates). "
            "WARNING: Only enable this for trusted servers in development environments."
        ),
    )


class MCPServer(BaseModel):
    url: str = Field(..., description="MCP server endpoint URL")
    name: Optional[str] = Field(None, description="Human-friendly name for this MCP server")
    description: Optional[str] = Field(
        None, description="Optional description of tools/capabilities"
    )
    enabled: bool = Field(True, description="Enable or disable this MCP server")
    api_key: Optional[str] = Field(
        None,
        description="API key for authentication (e.g., Bearer token, API key)",
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Additional HTTP headers for authentication (e.g., {'X-API-Key': 'xxx'})",
    )


class SearchPortal(BaseModel):
    url: str = Field(..., description="Geodata portal URL")
    enabled: bool = Field(True, description="Enable or disable this portal")


class ModelSettings(BaseModel):
    model_provider: str = Field(..., description="Provider name, e.g., openai, google")
    model_name: str = Field(..., description="Model identifier, e.g., gpt-4")
    max_tokens: int = Field(..., ge=1, description="Maximum tokens to generate")
    system_prompt: str = Field("", description="System-level prompt override")
    message_window_size: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Maximum number of recent messages to keep in context. "
            "If None, uses MESSAGE_WINDOW_SIZE env var (default: 20). "
            "Set to 0 to disable pruning."
        ),
    )
    enable_parallel_tools: bool = Field(
        False,
        description=(
            "Enable parallel tool execution for faster multi-tool queries. "
            "EXPERIMENTAL: May cause state corruption with concurrent updates. "
            "Only works with models that support parallel tool calls."
        ),
    )
    enable_performance_metrics: bool = Field(
        False,
        description=(
            "Enable performance metrics tracking and storage. "
            "When enabled, tracks timing, token usage, and tool performance. "
            "Metrics are available via the /metrics endpoint."
        ),
    )
    enable_dynamic_tools: bool = Field(
        False,
        description=(
            "Enable dynamic tool selection based on query analysis. "
            "When enabled, only relevant tools are loaded based on the query, "
            "reducing context size and improving performance. "
            "Supports all languages through semantic similarity."
        ),
    )
    tool_selection_strategy: str = Field(
        "conservative",
        description=(
            "Strategy for dynamic tool selection. Options: "
            "'all' (load all tools, disable dynamic selection), "
            "'semantic' (use semantic similarity), "
            "'conservative' (semantic + core tools), "
            "'minimal' (only most relevant tools)."
        ),
    )
    tool_similarity_threshold: float = Field(
        0.3,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum similarity score (0.0-1.0) for tool inclusion "
            "in semantic selection. Lower = more tools included."
        ),
    )
    max_tools_per_query: Optional[int] = Field(
        None,
        ge=1,
        description=(
            "Maximum number of tools to load per query. "
            "None = unlimited. Useful for strict context control."
        ),
    )
    use_summarization: bool = Field(
        False,
        description=(
            "Enable automatic conversation summarization for long conversations. "
            "When enabled, older messages are automatically summarized to reduce "
            "token usage while maintaining context. Requires session_id to track "
            "conversation state across requests."
        ),
    )


class ToolConfig(BaseModel):
    name: str = Field(..., description="Tool name as referenced in settings")
    enabled: bool = Field(True, description="Enable or disable this tool")
    prompt_override: str = Field("", description="Custom prompt to override default tool behavior")


class SettingsSnapshot(BaseModel):
    search_portals: List[SearchPortal] = Field(
        default_factory=list,
        description=(
            "[DEPRECATED] Configured data portal endpoints. " "No longer used in the application."
        ),
    )
    geoserver_backends: List[GeoServerBackend] = Field(
        ..., description="Configured GeoServer backends"
    )
    mcp_servers: List[MCPServer] = Field(
        default_factory=list, description="Configured MCP (Model Context Protocol) servers"
    )
    model_settings: ModelSettings = Field(..., description="Configuration for LLM model usage")
    tools: List[ToolConfig] = Field(..., description="Per-tool configuration overrides")
    session_id: Optional[str] = Field(
        None,
        description=(
            "Server-issued identifier used to scope cached resources such as prefetched"
            " GeoServer layers."
        ),
    )
