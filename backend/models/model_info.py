"""Data models for LLM provider and model information."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """Information about a specific LLM model including capabilities and pricing.

    Attributes:
        name: Model identifier (e.g., "gpt-5-mini", "gemini-1.5-pro")
        max_tokens: Maximum number of tokens the model can generate
        input_cost_per_million: Cost per 1M input tokens in USD (optional)
        output_cost_per_million: Cost per 1M output tokens in USD (optional)
        cache_cost_per_million: Cost per 1M cached tokens in USD (optional, for cache reads)
        description: Human-readable description of the model (optional)
        supports_tools: Whether the model supports function/tool calling
        supports_vision: Whether the model supports vision/image inputs
        context_window: Maximum context window in tokens (input + output combined)
        supports_parallel_tool_calls: Supports calling multiple tools in a single response
        tool_calling_quality: Quality rating of function calling implementation
        reasoning_capability: Model's reasoning and planning capabilities
    """

    name: str = Field(..., description="Model identifier")
    max_tokens: int = Field(..., ge=1, description="Maximum output tokens")
    input_cost_per_million: Optional[float] = Field(
        None, ge=0, description="Cost per 1M input tokens (USD)"
    )
    output_cost_per_million: Optional[float] = Field(
        None, ge=0, description="Cost per 1M output tokens (USD)"
    )
    cache_cost_per_million: Optional[float] = Field(
        None, ge=0, description="Cost per 1M cached tokens (USD)"
    )
    description: Optional[str] = Field(None, description="Model description")
    supports_tools: bool = Field(True, description="Supports function/tool calling")
    supports_vision: bool = Field(False, description="Supports vision/image inputs")

    # Phase 1: Critical fields for LangGraph ReAct agents
    context_window: int = Field(
        128000, ge=1, description="Maximum context window in tokens (input + output)"
    )
    supports_parallel_tool_calls: bool = Field(
        False, description="Supports calling multiple tools in a single response"
    )
    tool_calling_quality: Literal["none", "basic", "good", "excellent"] = Field(
        "basic", description="Quality of function calling implementation"
    )
    reasoning_capability: Literal["basic", "intermediate", "advanced", "expert"] = Field(
        "intermediate", description="Model's reasoning and planning capabilities"
    )


class ProviderInfo(BaseModel):
    """Information about an LLM provider.

    Attributes:
        name: Provider identifier (e.g., "openai", "google", "azure")
        display_name: Human-readable provider name
        available: Whether the provider is currently available (API key configured)
        models: List of models available from this provider
        error_message: Error message if provider is not available (optional)
    """

    name: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Human-readable provider name")
    available: bool = Field(..., description="Provider is configured and available")
    models: list[ModelInfo] = Field(default_factory=list, description="Available models")
    error_message: Optional[str] = Field(None, description="Error if unavailable")
