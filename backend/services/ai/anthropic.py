from os import getenv
from typing import Optional

from langchain_anthropic import ChatAnthropic

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if Anthropic provider is available (API key configured)."""
    api_key = getenv("ANTHROPIC_API_KEY")
    return api_key is not None and api_key != ""


def get_available_models() -> list[ModelInfo]:
    """Get list of available Anthropic models with pricing information.

    Pricing as of February 2026 (per 1M tokens in USD):
    Source: Anthropic API pricing page

    Phase 1 Enhancements:
    - context_window: Claude 3+ models have 200K+ token context windows
    - supports_parallel_tool_calls: True for Claude 3.5+ models
    - tool_calling_quality: Based on observed performance
    - reasoning_capability: Based on model tier
    """
    return [
        ModelInfo(
            name="claude-4-opus-20260207",
            max_tokens=4096,
            input_cost_per_million=15.00,
            output_cost_per_million=75.00,
            cache_cost_per_million=3.75,
            description="Claude 4 Opus - Most powerful model for highly complex tasks",
            supports_tools=True,
            supports_vision=True,
            context_window=200000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="claude-4-5-sonnet-20260207",
            max_tokens=4096,
            input_cost_per_million=3.00,
            output_cost_per_million=15.00,
            cache_cost_per_million=0.75,
            description="Claude 4.5 Sonnet - Best balance of speed and intelligence",
            supports_tools=True,
            supports_vision=True,
            context_window=200000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="claude-4-5-haiku-20260207",
            max_tokens=4096,
            input_cost_per_million=0.25,
            output_cost_per_million=1.25,
            cache_cost_per_million=0.0625,
            description="Claude 4.5 Haiku - Fastest and most cost-effective model",
            supports_tools=True,
            supports_vision=True,
            context_window=200000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            input_cost_per_million=3.00,
            output_cost_per_million=15.00,
            cache_cost_per_million=0.75,
            description="Claude 3.5 Sonnet (v2) - High intelligence and speed",
            supports_tools=True,
            supports_vision=True,
            context_window=200000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="claude-3-5-haiku-20241022",
            max_tokens=8192,
            input_cost_per_million=0.25,
            output_cost_per_million=1.25,
            cache_cost_per_million=0.0625,
            description="Claude 3.5 Haiku - Fast and capable model",
            supports_tools=True,
            supports_vision=False,
            context_window=200000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
    ]


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get ChatAnthropic instance.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Specific model to use (overrides env var)

    Returns:
        ChatAnthropic instance configured with the specified model
    """
    # Use provided model_name, fall back to env var, or default
    model = model_name or getenv("ANTHROPIC_MODEL", "claude-4-5-sonnet-20260207")

    return ChatAnthropic(
        model=model,
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
