from __future__ import annotations

from pydantic import BaseModel, Field


class ICPFilter(BaseModel):
    industries: list[str] = Field(default_factory=list)
    employee_ranges: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [self.industries, self.employee_ranges, self.stages, self.countries]
        )


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _matches_any(value: str | None, allowed: list[str]) -> bool:
    if not allowed:
        return True
    hay = _norm(value)
    if not hay:
        # Unknown profile field must not hard-exclude a lead.
        return True
    return any(_norm(item) in hay or hay in _norm(item) for item in allowed if item.strip())


def matches_icp(
    *,
    industry: str | None = None,
    employee_range: str | None = None,
    stage: str | None = None,
    headquarters: str | None = None,
    icp: ICPFilter | None = None,
) -> bool:
    if icp is None or icp.is_empty():
        return True
    # Industry is a search hint / scoring bonus, not a hard gate. Discover
    # historically stuffed query industries (SaaS, AI, Developer Tools) into
    # ICP, which dropped every lead whose LLM industry was "Fintech" etc.
    return (
        _matches_any(employee_range, icp.employee_ranges)
        and _matches_any(stage, icp.stages)
        and _matches_any(headquarters, icp.countries)
    )


def icp_fit_bonus(
    *,
    industry: str | None,
    employee_range: str | None,
    stage: str | None,
    headquarters: str | None,
    icp: ICPFilter | None,
) -> float:
    if icp is None or icp.is_empty():
        return 0.0
    score = 0.0
    if icp.industries and _matches_any(industry, icp.industries):
        score += 4.0
    if icp.stages and _matches_any(stage, icp.stages):
        score += 3.0
    if icp.employee_ranges and _matches_any(employee_range, icp.employee_ranges):
        score += 2.0
    if icp.countries and _matches_any(headquarters, icp.countries):
        score += 1.0
    return score
