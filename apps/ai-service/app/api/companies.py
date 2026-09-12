from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.client import AIClient
from app.ai.schemas import CompanyCandidate, IntentSignal
from app.companies.processor import process_company
from app.config import get_settings
from app.crawling.crawler import WebsiteCrawler
from app.db.supabase import Database
from app.scoring.scorer import calculate_score

router = APIRouter(tags=["companies"])


class EnrichResponse(BaseModel):
    company_id: str
    status: str
    intent_score: int | None = None
    intent_level: str | None = None


class BulkEnrichResponse(BaseModel):
    enriched: int
    failed: int


class ScoreResponse(BaseModel):
    company_id: str
    intent_score: int
    intent_level: str


async def _enrich_row(db: Database, company: dict) -> dict | None:
    settings = get_settings()
    candidate = CompanyCandidate(
        company_name=company["name"],
        company_domain=company.get("normalized_domain"),
        source_url=company.get("website")
        or f"https://{company.get('normalized_domain') or 'example.com'}",
        confidence=1.0,
    )
    return await process_company(
        candidate,
        db=db,
        settings=settings,
        ai=AIClient(settings),
        crawler=WebsiteCrawler(settings),
        discovery_run_id=company.get("discovery_run_id"),
        source=company.get("source") or "live",
    )


@router.post("/companies/{company_id}/enrich", response_model=EnrichResponse)
async def enrich_company(company_id: str) -> EnrichResponse:
    db = Database()
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    saved = await _enrich_row(db, company)
    if not saved:
        raise HTTPException(status_code=500, detail="Enrichment failed")
    return EnrichResponse(
        company_id=company_id,
        status="enriched",
        intent_score=saved.get("intent_score"),
        intent_level=saved.get("intent_level"),
    )


@router.post("/companies/{company_id}/recheck", response_model=EnrichResponse)
async def recheck_company(company_id: str) -> EnrichResponse:
    return await enrich_company(company_id)


@router.post("/companies/enrich-unscored", response_model=BulkEnrichResponse)
async def enrich_unscored() -> BulkEnrichResponse:
    db = Database()
    rows = db.list_unscored_companies(limit=25)
    enriched = 0
    failed = 0
    for company in rows:
        saved = await _enrich_row(db, company)
        if saved:
            enriched += 1
        else:
            failed += 1
    return BulkEnrichResponse(enriched=enriched, failed=failed)


@router.post("/companies/recheck-stale", response_model=BulkEnrichResponse)
async def recheck_stale() -> BulkEnrichResponse:
    settings = get_settings()
    db = Database()
    rows = db.list_stale_companies(hours=settings.signal_recheck_hours, limit=15)
    enriched = 0
    failed = 0
    for company in rows:
        saved = await _enrich_row(db, company)
        if saved:
            enriched += 1
        else:
            failed += 1
    return BulkEnrichResponse(enriched=enriched, failed=failed)


@router.post("/companies/{company_id}/score", response_model=ScoreResponse)
async def rescore_company(company_id: str) -> ScoreResponse:
    db = Database()
    company = db.get_company(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    rows = db.get_signals(company_id)
    signals = [
        IntentSignal(
            signal_type=row["signal_type"],
            strength=float(row["strength"]),
            evidence=row["evidence"],
            explanation=row["explanation"],
            title=row.get("title"),
            occurred_at=row.get("occurred_at"),
            source_url=row.get("source_url"),
        )
        for row in rows
    ]
    score = calculate_score(signals, company.get("estimated_stage"))
    db.upsert_company(
        {
            "normalized_domain": company.get("normalized_domain"),
            "name": company["name"],
            "normalized_name": company.get("normalized_name"),
            "intent_score": score.intent_score,
            "intent_level": score.intent_level,
            "ai_summary": company.get("ai_summary"),
        }
    )
    return ScoreResponse(
        company_id=company_id,
        intent_score=score.intent_score,
        intent_level=score.intent_level,
    )
