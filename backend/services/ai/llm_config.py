import os

llm_provider = os.getenv("LLM_PROVIDER").lower()

if llm_provider == "openai":
    from .openai import get_llm
elif llm_provider == "azure":
    from .azureai import get_llm
elif llm_provider == "anthropic":
    from .anthropic import get_llm
elif llm_provider == "deepseek":
    from .deepseek import get_llm
else:
    raise ValueError(f"Unsupported LLM provider: {llm_provider}")
