"""Unified interface for querying all LLM providers."""

import logging
from typing import Dict, List

from models.model_info import ModelInfo, ProviderInfo

logger = logging.getLogger(__name__)


def get_all_providers() -> Dict[str, ProviderInfo]:
    """Get information about all LLM providers and their availability.

    Returns:
        Dictionary mapping provider name to ProviderInfo with availability
        status and available models.
    """
    providers: Dict[str, ProviderInfo] = {}

    # OpenAI
    try:
        from services.ai import openai

        is_available = openai.is_available()
        models: List[ModelInfo] = openai.get_available_models() if is_available else []

        providers["openai"] = ProviderInfo(
            name="openai",
            display_name="OpenAI",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load OpenAI provider: {e}")
        providers["openai"] = ProviderInfo(
            name="openai",
            display_name="OpenAI",
            available=False,
            models=[],
            error_message=str(e),
        )

    # Azure OpenAI
    try:
        from services.ai import azureai

        is_available = azureai.is_available()
        models = azureai.get_available_models() if is_available else []

        providers["azure"] = ProviderInfo(
            name="azure",
            display_name="Azure OpenAI",
            available=is_available,
            models=models,
            error_message=None if is_available else "Azure credentials not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Azure OpenAI provider: {e}")
        providers["azure"] = ProviderInfo(
            name="azure",
            display_name="Azure OpenAI",
            available=False,
            models=[],
            error_message=str(e),
        )

    # Google Gemini
    try:
        from services.ai import google_genai

        is_available = google_genai.is_available()
        models = google_genai.get_available_models() if is_available else []

        providers["google"] = ProviderInfo(
            name="google",
            display_name="Google Gemini",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Google Gemini provider: {e}")
        providers["google"] = ProviderInfo(
            name="google",
            display_name="Google Gemini",
            available=False,
            models=[],
            error_message=str(e),
        )

    # Mistral AI
    try:
        from services.ai import mistralai

        is_available = mistralai.is_available()
        models = mistralai.get_available_models() if is_available else []

        providers["mistral"] = ProviderInfo(
            name="mistral",
            display_name="Mistral AI",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Mistral AI provider: {e}")
        providers["mistral"] = ProviderInfo(
            name="mistral",
            display_name="Mistral AI",
            available=False,
            models=[],
            error_message=str(e),
        )

    # DeepSeek
    try:
        from services.ai import deepseek

        is_available = deepseek.is_available()
        models = deepseek.get_available_models() if is_available else []

        providers["deepseek"] = ProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load DeepSeek provider: {e}")
        providers["deepseek"] = ProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            available=False,
            models=[],
            error_message=str(e),
        )

    return providers


def get_provider_by_name(provider_name: str) -> ProviderInfo:
    """Get information about a specific provider.

    Args:
        provider_name: Name of the provider (e.g., "openai", "google")

    Returns:
        ProviderInfo for the specified provider

    Raises:
        ValueError: If provider name is not recognized
    """
    providers = get_all_providers()
    if provider_name not in providers:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available providers: {', '.join(providers.keys())}"
        )
    return providers[provider_name]
