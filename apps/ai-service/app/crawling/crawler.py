from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.ai.usage import incr
from app.config import Settings
from app.crawling.firecrawl import FirecrawlClient
from app.crawling.url_safety import UnsafeURLError, validate_public_http_url
from app.utils.retry import gather_limited

DEFAULT_PATHS = ["/", "/about", "/careers"]


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


class WebsiteCrawler:
    """
    Crawl company pages.

    Primary: Firecrawl scrape
    Fallback: HTTPX + BeautifulSoup (when Firecrawl is unavailable or fails)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.firecrawl = FirecrawlClient(settings)

    async def fetch_text(self, url: str) -> str | None:
        try:
            validate_public_http_url(url)
        except UnsafeURLError:
            return None

        if self.firecrawl.enabled:
            markdown = await self.firecrawl.scrape_markdown(url)
            if markdown:
                return markdown[:12_000]

        return await self._fetch_httpx(url)

    async def _fetch_httpx(self, url: str) -> str | None:
        timeout = httpx.Timeout(self.settings.crawl_timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": "LeadIntelligenceBot/0.1 (+internal)"},
        ) as client:
            try:
                response = await client.get(url)
            except httpx.HTTPError:
                return None
            if response.status_code >= 400:
                return None
            content = response.content[: self.settings.max_response_bytes]
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                return None
            return clean_html(
                content.decode(response.encoding or "utf-8", errors="ignore")
            )

    async def crawl_company(self, website: str) -> list[dict[str, str]]:
        domain = website if "://" in website else f"https://{website}"
        try:
            validate_public_http_url(domain)
        except UnsafeURLError:
            return []

        parsed = urlparse(domain)
        base = f"{parsed.scheme}://{parsed.netloc}"
        paths = DEFAULT_PATHS[: self.settings.max_pages_per_company]
        urls = [urljoin(base, path) for path in paths]

        async def _one(url: str) -> dict[str, str] | None:
            incr("crawl_requests")
            text = await self.fetch_text(url)
            if not text:
                return None
            return {"url": url, "text": text[:12_000]}

        outcomes = await gather_limited([_one(url) for url in urls], limit=min(3, len(urls) or 1))
        pages: list[dict[str, str]] = []
        for outcome in outcomes:
            if isinstance(outcome, dict):
                pages.append(outcome)
        return pages
