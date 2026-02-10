import os
from typing import Optional, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()


if llm_provider == "openai":
    from .openai import get_llm
elif llm_provider == "azure":
    from .azureai import get_llm
elif llm_provider == "google":
    from .google_genai import get_llm
elif llm_provider == "mistral":
    from .mistralai import get_llm
elif llm_provider == "deepseek":
    from .deepseek import get_llm  # noqa: F401
elif llm_provider == "anthropic":
    from .anthropic import get_llm  # noqa: F401
else:
    raise ValueError(f"Unsupported LLM provider: {llm_provider}")


@dataclass
class ModelCapabilities:
    """Model capabilities metadata extracted during LLM initialization."""

    supports_parallel_tool_calls: bool = False
    context_window: int = 128000
    max_tokens: int = 4096


def get_llm_for_provider(
    provider_name: str, max_tokens: int = 6000, model_name: Optional[str] = None
) -> Tuple:
    """Get LLM instance and capabilities for a specific provider with validated max_tokens.

    Args:
        provider_name: Provider identifier (openai, azure, google, mistral, deepseek)
        max_tokens: Maximum tokens to generate (will be validated against model's limit)
        model_name: Specific model to use (optional, provider-specific default if not provided)

    Returns:
        Tuple of (LLM instance, ModelCapabilities) for the specified provider

    Raises:
        ValueError: If provider_name is not recognized
    """
    provider_name = provider_name.lower()

    # Get model info and validate max_tokens
    validated_max_tokens, capabilities = _validate_max_tokens_and_get_capabilities(
        provider_name, max_tokens, model_name
    )

    if provider_name == "openai":
        from .openai import get_llm as openai_get_llm

        llm = openai_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
        return llm, capabilities
    elif provider_name == "azure":
        from .azureai import get_llm as azure_get_llm

        llm = azure_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
        return llm, capabilities
    elif provider_name == "google":
        from .google_genai import get_llm as google_get_llm

        llm = google_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
        return llm, capabilities
    elif provider_name == "mistral":
        from .mistralai import get_llm as mistral_get_llm

        llm = mistral_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
        return llm, capabilities
    elif provider_name == "deepseek":
        from .deepseek import get_llm as deepseek_get_llm

        llm = deepseek_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
        return llm, capabilities
    elif provider_name == "anthropic":
        from .anthropic import get_llm as anthropic_get_llm

        llm = anthropic_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
        return llm, capabilities
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. "
            "Supported providers: openai, azure, google, mistral, deepseek, anthropic"
        )


def _validate_max_tokens_and_get_capabilities(
    provider_name: str, max_tokens: int, model_name: Optional[str] = None
) -> Tuple[int, ModelCapabilities]:
    """Validate max_tokens and extract model capabilities.

    Args:
        provider_name: Provider identifier
        max_tokens: Requested max tokens
        model_name: Specific model name (optional)

    Returns:
        Tuple of (validated_max_tokens, ModelCapabilities)
    """
    # Default capabilities
    capabilities = ModelCapabilities()

    # Import provider module to get available models
    try:
        if provider_name == "openai":
            from .openai import get_available_models
        elif provider_name == "azure":
            from .azureai import get_available_models
        elif provider_name == "google":
            from .google_genai import get_available_models
        elif provider_name == "mistral":
            from .mistralai import get_available_models
        elif provider_name == "deepseek":
            from .deepseek import get_available_models
        elif provider_name == "anthropic":
            from .anthropic import get_available_models
        else:
            # Unknown provider, return defaults
            return max_tokens, capabilities

        models = get_available_models()

        # Find the specific model or use first model as default
        target_model = None
        if model_name:
            target_model = next((m for m in models if m.name == model_name), None)

        if not target_model and models:
            # No specific model found, use first available
            target_model = models[0]

        if target_model:
            # Extract capabilities from model info
            capabilities = ModelCapabilities(
                supports_parallel_tool_calls=getattr(
                    target_model, "supports_parallel_tool_calls", False
                ),
                context_window=getattr(target_model, "context_window", 128000),
                max_tokens=target_model.max_tokens,
            )

            # Validate max_tokens
            if max_tokens <= 0 or max_tokens > target_model.max_tokens:
                # Invalid or exceeds limit, use model's default
                return target_model.max_tokens, capabilities

        return max_tokens, capabilities

    except Exception:
        # If anything fails, return original max_tokens with default capabilities
        return max_tokens, capabilities


def _validate_max_tokens(
    provider_name: str, max_tokens: int, model_name: Optional[str] = None
) -> int:
    """Validate max_tokens against model's maximum limit.

    DEPRECATED: Use _validate_max_tokens_and_get_capabilities instead.
    This function is kept for backwards compatibility.

    Args:
        provider_name: Provider identifier
        max_tokens: Requested max tokens
        model_name: Specific model name (optional)

    Returns:
        Validated max_tokens (clamped to model's limit if necessary)
    """
    validated_max_tokens, _ = _validate_max_tokens_and_get_capabilities(
        provider_name, max_tokens, model_name
    )
    return validated_max_tokens
