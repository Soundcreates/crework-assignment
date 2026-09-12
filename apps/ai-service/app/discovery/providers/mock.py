from __future__ import annotations

from datetime import datetime

from app.ai.schemas import SearchResult


class MockSearchProvider:
    """Deterministic search results for local Phase 3 development without API keys."""

    FIXTURES: dict[str, list[dict[str, str]]] = {
        "funding": [
            {
                "title": "Acme AI raises $4.2M seed to accelerate go-to-market",
                "url": "https://techcrunch.com/2026/08/acme-ai-seed",
                "snippet": "Acme AI, a B2B sales enablement startup (acme.ai), raised a $4.2M seed round.",
            },
            {
                "title": "Helix Stack announces $22M Series A",
                "url": "https://techcrunch.com/2026/08/helix-stack-series-a",
                "snippet": "Helix Stack (helixstack.dev) announced a $22M Series A to scale AI agent APIs.",
            },
            {
                "title": "Northstar Labs raises $18M Series A to scale sales",
                "url": "https://www.northstarlabs.io/blog/series-a",
                "snippet": "Northstar Labs closed an $18M Series A led by top-tier investors.",
            },
        ],
        "hiring": [
            {
                "title": "We're hiring SDRs | Acme AI Careers",
                "url": "https://acme.ai/careers",
                "snippet": "Acme AI is hiring three Sales Development Representatives.",
            },
            {
                "title": "Business Development Representative - Helix Stack",
                "url": "https://helixstack.dev/careers/bdr",
                "snippet": "Building our sales team — hiring Business Development Representatives.",
            },
            {
                "title": "Account Executive roles at Northstar Labs",
                "url": "https://northstarlabs.io/jobs/ae",
                "snippet": "We're hiring Account Executives to build our sales team.",
            },
        ],
        "growth": [
            {
                "title": "Expanding into North America - Acme AI Blog",
                "url": "https://acme.ai/blog/north-america",
                "snippet": "Expanding into North America with a dedicated outbound team.",
            },
            {
                "title": "Brightpath Commerce launches in new US markets",
                "url": "https://brightpath.com/blog/us-expansion",
                "snippet": "Brightpath Commerce is launching in new markets across the United States.",
            },
            {
                "title": "International expansion | Helix Stack",
                "url": "https://helixstack.dev/blog/europe",
                "snippet": "International expansion into Germany, France, and the UK.",
            },
        ],
    }

    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        q = query.lower()
        bucket = "funding"
        if any(token in q for token in ("sdr", "hiring", "account executive", "bdr", "sales team")):
            bucket = "hiring"
        elif any(token in q for token in ("expand", "market", "go-to-market", "international")):
            bucket = "growth"

        rows = self.FIXTURES[bucket][:limit]
        return [
            SearchResult(
                title=row["title"],
                url=row["url"],
                snippet=row["snippet"],
                published_at=datetime(2026, 8, 20),
                source="mock",
            )
            for row in rows
        ]
