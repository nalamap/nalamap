from langchain_community.llms import ChatOpenAI

def initlialize_openai_llm(model_name: str, max_tokens: int) -> ChatOpenAI:
    return ChatOpenAI(model_name=model_name, max_tokens=max_tokens)
