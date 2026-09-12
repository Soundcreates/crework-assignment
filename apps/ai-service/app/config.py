from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    frontend_url: str = "http://localhost:3000"

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # OpenRouter is the LLM provider. OPENROUTER_API_KEY preferred; LLM_API_KEY accepted as alias.
    openrouter_api_key: str = ""
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"
    llm_fallback_model: str = "openrouter/free"
    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_requests_per_minute: int = 15
    llm_max_tokens: int = 1500

    # firecrawl | mock  (firecrawl auto-falls back to mock when FIRECRAWL_API_KEY is empty)
    search_provider: str = "firecrawl"
    firecrawl_api_key: str = ""

    max_company_concurrency: int = 2
    max_pages_per_company: int = 3
    max_resolve_ai: int = 6
    crawl_timeout_seconds: float = 15.0
    max_response_bytes: int = 1_500_000
    candidate_confidence_threshold: float = 0.55
    stale_run_minutes: int = 15
    discovery_schedule_seconds: int = 0
    signal_recheck_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
