import os

from langchain_google_genai import ChatGoogleGenerativeAI


class LLMUnavailable(Exception):
    pass


def get_llm() -> ChatGoogleGenerativeAI:
    if not os.getenv("GOOGLE_API_KEY"):
        raise LLMUnavailable("GOOGLE_API_KEY is not set")
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        temperature=0,
        max_retries=2,
        timeout=40,
    )
