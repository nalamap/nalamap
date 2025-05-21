from langchain_openai import ChatOpenAI
from os import getenv

def get_llm(max_tokens: int = 6000):
    return ChatOpenAI(
        model="gpt-4.1-nano",
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )

