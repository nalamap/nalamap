# Implementation for Anthropic AI
from os import getenv
from langchain_anthropic import ChatAnthropic


def get_llm(max_tokens: int = 6000):
    return ChatAnthropic(
        model=getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
