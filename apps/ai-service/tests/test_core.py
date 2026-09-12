from datetime import datetime, timedelta, timezone

from app.companies.normalizer import normalize_company_name, normalize_domain
from app.crawling.url_safety import UnsafeURLError, validate_public_http_url
from app.ai.schemas import IntentSignal
from app.scoring.scorer import calculate_score, recency_multiplier
from app.scoring.weights import SIGNAL_WEIGHTS
import pytest


def test_normalize_domain():
    assert normalize_domain("https://www.acme.ai/about") == "acme.ai"
    assert normalize_domain("http://acme.ai") == "acme.ai"
    assert normalize_domain("acme.ai") == "acme.ai"


def test_normalize_company_name():
    assert normalize_company_name("Acme AI, Inc.") == "acme ai"


def test_url_safety_blocks_localhost():
    with pytest.raises(UnsafeURLError):
        validate_public_http_url("http://127.0.0.1/secret")
    with pytest.raises(UnsafeURLError):
        validate_public_http_url("http://localhost:8000")
    assert validate_public_http_url("https://acme.ai/careers") == "https://acme.ai/careers"


def test_recency_multiplier():
    now = datetime(2026, 9, 9, tzinfo=timezone.utc)
    assert recency_multiplier(now - timedelta(days=10), now) == 1.0
    assert recency_multiplier(now - timedelta(days=45), now) == 0.8
    assert recency_multiplier(now - timedelta(days=120), now) == 0.55
    assert recency_multiplier(now - timedelta(days=200), now) == 0.3
    assert recency_multiplier(None, now) == 0.6


def test_intent_scoring_funding_and_hiring():
    now = datetime(2026, 9, 9, tzinfo=timezone.utc)
    signals = [
        IntentSignal(
            signal_type="funding",
            strength=0.9,
            evidence="raised seed",
            explanation="funding",
            occurred_at=now - timedelta(days=5),
        ),
        IntentSignal(
            signal_type="sales_hiring",
            strength=0.95,
            evidence="hiring SDRs",
            explanation="hiring",
            occurred_at=now - timedelta(days=3),
        ),
    ]
    result = calculate_score(signals, estimated_stage="Seed", now=now)
    assert result.intent_score >= 60
    assert result.intent_level in {"HIGH", "MEDIUM HIGH"}
    assert "other_growth" in SIGNAL_WEIGHTS


@pytest.mark.asyncio
async def test_search_with_fallback_on_auth_error():
    import httpx

    from app.discovery.service import search_with_fallback

    class AuthFailProvider:
        async def search(self, query: str, limit: int = 10):
            request = httpx.Request("POST", "https://api.firecrawl.dev/v2/search")
            response = httpx.Response(403, request=request)
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    result = await search_with_fallback(
        AuthFailProvider(),
        ['"raised seed round" SaaS'],
        limit_per_query=3,
        concurrency=1,
    )
    assert result.used_mock_fallback
    assert result.results
    assert result.provider == "MockSearchProvider"


@pytest.mark.asyncio
async def test_process_company_extracts_signals_and_score():
    from app.ai.schemas import (
        CompanyCandidate,
        CompanyProfile,
        ContactExtractionResult,
        IntentSignal,
        SignalExtractionResult,
    )
    from app.companies.processor import process_company
    from app.db.supabase import Database

    class FakeCrawler:
        async def crawl_company(self, website: str):
            return [{"url": website, "text": "We raised seed and are hiring SDRs."}]

    class FakeAI:
        async def enrich_profile(self, name, pages):
            return CompanyProfile(name=name, website="https://acme.ai", estimated_stage="Seed")

        async def extract_signals_from_pages(self, name, pages):
            return (
                SignalExtractionResult(
                    signals=[
                        IntentSignal(
                            signal_type="funding",
                            strength=0.9,
                            evidence="raised seed",
                            explanation="funding",
                        ),
                        IntentSignal(
                            signal_type="sales_hiring",
                            strength=0.9,
                            evidence="hiring SDRs",
                            explanation="hiring",
                        ),
                    ]
                ),
                0,
            )

        async def extract_signals(self, *args, **kwargs):
            result, _ = await self.extract_signals_from_pages("Acme", [])
            return result

        async def extract_contacts(self, *args, **kwargs):
            return ContactExtractionResult(contacts=[])

        async def summarize(self, profile, signals, score, level):
            return f"{profile.name} scored {score}"

    saved = await process_company(
        CompanyCandidate(
            company_name="Acme AI",
            company_domain="acme.ai",
            source_url="https://acme.ai/careers",
            confidence=0.9,
        ),
        db=Database(client=None),
        ai=FakeAI(),  # type: ignore[arg-type]
        crawler=FakeCrawler(),  # type: ignore[arg-type]
    )
    assert saved is not None
    assert saved["ok"] is True
    assert saved["intent_score"] >= 40
    assert saved["ai_summary"]

    from app.companies.icp import ICPFilter

    class FintechAI(FakeAI):
        async def enrich_profile(self, name, pages):
            profile = await super().enrich_profile(name, pages)
            return profile.model_copy(update={"industry": "Fintech"})

    kept = await process_company(
        CompanyCandidate(
            company_name="Acme AI",
            company_domain="acme.ai",
            source_url="https://acme.ai/careers",
            confidence=0.9,
        ),
        db=Database(client=None),
        ai=FintechAI(),  # type: ignore[arg-type]
        crawler=FakeCrawler(),  # type: ignore[arg-type]
        icp=ICPFilter(industries=["SaaS", "AI", "Developer Tools"]),
    )
    assert kept is not None
    assert kept.get("ok") is True
    assert kept.get("reason") != "icp"


def test_health_endpoints():
    from starlette.testclient import TestClient
    from app.main import create_app

    client = TestClient(create_app())
    for path in ["/", "/health"]:
        res_get = client.get(path)
        assert res_get.status_code == 200
        assert res_get.json() == {"status": "ok"}

        res_head = client.head(path)
        assert res_head.status_code == 200

