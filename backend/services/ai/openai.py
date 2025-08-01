from os import getenv
from langchain_openai import ChatOpenAI


def get_llm(max_tokens: int = 6000):
    return ChatOpenAI(
        model=getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
