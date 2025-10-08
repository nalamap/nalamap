# Implementation for Google Generative AI
from os import getenv

from langchain_google_genai import ChatGoogleGenerativeAI


def get_llm(max_tokens: int = 6000):
    return ChatGoogleGenerativeAI(
        model=getenv("GOOGLE_MODEL", "gemini-1.5-pro-latest"),
        temperature=0,
        max_output_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
