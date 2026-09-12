from __future__ import annotations

import pytest

from app.ai.schemas import CompanyCandidate, SearchResult
from app.companies.deduplicator import deduplicate_candidates
from app.companies.resolver import CompanyResolver
from app.config import Settings
from app.db.supabase import Database
from app.discovery.providers.mock import MockSearchProvider
from app.discovery.query_generator import generate_queries
from app.discovery.service import get_search_provider, search_many
from app.workflows.search_discovery import SearchDiscoveryService


def test_generate_queries_includes_signal_categories():
    queries = generate_queries(industries=["SaaS", "AI"], year=2026)
    joined = " | ".join(queries).lower()
    assert "raised seed round" in joined or "raised funding" in joined
    assert "sdr" in joined or "sales development" in joined
    assert "expanding" in joined or "go-to-market" in joined
    assert "reddit.com" in joined
    assert len(queries) == len(set(queries))


def test_generate_queries_includes_keywords():
    queries = generate_queries(industries=["SaaS"], keywords=["dentists marketing"], year=2026)
    joined = " | ".join(queries).lower()
    assert "dentists marketing" in joined


@pytest.mark.asyncio
async def test_mock_search_provider_returns_normalized_results():
    provider = MockSearchProvider()
    results = await provider.search('"raised seed round" SaaS startup 2026', limit=5)
    assert results
    assert all(isinstance(r, SearchResult) for r in results)
    assert all(r.source == "mock" for r in results)
    assert all(r.url.startswith("http") for r in results)


def test_get_search_provider_falls_back_to_mock_without_key(monkeypatch):
    settings = Settings(search_provider="firecrawl", firecrawl_api_key="")
    provider = get_search_provider(settings)
    assert isinstance(provider, MockSearchProvider)


def test_firecrawl_search_normalizes_v2_payload():
    from app.discovery.providers.firecrawl import FirecrawlSearchProvider

    provider = FirecrawlSearchProvider(Settings(firecrawl_api_key="fc-test"))
    results = provider._normalize(
        {
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://acme.ai/careers",
                        "title": "Acme AI Careers",
                        "description": "Hiring SDRs",
                    }
                ],
                "news": [
                    {
                        "url": "https://techcrunch.com/acme-ai-seed",
                        "title": "Acme AI raises seed",
                        "description": "Seed round announced",
                    }
                ],
            },
        }
    )
    assert len(results) == 2
    assert all(r.source == "firecrawl" for r in results)
    assert results[0].url.startswith("https://")


def test_heuristic_resolver_extracts_company_from_publisher_article():
    settings = Settings(llm_api_key="", candidate_confidence_threshold=0.55)
    resolver = CompanyResolver(settings)
    result = SearchResult(
        title="Acme AI raises $4.2M seed to accelerate go-to-market",
        url="https://techcrunch.com/2026/08/acme-ai-seed",
        snippet="Acme AI, a B2B sales enablement startup (acme.ai), raised a $4.2M seed round.",
        published_at=None,
        source="mock",
    )
    candidate = resolver.resolve_heuristic(result)
    assert candidate is not None
    assert "acme" in candidate.company_name.lower()
    assert candidate.company_domain == "acme.ai"


def test_heuristic_resolver_uses_company_site_domain():
    settings = Settings(llm_api_key="")
    resolver = CompanyResolver(settings)
    result = SearchResult(
        title="We're hiring SDRs | Acme AI Careers",
        url="https://acme.ai/careers",
        snippet="Acme AI is hiring three Sales Development Representatives.",
        published_at=None,
        source="mock",
    )
    candidate = resolver.resolve_heuristic(result)
    assert candidate is not None
    assert candidate.company_domain == "acme.ai"
    assert candidate.confidence >= 0.7


def test_deduplicate_by_domain_and_name():
    candidates = [
        CompanyCandidate(
            company_name="Acme AI",
            company_domain="acme.ai",
            source_url="https://acme.ai/careers",
            confidence=0.9,
        ),
        CompanyCandidate(
            company_name="Acme AI Inc",
            company_domain="www.acme.ai",
            source_url="https://techcrunch.com/acme",
            confidence=0.7,
        ),
        CompanyCandidate(
            company_name="Helix Stack",
            company_domain="helixstack.dev",
            source_url="https://helixstack.dev/careers",
            confidence=0.8,
        ),
    ]
    deduped = deduplicate_candidates(candidates)
    assert len(deduped) == 2
    domains = {c.company_domain for c in deduped}
    assert "acme.ai" in domains or any(
        (c.company_domain or "").endswith("acme.ai") for c in deduped
    )


@pytest.mark.asyncio
async def test_phase3_search_discovery_end_to_end_without_supabase(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    # Clear cached settings / clients so monkeypatched env is honored
    from app.ai.openrouter import get_chat_openrouter
    from app.config import get_settings
    from app.db.supabase import get_supabase

    get_settings.cache_clear()
    get_supabase.cache_clear()
    get_chat_openrouter.cache_clear()

    service = SearchDiscoveryService(db=Database(client=None))
    result = await service.run(
        run_id="00000000-0000-0000-0000-000000000099",
        industries=["SaaS", "AI"],
        max_companies=10,
        persist=True,
        discovery_only=True,
    )
    assert result.status == "completed"
    assert result.queries
    assert result.search_results
    assert result.companies
    assert result.saved_companies
    assert all(c.get("normalized_domain") for c in result.saved_companies)


@pytest.mark.asyncio
async def test_search_many_dedupes_urls():
    provider = MockSearchProvider()
    results = await search_many(
        provider,
        [
            '"raised seed round" SaaS',
            '"raised funding" AI',
            '"raised seed round" SaaS',
        ],
        limit_per_query=5,
    )
    urls = [r.url.rstrip("/").lower() for r in results.results]
    assert len(urls) == len(set(urls))
