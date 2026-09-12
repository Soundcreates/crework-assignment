from __future__ import annotations

from app.ai.schemas import CompanyCandidate
from app.companies.normalizer import normalize_company_name, normalize_domain


def deduplicate_candidates(candidates: list[CompanyCandidate]) -> list[CompanyCandidate]:
    """Deduplicate by normalized domain, falling back to normalized company name."""
    by_domain: dict[str, CompanyCandidate] = {}
    by_name: dict[str, CompanyCandidate] = {}
    ordered: list[CompanyCandidate] = []

    for candidate in sorted(candidates, key=lambda c: c.confidence, reverse=True):
        domain = normalize_domain(candidate.company_domain or candidate.source_url)
        # If source is a publisher and company_domain is missing, don't key on publisher domain
        if candidate.company_domain:
            domain = normalize_domain(candidate.company_domain)
        elif domain and _looks_like_publisher(domain):
            domain = None

        name = normalize_company_name(candidate.company_name)
        if not name:
            continue

        if domain and domain in by_domain:
            continue
        if not domain and name in by_name:
            continue

        if domain:
            by_domain[domain] = candidate
        by_name[name] = candidate
        ordered.append(candidate)

    return ordered


def _looks_like_publisher(domain: str) -> bool:
    publishers = {
        "techcrunch.com",
        "news.ycombinator.com",
        "linkedin.com",
        "medium.com",
        "forbes.com",
        "crunchbase.com",
    }
    return domain in publishers
