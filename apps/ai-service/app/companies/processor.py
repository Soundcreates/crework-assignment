from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.ai.client import AIClient
from app.ai.schemas import (
    CompanyCandidate,
    CompanyProfile,
    ContactExtractionResult,
    IntentSignal,
)
from app.companies.icp import ICPFilter, matches_icp
from app.companies.normalizer import normalize_company_name, normalize_domain
from app.config import Settings, get_settings
from app.crawling.crawler import WebsiteCrawler
from app.db.supabase import Database
from app.scoring.scorer import calculate_score

logger = logging.getLogger(__name__)

OPTIONAL_COMPANY_COLUMNS = ("discovery_run_id", "source", "last_checked_at")


def _fallback_summary(profile: CompanyProfile, signals: list, score: int, level: str) -> str:
    if signals:
        return (
            f"{profile.name} shows {len(signals)} buying-intent signal(s) "
            f"with an intent score of {score} ({level})."
        )
    return f"{profile.name} was discovered but lacks strong recent intent signals."


async def process_company(
    candidate: CompanyCandidate,
    *,
    db: Database,
    settings: Settings | None = None,
    ai: AIClient | None = None,
    crawler: WebsiteCrawler | None = None,
    discovery_run_id: str | None = None,
    source: str = "live",
    icp: ICPFilter | None = None,
) -> dict[str, Any] | None:
    settings = settings or get_settings()
    ai = ai or AIClient(settings)
    crawler = crawler or WebsiteCrawler(settings)
    ai_failures = 0

    domain = normalize_domain(candidate.company_domain or candidate.source_url)
    website = f"https://{domain}" if domain else None
    try:
        pages = await crawler.crawl_company(website) if website else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("crawl failed name=%s website=%s error=%s", candidate.company_name, website, exc)
        pages = []
    source_texts = pages or [
        {"url": candidate.source_url, "text": f"{candidate.company_name} source page"}
    ]

    profile: CompanyProfile | None = None
    signals: list[IntentSignal] = []
    contacts = ContactExtractionResult(contacts=[])
    summary: str | None = None

    bundle_fn = getattr(ai, "enrich_company_bundle", None)
    bundle_attempted = False
    if bundle_fn is not None:
        bundle_attempted = True
        bundle = await bundle_fn(candidate.company_name, source_texts)
        if bundle is None:
            ai_failures += 1
        else:
            profile = CompanyProfile(
                name=bundle.name or candidate.company_name,
                website=bundle.website or website,
                description=bundle.description,
                industry=bundle.industry,
                estimated_employee_range=bundle.estimated_employee_range,
                estimated_stage=bundle.estimated_stage,
                business_model=bundle.business_model,
                headquarters=bundle.headquarters,
            )
            signals = list(bundle.signals or [])
            contacts = ContactExtractionResult(contacts=list(bundle.contacts or []))
            summary = bundle.summary

    if profile is None:
        if not bundle_attempted:
            profile = await ai.enrich_profile(candidate.company_name, pages)
            if profile is None:
                ai_failures += 1
            extract_pages = getattr(ai, "extract_signals_from_pages", None)
            if extract_pages is not None and not signals:
                extracted, failed = await extract_pages(
                    (profile.name if profile else candidate.company_name),
                    source_texts,
                )
                ai_failures += failed
                signals = list(extracted.signals)
        if profile is None:
            profile = CompanyProfile(
                name=candidate.company_name,
                website=website,
                description=None,
            )

    if not matches_icp(
        industry=profile.industry,
        employee_range=profile.estimated_employee_range,
        stage=profile.estimated_stage,
        headquarters=profile.headquarters,
        icp=icp,
    ):
        logger.info(
            "ICP skip name=%s industry=%s stage=%s size=%s hq=%s icp=%s",
            profile.name,
            profile.industry,
            profile.estimated_stage,
            profile.estimated_employee_range,
            profile.headquarters,
            icp.model_dump() if icp else None,
        )
        return {
            "ok": False,
            "reason": "icp",
            "name": profile.name,
            "normalized_domain": domain,
            "ai_failures": ai_failures,
            "signals_found": len(signals),
        }

    for signal in signals:
        if not signal.source_url:
            signal.source_url = source_texts[0]["url"]

    score = calculate_score(
        signals,
        profile.estimated_stage,
        industry=profile.industry,
        employee_range=profile.estimated_employee_range,
        headquarters=profile.headquarters,
        icp=icp,
    )
    if not summary:
        summary = _fallback_summary(
            profile, signals, score.intent_score, score.intent_level
        )

    now = datetime.now(timezone.utc).isoformat()
    company_payload = {
        "name": profile.name,
        "normalized_name": normalize_company_name(profile.name),
        "website": profile.website or website,
        "normalized_domain": domain,
        "description": profile.description,
        "industry": profile.industry,
        "estimated_employee_range": profile.estimated_employee_range,
        "estimated_stage": profile.estimated_stage,
        "business_model": profile.business_model,
        "headquarters": profile.headquarters,
        "intent_score": score.intent_score,
        "intent_level": score.intent_level,
        "ai_summary": summary,
        "last_updated_at": now,
        "last_checked_at": now,
        "source": source,
    }
    if discovery_run_id:
        company_payload["discovery_run_id"] = discovery_run_id
    saved = db.upsert_company(company_payload)
    if not saved and db.available:
        slim = {k: v for k, v in company_payload.items() if k not in OPTIONAL_COMPANY_COLUMNS}
        logger.warning(
            "upsert retry without optional columns domain=%s",
            company_payload.get("normalized_domain"),
        )
        saved = db.upsert_company(slim)
    if not saved:
        if db.available:
            logger.error(
                "upsert_company returned no row domain=%s name=%s",
                domain,
                profile.name,
            )
            return {
                "ok": False,
                "reason": "persist",
                "name": profile.name,
                "normalized_domain": domain,
                "ai_failures": ai_failures,
                "signals_found": len(signals),
            }
        saved = {**company_payload, "id": None}
    logger.info(
        "company saved name=%s domain=%s score=%s id=%s",
        profile.name,
        domain,
        score.intent_score,
        saved.get("id"),
    )

    if saved.get("id"):
        signal_rows = [
            {
                "signal_type": s.signal_type,
                "strength": s.strength,
                "title": s.title,
                "explanation": s.explanation,
                "evidence": s.evidence,
                "source_url": s.source_url or candidate.source_url,
                "source_domain": normalize_domain(
                    s.source_url or candidate.source_url
                ),
                "occurred_at": s.occurred_at.isoformat() if s.occurred_at else None,
            }
            for s in signals
        ]
        db.replace_signals(saved["id"], signal_rows)
        if contacts.contacts:
            db.replace_contacts(
                saved["id"],
                [
                    {
                        "name": c.name,
                        "title": c.title,
                        "source_url": c.source_url or candidate.source_url,
                    }
                    for c in contacts.contacts
                    if c.name.strip()
                ],
            )
    saved["ok"] = True
    saved["ai_failures"] = ai_failures
    saved["signals_found"] = len(signals)
    return saved
