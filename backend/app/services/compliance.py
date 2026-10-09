"""Compliance engine: deterministic rules first, constrained LLM second (spec stages 6-7)."""
from __future__ import annotations

from ..adapters.llm import LLMClient
from ..config import get_settings
from ..enums import Category, MandatoryLevel, Method, ReasonCode, Status
from ..schemas import ClassificationResult, ComplianceResult, Evidence, Requirement
from .rules import evaluate

CLASSIFY_SYSTEM = (
    "Decide whether the supplier evidence satisfies the tender requirement. Use ONLY the evidence given. "
    "Return MET only if evidence clearly satisfies it, PARTIALLY_MET if it satisfies part, NOT_MET only if "
    "evidence clearly contradicts it, otherwise UNKNOWN. Cite evidence_ids you relied on. "
    "Never use outside knowledge about the company."
)


def reason_code_for(req: Requirement, status: Status) -> ReasonCode | None:
    if status == Status.UNKNOWN and req.mandatory_level == MandatoryLevel.MANDATORY:
        return ReasonCode.MANDATORY_EVIDENCE_UNKNOWN
    if status not in (Status.NOT_MET, Status.PARTIALLY_MET):
        return None
    fallback = (ReasonCode.MANDATORY_REQUIREMENT_NOT_MET if status == Status.NOT_MET
                else ReasonCode.MANDATORY_PARTIALLY_MET)
    return {
        Category.CERTIFICATION: ReasonCode.MANDATORY_CERTIFICATION_MISSING,
        Category.EXPERIENCE: ReasonCode.EXPERIENCE_THRESHOLD_NOT_MET,
        Category.FINANCIAL: ReasonCode.FINANCIAL_THRESHOLD_NOT_MET,
        Category.DOCUMENTATION: ReasonCode.DOCUMENT_REQUIRED_MISSING,
        Category.DELIVERY: ReasonCode.DELIVERY_CONSTRAINT_RISK,
    }.get(req.category, fallback)


def classify(req: Requirement, all_evidence: list[Evidence], candidates: list[tuple[Evidence, float]],
             llm: LLMClient | None, complete_types: set[str] | None = None) -> ComplianceResult:
    # 1. deterministic
    outcome = evaluate(req.normalized_rule, all_evidence, complete_types=complete_types)
    if outcome is not None:
        return ComplianceResult(
            requirement_id=req.requirement_id, status=outcome.status, method=Method.DETERMINISTIC_RULE,
            supporting_evidence_ids=outcome.evidence_ids, rationale=outcome.rationale, confidence=0.99,
            reason_code=reason_code_for(req, outcome.status))

    # 2. nothing retrievable -> UNKNOWN, never a guess
    if not candidates or llm is None:
        return ComplianceResult(
            requirement_id=req.requirement_id, status=Status.UNKNOWN, method=Method.NO_EVIDENCE,
            rationale="No supplier evidence available to verify this requirement.", confidence=1.0,
            reason_code=reason_code_for(req, Status.UNKNOWN))

    # 3. semantic: only the requirement + retrieved evidence are sent (no unrelated company facts)
    ev_block = "\n".join(f'<evidence id="{e.evidence_id}">{e.label}: {e.text}</evidence>' for e, _ in candidates)
    user = f"<requirement>{req.text}</requirement>\n{ev_block}"
    res = llm.complete_json(system=CLASSIFY_SYSTEM, user=user, schema=ClassificationResult,
                            model=get_settings().llm_classification_model)

    valid_ids = {e.evidence_id for e, _ in candidates}
    cited = [i for i in res.evidence_ids if i in valid_ids]  # drop hallucinated ids
    status = res.status
    if status in (Status.MET, Status.PARTIALLY_MET) and not cited:
        status = Status.UNKNOWN  # FR-034: no unsupported positives
    return ComplianceResult(
        requirement_id=req.requirement_id, status=status, method=Method.LLM_SEMANTIC,
        supporting_evidence_ids=cited, rationale=res.rationale, confidence=res.confidence,
        reason_code=reason_code_for(req, status))
