from os import getenv
from langchain_openai import ChatOpenAI


def get_llm(max_tokens: int = 6000):
    api_key = getenv("OPENAI_API_KEY")
    if not api_key:
        # For testing/development without AI features
        api_key = "sk-test-key-not-set"
    return ChatOpenAI(
        model=getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
        api_key=api_key,
    )
