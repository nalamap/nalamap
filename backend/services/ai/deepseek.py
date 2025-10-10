# Implementation for DeepSeek
from os import getenv
from typing import Optional

from langchain_openai import ChatOpenAI

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if DeepSeek provider is available (API key configured)."""
    api_key = getenv("DEEPSEEK_API_KEY")
    return api_key is not None and api_key != ""


def get_available_models() -> list[ModelInfo]:
    """Get list of available DeepSeek models with pricing information.

    Pricing as of October 2025 (per 1M tokens in USD):
    Source: DeepSeek pricing page
    """
    return [
        ModelInfo(
            name="deepseek-chat",
            max_tokens=4096,
            input_cost_per_million=0.14,
            output_cost_per_million=0.28,
            cache_cost_per_million=0.014,
            description="DeepSeek Chat - General purpose chat model",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="deepseek-coder",
            max_tokens=4096,
            input_cost_per_million=0.14,
            output_cost_per_million=0.28,
            cache_cost_per_million=0.014,
            description="DeepSeek Coder - Specialized coding model",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="deepseek-reasoner",
            max_tokens=8192,
            input_cost_per_million=0.55,
            output_cost_per_million=2.19,
            cache_cost_per_million=0.014,
            description="DeepSeek Reasoner - Advanced reasoning capabilities",
            supports_tools=True,
            supports_vision=False,
        ),
    ]


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get ChatOpenAI instance configured for DeepSeek.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Specific model to use (overrides env var)

    Returns:
        ChatOpenAI instance configured for DeepSeek API
    """
    # Use provided model_name, fall back to env var, or default
    model = model_name or getenv("DEEPSEEK_MODEL", "deepseek-chat")

    return ChatOpenAI(
        model=model,
        base_url="https://api.deepseek.com",
        api_key=getenv("DEEPSEEK_API_KEY"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
