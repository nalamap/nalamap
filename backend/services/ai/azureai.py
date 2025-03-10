# Implementation for Azure AI
from langchain_community.llms import AzureChatOpenAI
from os import getenv

def get_llm(llm_type: str, llm_model: str, max_tokens: int = 5000):
    if llm_type == "Azure":
        return AzureChatOpenAI(
            azure_deployment=getenv("AZURE_OPENAI_DEPLOYMENT"),
            api_version=getenv("AZURE_OPENAI_API_VERSION"),
            temperature=0,
            max_tokens=max_tokens,
            timeout=None,
            max_retries=3,
        )