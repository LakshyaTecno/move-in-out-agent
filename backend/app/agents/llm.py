"""Gemini models. Free-tier quotas are per model and small (a few requests per
minute), so calls fail over along a chain of models, each with its own quota,
instead of waiting out a rate limit."""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

DEFAULT_MODELS = "gemini-3.8-flash,gemini-3.5-flash,gemini-3.1-flash-lite,gemini-flash-lite-latest"


class LLMUnavailable(Exception):
    pass


def model_names() -> list[str]:
    return [m.strip() for m in os.getenv("GEMINI_MODELS", DEFAULT_MODELS).split(",") if m.strip()]


def _model(name: str) -> ChatGoogleGenerativeAI:
    # No retries: on a 429 it's faster to move to the next model.
    return ChatGoogleGenerativeAI(model=name, temperature=0, max_retries=0, timeout=40)


def get_models() -> list[ChatGoogleGenerativeAI]:
    """Primary model first, then fallbacks."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise LLMUnavailable("GOOGLE_API_KEY is not set")
    return [_model(name) for name in model_names()]
