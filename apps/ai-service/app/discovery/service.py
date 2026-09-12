from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from app.ai.schemas import SearchResult
from app.config import Settings, get_settings
from app.discovery.providers.firecrawl import FirecrawlSearchProvider
from app.discovery.providers.mock import MockSearchProvider

logger = logging.getLogger(__name__)


class SearchAuthError(Exception):
    """Raised when the configured search provider rejects credentials."""


@dataclass
class SearchManyResult:
    results: list[SearchResult]
    failures: int = 0
    query_count: int = 0
    auth_failed: bool = False
    provider: str = "unknown"
    used_mock_fallback: bool = False
    error: str | None = None


def get_search_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    provider = (settings.search_provider or "firecrawl").lower()
    if provider == "mock":
        logger.info("search provider=MockSearchProvider")
        return MockSearchProvider()
    if provider == "firecrawl":
        if not settings.firecrawl_api_key:
            logger.info("search provider=MockSearchProvider (no FIRECRAWL_API_KEY)")
            return MockSearchProvider()
        logger.info("search provider=FirecrawlSearchProvider")
        return FirecrawlSearchProvider(settings)
    raise ValueError(f"Unsupported search provider: {provider}")


def _is_auth_error(exc: BaseException) -> bool:
    if isinstance(exc, SearchAuthError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {401, 403}
    text = str(exc).lower()
    return "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text


async def search_many(
    provider,
    queries: list[str],
    *,
    limit_per_query: int = 8,
    concurrency: int = 4,
) -> SearchManyResult:
    from app.utils.retry import gather_limited

    logger.info(
        "search_many start queries=%s limit_per_query=%s concurrency=%s provider=%s",
        len(queries),
        limit_per_query,
        concurrency,
        type(provider).__name__,
    )
    started = time.perf_counter()

    async def _tracked(index: int, query: str):
        q_started = time.perf_counter()
        logger.info("search query[%s/%s] start: %s", index + 1, len(queries), query)
        try:
            from app.ai.usage import incr

            incr("search_requests")
            batch = await provider.search(query, limit=limit_per_query)
            logger.info(
                "search query[%s/%s] done results=%s elapsed_ms=%s",
                index + 1,
                len(queries),
                len(batch) if isinstance(batch, list) else 0,
                int((time.perf_counter() - q_started) * 1000),
            )
            return batch
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "search query[%s/%s] failed elapsed_ms=%s error=%s",
                index + 1,
                len(queries),
                int((time.perf_counter() - q_started) * 1000),
                exc,
            )
            raise

    batches = await gather_limited(
        [_tracked(i, q) for i, q in enumerate(queries)],
        limit=concurrency,
    )
    results: list[SearchResult] = []
    failures = 0
    auth_failed = False
    for batch in batches:
        if isinstance(batch, Exception):
            failures += 1
            if _is_auth_error(batch):
                auth_failed = True
            continue
        if isinstance(batch, list):
            results.extend(batch)

    seen: set[str] = set()
    unique: list[SearchResult] = []
    for item in results:
        key = item.url.rstrip("/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)

    logger.info(
        "search_many done unique_results=%s raw_results=%s failures=%s elapsed_ms=%s",
        len(unique),
        len(results),
        failures,
        int((time.perf_counter() - started) * 1000),
    )
    error = None
    if auth_failed:
        error = "Search provider rejected credentials (401/403)."
    elif failures and not unique:
        error = f"All {failures} search queries failed."
    elif failures:
        error = f"{failures} of {len(queries)} search queries failed."

    return SearchManyResult(
        results=unique,
        failures=failures,
        query_count=len(queries),
        auth_failed=auth_failed,
        provider=type(provider).__name__,
        error=error,
    )


async def search_with_fallback(
    provider,
    queries: list[str],
    *,
    limit_per_query: int = 8,
    concurrency: int = 4,
) -> SearchManyResult:
    batch = await search_many(
        provider,
        queries,
        limit_per_query=limit_per_query,
        concurrency=concurrency,
    )
    should_fallback = (
        not isinstance(provider, MockSearchProvider)
        and (batch.auth_failed or (batch.failures == len(queries) and not batch.results))
    )
    if not should_fallback:
        return batch

    logger.warning(
        "search falling back to mock provider auth_failed=%s failures=%s results=%s",
        batch.auth_failed,
        batch.failures,
        len(batch.results),
    )
    mock_batch = await search_many(
        MockSearchProvider(),
        queries,
        limit_per_query=limit_per_query,
        concurrency=concurrency,
    )
    mock_batch.used_mock_fallback = True
    mock_batch.error = (
        (batch.error or "Live search failed") + " Fell back to mock fixture results."
    )
    return mock_batch
