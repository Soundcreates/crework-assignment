from datetime import datetime

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    published_at: datetime | None = None
    source: str


class CompanyCandidate(BaseModel):
    company_name: str
    company_domain: str | None = None
    source_url: str
    confidence: float = Field(ge=0, le=1)


class CompanyProfile(BaseModel):
    name: str
    website: str | None = None
    description: str | None = None
    industry: str | None = None
    estimated_employee_range: str | None = None
    estimated_stage: str | None = None
    business_model: str | None = None
    headquarters: str | None = None


class IntentSignal(BaseModel):
    signal_type: str
    strength: float = Field(ge=0, le=1)
    evidence: str
    explanation: str
    title: str | None = None
    occurred_at: datetime | None = None
    source_url: str | None = None


class SignalExtractionResult(BaseModel):
    signals: list[IntentSignal] = Field(default_factory=list)


class ContactCandidate(BaseModel):
    name: str
    title: str | None = None
    source_url: str | None = None


class ContactExtractionResult(BaseModel):
    contacts: list[ContactCandidate] = Field(default_factory=list)


class CompanySummary(BaseModel):
    summary: str


class CompanyEnrichmentResult(BaseModel):
    """Single-call profile + signals + contacts + sales summary."""

    name: str
    website: str | None = None
    description: str | None = None
    industry: str | None = None
    estimated_employee_range: str | None = None
    estimated_stage: str | None = None
    business_model: str | None = None
    headquarters: str | None = None
    signals: list[IntentSignal] = Field(default_factory=list)
    contacts: list[ContactCandidate] = Field(default_factory=list)
    summary: str | None = None


class ScoreResult(BaseModel):
    intent_score: int
    intent_level: str
    breakdown: dict[str, float]
