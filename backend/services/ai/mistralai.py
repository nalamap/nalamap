# Implementation for Mistral AI
from os import getenv
from typing import Optional

from langchain_mistralai import ChatMistralAI

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if Mistral AI provider is available (API key configured)."""
    api_key = getenv("MISTRAL_API_KEY")
    return api_key is not None and api_key != ""


def get_available_models() -> list[ModelInfo]:
    """Get list of available Mistral AI models with pricing information.

    Pricing as of October 2025 (per 1M tokens in USD):
    Source: Mistral AI pricing page

    Phase 1 Enhancements:
    - context_window: Based on Mistral AI documentation (32K for most models)
    - supports_parallel_tool_calls: True for latest models
    - tool_calling_quality: Based on observed performance
    - reasoning_capability: Based on model tier
    """
    return [
        ModelInfo(
            name="mistral-large-latest",
            max_tokens=8192,
            input_cost_per_million=2.00,
            output_cost_per_million=6.00,
            cache_cost_per_million=None,
            description="Mistral Large - Most capable model for complex reasoning",
            supports_tools=True,
            supports_vision=False,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="mistral-medium-latest",
            max_tokens=8192,
            input_cost_per_million=0.70,
            output_cost_per_million=2.10,
            cache_cost_per_million=None,
            description="Mistral Medium - Balanced performance model",
            supports_tools=True,
            supports_vision=False,
            context_window=32000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="mistral-small-latest",
            max_tokens=8192,
            input_cost_per_million=0.20,
            output_cost_per_million=0.60,
            cache_cost_per_million=None,
            description="Mistral Small - Fast and cost-effective model",
            supports_tools=True,
            supports_vision=False,
            context_window=32000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="intermediate",
        ),
        ModelInfo(
            name="open-mistral-7b",
            max_tokens=8192,
            input_cost_per_million=0.15,
            output_cost_per_million=0.15,
            cache_cost_per_million=None,
            description="Open Mistral 7B - Open-source efficient model",
            supports_tools=True,
            supports_vision=False,
            context_window=32000,
            supports_parallel_tool_calls=False,
            tool_calling_quality="basic",
            reasoning_capability="basic",
        ),
        ModelInfo(
            name="open-mixtral-8x7b",
            max_tokens=8192,
            input_cost_per_million=0.50,
            output_cost_per_million=0.50,
            cache_cost_per_million=None,
            description="Open Mixtral 8x7B - Open-source mixture-of-experts model",
            supports_tools=True,
            supports_vision=False,
            context_window=32000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="intermediate",
        ),
    ]


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get ChatMistralAI instance.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Specific model to use (overrides env var)

    Returns:
        ChatMistralAI instance configured with the specified model
    """
    # Use provided model_name, fall back to env var, or default
    model = model_name or getenv("MISTRAL_MODEL", "mistral-large-latest")

    return ChatMistralAI(
        model=model,
        temperature=0,
        max_tokens=max_tokens,
        max_retries=3,
    )
