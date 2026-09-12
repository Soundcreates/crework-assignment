from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.companies.icp import ICPFilter
from app.db.supabase import Database
from app.workflows.discovery_pipeline import DiscoveryPipeline
from app.workflows.search_discovery import SearchDiscoveryService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["discovery"])


class DiscoveryRequest(BaseModel):
    industries: list[str] = Field(default_factory=lambda: ["SaaS", "AI", "Developer Tools"])
    keywords: list[str] = Field(default_factory=list)
    country: str | None = None
    max_companies: int = Field(default=25, ge=1, le=100)
    run_id: str | None = None
    discovery_only: bool = Field(
        default=False,
        description="If true, search → resolve → dedupe → upsert stubs (no enrichment).",
    )
    icp: ICPFilter | None = None


class DiscoveryResponse(BaseModel):
    run_id: str
    status: str


class CompanyDiscoveryItem(BaseModel):
    id: str | None = None
    name: str
    domain: str | None = None
    website: str | None = None
    source_url: str | None = None
    confidence: float | None = None
    intent_score: int | None = None
    intent_level: str | None = None
    source: str | None = None


class CostSummary(BaseModel):
    llm_calls: int = 0
    llm_tokens: int = 0
    search_requests: int = 0
    crawl_requests: int = 0


class DiscoverySyncResponse(BaseModel):
    run_id: str
    status: str
    queries_generated: int
    search_results_found: int
    companies_discovered: int
    companies: list[CompanyDiscoveryItem]
    provider: str
    used_mock_fallback: bool = False
    error: str | None = None
    costs: CostSummary | None = None


def _ensure_run(db: Database, run_id: str, payload: DiscoveryRequest) -> None:
    if not db.available or not db.client:
        logger.info("ensure_run skipped (supabase unavailable) run_id=%s", run_id)
        return
    row = {
        "id": run_id,
        "status": "pending",
        "industries": payload.industries,
        "country": payload.country,
        "max_companies": payload.max_companies,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "search_provider": None,
        "used_mock_fallback": False,
        "icp": payload.icp.model_dump() if payload.icp else {},
    }
    try:
        existing = (
            db.client.table("discovery_runs").select("id").eq("id", run_id).limit(1).execute()
        )
        if existing.data:
            db.update_run(run_id, status="pending")
            logger.info("ensure_run updated existing run_id=%s", run_id)
        else:
            db.client.table("discovery_runs").insert(row).execute()
            logger.info("ensure_run inserted run_id=%s", run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_run failed run_id=%s error=%s", run_id, exc)


def _company_items_from_final(companies: list, saved: list[dict]) -> list[CompanyDiscoveryItem]:
    if saved:
        return [
            CompanyDiscoveryItem(
                id=row.get("id"),
                name=row.get("name") or "",
                domain=row.get("normalized_domain"),
                website=row.get("website"),
                intent_score=row.get("intent_score"),
                intent_level=row.get("intent_level"),
                source=row.get("source"),
            )
            for row in saved
        ]
    return [
        CompanyDiscoveryItem(
            name=c.company_name,
            domain=c.company_domain,
            source_url=c.source_url,
            confidence=c.confidence,
        )
        for c in companies
    ]


def _cost_summary(row: dict | None) -> CostSummary | None:
    if not row:
        return None
    return CostSummary(
        llm_calls=int(row.get("llm_calls") or 0),
        llm_tokens=int(row.get("llm_tokens") or 0),
        search_requests=int(row.get("search_requests") or 0),
        crawl_requests=int(row.get("crawl_requests") or 0),
    )


def _icp_payload(payload: DiscoveryRequest) -> dict | None:
    if payload.icp is None or payload.icp.is_empty():
        return None
    return payload.icp.model_dump()


@router.post("/discovery", response_model=DiscoveryResponse)
async def start_discovery(
    payload: DiscoveryRequest,
    background_tasks: BackgroundTasks,
) -> DiscoveryResponse:
    db = Database()
    run_id = payload.run_id or str(uuid4())
    logger.info(
        "async discovery queued run_id=%s industries=%s keywords=%s country=%s max=%s discovery_only=%s",
        run_id,
        payload.industries,
        payload.keywords,
        payload.country,
        payload.max_companies,
        payload.discovery_only,
    )
    _ensure_run(db, run_id, payload)

    pipeline = DiscoveryPipeline(db=db)
    background_tasks.add_task(
        pipeline.run,
        run_id,
        payload.industries,
        payload.country,
        payload.max_companies,
        discovery_only=payload.discovery_only,
        keywords=payload.keywords,
        icp=_icp_payload(payload),
    )
    return DiscoveryResponse(run_id=run_id, status="started")


@router.get("/discovery/{run_id}", response_model=DiscoverySyncResponse)
async def get_discovery_run(run_id: str) -> DiscoverySyncResponse:
    db = Database()
    row = db.get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    companies = db.list_companies_for_run(run_id, limit=row.get("max_companies") or 25)
    costs = db.get_run_costs(run_id)
    return DiscoverySyncResponse(
        run_id=run_id,
        status=row.get("status") or "unknown",
        queries_generated=row.get("queries_generated") or 0,
        search_results_found=row.get("search_results_found") or 0,
        companies_discovered=row.get("companies_discovered") or 0,
        companies=[
            CompanyDiscoveryItem(
                id=c.get("id"),
                name=c.get("name") or "",
                domain=c.get("normalized_domain"),
                website=c.get("website"),
                intent_score=c.get("intent_score"),
                intent_level=c.get("intent_level"),
                source=c.get("source"),
            )
            for c in companies
        ],
        provider=row.get("search_provider") or "unknown",
        used_mock_fallback=bool(row.get("used_mock_fallback")),
        error=row.get("error"),
        costs=_cost_summary(costs),
    )


@router.post("/discovery/search", response_model=DiscoverySyncResponse)
async def run_search_discovery(payload: DiscoveryRequest) -> DiscoverySyncResponse:
    """Synchronous discovery. Defaults to full enrich/score unless discovery_only=true."""
    db = Database()
    run_id = payload.run_id or str(uuid4())
    started = time.time()
    logger.info(
        "=== discovery/search START run_id=%s industries=%s keywords=%s country=%s max_companies=%s discovery_only=%s ===",
        run_id,
        payload.industries,
        payload.keywords,
        payload.country,
        payload.max_companies,
        payload.discovery_only,
    )
    _ensure_run(db, run_id, payload)

    service = SearchDiscoveryService(db=db)
    result = await service.run(
        run_id=run_id,
        industries=payload.industries,
        keywords=payload.keywords,
        country=payload.country,
        max_companies=payload.max_companies,
        persist=True,
        discovery_only=payload.discovery_only,
        icp=_icp_payload(payload),
    )
    elapsed_ms = int((time.time() - started) * 1000)
    logger.info(
        "=== discovery/search DONE run_id=%s status=%s queries=%s results=%s companies=%s "
        "provider=%s elapsed_ms=%s error=%s ===",
        run_id,
        result.status,
        len(result.queries),
        len(result.search_results),
        len(result.companies),
        result.search_provider,
        elapsed_ms,
        result.error,
    )
    costs = db.get_run_costs(run_id)
    return DiscoverySyncResponse(
        run_id=run_id,
        status=result.status,
        queries_generated=len(result.queries),
        search_results_found=len(result.search_results),
        companies_discovered=len(result.companies),
        companies=_company_items_from_final(result.companies, result.saved_companies),
        provider=result.search_provider,
        used_mock_fallback=result.used_mock_fallback,
        error=result.error,
        costs=_cost_summary(costs),
    )
