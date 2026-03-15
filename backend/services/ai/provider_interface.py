"""Unified interface for querying all LLM providers."""

import logging
import os
from typing import Dict, List

from models.model_info import ModelInfo, ProviderInfo

logger = logging.getLogger(__name__)


def get_all_providers() -> Dict[str, ProviderInfo]:
    """Get information about all LLM providers and their availability.

    Returns:
        Dictionary mapping provider name to ProviderInfo with availability
        status and available models. Order is determined by DEFAULT_LLM_PROVIDER
        or LLM_PROVIDER environment variable if set.
    """
    providers_unordered: Dict[str, ProviderInfo] = {}

    # OpenAI
    try:
        from services.ai import openai

        is_available = openai.is_available()
        models: List[ModelInfo] = openai.get_available_models() if is_available else []

        providers_unordered["openai"] = ProviderInfo(
            name="openai",
            display_name="OpenAI",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load OpenAI provider: {e}")
        providers_unordered["openai"] = ProviderInfo(
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

        providers_unordered["azure"] = ProviderInfo(
            name="azure",
            display_name="Azure OpenAI",
            available=is_available,
            models=models,
            error_message=None if is_available else "Azure credentials not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Azure OpenAI provider: {e}")
        providers_unordered["azure"] = ProviderInfo(
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

        providers_unordered["google"] = ProviderInfo(
            name="google",
            display_name="Google Gemini",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Google Gemini provider: {e}")
        providers_unordered["google"] = ProviderInfo(
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

        providers_unordered["mistral"] = ProviderInfo(
            name="mistral",
            display_name="Mistral AI",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Mistral AI provider: {e}")
        providers_unordered["mistral"] = ProviderInfo(
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

        providers_unordered["deepseek"] = ProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load DeepSeek provider: {e}")
        providers_unordered["deepseek"] = ProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            available=False,
            models=[],
            error_message=str(e),
        )

    # Anthropic
    try:
        from services.ai import anthropic

        is_available = anthropic.is_available()
        models = anthropic.get_available_models() if is_available else []

        providers_unordered["anthropic"] = ProviderInfo(
            name="anthropic",
            display_name="Anthropic",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Anthropic provider: {e}")
        providers_unordered["anthropic"] = ProviderInfo(
            name="anthropic",
            display_name="Anthropic",
            available=False,
            models=[],
            error_message=str(e),
        )

    # Moonshot AI (Kimi)
    try:
        from services.ai import moonshot

        is_available = moonshot.is_available()
        models = moonshot.get_available_models() if is_available else []

        providers_unordered["moonshot"] = ProviderInfo(
            name="moonshot",
            display_name="Moonshot AI (Kimi)",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load Moonshot AI provider: {e}")
        providers_unordered["moonshot"] = ProviderInfo(
            name="moonshot",
            display_name="Moonshot AI (Kimi)",
            available=False,
            models=[],
            error_message=str(e),
        )

    # xAI (Grok)
    try:
        from services.ai import xai

        is_available = xai.is_available()
        models = xai.get_available_models() if is_available else []

        providers_unordered["xai"] = ProviderInfo(
            name="xai",
            display_name="xAI (Grok)",
            available=is_available,
            models=models,
            error_message=None if is_available else "API key not configured",
        )
    except Exception as e:
        logger.warning(f"Failed to load xAI provider: {e}")
        providers_unordered["xai"] = ProviderInfo(
            name="xai",
            display_name="xAI (Grok)",
            available=False,
            models=[],
            error_message=str(e),
        )

    # Order providers based on DEFAULT_LLM_PROVIDER or LLM_PROVIDER env var
    # The first provider in the ordered dict will be selected by default in the UI
    preferred_provider = (
        os.getenv("DEFAULT_LLM_PROVIDER", "").lower().strip()
        or os.getenv("LLM_PROVIDER", "").lower().strip()
    )

    # If a preferred provider is set and exists, put it first
    providers: Dict[str, ProviderInfo] = {}
    if preferred_provider and preferred_provider in providers_unordered:
        providers[preferred_provider] = providers_unordered[preferred_provider]
        logger.info(f"Prioritizing provider '{preferred_provider}' as default")

    # Add remaining providers in their original order
    for name, info in providers_unordered.items():
        if name not in providers:
            providers[name] = info

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
