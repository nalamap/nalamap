# Implementation for Google Generative AI
from os import getenv
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if Google AI provider is available (API key configured)."""
    api_key = getenv("GOOGLE_API_KEY")
    return api_key is not None and api_key != ""


def get_available_models() -> list[ModelInfo]:
    """Get list of available Google Gemini models with pricing information.

    Pricing as of October 2025 (per 1M tokens in USD):
    Source: Google AI pricing page
    """
    return [
        ModelInfo(
            name="gemini-1.5-pro-latest",
            max_tokens=8192,
            input_cost_per_million=1.25,
            output_cost_per_million=5.00,
            cache_cost_per_million=0.3125,
            description="Gemini 1.5 Pro - Most capable multimodal model",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gemini-1.5-flash",
            max_tokens=8192,
            input_cost_per_million=0.075,
            output_cost_per_million=0.30,
            cache_cost_per_million=0.01875,
            description="Gemini 1.5 Flash - Fast and efficient model",
            supports_tools=True,
            supports_vision=True,
        ),
        ModelInfo(
            name="gemini-1.0-pro",
            max_tokens=8192,
            input_cost_per_million=0.50,
            output_cost_per_million=1.50,
            cache_cost_per_million=None,
            description="Gemini 1.0 Pro - Previous generation model",
            supports_tools=True,
            supports_vision=False,
        ),
        ModelInfo(
            name="gemini-2.0-flash-exp",
            max_tokens=8192,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            cache_cost_per_million=None,
            description="Gemini 2.0 Flash Experimental - Free preview of next-gen model",
            supports_tools=True,
            supports_vision=True,
        ),
    ]


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get ChatGoogleGenerativeAI instance.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Specific model to use (overrides env var)

    Returns:
        ChatGoogleGenerativeAI instance configured with the specified model
    """
    # Use provided model_name, fall back to env var, or default
    model = model_name or getenv("GOOGLE_MODEL", "gemini-1.5-pro-latest")

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0,
        max_output_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
