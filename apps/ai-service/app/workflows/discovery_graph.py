from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.client import AIClient
from app.ai.schemas import CompanyCandidate, SearchResult
from app.ai.usage import bind_run, snapshot
from app.companies.deduplicator import deduplicate_candidates
from app.companies.icp import ICPFilter
from app.companies.normalizer import normalize_company_name, normalize_domain
from app.companies.processor import process_company
from app.companies.resolver import CompanyResolver, is_listicle_title, rank_search_results
from app.config import Settings, get_settings
from app.crawling.crawler import WebsiteCrawler
from app.db.supabase import Database
from app.discovery.query_generator import generate_queries
from app.discovery.service import get_search_provider, search_with_fallback
from app.utils.retry import gather_limited

logger = logging.getLogger(__name__)


class DiscoveryGraphState(TypedDict, total=False):
    run_id: str
    industries: list[str]
    keywords: list[str]
    country: str | None
    max_companies: int
    discovery_only: bool
    persist: bool
    status: str
    error: str | None
    queries: list[str]
    search_results: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    companies: list[dict[str, Any]]
    saved_companies: list[dict[str, Any]]
    companies_enriched: int
    companies_failed: int
    ai_failures: int
    search_provider: str
    used_mock_fallback: bool
    icp: dict[str, Any]


def _candidate_from_dict(data: dict[str, Any]) -> CompanyCandidate:
    return CompanyCandidate.model_validate(data)


def _search_from_dict(data: dict[str, Any]) -> SearchResult:
    return SearchResult.model_validate(data)


def _icp_from_state(state: DiscoveryGraphState) -> ICPFilter | None:
    raw = state.get("icp")
    if not raw:
        return None
    icp = ICPFilter.model_validate(raw)
    return None if icp.is_empty() else icp


def resolve_budget_for(max_companies: int, total: int) -> int:
    return min(total, max(max_companies * 2, 8))


class DiscoveryGraphRuntime:
    def __init__(self, db: Database | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.db = db or Database()
        self.search = get_search_provider(self.settings)
        self.ai = AIClient(self.settings)
        self.resolver = CompanyResolver(self.settings, self.ai)
        self.crawler = WebsiteCrawler(self.settings)

    async def start_run(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        bind_run(state.get("run_id"))
        logger.info(
            "[graph] start_run run_id=%s industries=%s keywords=%s country=%s max=%s provider=%s ai=%s model=%s",
            state.get("run_id"),
            state.get("industries"),
            state.get("keywords"),
            state.get("country"),
            state.get("max_companies"),
            type(self.search).__name__,
            self.ai.enabled,
            self.settings.llm_model,
        )
        self.db.update_run(
            state["run_id"],
            status="searching",
            search_provider=type(self.search).__name__,
        )
        return {
            "status": "searching",
            "error": None,
            "queries": [],
            "search_results": [],
            "candidates": [],
            "companies": [],
            "saved_companies": [],
            "companies_enriched": 0,
            "companies_failed": 0,
            "ai_failures": 0,
            "search_provider": type(self.search).__name__,
            "used_mock_fallback": False,
        }

    async def generate_queries_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        queries = generate_queries(
            industries=state.get("industries"),
            country=state.get("country"),
            keywords=state.get("keywords"),
        )
        max_companies = state.get("max_companies") or 25
        query_budget = min(len(queries), max(8, min(12, max_companies)))
        if len(queries) > query_budget:
            logger.info(
                "[graph] generate_queries capping %s -> %s (max_companies=%s)",
                len(queries),
                query_budget,
                max_companies,
            )
            queries = queries[:query_budget]
        logger.info(
            "[graph] generate_queries count=%s sample=%s",
            len(queries),
            queries[:3],
        )
        self.db.update_run(state["run_id"], queries_generated=len(queries))
        return {"queries": queries}

    async def search_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        started = time.perf_counter()
        queries = state.get("queries") or []
        logger.info("[graph] search_node start query_count=%s", len(queries))
        batch = await search_with_fallback(
            self.search,
            queries,
            limit_per_query=8,
            concurrency=4,
        )
        logger.info(
            "[graph] search_node done results=%s failures=%s fallback=%s elapsed_ms=%s",
            len(batch.results),
            batch.failures,
            batch.used_mock_fallback,
            int((time.perf_counter() - started) * 1000),
        )
        self.db.update_run(
            state["run_id"],
            search_results_found=len(batch.results),
            search_provider=batch.provider,
            used_mock_fallback=batch.used_mock_fallback,
        )
        error = None
        if not batch.results and batch.failures:
            error = batch.error or "Search returned no results."
        return {
            "search_results": [r.model_dump(mode="json") for r in batch.results],
            "search_provider": batch.provider,
            "used_mock_fallback": batch.used_mock_fallback,
            "error": error,
        }

    async def resolve_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        if state.get("error") and not state.get("search_results"):
            return {"candidates": []}
        results = [_search_from_dict(item) for item in state.get("search_results") or []]
        started = time.perf_counter()
        ranked = [r for r in rank_search_results(results) if not is_listicle_title(r.title)]
        max_companies = state.get("max_companies") or 25
        budget = resolve_budget_for(max_companies, len(ranked))
        sliced = ranked[:budget]
        logger.info(
            "[graph] resolve_node start search_results=%s ranked_budget=%s",
            len(results),
            len(sliced),
        )
        candidates = await self.resolver.resolve_many(sliced)
        logger.info(
            "[graph] resolve_node done candidates=%s elapsed_ms=%s",
            len(candidates),
            int((time.perf_counter() - started) * 1000),
        )
        return {"candidates": [c.model_dump(mode="json") for c in candidates]}

    async def dedupe_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        candidates = [
            _candidate_from_dict(item) for item in state.get("candidates") or []
        ]
        max_companies = state.get("max_companies") or 25
        companies = deduplicate_candidates(candidates)[:max_companies]
        logger.info(
            "[graph] dedupe_node candidates=%s kept=%s max=%s",
            len(candidates),
            len(companies),
            max_companies,
        )
        self.db.update_run(
            state["run_id"],
            companies_discovered=len(companies),
        )
        return {"companies": [c.model_dump(mode="json") for c in companies]}

    def _source(self, state: DiscoveryGraphState) -> str:
        provider = (state.get("search_provider") or "").lower()
        if state.get("used_mock_fallback") or "mock" in provider:
            return "mock"
        return "live"

    async def persist_discovered_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        if not state.get("persist", True):
            return {"saved_companies": []}

        started = time.perf_counter()
        company_count = len(state.get("companies") or [])
        logger.info(
            "[graph] persist_discovered start companies=%s db_available=%s",
            company_count,
            self.db.available,
        )
        saved: list[dict[str, Any]] = []
        failed = 0
        source = self._source(state)
        for item in state.get("companies") or []:
            candidate = _candidate_from_dict(item)
            domain = normalize_domain(candidate.company_domain)
            if not domain:
                failed += 1
                continue
            row = {
                "name": candidate.company_name.strip(),
                "normalized_name": normalize_company_name(candidate.company_name),
                "website": f"https://{domain}",
                "normalized_domain": domain,
                "description": None,
                "industry": None,
                "estimated_employee_range": None,
                "estimated_stage": None,
                "business_model": None,
                "headquarters": None,
                "intent_score": 0,
                "intent_level": "LOW",
                "ai_summary": (
                    f"Discovered via public source: {candidate.source_url}. "
                    "Awaiting enrichment and signal extraction."
                ),
                "review_status": "new",
                "last_updated_at": datetime.now(timezone.utc).isoformat(),
                "discovery_run_id": state["run_id"],
                "source": source,
            }
            upserted = self.db.upsert_company(row)
            if upserted:
                saved.append(upserted)
            elif not self.db.available:
                saved.append({**row, "id": None})
            else:
                failed += 1
        logger.info(
            "[graph] persist_discovered done saved=%s failed=%s elapsed_ms=%s",
            len(saved),
            failed,
            int((time.perf_counter() - started) * 1000),
        )
        return {"saved_companies": saved, "companies_failed": failed}

    async def enrich_companies_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        bind_run(state.get("run_id"))
        self.db.update_run(state["run_id"], status="enriching")
        companies = [
            _candidate_from_dict(item) for item in state.get("companies") or []
        ]
        icp = _icp_from_state(state)
        source = self._source(state)
        outcomes = await gather_limited(
            [
                process_company(
                    c,
                    db=self.db,
                    settings=self.settings,
                    ai=self.ai,
                    crawler=self.crawler,
                    discovery_run_id=state["run_id"],
                    source=source,
                    icp=icp,
                )
                for c in companies
            ],
            limit=self.settings.max_company_concurrency,
        )
        saved: list[dict[str, Any]] = []
        failed = 0
        skipped_icp = 0
        ai_failures = 0
        for idx, outcome in enumerate(outcomes):
            if isinstance(outcome, Exception):
                failed += 1
                logger.warning(
                    "company processing exception name=%s error=%s",
                    companies[idx].company_name if idx < len(companies) else "?",
                    outcome,
                )
                continue
            if isinstance(outcome, dict) and outcome.get("ok") is False:
                reason = outcome.get("reason")
                if reason == "icp":
                    skipped_icp += 1
                    logger.info("company skipped by ICP name=%s", outcome.get("name"))
                else:
                    failed += 1
                    logger.warning(
                        "company persist/process failed name=%s reason=%s",
                        outcome.get("name"),
                        reason,
                    )
                continue
            if isinstance(outcome, dict):
                saved.append(outcome)
                ai_failures += int(outcome.get("ai_failures") or 0)
                continue
            failed += 1
            logger.warning("company processing returned %r", type(outcome))
        error = None
        if skipped_icp and not saved and not failed:
            error = (
                f"{skipped_icp} companies skipped by ICP filters "
                "(stage/headcount/industry did not match)."
            )
        logger.info(
            "[graph] enrich_node saved=%s failed=%s skipped_icp=%s ai_failures=%s",
            len(saved),
            failed,
            skipped_icp,
            ai_failures,
        )
        self.db.update_run(state["run_id"], status="scoring")
        return {
            "status": "enriching",
            "companies_enriched": len(saved),
            "companies_failed": failed,
            "ai_failures": ai_failures,
            "saved_companies": saved,
            "error": error,
        }

    def _finalize_status(self, state: DiscoveryGraphState) -> tuple[str, str | None]:
        if state.get("error") and not state.get("saved_companies") and not state.get("companies"):
            return "failed", state.get("error")
        failed = int(state.get("companies_failed") or 0)
        ai_failures = int(state.get("ai_failures") or 0)
        error = state.get("error")
        if failed:
            parts = [f"{failed} companies failed"]
            if ai_failures:
                parts.append(f"{ai_failures} AI extraction failures")
            if error:
                parts.append(error)
            return "completed_with_errors", "; ".join(parts)
        if error and not state.get("saved_companies"):
            return "completed_with_errors", error
        if state.get("used_mock_fallback"):
            return "completed_with_errors", error or "Used mock search fallback."
        return "completed", None

    async def finalize_node(self, state: DiscoveryGraphState) -> DiscoveryGraphState:
        bind_run(state.get("run_id"))
        status, error = self._finalize_status(state)
        costs = snapshot(state["run_id"])
        self.db.update_run(
            state["run_id"],
            status=status,
            error=error,
            completed_at=datetime.now(timezone.utc).isoformat(),
            companies_enriched=state.get("companies_enriched") or 0,
            companies_failed=state.get("companies_failed") or 0,
            search_provider=state.get("search_provider"),
            used_mock_fallback=bool(state.get("used_mock_fallback")),
        )
        self.db.upsert_run_costs(
            state["run_id"],
            llm_calls=costs.llm_calls,
            llm_tokens=costs.llm_tokens,
            search_requests=costs.search_requests,
            crawl_requests=costs.crawl_requests,
        )
        logger.info(
            {
                "run_id": state["run_id"],
                "stage": "langgraph_discovery",
                "queries": len(state.get("queries") or []),
                "search_results": len(state.get("search_results") or []),
                "companies": len(state.get("companies") or []),
                "discovery_only": state.get("discovery_only", False),
                "provider": state.get("search_provider"),
                "used_mock_fallback": state.get("used_mock_fallback"),
                "status": status,
                "llm_calls": costs.llm_calls,
            }
        )
        return {"status": status, "error": error}


def finalize_status(
    *,
    error: str | None,
    saved_companies: list | None,
    companies: list | None,
    companies_failed: int = 0,
    ai_failures: int = 0,
    used_mock_fallback: bool = False,
) -> str:
    runtime = DiscoveryGraphRuntime.__new__(DiscoveryGraphRuntime)
    state: DiscoveryGraphState = {
        "error": error,
        "saved_companies": saved_companies or [],
        "companies": companies or [],
        "companies_failed": companies_failed,
        "ai_failures": ai_failures,
        "used_mock_fallback": used_mock_fallback,
    }
    status, _ = DiscoveryGraphRuntime._finalize_status(runtime, state)
    return status


def route_after_search(state: DiscoveryGraphState) -> Literal["resolve", "finalize"]:
    if state.get("error") and not state.get("search_results"):
        return "finalize"
    return "resolve"


def route_after_dedupe(state: DiscoveryGraphState) -> Literal["persist_discovered", "enrich_companies"]:
    if state.get("discovery_only", False):
        return "persist_discovered"
    return "enrich_companies"


def build_discovery_graph(runtime: DiscoveryGraphRuntime | None = None):
    runtime = runtime or DiscoveryGraphRuntime()
    graph = StateGraph(DiscoveryGraphState)

    graph.add_node("start_run", runtime.start_run)
    graph.add_node("generate_queries", runtime.generate_queries_node)
    graph.add_node("search", runtime.search_node)
    graph.add_node("resolve", runtime.resolve_node)
    graph.add_node("dedupe", runtime.dedupe_node)
    graph.add_node("persist_discovered", runtime.persist_discovered_node)
    graph.add_node("enrich_companies", runtime.enrich_companies_node)
    graph.add_node("finalize", runtime.finalize_node)

    graph.add_edge(START, "start_run")
    graph.add_edge("start_run", "generate_queries")
    graph.add_edge("generate_queries", "search")
    graph.add_conditional_edges(
        "search",
        route_after_search,
        {
            "resolve": "resolve",
            "finalize": "finalize",
        },
    )
    graph.add_edge("resolve", "dedupe")
    graph.add_conditional_edges(
        "dedupe",
        route_after_dedupe,
        {
            "persist_discovered": "persist_discovered",
            "enrich_companies": "enrich_companies",
        },
    )
    graph.add_edge("persist_discovered", "finalize")
    graph.add_edge("enrich_companies", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


async def run_discovery_graph(
    *,
    run_id: str,
    industries: list[str] | None = None,
    keywords: list[str] | None = None,
    country: str | None = None,
    max_companies: int = 25,
    discovery_only: bool = False,
    persist: bool = True,
    db: Database | None = None,
    icp: dict[str, Any] | ICPFilter | None = None,
) -> DiscoveryGraphState:
    runtime = DiscoveryGraphRuntime(db=db)
    app = build_discovery_graph(runtime)
    icp_payload: dict[str, Any] = {}
    if isinstance(icp, ICPFilter):
        icp_payload = icp.model_dump()
    elif icp:
        icp_payload = dict(icp)
    initial: DiscoveryGraphState = {
        "run_id": run_id,
        "industries": industries or ["SaaS", "AI", "Developer Tools"],
        "keywords": keywords or [],
        "country": country,
        "max_companies": max_companies,
        "discovery_only": discovery_only,
        "persist": persist,
        "status": "pending",
        "error": None,
        "icp": icp_payload,
    }
    try:
        return await app.ainvoke(initial)
    except Exception as exc:  # noqa: BLE001
        logger.exception("langgraph discovery failed")
        runtime.db.update_run(
            run_id,
            status="failed",
            error=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        return {
            **initial,
            "status": "failed",
            "error": str(exc),
            "queries": [],
            "search_results": [],
            "candidates": [],
            "companies": [],
            "saved_companies": [],
            "companies_enriched": 0,
            "companies_failed": 0,
            "ai_failures": 0,
            "search_provider": type(runtime.search).__name__,
            "used_mock_fallback": False,
        }
