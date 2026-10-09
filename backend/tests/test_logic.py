"""Unit tests for the deterministic core: rules, compliance guards, risk severity, scoring + veto."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.adapters.embeddings import HashingEmbedder
from app.enums import (Category, MandatoryLevel, Method, Recommendation, RuleType, Severity, Status)
from app.schemas import ClassificationResult, ComplianceResult, NormalizedRule, Requirement, SourceRef
from app.services import compliance, risk, scoring
from app.services.evidence import build_evidence
from app.services.matcher import match_evidence
from app.services.rules import evaluate

PROFILE = json.loads((Path(__file__).parent.parent / "fixtures" / "supplier_caspiantech.json").read_text())
EVIDENCE = build_evidence(PROFILE)


def req(rid, cat, level=MandatoryLevel.MANDATORY, rule=None, text="x"):
    return Requirement(requirement_id=rid, text=text, category=cat, mandatory_level=level,
                       normalized_rule=rule or NormalizedRule(),
                       sources=[SourceRef(document_id="d", page=1, excerpt="e")], extraction_confidence=0.9)


ISO27001 = NormalizedRule(rule_type=RuleType.MEMBERSHIP, field="certifications", operator="contains", value="ISO 27001")
ISO9001 = NormalizedRule(rule_type=RuleType.MEMBERSHIP, field="certifications", operator="contains", value="ISO 9001")


def test_membership_met_and_not_met():
    assert evaluate(ISO9001, EVIDENCE).status == Status.MET
    out = evaluate(ISO27001, EVIDENCE, complete_types={"CERTIFICATE"})
    assert out.status == Status.NOT_MET and "ISO 9001" in out.rationale


def test_absence_is_unknown_unless_profile_declared_complete():  # FR-012
    assert evaluate(ISO27001, EVIDENCE) is None


def test_threshold_and_count():
    rev = NormalizedRule(rule_type=RuleType.THRESHOLD, field="annual_revenue", operator=">=", value=500000)
    assert evaluate(rev, EVIDENCE).status == Status.MET
    rev.value = 5_000_000
    assert evaluate(rev, EVIDENCE).status == Status.NOT_MET
    cnt = NormalizedRule(rule_type=RuleType.COUNT, field="projects_count", operator=">=", value=2)
    assert evaluate(cnt, EVIDENCE).status == Status.PARTIALLY_MET  # 1 of 2


def test_expired_certificate_is_not_met():
    from datetime import date
    out = evaluate(ISO9001, EVIDENCE, today=date(2030, 1, 1))
    assert out.status == Status.NOT_MET


def test_unsupported_positive_is_rejected():  # FR-034
    with pytest.raises(ValidationError):
        ComplianceResult(requirement_id="R", status=Status.MET, method=Method.LLM_SEMANTIC, rationale="x", confidence=1)


def test_hallucinated_evidence_id_downgrades_to_unknown():
    class FakeLLM:
        def complete_json(self, **kw):
            return ClassificationResult(status=Status.MET, rationale="ok", evidence_ids=["EVD-FAKE"], confidence=0.9)

    r = req("R1", Category.TECHNICAL, text="Provide managed network services")
    cands = match_evidence([r], EVIDENCE, HashingEmbedder())["R1"]
    res = compliance.classify(r, EVIDENCE, cands, FakeLLM())
    assert res.status == Status.UNKNOWN


def test_no_evidence_gives_unknown_without_llm_call():
    r = req("R1", Category.TECHNICAL)
    res = compliance.classify(r, EVIDENCE, [], llm=None)
    assert res.status == Status.UNKNOWN and res.method == Method.NO_EVIDENCE


def test_severity_mapping():
    m = req("a", Category.CERTIFICATION)
    assert risk.severity_for(m, Status.NOT_MET) == Severity.CRITICAL
    assert risk.severity_for(m, Status.PARTIALLY_MET) == Severity.HIGH
    assert risk.severity_for(m, Status.UNKNOWN) == Severity.HIGH
    assert risk.severity_for(req("b", Category.CONTRACTUAL), Status.UNKNOWN) == Severity.MEDIUM
    assert risk.severity_for(req("c", Category.TECHNICAL, MandatoryLevel.PREFERRED), Status.NOT_MET) == Severity.LOW
    assert risk.severity_for(m, Status.MET) is None


def _result(rid, status):
    return ComplianceResult(requirement_id=rid, status=status, method=Method.DETERMINISTIC_RULE,
                            rationale=status.value, confidence=1)


def test_veto_overrides_high_score():
    reqs = [req(f"T{i}", Category.TECHNICAL) for i in range(9)] + [req("C", Category.CERTIFICATION)]
    results = [_result(f"T{i}", Status.MET) for i in range(9)] + [_result("C", Status.NOT_MET)]
    risks = risk.build_risks(reqs, results)
    snap = scoring.compute_score(reqs, results, risks)
    assert snap.final_score > 70  # looks attractive...
    assert snap.recommendation == Recommendation.NO_GO  # ...but the critical gap vetoes it


def test_go_with_conditions_and_go():
    reqs = [req("A", Category.TECHNICAL), req("B", Category.FINANCIAL)]
    ok = [_result("A", Status.MET), _result("B", Status.MET)]
    assert scoring.compute_score(reqs, ok, risk.build_risks(reqs, ok)).recommendation == Recommendation.GO
    unk = [_result("A", Status.MET), _result("B", Status.UNKNOWN)]
    snap = scoring.compute_score(reqs, unk, risk.build_risks(reqs, unk))
    assert snap.recommendation == Recommendation.GO_WITH_CONDITIONS
    assert snap.overall_coverage == 0.5  # uncertainty is visible, UNKNOWN never counted as MET


def test_score_is_reproducible_from_inputs():
    reqs = [req("A", Category.TECHNICAL), req("B", Category.EXPERIENCE)]
    res = [_result("A", Status.MET), _result("B", Status.PARTIALLY_MET)]
    risks = risk.build_risks(reqs, res)
    assert scoring.compute_score(reqs, res, risks) == scoring.compute_score(reqs, res, risks)


def test_requirement_without_source_is_rejected():  # FR-002
    with pytest.raises(ValidationError):
        Requirement(requirement_id="R", text="t", category=Category.LEGAL, mandatory_level=MandatoryLevel.MANDATORY,
                    sources=[], extraction_confidence=0.5)


def test_matcher_ranks_relevant_evidence_first():
    r = req("R", Category.CERTIFICATION, text="Bidder must hold a valid ISO 9001 certificate")
    top = match_evidence([r], EVIDENCE, HashingEmbedder())["R"]
    assert top and top[0][0].type in ("CERTIFICATE", "DOCUMENT")


def test_filtered_or_upper_bound_counts_are_not_deterministic():
    cnt = NormalizedRule(rule_type=RuleType.COUNT, field="projects_count", operator=">=", value=1,
                         filters={"min_value": 1_000_000})
    assert evaluate(cnt, EVIDENCE) is None  # needs semantic judgement
    cnt = NormalizedRule(rule_type=RuleType.COUNT, field="projects_count", operator="<=", value=5)
    assert evaluate(cnt, EVIDENCE) is None  # "at most N projects" is not a qualification test


def test_currency_mismatch_is_unknown_unless_fx_rate_given():
    rev = NormalizedRule(rule_type=RuleType.THRESHOLD, field="annual_revenue", operator=">", value=2_500_000, unit="EUR")
    assert evaluate(rev, EVIDENCE) is None  # no EUR rate -> UNKNOWN, never a bare-number compare
    out = evaluate(rev, EVIDENCE, fx_rates={"EUR": 1.95})  # 2.5M EUR = 4.875M AZN > 1.2M AZN
    assert out.status == Status.NOT_MET and "AZN" in out.rationale
    usd = NormalizedRule(rule_type=RuleType.THRESHOLD, field="annual_revenue", operator=">", value=500_000, unit="USD")
    assert evaluate(usd, EVIDENCE).status == Status.MET  # 500k USD = 850k AZN < 1.2M AZN


def test_llm_not_met_without_contradiction_becomes_unknown():
    class AbsentLLM:
        def complete_json(self, **kw):
            return ClassificationResult(status=Status.NOT_MET, rationale="not mentioned", evidence_ids=["EVD-001"],
                                        evidence_contradicts=False, confidence=0.9)

    r = req("R1", Category.DOCUMENTATION, text="Submit a signed declaration of honour")
    res = compliance.classify(r, EVIDENCE, [(next(e for e in EVIDENCE if e.evidence_id == "EVD-001"), 0.5)], AbsentLLM())
    assert res.status == Status.UNKNOWN


def test_rule_mapped_to_wrong_field_is_not_applied():
    wrong = NormalizedRule(rule_type=RuleType.THRESHOLD, field="annual_revenue", operator=">=", value=200000, unit="USD")
    r = req("R1", Category.FINANCIAL, rule=wrong, text="Bids need to be secured by a Bid Security of USD 200.000")
    res = compliance.classify(r, EVIDENCE, [], llm=None)
    assert res.status == Status.UNKNOWN and res.method == Method.NO_EVIDENCE
    ok = req("R2", Category.FINANCIAL, rule=wrong, text="Average annual turnover must exceed USD 200.000")
    assert compliance.classify(ok, EVIDENCE, [], llm=None).status == Status.MET
