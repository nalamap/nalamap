# Implementation for Mistral AI
from os import getenv

from langchain_mistralai import ChatMistralAI


def get_llm(max_tokens: int = 6000):
    return ChatMistralAI(
        model=getenv("MISTRAL_MODEL", "mistral-large-latest"),
        temperature=0,
        max_tokens=max_tokens,
        max_retries=3,
    )
