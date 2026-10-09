"""Canonical data contracts (spec section 5). Every LLM output is validated against these."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import Category, MandatoryLevel, Method, ReasonCode, Recommendation, RuleType, Severity, Status


class NormalizedRule(BaseModel):
    rule_type: RuleType = RuleType.NONE
    field: Optional[str] = None  # e.g. certifications, annual_revenue, projects_count
    operator: Optional[str] = None  # contains | >= | > | <= | < | ==
    value: Optional[Any] = None
    unit: Optional[str] = None  # e.g. AZN, years
    filters: dict[str, Any] = Field(default_factory=dict)  # e.g. {"tags": [...], "min_value": 300000}


class SourceRef(BaseModel):
    document_id: str
    page: int
    section: Optional[str] = None
    excerpt: str


class Requirement(BaseModel):
    requirement_id: str
    text: str
    category: Category
    mandatory_level: MandatoryLevel
    normalized_rule: NormalizedRule = Field(default_factory=NormalizedRule)
    sources: list[SourceRef]
    extraction_confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _needs_provenance(self):  # FR-002: no requirement without source
        if not self.sources:
            raise ValueError("requirement must have at least one source")
        return self


class ExtractedRequirement(BaseModel):
    """What the LLM returns for one chunk. Source page/excerpt are attached by the app, not the model."""

    text: str
    category: Category
    mandatory_level: MandatoryLevel
    normalized_rule: NormalizedRule = Field(default_factory=NormalizedRule)
    supporting_quote: str = Field(description="Verbatim quote from the chunk that contains the requirement")
    extraction_confidence: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    requirements: list[ExtractedRequirement] = Field(default_factory=list)


class Evidence(BaseModel):
    evidence_id: str
    type: str  # CERTIFICATE | FINANCIAL | PROJECT | COMPANY_FACT | DOCUMENT
    label: str
    value: Any = None
    text: str = ""  # searchable text rendering
    source: str = "company_profile"
    issued_date: Optional[str] = None
    expiry_date: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationResult(BaseModel):
    """LLM semantic output: status + short rationale + evidence ids ONLY (FR-032)."""

    status: Status
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @field_validator("rationale")
    @classmethod
    def _short(cls, v: str) -> str:
        return v[:600]


class ComplianceResult(BaseModel):
    requirement_id: str
    status: Status
    method: Method
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0, le=1)
    risk_severity: Optional[Severity] = None
    reason_code: Optional[ReasonCode] = None

    @model_validator(mode="after")
    def _no_unsupported_positive(self):  # FR-034
        if self.status in (Status.MET, Status.PARTIALLY_MET):
            if not self.supporting_evidence_ids and self.method != Method.DETERMINISTIC_RULE:
                raise ValueError("MET/PARTIALLY_MET requires evidence ids or a deterministic result")
        return self


class RiskItem(BaseModel):
    requirement_id: str
    severity: Severity
    explanation: str
    recommended_action: str
    reason_code: ReasonCode


class DimensionScore(BaseModel):
    name: str
    weight: float
    score: Optional[float]  # None if the dimension has no requirements
    coverage: Optional[float]  # share of requirements NOT unknown
    requirement_count: int


class ScoreSnapshot(BaseModel):
    dimensions: list[DimensionScore]
    final_score: float  # 0-100
    recommendation: Recommendation
    reason_codes: list[ReasonCode]
    overall_coverage: float
    config: dict[str, Any]  # weights + status points used, so the score is reproducible
