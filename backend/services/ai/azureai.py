# Implementation for Azure AI
from langchain_openai import AzureChatOpenAI
from os import getenv

def get_llm(max_tokens: int = 6000):
    return AzureChatOpenAI(
        azure_deployment=getenv("AZURE_OPENAI_DEPLOYMENT"),
        api_version=getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=3,
    )
