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

    Pricing as of October 2025 (per 1M tokens in USD):
    Source: OpenAI API pricing page
    """
    return [
        ModelInfo(
            name="gpt-5",
            max_tokens=50000,
            input_cost_per_million=1.25,
            output_cost_per_million=0.125,
            cache_cost_per_million=10.00,
            description="GPT-5 - Most capable model for complex tasks",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-5-mini",
            max_tokens=100000,
            input_cost_per_million=0.25,
            output_cost_per_million=0.025,
            cache_cost_per_million=2.00,
            description="GPT-5 Mini - Balanced performance and cost",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-5-nano",
            max_tokens=50000,
            input_cost_per_million=0.05,
            output_cost_per_million=0.005,
            cache_cost_per_million=0.40,
            description="GPT-5 Nano - Fast and efficient for simple tasks",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="gpt-5-chat-latest",
            max_tokens=50000,
            input_cost_per_million=1.25,
            output_cost_per_million=0.125,
            cache_cost_per_million=10.00,
            description="GPT-5 Chat Latest - Always updated chat model",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-5-codex",
            max_tokens=50000,
            input_cost_per_million=1.25,
            output_cost_per_million=0.125,
            cache_cost_per_million=10.00,
            description="GPT-5 Codex - Optimized for code generation",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="gpt-5-pro",
            max_tokens=50000,
            input_cost_per_million=15.00,
            output_cost_per_million=None,
            cache_cost_per_million=120.00,
            description="GPT-5 Pro - Premium model for expert-level tasks",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4.1",
            max_tokens=50000,
            input_cost_per_million=2.00,
            output_cost_per_million=0.50,
            cache_cost_per_million=8.00,
            description="GPT-4.1 - Enhanced GPT-4 model",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4.1-mini",
            max_tokens=50000,
            input_cost_per_million=0.40,
            output_cost_per_million=0.10,
            cache_cost_per_million=1.60,
            description="GPT-4.1 Mini - Efficient GPT-4.1 variant",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4.1-nano",
            max_tokens=50000,
            input_cost_per_million=0.10,
            output_cost_per_million=0.025,
            cache_cost_per_million=0.40,
            description="GPT-4.1 Nano - Lightweight GPT-4.1 variant",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="gpt-4o",
            max_tokens=50000,
            input_cost_per_million=2.50,
            output_cost_per_million=1.25,
            cache_cost_per_million=10.00,
            description="GPT-4o - Multimodal model with vision",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4o-2024-05-13",
            max_tokens=50000,
            input_cost_per_million=5.00,
            output_cost_per_million=None,
            cache_cost_per_million=15.00,
            description="GPT-4o (2024-05-13) - Specific snapshot version",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4o-mini",
            max_tokens=50000,
            input_cost_per_million=0.15,
            output_cost_per_million=0.075,
            cache_cost_per_million=0.60,
            description="GPT-4o Mini - Cost-effective multimodal model",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-realtime",
            max_tokens=50000,
            input_cost_per_million=4.00,
            output_cost_per_million=0.40,
            cache_cost_per_million=16.00,
            description="GPT Realtime - Optimized for streaming responses",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="gpt-realtime-mini",
            max_tokens=50000,
            input_cost_per_million=0.60,
            output_cost_per_million=0.06,
            cache_cost_per_million=2.40,
            description="GPT Realtime Mini - Efficient streaming model",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="gpt-4o-realtime-preview",
            max_tokens=50000,
            input_cost_per_million=5.00,
            output_cost_per_million=2.50,
            cache_cost_per_million=20.00,
            description="GPT-4o Realtime Preview - Preview streaming model",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gpt-4o-mini-realtime-preview",
            max_tokens=50000,
            input_cost_per_million=0.60,
            output_cost_per_million=0.30,
            cache_cost_per_million=2.40,
            description="GPT-4o Mini Realtime Preview - Preview mini streaming model",
            supports_tools=True,
            supports_vision=True,
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
    model = model_name or getenv("OPENAI_MODEL", "gpt-5-mini")

    return ChatOpenAI(
        model=model,
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
        api_key=api_key,
    )
