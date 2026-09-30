"""Gemini models. Free-tier quotas are per model and small (a few requests per
minute, shared by everyone using the key), so calls fail over along a chain of
models, each with its own quota, instead of waiting out a rate limit.

The two agents use different chains because they need different things:
- chat makes several calls per turn, so it leads with the fastest model;
- review is one call per submission where judgement matters most, so it leads
  with the strongest model."""

import os

from langchain_google_genai import ChatGoogleGenerativeAI

DEFAULT_CHAINS = {
    "chat": "gemini-3.1-flash-lite,gemini-3.8-flash,gemini-flash-lite-latest",
    "review": "gemini-3.8-flash,gemini-3.1-flash-lite,gemini-flash-lite-latest",
}


class LLMUnavailable(Exception):
    pass


def model_names(purpose: str) -> list[str]:
    raw = os.getenv(f"GEMINI_{purpose.upper()}_MODELS", DEFAULT_CHAINS[purpose])
    return [m.strip() for m in raw.split(",") if m.strip()]


def _model(name: str) -> ChatGoogleGenerativeAI:
    # No retries and a short timeout: on a 429 or a stall, the next model is faster.
    return ChatGoogleGenerativeAI(model=name, temperature=0, max_retries=0, timeout=20)


def get_models(purpose: str) -> list[ChatGoogleGenerativeAI]:
    """Primary model first, then fallbacks."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise LLMUnavailable("GOOGLE_API_KEY is not set")
    return [_model(name) for name in model_names(purpose)]
