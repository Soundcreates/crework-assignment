from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import Settings, get_settings

DEFAULT_MODEL = "openai/gpt-4o-mini"
FALLBACK_FREE_MODEL = "openrouter/free"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def resolve_openrouter_api_key(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return (settings.openrouter_api_key or settings.llm_api_key or "").strip()


def resolve_openrouter_model(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return (settings.llm_model or DEFAULT_MODEL).strip()


def _build_chat(settings: Settings, model: str | None = None) -> ChatOpenAI | None:
    api_key = resolve_openrouter_api_key(settings)
    if not api_key:
        return None
    chosen = (model or resolve_openrouter_model(settings)).strip()
    max_tokens = getattr(settings, "llm_max_tokens", 1500)
    return ChatOpenAI(
        api_key=api_key,
        base_url=(settings.llm_base_url or DEFAULT_BASE_URL).strip(),
        model=chosen,
        temperature=0,
        max_tokens=max_tokens,
        max_retries=0,
        extra_body={"provider": {"require_parameters": True}},
        default_headers={
            "HTTP-Referer": settings.frontend_url or "http://localhost:3000",
            "X-Title": "Lead Intelligence",
        },
    )


@lru_cache
def get_chat_openrouter() -> ChatOpenAI | None:
    return _build_chat(get_settings())


def build_chat_openrouter(settings: Settings | None = None, model: str | None = None) -> ChatOpenAI | None:
    """Non-cached factory useful in tests."""
    return _build_chat(settings or get_settings(), model=model)
