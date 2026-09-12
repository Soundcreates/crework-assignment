"""Firecrawl HTTP client for search-adjacent scrape operations."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings


class FirecrawlClient:
    """Primary page scraper via Firecrawl /v2/scrape."""

    def __init__(self, settings: Settings):
        self.api_key = settings.firecrawl_api_key
        self.base_url = "https://api.firecrawl.dev/v2/scrape"
        self.timeout_seconds = max(settings.crawl_timeout_seconds, 45.0)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def scrape_markdown(self, url: str) -> str | None:
        if not self.enabled:
            return None
        try:
            return await self._scrape_with_retry(url)
        except Exception:  # noqa: BLE001
            return None

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)
        ),
    )
    async def _scrape_with_retry(self, url: str) -> str | None:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            if response.status_code in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            if response.status_code >= 400:
                return None
            data = response.json()

        body = data.get("data", data)
        markdown = None
        if isinstance(body, dict):
            markdown = body.get("markdown")
        return markdown.strip() if isinstance(markdown, str) and markdown.strip() else None
