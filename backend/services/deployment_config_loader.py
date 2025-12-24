"""
Deployment Configuration Loader

Loads and validates custom deployment configurations for NaLaMap.
Configurations can be provided via environment variable DEPLOYMENT_CONFIG_PATH
pointing to a JSON file.

Usage:
    export DEPLOYMENT_CONFIG_PATH=/path/to/config.json
    # or in .env file

The loader:
1. Reads the config file if path is set
2. Validates against DeploymentConfig schema
3. Checks tool names exist in DEFAULT_AVAILABLE_TOOLS
4. Checks model provider/name availability
5. Logs warnings for non-fatal issues
6. Returns None or falls back to defaults on errors
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError

from models.deployment_config import (
    ColorSettings,
    DeploymentConfig,
    DeploymentConfigValidationResult,
    DeploymentGeoServerBackend,
    DeploymentModelSettings,
    DeploymentToolConfig,
)
from services.default_agent_settings import DEFAULT_AVAILABLE_TOOLS

logger = logging.getLogger(__name__)

# Environment variable for config file path
DEPLOYMENT_CONFIG_ENV_VAR = "DEPLOYMENT_CONFIG_PATH"

# Module-level cache for loaded config
_cached_config: Optional[DeploymentConfigValidationResult] = None
_config_loaded: bool = False


def get_deployment_config_path() -> Optional[str]:
    """Get the deployment config file path from environment."""
    return os.environ.get(DEPLOYMENT_CONFIG_ENV_VAR)


def load_config_file(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Load and parse a JSON config file.

    Args:
        path: Path to the config file

    Returns:
        Tuple of (parsed dict or None, error message or None)
    """
    config_path = Path(path)

    if not config_path.exists():
        return None, f"Config file not found: {path}"

    if not config_path.is_file():
        return None, f"Config path is not a file: {path}"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in config file: {e}"
    except PermissionError:
        return None, f"Permission denied reading config file: {path}"
    except Exception as e:
        return None, f"Error reading config file: {e}"


def validate_tools(
    tool_configs: List[DeploymentToolConfig],
) -> Tuple[List[DeploymentToolConfig], List[str]]:
    """Validate tool configurations against available tools.

    Args:
        tool_configs: List of tool configurations from the deployment config

    Returns:
        Tuple of (valid tool configs, warning messages)
    """
    warnings: List[str] = []
    valid_configs: List[DeploymentToolConfig] = []
    known_tools: Set[str] = set(DEFAULT_AVAILABLE_TOOLS.keys())

    for config in tool_configs:
        if config.name not in known_tools:
            warnings.append(
                f"Unknown tool '{config.name}' in deployment config - ignoring. "
                f"Available tools: {sorted(known_tools)}"
            )
        else:
            valid_configs.append(config)

    return valid_configs, warnings


def validate_model_settings(
    model_settings: Optional[DeploymentModelSettings],
) -> Tuple[Optional[DeploymentModelSettings], List[str]]:
    """Validate model settings against available providers and models.

    Args:
        model_settings: Model settings from deployment config

    Returns:
        Tuple of (validated settings or None, warning messages)
    """
    if model_settings is None:
        return None, []

    warnings: List[str] = []

    # Only validate if provider is specified
    if model_settings.model_provider:
        try:
            from services.ai.provider_interface import get_all_providers

            providers = get_all_providers()

            if model_settings.model_provider not in providers:
                warnings.append(
                    f"Unknown model provider '{model_settings.model_provider}' - "
                    f"will fall back to default. Available: {list(providers.keys())}"
                )
            else:
                provider_info = providers[model_settings.model_provider]
                if not provider_info.available:
                    warnings.append(
                        f"Model provider '{model_settings.model_provider}' is not available "
                        f"(API key not configured?) - will fall back to default. "
                        f"Error: {provider_info.error_message}"
                    )
                elif model_settings.model_name:
                    # Check if model name is valid for this provider
                    available_models = [m.name for m in provider_info.models]
                    if model_settings.model_name not in available_models:
                        warnings.append(
                            f"Unknown model '{model_settings.model_name}' for provider "
                            f"'{model_settings.model_provider}' - will fall back to first "
                            f"available. Available models: {available_models}"
                        )
        except Exception as e:
            warnings.append(f"Could not validate model settings: {e}")

    # Validate strategy if provided
    if model_settings.tool_selection_strategy:
        valid_strategies = {"all", "semantic", "conservative", "minimal"}
        if model_settings.tool_selection_strategy not in valid_strategies:
            warnings.append(
                f"Invalid tool_selection_strategy '{model_settings.tool_selection_strategy}' - "
                f"using default. Valid options: {valid_strategies}"
            )

    return model_settings, warnings


def validate_geoserver_backends(
    backends: List[DeploymentGeoServerBackend],
) -> Tuple[List[DeploymentGeoServerBackend], List[str]]:
    """Validate GeoServer backend configurations.

    Args:
        backends: List of GeoServer backends from deployment config

    Returns:
        Tuple of (validated backends, warning messages)
    """
    warnings: List[str] = []
    validated: List[DeploymentGeoServerBackend] = []

    for backend in backends:
        # Basic URL validation
        if not backend.url:
            warnings.append("GeoServer backend with empty URL - skipping")
            continue

        url = backend.url.strip()
        if not url.lower().startswith(("http://", "https://")):
            warnings.append(
                f"GeoServer URL '{url}' missing protocol - " "will add https:// automatically"
            )

        validated.append(backend)

    return validated, warnings


def validate_color_settings(
    color_settings: Optional[ColorSettings],
) -> Tuple[Optional[ColorSettings], List[str]]:
    """Validate color settings format.

    Args:
        color_settings: Color settings from deployment config

    Returns:
        Tuple of (validated settings, warning messages)
    """
    if color_settings is None:
        return None, []

    warnings: List[str] = []

    # Validate hex color format for each scale
    required_scales = [
        "primary",
        "second_primary",
        "secondary",
        "tertiary",
        "danger",
        "warning",
        "info",
        "neutral",
        "corporate_1",
        "corporate_2",
        "corporate_3",
    ]

    for scale_name in required_scales:
        scale = getattr(color_settings, scale_name, None)
        if scale is None:
            warnings.append(f"Missing color scale '{scale_name}' - will use default")
            continue

        # Check each shade is a valid hex color
        for shade_name in [
            "shade_50",
            "shade_100",
            "shade_200",
            "shade_300",
            "shade_400",
            "shade_500",
            "shade_600",
            "shade_700",
            "shade_800",
            "shade_900",
            "shade_950",
        ]:
            shade_value = getattr(scale, shade_name, None)
            if shade_value and not shade_value.startswith("#"):
                warnings.append(
                    f"Color value '{shade_value}' for {scale_name}.{shade_name} "
                    "should be a hex color (e.g., #FFFFFF)"
                )

    return color_settings, warnings


def load_and_validate_config() -> DeploymentConfigValidationResult:
    """Load and validate deployment configuration from file.

    Returns:
        DeploymentConfigValidationResult with config and any warnings/errors
    """
    global _cached_config, _config_loaded

    # Return cached result if already loaded
    if _config_loaded and _cached_config is not None:
        return _cached_config

    config_path = get_deployment_config_path()

    # No config path set - return empty result (use defaults)
    if not config_path:
        logger.info(
            f"No deployment config specified ({DEPLOYMENT_CONFIG_ENV_VAR} not set). "
            "Using default configuration."
        )
        result = DeploymentConfigValidationResult(
            valid=True,
            config=None,
            warnings=[],
            errors=[],
        )
        _cached_config = result
        _config_loaded = True
        return result

    logger.info(f"Loading deployment configuration from: {config_path}")

    errors: List[str] = []
    warnings: List[str] = []

    # Load the file
    data, load_error = load_config_file(config_path)
    if load_error:
        errors.append(load_error)
        logger.error(f"Failed to load deployment config: {load_error}")
        result = DeploymentConfigValidationResult(
            valid=False, config=None, warnings=[], errors=errors
        )
        _cached_config = result
        _config_loaded = True
        return result

    # Parse with Pydantic
    try:
        config = DeploymentConfig.model_validate(data)
    except ValidationError as e:
        errors.append(f"Configuration validation failed: {e}")
        logger.error(f"Deployment config validation failed: {e}")
        result = DeploymentConfigValidationResult(
            valid=False, config=None, warnings=[], errors=errors
        )
        _cached_config = result
        _config_loaded = True
        return result

    # Validate individual sections
    valid_tools, tool_warnings = validate_tools(config.tools)
    warnings.extend(tool_warnings)
    config.tools = valid_tools

    validated_model_settings, model_warnings = validate_model_settings(config.model_settings)
    warnings.extend(model_warnings)
    config.model_settings = validated_model_settings

    validated_backends, backend_warnings = validate_geoserver_backends(config.geoserver_backends)
    warnings.extend(backend_warnings)
    config.geoserver_backends = validated_backends

    validated_colors, color_warnings = validate_color_settings(config.color_settings)
    warnings.extend(color_warnings)
    config.color_settings = validated_colors

    # Validate theme
    if config.theme and config.theme not in ("light", "dark"):
        warnings.append(
            f"Invalid theme '{config.theme}' - must be 'light' or 'dark'. Using default."
        )
        config.theme = None

    # Log summary
    if warnings:
        for warning in warnings:
            logger.warning(f"Deployment config: {warning}")

    preload_backends = [b for b in config.geoserver_backends if b.preload_on_startup]
    logger.info(
        f"Deployment config loaded successfully:\n"
        f"  - Config name: {config.config_name or '(unnamed)'}\n"
        f"  - GeoServer backends: {len(config.geoserver_backends)} "
        f"({len(preload_backends)} to preload)\n"
        f"  - Tool overrides: {len(config.tools)}\n"
        f"  - Custom model settings: {config.model_settings is not None}\n"
        f"  - Custom colors: {config.color_settings is not None}\n"
        f"  - Theme: {config.theme or 'default'}\n"
        f"  - Warnings: {len(warnings)}"
    )

    result = DeploymentConfigValidationResult(
        valid=True,
        config=config,
        warnings=warnings,
        errors=errors,
    )
    _cached_config = result
    _config_loaded = True
    return result


def get_cached_config() -> Optional[DeploymentConfig]:
    """Get the cached deployment config if loaded and valid.

    Returns:
        The loaded config or None if not loaded/invalid
    """
    # Access module-level globals for reading
    if not _config_loaded:
        result = load_and_validate_config()
        return result.config if result.valid else None

    return _cached_config.config if _cached_config and _cached_config.valid else None


def get_preload_backends() -> List[DeploymentGeoServerBackend]:
    """Get list of GeoServer backends that should be preloaded on startup.

    Returns:
        List of backends with preload_on_startup=True
    """
    config = get_cached_config()
    if not config:
        return []

    return [b for b in config.geoserver_backends if b.preload_on_startup]


def get_tool_overrides() -> Dict[str, bool]:
    """Get tool enable/disable overrides from deployment config.

    Returns:
        Dict mapping tool name to enabled state
    """
    config = get_cached_config()
    if not config:
        return {}

    return {t.name: t.enabled for t in config.tools}


def merge_tool_metadata_with_config(
    base_metadata: Dict[str, Dict],
) -> Dict[str, Dict]:
    """Merge tool metadata with deployment config overrides.

    Args:
        base_metadata: The default TOOL_METADATA dict

    Returns:
        Merged metadata with deployment config overrides applied
    """
    config = get_cached_config()
    if not config:
        return base_metadata

    merged = {k: dict(v) for k, v in base_metadata.items()}  # Deep copy

    # Apply tool overrides from config
    for tool_config in config.tools:
        if tool_config.name in merged:
            merged[tool_config.name]["enabled"] = tool_config.enabled

    # Add any tools that exist but weren't in the config (as disabled if we want to be strict)
    # Actually, we keep default state - only override what's explicitly configured

    return merged


def clear_config_cache():
    """Clear the cached configuration. Useful for testing."""
    global _cached_config, _config_loaded
    _cached_config = None
    _config_loaded = False
