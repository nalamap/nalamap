# Implementation for Azure AI
from os import getenv
from typing import Optional

from langchain_openai import AzureChatOpenAI

from models.model_info import ModelInfo


def is_available() -> bool:
    """Check if Azure OpenAI provider is available (credentials configured)."""
    endpoint = getenv("AZURE_OPENAI_ENDPOINT")
    api_key = getenv("AZURE_OPENAI_API_KEY")
    deployment = getenv("AZURE_OPENAI_DEPLOYMENT")
    return all([endpoint, api_key, deployment])


def get_available_models() -> list[ModelInfo]:
    """Get list of available Azure OpenAI models.

    Azure OpenAI uses deployment-based models. The actual model depends on
    what the user has deployed in their Azure OpenAI resource.
    We return the configured deployment as a single "model".

    Note: Pricing varies by region and deployment. User should check their
    Azure pricing page for accurate costs.

    Phase 1 Enhancements:
    - context_window: Conservative default (128K for GPT-4/GPT-4o deployments)
    - supports_parallel_tool_calls: True (most Azure deployments support this)
    - tool_calling_quality: "good" as default (depends on underlying model)
    - reasoning_capability: "advanced" as default (depends on underlying model)
    """
    deployment = getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")

    return [
        ModelInfo(
            name=deployment,
            max_tokens=6000,
            input_cost_per_million=None,  # Varies by region and deployment
            output_cost_per_million=None,
            cache_cost_per_million=None,
            description=f"Azure OpenAI deployment: {deployment}",
            supports_tools=True,
            supports_vision=False,  # Depends on deployment
            context_window=128000,  # Conservative default for modern deployments
            supports_parallel_tool_calls=True,
            tool_calling_quality="good",
            reasoning_capability="advanced",
        ),
    ]


def get_llm(max_tokens: int = 6000, model_name: Optional[str] = None):
    """Get AzureChatOpenAI instance.

    Args:
        max_tokens: Maximum tokens to generate
        model_name: Not used for Azure (deployment is pre-configured)

    Returns:
        AzureChatOpenAI instance configured with the deployment
    """
    return AzureChatOpenAI(
        azure_deployment=getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
