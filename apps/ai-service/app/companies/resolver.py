from __future__ import annotations

import logging
import re
import time

from app.ai.client import AIClient
from app.ai.schemas import CompanyCandidate, SearchResult
from app.companies.normalizer import normalize_domain
from app.config import Settings
from app.utils.retry import gather_limited

logger = logging.getLogger(__name__)

PUBLISHER_DOMAINS = {
    "techcrunch.com",
    "news.ycombinator.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "youtube.com",
    "medium.com",
    "forbes.com",
    "businessinsider.com",
    "crunchbase.com",
    "bloomberg.com",
    "reuters.com",
    "wsj.com",
    "theverge.com",
    "wired.com",
    "producthunt.com",
    "indeed.com",
    "lever.co",
    "greenhouse.io",
    "jobs.ashbyhq.com",
    "entrackr.com",
    "vccircle.com",
    "eu-startups.com",
    "ventureburn.com",
    "bwdisrupt.com",
    "startupdatabase.com",
    "pitchbook.com",
    "cbinsights.com",
    "tracxn.com",
    "dealroom.co",
    "owler.com",
    "zoominfo.com",
    "apollo.io",
    "clutch.co",
    "g2.com",
    "capterra.com",
    "wikipedia.org",
    "ycombinator.com",
    "angel.co",
    "wellfound.com",
    "betalist.com",
    "failory.com",
    "saashub.com",
}

LISTICLE_TITLE = re.compile(
    r"(?i)(\btop\s+\d+\b|\b\d+\s*\+?\s*(funded|startups|companies)\b|"
    r"\b\d+k\+\b|\bdatabase\b|\bdirectory\b|\blist of\b|"
    r"\bcompanies\s*[|\u2013\u2014-]|b2b prospecting|"
    r"\bfind\s+.+\s+companies\b|\bstartup database\b)",
)

INTENT_TITLE = re.compile(
    r"(?i)(raises?|raised|hiring|seed|series [abc]|funding|careers|sdr|gtm|expanding)",
)

DOMAIN_IN_TEXT = re.compile(
    r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z]{2,}){1,})\b",
    re.IGNORECASE,
)


def is_listicle_title(title: str | None) -> bool:
    return bool(LISTICLE_TITLE.search(title or ""))


def is_publisher_domain(domain: str | None) -> bool:
    domain = (domain or "").lower()
    if not domain:
        return False
    if domain in PUBLISHER_DOMAINS:
        return True
    return any(domain.endswith(f".{pub}") for pub in PUBLISHER_DOMAINS)


def rank_search_results(results: list[SearchResult]) -> list[SearchResult]:
    def score(result: SearchResult) -> float:
        value = 0.0
        domain = normalize_domain(result.url)
        blob = f"{result.title} {result.snippet or ''}"
        if is_publisher_domain(domain):
            value -= 5.0
        else:
            value += 3.0
        if is_listicle_title(result.title):
            value -= 8.0
        if INTENT_TITLE.search(blob):
            value += 6.0
        return value

    return sorted(results, key=score, reverse=True)


class CompanyResolver:
    """Resolve which company a search result is about."""

    def __init__(self, settings: Settings, ai: AIClient | None = None):
        self.settings = settings
        self.ai = ai or AIClient(settings)

    async def resolve(self, result: SearchResult, *, use_ai: bool = True) -> CompanyCandidate | None:
        if is_listicle_title(result.title) and is_publisher_domain(normalize_domain(result.url)):
            return None
        if use_ai and self.ai.enabled:
            resolved = await self.ai.resolve_candidate(result.title, result.url, result.snippet)
            if (
                resolved
                and resolved.confidence >= self.settings.candidate_confidence_threshold
            ):
                if not resolved.company_domain:
                    resolved.company_domain = self._guess_domain(result)
                if self._is_garbage(resolved, result):
                    return None
                return resolved

        return self.resolve_heuristic(result)

    def resolve_heuristic(self, result: SearchResult) -> CompanyCandidate | None:
        if is_listicle_title(result.title):
            logger.info("reject listicle title=%r", (result.title or "")[:80])
            return None

        source_domain = normalize_domain(result.url)
        company_domain = self._guess_domain(result)
        name = self._guess_name(result, company_domain)

        if not name:
            return None

        if is_publisher_domain(source_domain) and (
            not company_domain or is_publisher_domain(company_domain)
        ):
            return None

        confidence = 0.72
        if is_publisher_domain(source_domain):
            confidence = 0.58 if company_domain else 0.35
        elif company_domain and source_domain == company_domain:
            confidence = 0.80

        if confidence < min(0.45, self.settings.candidate_confidence_threshold):
            return None

        candidate = CompanyCandidate(
            company_name=name,
            company_domain=company_domain,
            source_url=result.url,
            confidence=confidence,
        )
        if self._is_garbage(candidate, result):
            return None
        return candidate

    async def resolve_many(
        self,
        results: list[SearchResult],
        *,
        ai_failure_budget: int = 8,
    ) -> list[CompanyCandidate]:
        ranked = rank_search_results(results)
        ai_budget = min(len(ranked), max(0, self.settings.max_resolve_ai))
        logger.info(
            "resolve_many start total=%s ai_enabled=%s ai_budget=%s",
            len(ranked),
            self.ai.enabled,
            ai_budget,
        )
        started = time.perf_counter()
        limit = max(1, min(4, self.settings.max_company_concurrency))
        jobs = [
            self.resolve(result, use_ai=self.ai.enabled and idx < ai_budget)
            for idx, result in enumerate(ranked)
        ]
        outcomes = await gather_limited(jobs, limit=limit)
        candidates: list[CompanyCandidate] = []
        ai_failures = 0
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                ai_failures += 1
                continue
            if outcome is None:
                continue
            if outcome.confidence >= min(0.45, self.settings.candidate_confidence_threshold):
                candidates.append(outcome)
        logger.info(
            "resolve_many done candidates=%s of %s ai_failures=%s elapsed_ms=%s",
            len(candidates),
            len(ranked),
            ai_failures,
            int((time.perf_counter() - started) * 1000),
        )
        return candidates

    def _is_garbage(self, candidate: CompanyCandidate, result: SearchResult) -> bool:
        source_domain = normalize_domain(result.url)
        company_domain = normalize_domain(candidate.company_domain)
        if is_listicle_title(candidate.company_name) or is_listicle_title(result.title):
            return True
        if company_domain and is_publisher_domain(company_domain):
            return True
        if is_publisher_domain(source_domain) and (
            not company_domain or company_domain == source_domain
        ):
            return True
        return False

    def _guess_domain(self, result: SearchResult) -> str | None:
        source_domain = normalize_domain(result.url)
        if source_domain and not is_publisher_domain(source_domain):
            return source_domain

        text = f"{result.title} {result.snippet or ''}"
        for match in DOMAIN_IN_TEXT.finditer(text):
            candidate = normalize_domain(match.group(1))
            if not candidate or is_publisher_domain(candidate):
                continue
            if candidate.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
                continue
            return candidate
        return None

    def _guess_name(self, result: SearchResult, company_domain: str | None) -> str | None:
        title = result.title or ""
        patterns = [
            r"^([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,4})\s+(?:raises|raised|announces|hiring|launches)",
            r"(?:at|for|[-|\u2013\u2014:])\s*([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,4})\s*$",
            r"^([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,4})\s*[|\u2013\u2014-]",
        ]
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                name = self._clean_name(match.group(1))
                if name and name.lower() not in {"we", "our", "the", "hiring", "find"}:
                    if not is_listicle_title(name):
                        return name

        if company_domain and not is_publisher_domain(company_domain):
            label = company_domain.split(".")[0].replace("-", " ").title()
            return label

        return None

    def _clean_name(self, name: str) -> str:
        cleaned = name.strip(" |-\u2013\u2014")
        cleaned = re.sub(
            r"\b(careers|jobs|job|blog|news|press|about|home)\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", cleaned).strip(" |-\u2013\u2014")
