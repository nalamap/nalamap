import os

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
