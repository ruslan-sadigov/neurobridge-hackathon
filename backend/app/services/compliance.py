"""Compliance engine: deterministic rules first, constrained LLM second (spec stages 6-7).

LLM classification is batched (several requirements per call) to keep API usage low. The guards that stop
unsupported positives and made-up evidence ids are applied per requirement in `_finalize`, whatever the call shape.
"""
from __future__ import annotations

import logging

from ..adapters.llm import LLMClient, LLMError
from ..config import get_settings
from ..enums import Category, MandatoryLevel, Method, ReasonCode, Status
from ..schemas import (BatchClassification, ClassificationResult, ComplianceResult, Evidence, Requirement)
from .rules import evaluate, field_matches_text

log = logging.getLogger(__name__)

RULES_TEXT = (
    "Return MET only if evidence clearly satisfies it, PARTIALLY_MET if it satisfies part, NOT_MET only if "
    "an evidence record states something that CONFLICTS with the requirement (set evidence_contradicts=true). "
    "A conflict means the evidence gives a value or fact for the SAME thing the requirement asks about and it falls "
    "short. Evidence about a different or partial item is NOT a conflict: for example one bank guarantee facility "
    "does not show the supplier's total liquid assets or credit lines, so answer UNKNOWN, not NOT_MET. "
    "PARTIALLY_MET means a distinct part of the requirement is clearly satisfied (for example one of two required "
    "items); being below a required amount is not partial satisfaction. "
    "If the evidence merely does not mention the required item, the answer is UNKNOWN, not NOT_MET. "
    "Cite evidence_ids you relied on. Never use outside knowledge about the company."
)
CLASSIFY_SYSTEM = "Decide whether the supplier evidence satisfies the tender requirement. Use ONLY the evidence given. " + RULES_TEXT
BATCH_SYSTEM = (
    "You receive several <item> blocks. Each has one tender requirement and the supplier evidence retrieved for it. "
    "For EACH item decide whether ITS OWN evidence satisfies ITS requirement; never use evidence from another item. "
    + RULES_TEXT + " Return exactly one result per item, with requirement_id copied exactly from the item id."
)


def reason_code_for(req: Requirement, status: Status) -> ReasonCode | None:
    if status == Status.UNKNOWN and req.mandatory_level == MandatoryLevel.MANDATORY:
        return ReasonCode.MANDATORY_EVIDENCE_UNKNOWN
    if status == Status.PARTIALLY_MET:  # a partial result is not a threshold failure, whatever the category
        return ReasonCode.MANDATORY_PARTIALLY_MET
    if status != Status.NOT_MET:
        return None
    fallback = ReasonCode.MANDATORY_REQUIREMENT_NOT_MET
    return {
        Category.CERTIFICATION: ReasonCode.MANDATORY_CERTIFICATION_MISSING,
        Category.EXPERIENCE: ReasonCode.EXPERIENCE_THRESHOLD_NOT_MET,
        Category.FINANCIAL: ReasonCode.FINANCIAL_THRESHOLD_NOT_MET,
        Category.DOCUMENTATION: ReasonCode.DOCUMENT_REQUIRED_MISSING,
        Category.DELIVERY: ReasonCode.DELIVERY_CONSTRAINT_RISK,
    }.get(req.category, fallback)


def _unknown(req: Requirement, rationale: str) -> ComplianceResult:
    return ComplianceResult(
        requirement_id=req.requirement_id, status=Status.UNKNOWN, method=Method.NO_EVIDENCE,
        rationale=rationale, confidence=1.0, reason_code=reason_code_for(req, Status.UNKNOWN))


def prepare(req: Requirement, all_evidence: list[Evidence], candidates: list[tuple[Evidence, float]],
            complete_types: set[str] | None = None, fx_rates: dict[str, float] | None = None) -> ComplianceResult | None:
    """Everything that does not need the model. Returns None when the requirement needs LLM classification."""
    outcome = None
    if field_matches_text(req.normalized_rule, req.text):
        outcome = evaluate(req.normalized_rule, all_evidence, complete_types=complete_types, fx_rates=fx_rates)
    if outcome is not None:
        return ComplianceResult(
            requirement_id=req.requirement_id, status=outcome.status, method=Method.DETERMINISTIC_RULE,
            supporting_evidence_ids=outcome.evidence_ids, rationale=outcome.rationale, confidence=0.99,
            reason_code=reason_code_for(req, outcome.status))
    if req.mandatory_level == MandatoryLevel.INFORMATIONAL:  # tender mechanics: no score, no risk, no model call
        return _unknown(req, "Tender-process clause (informational); not assessed against supplier evidence.")
    if not candidates:  # nothing retrievable -> UNKNOWN, never a guess
        return _unknown(req, "No supplier evidence available to verify this requirement.")
    return None


def _finalize(req: Requirement, candidates: list[tuple[Evidence, float]],
              res: ClassificationResult) -> ComplianceResult:
    valid_ids = {e.evidence_id for e, _ in candidates}
    cited = [i for i in res.evidence_ids if i in valid_ids]  # drop hallucinated ids
    status = res.status
    if status in (Status.MET, Status.PARTIALLY_MET) and not cited:
        status = Status.UNKNOWN  # FR-034: no unsupported positives
    if status == Status.NOT_MET and not (res.evidence_contradicts and cited):
        status = Status.UNKNOWN  # FR-012: absence of evidence is UNKNOWN, not NOT_MET
    return ComplianceResult(
        requirement_id=req.requirement_id, status=status, method=Method.LLM_SEMANTIC,
        supporting_evidence_ids=cited, rationale=res.rationale, confidence=res.confidence,
        reason_code=reason_code_for(req, status))


def _evidence_block(candidates: list[tuple[Evidence, float]]) -> str:
    return "\n".join(f'<evidence id="{e.evidence_id}">{e.label}: {e.text}</evidence>' for e, _ in candidates)


def classify(req: Requirement, all_evidence: list[Evidence], candidates: list[tuple[Evidence, float]],
             llm: LLMClient | None, complete_types: set[str] | None = None,
             fx_rates: dict[str, float] | None = None) -> ComplianceResult:
    """One requirement, one call. Kept for single-requirement use and tests; the pipeline uses classify_many."""
    done = prepare(req, all_evidence, candidates, complete_types, fx_rates)
    if done is not None:
        return done
    if llm is None:
        return _unknown(req, "No supplier evidence available to verify this requirement.")
    user = f"<requirement>{req.text}</requirement>\n{_evidence_block(candidates)}"
    res = llm.complete_json(system=CLASSIFY_SYSTEM, user=user, schema=ClassificationResult,
                            model=get_settings().classification_model)
    return _finalize(req, candidates, res)


def classify_many(reqs: list[Requirement], all_evidence: list[Evidence],
                  matches: dict[str, list[tuple[Evidence, float]]], llm: LLMClient | None,
                  complete_types: set[str] | None = None, fx_rates: dict[str, float] | None = None,
                  batch_size: int | None = None, warnings: list[str] | None = None) -> list[ComplianceResult]:
    """Classify all requirements with as few LLM calls as possible. Output order matches `reqs`."""
    batch_size = batch_size or get_settings().classify_batch_size
    warnings = warnings if warnings is not None else []
    results: dict[str, ComplianceResult] = {}
    pending: list[tuple[Requirement, list[tuple[Evidence, float]]]] = []
    for r in reqs:
        cands = matches.get(r.requirement_id, [])
        done = prepare(r, all_evidence, cands, complete_types, fx_rates)
        if done is not None:
            results[r.requirement_id] = done
        elif llm is None:
            results[r.requirement_id] = _unknown(r, "No supplier evidence available to verify this requirement.")
        else:
            pending.append((r, cands))

    for i in range(0, len(pending), batch_size):
        chunk = pending[i:i + batch_size]
        user = "\n".join(
            f'<item id="{r.requirement_id}">\n<requirement>{r.text}</requirement>\n{_evidence_block(c)}\n</item>'
            for r, c in chunk)
        try:
            batch = llm.complete_json(system=BATCH_SYSTEM, user=user, schema=BatchClassification,
                                      model=get_settings().classification_model)
        except LLMError as e:  # surface it; never turn a failed call into a positive result
            warnings.append(f"Classification of {', '.join(r.requirement_id for r, _ in chunk)} failed: {e}")
            for r, _ in chunk:
                results[r.requirement_id] = _unknown(r, "Classification call failed; requirement not assessed.")
            continue
        by_id = {b.requirement_id: b for b in batch.results}
        for r, c in chunk:
            b = by_id.get(r.requirement_id)
            results[r.requirement_id] = (_finalize(r, c, b) if b is not None
                                         else _unknown(r, "The model returned no verdict for this requirement."))
    return [results[r.requirement_id] for r in reqs]
