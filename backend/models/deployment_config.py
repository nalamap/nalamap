"""
Deployment Configuration Models

Defines the schema for custom deployment configurations that allow operators
to customize NaLaMap deployments with pre-configured settings.

Configuration can be provided via JSON file (DEPLOYMENT_CONFIG_PATH env var)
and is validated against these models on server startup.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from models.settings_model import GeoServerBackend, MCPServer


class DeploymentGeoServerBackend(GeoServerBackend):
    """Extended GeoServer backend with startup preload option."""

    preload_on_startup: bool = Field(
        False,
        description=(
            "If True, this backend's layers will be preloaded (embedded) "
            "when the server starts. Embeddings are shared across all sessions."
        ),
    )
    search_term: Optional[str] = Field(
        None,
        description=(
            "Optional search term to filter which layers are preloaded. "
            "If not provided, all layers are preloaded."
        ),
    )


class DeploymentToolConfig(BaseModel):
    """Tool configuration for deployment."""

    name: str = Field(..., description="Tool name as defined in DEFAULT_AVAILABLE_TOOLS")
    enabled: bool = Field(True, description="Whether this tool is enabled by default")
    prompt_override: Optional[str] = Field(None, description="Custom prompt override for this tool")


class ColorScale(BaseModel):
    """Color scale with 11 shades (50-950)."""

    shade_50: str = Field(..., description="Lightest shade")
    shade_100: str
    shade_200: str
    shade_300: str
    shade_400: str
    shade_500: str
    shade_600: str
    shade_700: str
    shade_800: str
    shade_900: str
    shade_950: str = Field(..., description="Darkest shade")


class ColorSettings(BaseModel):
    """User-customizable color settings for the UI."""

    primary: ColorScale
    second_primary: ColorScale
    secondary: ColorScale
    tertiary: ColorScale
    danger: ColorScale
    warning: ColorScale
    info: ColorScale
    neutral: ColorScale
    corporate_1: ColorScale
    corporate_2: ColorScale
    corporate_3: ColorScale


class DeploymentModelSettings(BaseModel):
    """Model settings for deployment configuration.

    More permissive than runtime ModelSettings - allows partial configuration
    that will be merged with defaults.
    """

    model_provider: Optional[str] = Field(
        None, description="Provider name, e.g., openai, google, azure"
    )
    model_name: Optional[str] = Field(None, description="Model identifier, e.g., gpt-4o")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens to generate")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    message_window_size: Optional[int] = Field(
        None, ge=0, description="Max messages in context window"
    )
    enable_parallel_tools: Optional[bool] = Field(
        None, description="Enable parallel tool execution"
    )
    enable_performance_metrics: Optional[bool] = Field(
        None, description="Enable performance metrics tracking"
    )
    enable_dynamic_tools: Optional[bool] = Field(None, description="Enable dynamic tool selection")
    tool_selection_strategy: Optional[str] = Field(
        None, description="Strategy for dynamic tool selection"
    )
    tool_similarity_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Similarity threshold for tool selection"
    )
    max_tools_per_query: Optional[int] = Field(None, ge=1, description="Max tools per query")
    use_summarization: Optional[bool] = Field(None, description="Enable conversation summarization")
    enable_smart_crs: Optional[bool] = Field(None, description="Enable intelligent CRS selection")


class DeploymentConfig(BaseModel):
    """
    Root deployment configuration model.

    This represents the structure of a deployment configuration file that
    operators can provide to customize NaLaMap for their specific needs.

    Example file: deployment-config.json
    ```json
    {
        "geoserver_backends": [
            {
                "url": "https://geoserver.example.org/geoserver/",
                "name": "Corporate GeoServer",
                "enabled": true,
                "preload_on_startup": true
            }
        ],
        "model_settings": {
            "model_provider": "azure",
            "model_name": "gpt-4o"
        },
        "tools": [
            {"name": "geoprocess", "enabled": true}
        ]
    }
    ```
    """

    # GeoServer backends to pre-configure
    geoserver_backends: List[DeploymentGeoServerBackend] = Field(
        default_factory=list,
        description=(
            "Pre-configured GeoServer backends. "
            "Backends with preload_on_startup=True will have their layers "
            "embedded at server startup for faster search."
        ),
    )

    # MCP servers to pre-configure
    mcp_servers: List[MCPServer] = Field(
        default_factory=list,
        description="Pre-configured MCP servers for tool extension.",
    )

    # Model settings overrides
    model_settings: Optional[DeploymentModelSettings] = Field(
        None,
        description=(
            "Default model settings. Any unspecified fields will use "
            "the system defaults. Invalid provider/model combinations "
            "will be logged as warnings and fall back to defaults."
        ),
    )

    # Tool configurations
    tools: List[DeploymentToolConfig] = Field(
        default_factory=list,
        description=(
            "Tool enable/disable configuration. Tools not listed here will "
            "use their default enabled state. Unknown tool names are logged "
            "as warnings and ignored."
        ),
    )

    # System prompt override
    system_prompt: Optional[str] = Field(
        None, description="Custom system prompt to replace the default."
    )

    # Color settings
    color_settings: Optional[ColorSettings] = Field(
        None, description="Custom color scheme for the UI."
    )

    # Theme preference
    theme: Optional[str] = Field(None, description="Theme preference: 'light' or 'dark'")

    # Additional metadata
    config_version: Optional[str] = Field(
        None, description="Version of the config schema (for future migrations)"
    )
    config_name: Optional[str] = Field(
        None, description="Human-readable name for this configuration"
    )
    config_description: Optional[str] = Field(
        None, description="Description of what this configuration customizes"
    )

    class Config:
        # Allow extra fields for forward compatibility
        extra = "allow"


class DeploymentConfigValidationResult(BaseModel):
    """Result of validating a deployment configuration."""

    valid: bool = Field(..., description="Whether the config is valid and usable")
    config: Optional[DeploymentConfig] = Field(None, description="The validated config (if valid)")
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings (unknown tools, unavailable models, etc.)",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Fatal errors that prevent config from being used",
    )
