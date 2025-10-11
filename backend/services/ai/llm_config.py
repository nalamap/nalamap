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
    """Get LLM instance for a specific provider.

    Args:
        provider_name: Provider identifier (openai, azure, google, mistral, deepseek)
        max_tokens: Maximum tokens to generate
        model_name: Specific model to use (optional, provider-specific default if not provided)

    Returns:
        LLM instance for the specified provider

    Raises:
        ValueError: If provider_name is not recognized
    """
    provider_name = provider_name.lower()

    if provider_name == "openai":
        from .openai import get_llm as openai_get_llm

        return openai_get_llm(max_tokens=max_tokens, model_name=model_name)
    elif provider_name == "azure":
        from .azureai import get_llm as azure_get_llm

        return azure_get_llm(max_tokens=max_tokens, model_name=model_name)
    elif provider_name == "google":
        from .google_genai import get_llm as google_get_llm

        return google_get_llm(max_tokens=max_tokens, model_name=model_name)
    elif provider_name == "mistral":
        from .mistralai import get_llm as mistral_get_llm

        return mistral_get_llm(max_tokens=max_tokens, model_name=model_name)
    elif provider_name == "deepseek":
        from .deepseek import get_llm as deepseek_get_llm

        return deepseek_get_llm(max_tokens=max_tokens, model_name=model_name)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. "
            "Supported providers: openai, azure, google, mistral, deepseek"
        )
