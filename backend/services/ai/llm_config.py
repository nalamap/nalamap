import os
from typing import Optional

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
else:
    raise ValueError(f"Unsupported LLM provider: {llm_provider}")


def get_llm_for_provider(
    provider_name: str, max_tokens: int = 6000, model_name: Optional[str] = None
):
    """Get LLM instance for a specific provider with validated max_tokens.

    Args:
        provider_name: Provider identifier (openai, azure, google, mistral, deepseek)
        max_tokens: Maximum tokens to generate (will be validated against model's limit)
        model_name: Specific model to use (optional, provider-specific default if not provided)

    Returns:
        LLM instance for the specified provider

    Raises:
        ValueError: If provider_name is not recognized
    """
    provider_name = provider_name.lower()

    # Validate and clamp max_tokens to model's limit
    validated_max_tokens = _validate_max_tokens(provider_name, max_tokens, model_name)

    if provider_name == "openai":
        from .openai import get_llm as openai_get_llm

        return openai_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
    elif provider_name == "azure":
        from .azureai import get_llm as azure_get_llm

        return azure_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
    elif provider_name == "google":
        from .google_genai import get_llm as google_get_llm

        return google_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
    elif provider_name == "mistral":
        from .mistralai import get_llm as mistral_get_llm

        return mistral_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
    elif provider_name == "deepseek":
        from .deepseek import get_llm as deepseek_get_llm

        return deepseek_get_llm(max_tokens=validated_max_tokens, model_name=model_name)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. "
            "Supported providers: openai, azure, google, mistral, deepseek"
        )


def _validate_max_tokens(
    provider_name: str, max_tokens: int, model_name: Optional[str] = None
) -> int:
    """Validate max_tokens against model's maximum limit.

    Args:
        provider_name: Provider identifier
        max_tokens: Requested max tokens
        model_name: Specific model name (optional)

    Returns:
        Validated max_tokens (clamped to model's limit if necessary)
    """
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
        else:
            # Unknown provider, return original value
            return max_tokens

        models = get_available_models()

        # Find the specific model or use first model as default
        target_model = None
        if model_name:
            target_model = next((m for m in models if m.name == model_name), None)

        if not target_model and models:
            # No specific model found, use first available
            target_model = models[0]

        if target_model:
            # Validate max_tokens
            if max_tokens <= 0 or max_tokens > target_model.max_tokens:
                # Invalid or exceeds limit, use model's default
                return target_model.max_tokens

        return max_tokens

    except Exception:
        # If anything fails, return original max_tokens (fail-safe)
        return max_tokens
