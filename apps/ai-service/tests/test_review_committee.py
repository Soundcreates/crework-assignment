from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.rate_limiter import parse_rate_limit_wait, is_rate_limit_error
from app.ai.schemas import SearchResult
from app.companies.icp import ICPFilter, matches_icp
from app.companies.resolver import (
    CompanyResolver,
    is_listicle_title,
    rank_search_results,
)
from app.config import Settings
from app.crawling.crawler import DEFAULT_PATHS
from app.db import supabase as supabase_mod
from app.db.supabase import Database
from app.runtime import should_enable_reload
from app.workflows.discovery_graph import finalize_status, resolve_budget_for

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = Path(__file__).resolve().parents[1]


def test_p0_default_model_is_not_openrouter_free():
    assert Settings.model_fields["llm_model"].default != "openrouter/free"
    assert Settings.model_fields["llm_fallback_model"].default == "openrouter/free"
    assert Settings.model_fields["max_company_concurrency"].default <= 2
    assert Settings.model_fields["max_pages_per_company"].default == 3
    assert Settings.model_fields["llm_requests_per_minute"].default <= 20


def test_p0_rate_limit_header_parsing():
    wait = parse_rate_limit_wait({"X-RateLimit-Reset": "3", "Retry-After": "4"})
    assert wait >= 4
    wait_reset = parse_rate_limit_wait({"x-ratelimit-reset": "2.5"})
    assert wait_reset >= 2.5

    class Fake:
        def __init__(self):
            self.response = type("R", (), {"status_code": 429, "headers": {}})()

    assert is_rate_limit_error(Fake())


@pytest.mark.asyncio
async def test_p0_shared_limiter_caps_burst():
    from app.ai.rate_limiter import TokenBucketLimiter
    import time

    limiter = TokenBucketLimiter(rate_per_minute=2, window_seconds=0.2)
    t0 = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    waited = await limiter.acquire()
    elapsed = time.monotonic() - t0
    assert waited > 0 or elapsed >= 0.04


def test_p0_signals_extracted_in_one_call():
    text = Path(AI_ROOT / "app/companies/processor.py").read_text()
    assert "extract_signals_from_pages" in text
    assert "for page in source_texts[:4]" not in text


def test_p0_resolver_rejects_listicles_and_publishers():
    assert is_listicle_title("31K+ Funded United States Startups 2026 | Startup Database")
    assert is_listicle_title("Find GPU Infrastructure Companies | B2B Prospecting 2026")
    settings = Settings(llm_api_key="", openrouter_api_key="")
    resolver = CompanyResolver(settings)
    rejected = resolver.resolve_heuristic(
        SearchResult(
            title="31K+ Funded United States Startups 2026 | Startup Database",
            url="https://startupdatabase.com/list",
            snippet="Directory of funded companies",
            source="firecrawl",
        )
    )
    assert rejected is None
    publisher = resolver.resolve_heuristic(
        SearchResult(
            title="Daily funding roundup",
            url="https://entrackr.com/news/roundup",
            snippet="Oracle, Avalara and others",
            source="firecrawl",
        )
    )
    assert publisher is None


def test_p0_database_none_is_offline(monkeypatch):
    called = {"n": 0}

    def boom():
        called["n"] += 1
        raise AssertionError("get_supabase should not be called")

    monkeypatch.setattr(supabase_mod, "get_supabase", boom)
    db = Database(client=None)
    assert db.client is None
    assert Database.offline().client is None
    assert called["n"] == 0


def test_p1_contacts_migration_path():
    assert (ROOT / "supabase/migrations/002_contacts.sql").exists()
    assert not (ROOT / "apps/supabase").exists()
    assert (ROOT / "supabase/migrations/003_review_fixes.sql").exists()


def test_p1_get_discovery_run_filters_by_run():
    text = (AI_ROOT / "app/api/discovery.py").read_text()
    assert "list_companies_for_run" in text
    assert 'provider="unknown"' not in text


def test_p1_reload_off_by_default():
    assert should_enable_reload({}) is False
    assert should_enable_reload({"UVICORN_RELOAD": "1"}) is True
    main = (AI_ROOT / "app/main.py").read_text()
    assert "reload=True" not in main
    assert "fail_stale_runs" in main


def test_p1_search_ranked_before_cap():
    results = [
        SearchResult(
            title="31K+ Funded United States Startups 2026 | Startup Database",
            url="https://startupdatabase.com/x",
            snippet="directory",
            source="firecrawl",
        ),
        SearchResult(
            title="Acme AI raises seed and is hiring SDRs",
            url="https://acme.ai/careers",
            snippet="hiring",
            source="firecrawl",
        ),
    ]
    ranked = rank_search_results(results)
    assert ranked[0].url.endswith("acme.ai/careers")
    assert resolve_budget_for(5, 110) <= 12
    assert resolve_budget_for(5, 110) >= 8


def test_p1_crawler_defaults():
    assert DEFAULT_PATHS == ["/", "/about", "/careers"]
    crawler = (AI_ROOT / "app/crawling/crawler.py").read_text()
    assert "gather_limited" in crawler


def test_p2_finalize_completed_with_errors():
    assert (
        finalize_status(
            error=None,
            saved_companies=[{"id": "1"}],
            companies=[{"x": 1}],
            companies_failed=1,
            ai_failures=2,
        )
        == "completed_with_errors"
    )
    assert (
        finalize_status(
            error=None,
            saved_companies=[{"id": "1"}],
            companies=[{"x": 1}],
            companies_failed=0,
            ai_failures=0,
        )
        == "completed"
    )


def test_p2_icp_filter_and_schedule_workflow():
    icp = ICPFilter(stages=["seed"], industries=["saas"])
    assert matches_icp(industry="B2B SaaS", stage="Seed", icp=icp)
    assert matches_icp(industry=None, stage="Seed", icp=icp)
    assert matches_icp(industry="Fintech", stage="Seed", icp=icp)
    assert not matches_icp(industry="mining", stage="public", icp=icp)
    assert (ROOT / ".github/workflows/scheduled-discovery.yml").exists()


def test_p2_frontend_enrich_and_empty_state():
    web = ROOT / "apps/web/src"
    api = (web / "lib/api/ai-service.ts").read_text()
    dash = (web / "components/dashboard/dashboard-view.tsx").read_text()
    nxt = (web / "../next.config.ts").read_text()
    assert "export async function enrichCompany" in api
    assert "enrichUnscored" in api
    assert "Enrich unscored" in dash
    assert "EMPTY_LEADS_CTA" in dash
    assert "allowedDevOrigins" in nxt
    assert "PAGE_SIZE" in dash
    assert "mock" in dash.lower()


def test_p3_readme_and_deploy_configs():
    readme = (ROOT / "README.md").read_text()
    assert "V1" in readme and "V2" in readme
    assert (AI_ROOT / "Dockerfile").exists()
    assert (ROOT / "render.yaml").exists()


def test_processor_ast_no_per_page_signal_loop():
    source = (AI_ROOT / "app/companies/processor.py").read_text()
    assert "extract_signals_from_pages" in source
    assert "for page in source_texts[:4]" not in source
