# Implementation for Azure AI
import json
import logging
from os import getenv
from typing import Dict, List, Optional

from langchain_openai import AzureChatOpenAI

from models.model_info import ModelInfo

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Check if Azure OpenAI provider is available (credentials configured)."""
    endpoint = getenv("AZURE_OPENAI_ENDPOINT")
    api_key = getenv("AZURE_OPENAI_API_KEY")
    # Check for either single deployment or models config
    deployment = getenv("AZURE_OPENAI_DEPLOYMENT")
    models_config = getenv("AZURE_MODELS_CONFIG")
    return bool(all([endpoint, api_key]) and (deployment or models_config))


def _parse_azure_models_config() -> List[Dict]:
    """Parse AZURE_MODELS_CONFIG environment variable.

    Expected format (JSON array):
    [
        {
            "deployment": "gpt-4o",
            "model_name": "gpt-4o",
            "max_tokens": 4096,
            "context_window": 128000,
            "input_cost": 5.00,
            "output_cost": 15.00,
            "cache_cost": 1.25,
            "description": "GPT-4o via Azure",
            "supports_tools": true,
            "supports_vision": true,
            "parallel_tools": true,
            "tool_quality": "excellent",
            "reasoning": "expert"
        }
    ]

    Returns:
        List of model configuration dictionaries
    """
    config_str = getenv("AZURE_MODELS_CONFIG", "")
    if not config_str:
        return []

    try:
        models = json.loads(config_str)
        if not isinstance(models, list):
            logger.warning("AZURE_MODELS_CONFIG must be a JSON array")
            return []
        return models
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AZURE_MODELS_CONFIG: {e}")
        return []


def _create_model_info_from_config(config: Dict) -> ModelInfo:
    """Create ModelInfo from configuration dictionary."""
    return ModelInfo(
        name=config.get("model_name", config.get("deployment", "unknown")),
        max_tokens=config.get("max_tokens", 4096),
        input_cost_per_million=config.get("input_cost"),
        output_cost_per_million=config.get("output_cost"),
        cache_cost_per_million=config.get("cache_cost"),
        description=config.get("description", f"Azure deployment: {config.get('deployment')}"),
        supports_tools=config.get("supports_tools", True),
        supports_vision=config.get("supports_vision", False),
        context_window=config.get("context_window", 128000),
        supports_parallel_tool_calls=config.get("parallel_tools", True),
        tool_calling_quality=config.get("tool_quality", "good"),
        reasoning_capability=config.get("reasoning", "advanced"),
    )


def get_available_models() -> list[ModelInfo]:
    """Get list of available Azure OpenAI and Azure AI Foundry models.

    Supports two configuration methods:
    1. Single deployment (legacy): AZURE_OPENAI_DEPLOYMENT
    2. Multiple models: AZURE_MODELS_CONFIG (JSON array)

    The AZURE_MODELS_CONFIG format allows configuring multiple deployments
    including Azure OpenAI models and Azure AI Foundry models (Meta Llama,
    DeepSeek, Mistral, etc.) with full capability specifications.

    Returns:
        List of ModelInfo objects for all configured Azure deployments
    """
    models = []

    # Try parsing AZURE_MODELS_CONFIG first (new multi-model format)
    model_configs = _parse_azure_models_config()
    if model_configs:
        for config in model_configs:
            try:
                model_info = _create_model_info_from_config(config)
                models.append(model_info)
                logger.info(f"Loaded Azure model: {model_info.name}")
            except Exception as e:
                logger.warning(f"Failed to create model from config {config}: {e}")
        return models

    # Fallback to single deployment (legacy compatibility)
    deployment = getenv("AZURE_OPENAI_DEPLOYMENT")
    if deployment:
        models.append(
            ModelInfo(
                name=deployment,
                max_tokens=6000,
                input_cost_per_million=None,  # Varies by region and deployment
                output_cost_per_million=None,
                cache_cost_per_million=None,
                description=f"Azure OpenAI deployment: {deployment}",
                supports_tools=True,
                supports_vision=False,  # Depends on deployment
                context_window=128000,  # Conservative default
                supports_parallel_tool_calls=True,
                tool_calling_quality="good",
                reasoning_capability="advanced",
            )
        )
        logger.info(f"Loaded Azure model (legacy): {deployment}")

    return models


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get AzureChatOpenAI instance.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Name of the model to use. If provided and AZURE_MODELS_CONFIG
                   is configured, will use the corresponding deployment.
                   Falls back to AZURE_OPENAI_DEPLOYMENT if not found.

    Returns:
        AzureChatOpenAI instance configured with the deployment
    """
    deployment_name = None

    # If model_name provided and we have multi-model config, find the deployment
    if model_name:
        model_configs = _parse_azure_models_config()
        for config in model_configs:
            config_model_name = config.get("model_name", config.get("deployment"))
            if config_model_name == model_name:
                deployment_name = config.get("deployment")
                logger.info(f"Using Azure deployment '{deployment_name}' for model '{model_name}'")
                break

    # Fall back to default deployment if not found or not specified
    if not deployment_name:
        deployment_name = getenv("AZURE_OPENAI_DEPLOYMENT")
        if model_name:
            logger.warning(
                f"Model '{model_name}' not found in AZURE_MODELS_CONFIG, "
                f"using default deployment: {deployment_name}"
            )

    return AzureChatOpenAI(
        azure_deployment=deployment_name,
        api_version=getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
