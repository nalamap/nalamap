from os import getenv
from typing import Optional

from langchain_openai import ChatOpenAI

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if OpenAI provider is available (API key configured)."""
    api_key = getenv("OPENAI_API_KEY")
    return api_key is not None and api_key != "" and api_key != "sk-test-key-not-set"


def get_available_models() -> list[ModelInfo]:
    """Get list of available OpenAI models with pricing information.

    Pricing as of February 2026 (per 1M tokens in USD):
    Source: OpenAI API pricing page

    Phase 1 Enhancements:
    - context_window: Based on OpenAI documentation
    - supports_parallel_tool_calls: True for models supporting parallel function calling
    - tool_calling_quality: Based on observed performance and capabilities
    - reasoning_capability: Based on model tier and observed reasoning performance
    """
    return [
        ModelInfo(
            name="gpt-5.5",
            max_tokens=128000,
            input_cost_per_million=1.00,
            output_cost_per_million=8.00,
            cache_cost_per_million=0.10,
            description="GPT-5.5 - Most capable model for extremely complex reasoning and planning",
            supports_tools=True,
            supports_vision=True,
            context_window=1000000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="gpt-5.5-mini",
            max_tokens=128000,
            input_cost_per_million=0.15,
            output_cost_per_million=0.60,
            cache_cost_per_million=0.015,
            description="GPT-5.5 Mini - Balanced high performance and low cost",
            supports_tools=True,
            supports_vision=True,
            context_window=1000000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="gpt-5",
            max_tokens=128000,
            input_cost_per_million=1.25,
            output_cost_per_million=10.00,
            cache_cost_per_million=0.125,
            description="GPT-5 - Most capable model for complex tasks",
            supports_tools=True,
            supports_vision=True,
            context_window=400000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="gpt-5-chat-latest",
            max_tokens=128000,
            input_cost_per_million=1.25,
            output_cost_per_million=10.00,
            cache_cost_per_million=0.125,
            description="GPT-5 Chat Latest - Always updated chat model",
            supports_tools=True,
            supports_vision=True,
            context_window=400000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        # ModelInfo( # not capable of chat/completions
        #    name="gpt-5-codex",
        #    max_tokens=128000,
        #    input_cost_per_million=1.25,
        #    output_cost_per_million=10.00,
        #    cache_cost_per_million=0.125,
        #    description="GPT-5 Codex - Optimized for code generation",
        #    supports_tools=True,
        #    supports_vision=False,
        #    context_window=400000,
        #    supports_parallel_tool_calls=True,
        #    tool_calling_quality="excellent",
        #    reasoning_capability="expert",
        # ),
        # ModelInfo( # too expensive
        #    name="gpt-5-pro",
        #    max_tokens=128000,
        #    input_cost_per_million=15.00,
        #    output_cost_per_million=120.00,
        #    cache_cost_per_million=None,
        #    description="GPT-5 Pro - Premium model for expert-level tasks",
        #    supports_tools=True,
        #    supports_vision=True,
        #    context_window=400000,
        #    supports_parallel_tool_calls=True,
        #    tool_calling_quality="excellent",
        #    reasoning_capability="expert",
        # ),
        ModelInfo(
            name="o1-mini",
            max_tokens=65536,
            input_cost_per_million=1.10,
            output_cost_per_million=4.40,
            cache_cost_per_million=0.55,
            description="o1-mini — compact reasoning model with strong math/coding skills",
            supports_tools=True,
            supports_vision=False,
            context_window=128000,
            supports_parallel_tool_calls=False,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="o3-mini",
            max_tokens=100000,
            input_cost_per_million=1.10,
            output_cost_per_million=4.40,
            cache_cost_per_million=0.55,
            description="o3-mini — cost-efficient reasoning model optimized for STEM and coding",
            supports_tools=True,
            supports_vision=False,
            context_window=200000,
            supports_parallel_tool_calls=False,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="gpt-4.1",
            max_tokens=32768,
            input_cost_per_million=2.00,
            output_cost_per_million=8.00,
            cache_cost_per_million=0.50,
            description="GPT-4.1 - Enhanced GPT-4 model",
            supports_tools=True,
            supports_vision=True,
            context_window=1000000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="gpt-4o",
            max_tokens=16384,
            input_cost_per_million=2.50,
            output_cost_per_million=10.00,
            cache_cost_per_million=1.25,
            description="GPT-4o - Multimodal model with vision",
            supports_tools=True,
            supports_vision=True,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="gpt-4o-2024-05-13",
            max_tokens=16384,
            input_cost_per_million=5.00,
            output_cost_per_million=20.00,
            cache_cost_per_million=2.50,
            description="GPT-4o (2024-05-13) - Specific snapshot version",
            supports_tools=True,
            supports_vision=True,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="gpt-realtime",
            max_tokens=16384,
            input_cost_per_million=4.00,
            output_cost_per_million=16.00,
            cache_cost_per_million=0.40,
            description="GPT-5 Realtime - Optimized for streaming responses",
            supports_tools=True,
            supports_vision=False,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="gpt-realtime-mini",
            max_tokens=16384,
            input_cost_per_million=0.60,
            output_cost_per_million=2.40,
            cache_cost_per_million=0.06,
            description="GPT-5 Realtime Mini - Efficient streaming model",
            supports_tools=True,
            supports_vision=False,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="intermediate",
        ),
        ModelInfo(
            name="gpt-4o-realtime-preview",
            max_tokens=16384,
            input_cost_per_million=5.00,
            output_cost_per_million=20.00,
            cache_cost_per_million=2.50,
            description="GPT-4o Realtime Preview - Preview streaming model",
            supports_tools=True,
            supports_vision=True,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="expert",
        ),
        ModelInfo(
            name="gpt-4o-mini-realtime-preview",
            max_tokens=16384,
            input_cost_per_million=0.60,
            output_cost_per_million=2.40,
            cache_cost_per_million=0.30,
            description="GPT-4o Mini Realtime Preview - Preview mini streaming model",
            supports_tools=True,
            supports_vision=True,
            context_window=128000,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
    ]


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get ChatOpenAI instance.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Specific model to use (overrides env var)

    Returns:
        ChatOpenAI instance configured with the specified model
    """
    api_key = getenv("OPENAI_API_KEY")
    if not api_key:
        # For testing/development without AI features
        api_key = "sk-test-key-not-set"

    # Use provided model_name, fall back to env var, or default
    model = model_name or getenv("OPENAI_MODEL", "gpt-4.1-mini")

    return ChatOpenAI(
        model=model,
        temperature=1,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
        api_key=api_key,
    )
