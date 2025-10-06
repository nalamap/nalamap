# Implementation for DeepSeek
from os import getenv

from langchain_openai import ChatOpenAI


def get_llm(max_tokens: int = 6000):
    return ChatOpenAI(
        model=getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url="https://api.deepseek.com",
        api_key=getenv("DEEPSEEK_API_KEY"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
