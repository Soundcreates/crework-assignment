from __future__ import annotations

import logging
import time
from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.ai.schemas import SearchResult
from app.config import Settings

logger = logging.getLogger(__name__)


class FirecrawlSearchProvider:
    """Firecrawl /v2/search adapter normalized into SearchResult."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.firecrawl_api_key
        self.base_url = "https://api.firecrawl.dev/v2/search"

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not self.api_key:
            logger.warning("Firecrawl search skipped: missing API key")
            return []
        return await self._search_with_retry(query, limit)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)
        ),
    )
    async def _search_with_retry(self, query: str, limit: int) -> list[SearchResult]:
        payload = {
            "query": query,
            "limit": limit,
            "sources": [{"type": "web"}, {"type": "news"}],
            "ignoreInvalidURLs": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            if response.status_code in {429, 500, 502, 503, 504}:
                logger.warning(
                    "Firecrawl retryable status=%s query=%r",
                    response.status_code,
                    query[:80],
                )
                response.raise_for_status()
            response.raise_for_status()
            data = response.json()

        results = self._normalize(data)
        logger.info(
            "Firecrawl ok status=%s results=%s elapsed_ms=%s query=%r",
            response.status_code,
            len(results),
            int((time.perf_counter() - started) * 1000),
            query[:80],
        )
        return results

    def _normalize(self, payload: dict) -> list[SearchResult]:
        data = payload.get("data", payload)
        rows: list[dict] = []

        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("web", "news"):
                items = data.get(key) or []
                if isinstance(items, list):
                    rows.extend(items)

        results: list[SearchResult] = []
        for item in rows:
            url = item.get("url") or ""
            if not url:
                continue
            published_at = None
            raw_date = item.get("publishedDate") or item.get("published_date")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(
                        str(raw_date).replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None
            results.append(
                SearchResult(
                    title=item.get("title") or url,
                    url=url,
                    snippet=item.get("description")
                    or item.get("snippet")
                    or item.get("markdown"),
                    published_at=published_at,
                    source="firecrawl",
                )
            )
        return results
