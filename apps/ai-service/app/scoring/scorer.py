from __future__ import annotations

from datetime import datetime, timezone

from app.ai.schemas import IntentSignal, ScoreResult
from app.companies.icp import ICPFilter, icp_fit_bonus
from app.scoring.weights import SIGNAL_WEIGHTS, STAGE_SUITABILITY


def recency_multiplier(occurred_at: datetime | None, now: datetime | None = None) -> float:
    if occurred_at is None:
        return 0.60
    now = now or datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    days = (now - occurred_at).days
    if days <= 30:
        return 1.00
    if days <= 90:
        return 0.80
    if days <= 180:
        return 0.55
    return 0.30


def intent_level_for_score(score: int) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def calculate_score(
    signals: list[IntentSignal],
    estimated_stage: str | None = None,
    now: datetime | None = None,
    *,
    industry: str | None = None,
    employee_range: str | None = None,
    headquarters: str | None = None,
    icp: ICPFilter | None = None,
) -> ScoreResult:
    breakdown: dict[str, float] = {key: 0.0 for key in SIGNAL_WEIGHTS}
    for signal in signals:
        weight = SIGNAL_WEIGHTS.get(signal.signal_type, 0.0)
        if weight <= 0:
            continue
        contribution = weight * signal.strength * recency_multiplier(signal.occurred_at, now)
        breakdown[signal.signal_type] = max(breakdown[signal.signal_type], contribution)

    stage_score = 0.0
    if estimated_stage:
        key = estimated_stage.strip().lower()
        stage_score = STAGE_SUITABILITY.get(key, 5.0)
    breakdown["stage_suitability"] = stage_score
    breakdown["icp_fit"] = icp_fit_bonus(
        industry=industry,
        employee_range=employee_range,
        stage=estimated_stage,
        headquarters=headquarters,
        icp=icp,
    )

    total = min(100, round(sum(breakdown.values())))
    return ScoreResult(
        intent_score=int(total),
        intent_level=intent_level_for_score(int(total)),
        breakdown=breakdown,
    )
