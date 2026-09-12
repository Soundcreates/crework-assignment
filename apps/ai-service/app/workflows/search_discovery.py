from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.schemas import CompanyCandidate, SearchResult
from app.db.supabase import Database
from app.workflows.discovery_graph import run_discovery_graph


@dataclass
class DiscoveryStageResult:
    run_id: str
    queries: list[str] = field(default_factory=list)
    search_results: list[SearchResult] = field(default_factory=list)
    candidates: list[CompanyCandidate] = field(default_factory=list)
    companies: list[CompanyCandidate] = field(default_factory=list)
    saved_companies: list[dict[str, Any]] = field(default_factory=list)
    status: str = "completed"
    error: str | None = None
    search_provider: str = "unknown"
    used_mock_fallback: bool = False


class SearchDiscoveryService:
    """LangGraph discovery: queries → search → resolve → dedupe → enrich/score (unless discovery_only)."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self.search_provider_name = "unknown"

    async def run(
        self,
        run_id: str,
        industries: list[str] | None = None,
        country: str | None = None,
        max_companies: int = 25,
        persist: bool = True,
        discovery_only: bool = False,
        keywords: list[str] | None = None,
        icp: dict | None = None,
    ) -> DiscoveryStageResult:
        final = await run_discovery_graph(
            run_id=run_id,
            industries=industries,
            keywords=keywords,
            country=country,
            max_companies=max_companies,
            discovery_only=discovery_only,
            persist=persist,
            db=self.db,
            icp=icp,
        )
        self.search_provider_name = final.get("search_provider") or "unknown"

        companies = [
            CompanyCandidate.model_validate(item)
            for item in final.get("companies") or []
        ]
        candidates = [
            CompanyCandidate.model_validate(item)
            for item in final.get("candidates") or []
        ]
        search_results = [
            SearchResult.model_validate(item)
            for item in final.get("search_results") or []
        ]

        return DiscoveryStageResult(
            run_id=run_id,
            queries=list(final.get("queries") or []),
            search_results=search_results,
            candidates=candidates,
            companies=companies,
            saved_companies=list(final.get("saved_companies") or []),
            status=final.get("status") or "completed",
            error=final.get("error"),
            search_provider=self.search_provider_name,
            used_mock_fallback=bool(final.get("used_mock_fallback")),
        )
