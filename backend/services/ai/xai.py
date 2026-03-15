from os import getenv
from typing import Optional

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if xAI (Grok) provider is available (API key configured)."""
    api_key = getenv("XAI_API_KEY")
    return api_key is not None and api_key != ""


def get_llm(max_tokens: int = 4096, model_name: Optional[str] = None):
    """Factory function to get an xAI (Grok) LLM instance via ChatOpenAI."""
    from langchain_openai import ChatOpenAI

    if not model_name:
        model_name = "grok-2-latest"

    return ChatOpenAI(
        model=model_name,
        openai_api_key=getenv("XAI_API_KEY"),
        openai_api_base="https://api.x.ai/v1",
        max_tokens=max_tokens,
        temperature=0.7,
    )


def get_available_models() -> list[ModelInfo]:
    """Get list of available xAI models with pricing information.

    Base URL: https://api.x.ai/v1

    Pricing as of February 2026 (Estimates based on public beta/docs):
    """
    return [
        ModelInfo(
            name="grok-2-latest",
            max_tokens=4096,
            input_cost_per_million=5.00,  # Estimated based on grok-beta
            output_cost_per_million=15.00,  # Estimated based on grok-beta
            description="Grok 2 - Strong reasoning and multimodal capabilities",
            supports_tools=True,
            supports_vision=True,
            context_window=131072,  # 128k typical
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="grok-2-vision-latest",
            max_tokens=4096,
            input_cost_per_million=5.00,
            output_cost_per_million=15.00,
            description="Grok 2 Vision - Optimized for visual tasks",
            supports_tools=True,
            supports_vision=True,
            context_window=131072,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="grok-4-1-fast-reasoning",
            max_tokens=8192,
            input_cost_per_million=2.00,  # "Low cost" - estimated
            output_cost_per_million=8.00,  # "Low cost" - estimated
            description="Grok 4.1 Fast - Optimized for high-performance agentic tool calling",
            supports_tools=True,
            supports_vision=True,
            context_window=2000000,  # 2M as per docs
            supports_parallel_tool_calls=True,
            tool_calling_quality="excellent",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="grok-beta",
            max_tokens=4096,
            input_cost_per_million=5.00,
            output_cost_per_million=15.00,
            description="Grok Beta - Legacy beta model",
            supports_tools=True,
            supports_vision=False,
            context_window=131072,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="good",
        ),
    ]
