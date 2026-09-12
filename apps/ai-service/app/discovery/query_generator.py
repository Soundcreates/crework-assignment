from __future__ import annotations

from datetime import UTC, datetime

DEFAULT_INDUSTRIES = ["SaaS", "AI", "Developer Tools", "B2B"]


def generate_queries(
    industries: list[str] | None = None,
    country: str | None = None,
    year: int | None = None,
    keywords: list[str] | None = None,
) -> list[str]:
    industries = industries or DEFAULT_INDUSTRIES
    year = year or datetime.now(UTC).year
    geo = f" {country}" if country else ""
    keywords = [k.strip() for k in (keywords or []) if k and k.strip()]

    funding = [
        f'"raised seed round" {industry} startup {year}{geo}'
        for industry in industries
    ] + [
        f'"raised funding" B2B {industry}{geo}' for industry in industries[:2]
    ] + [
        f'"series A" sales software {year}{geo}',
        f'"seed funding" startup {year}{geo}',
    ]

    hiring = [
        f'"we\'re hiring SDR" {industry}{geo}' for industry in industries[:2]
    ] + [
        '"sales development representative" startup',
        '"business development representative" startup',
        '"building our sales team" SaaS',
        '"hiring account executives" startup',
    ]

    growth = [
        f'"expanding into the US" {industry}{geo}' for industry in industries[:2]
    ] + [
        '"expanding our sales team"',
        '"launching in new markets" SaaS',
        '"scaling go-to-market"',
        '"international expansion" SaaS',
    ]

    demand = [
        '"looking for sales agency" startup',
        '"need help with outbound" SaaS',
        '"looking for appointment setting"',
        'site:reddit.com "need an SDR agency" OR "appointment setting"',
        'site:news.ycombinator.com "outbound sales" hiring OR agency',
        'site:linkedin.com/posts "looking for appointment setting"',
    ]

    keyword_queries = [
        f'"{keyword}" {industry}{geo}'
        for keyword in keywords[:6]
        for industry in industries[:2]
    ] + [
        f'site:reddit.com "{keyword}" sales OR outbound'
        for keyword in keywords[:3]
    ]

    seen: set[str] = set()
    queries: list[str] = []
    for q in funding + hiring + growth + demand + keyword_queries:
        if q not in seen:
            seen.add(q)
            queries.append(q)
    return queries
