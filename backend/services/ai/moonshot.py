from os import getenv
from typing import Optional

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if Moonshot AI (Kimi) provider is available (API key configured)."""
    api_key = getenv("MOONSHOT_API_KEY")
    return api_key is not None and api_key != ""


def get_llm(max_tokens: int = 4096, model_name: Optional[str] = None):
    """Factory function to get a Moonshot AI LLM instance via ChatOpenAI."""
    from langchain_openai import ChatOpenAI

    if not model_name:
        model_name = "kimi-k2.5"

    return ChatOpenAI(
        model=model_name,
        openai_api_key=getenv("MOONSHOT_API_KEY"),
        openai_api_base="https://api.moonshot.cn/v1",
        max_tokens=max_tokens,
        temperature=0.7,
    )


def get_available_models() -> list[ModelInfo]:
    """Get list of available Moonshot AI (Kimi) models with pricing information.

    Base URL: https://api.moonshot.cn/v1

    Pricing as of February 2026 (approximate USD conversion from RMB, 1 USD ≈ 7.2 RMB):
    Source: Moonshot AI platform pricing page
    """
    return [
        ModelInfo(
            name="kimi-k2.5",
            max_tokens=4096,  # Typical output limit, though context is large
            input_cost_per_million=0.10,  # ¥0.70
            output_cost_per_million=0.56,  # ¥4.00
            description="Kimi k2.5 - Latest multimodal model with enhanced reasoning",
            supports_tools=True,
            supports_vision=True,
            context_window=262144,  # 256k
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="kimi-k2-turbo",
            max_tokens=4096,
            input_cost_per_million=0.14,  # ¥1.00
            output_cost_per_million=1.11,  # ¥8.00
            description="Kimi k2 Turbo - High speed, low latency model",
            supports_tools=True,
            supports_vision=False,
            context_window=262144,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
        ModelInfo(
            name="moonshot-v1-128k",
            max_tokens=4096,
            input_cost_per_million=1.39,  # ¥10.00
            output_cost_per_million=4.17,  # ¥30.00
            description="Moonshot v1 (128k) - Large context window for document processing",
            supports_tools=True,
            supports_vision=False,
            context_window=131072,  # 128k
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="good",
        ),
        ModelInfo(
            name="moonshot-v1-32k",
            max_tokens=4096,
            input_cost_per_million=0.69,  # ¥5.00
            output_cost_per_million=2.78,  # ¥20.00
            description="Moonshot v1 (32k) - Balanced context and cost",
            supports_tools=True,
            supports_vision=False,
            context_window=32768,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="good",
        ),
        ModelInfo(
            name="moonshot-v1-8k",
            max_tokens=4096,
            input_cost_per_million=0.28,  # ¥2.00
            output_cost_per_million=1.39,  # ¥10.00
            description="Moonshot v1 (8k) - Cost effective for short tasks",
            supports_tools=True,
            supports_vision=False,
            context_window=8192,
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="good",
        ),
    ]
