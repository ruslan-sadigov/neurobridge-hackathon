"""The strong synthetic supplier: evidence building and the deterministic checks it should pass or fail."""
import json
from pathlib import Path

from app.enums import RuleType, Status
from app.schemas import NormalizedRule
from app.services.evidence import build_evidence
from app.services.rules import evaluate

PROFILE = json.loads((Path(__file__).parent.parent / "fixtures" / "supplier_marmara_secure.json").read_text(encoding="utf-8"))
EVIDENCE = build_evidence(PROFILE)
FX = PROFILE["fx_rates"]


def test_profile_is_labelled_synthetic():
    assert PROFILE["synthetic"] is True and "synthetic" in PROFILE["company_name"].lower()


def test_facts_descriptions_and_ids_become_evidence():  # noqa: D103
    ids = {e.evidence_id for e in EVIDENCE}
    assert {"EVD-F-country", "EVD-C-27001", "EVD-P-002", "EVD-D-bank"} <= ids
    assert len(ids) == len(EVIDENCE)  # ids are unique
    bank = next(e for e in EVIDENCE if e.evidence_id == "EVD-D-bank")
    assert "within two working days" in bank.text  # the facility, not a ready-made guarantee, is what the profile claims


def test_turnover_in_eur_is_met_without_conversion():
    for threshold in (2_500_000, 2_800_000):
        rule = NormalizedRule(rule_type=RuleType.THRESHOLD, field="annual_revenue", operator=">", value=threshold, unit="EUR")
        assert evaluate(rule, EVIDENCE, fx_rates=FX).status == Status.MET


def test_iso_27001_is_met_and_expired_iso_9001_is_not():
    iso = NormalizedRule(rule_type=RuleType.MEMBERSHIP, field="certifications", operator="contains", value="ISO 27001")
    assert evaluate(iso, EVIDENCE).status == Status.MET
    old = NormalizedRule(rule_type=RuleType.MEMBERSHIP, field="certifications", operator="contains", value="ISO 9001")
    from datetime import date
    assert evaluate(old, EVIDENCE, today=date(2027, 6, 1)).status == Status.NOT_MET  # expired 2027-03-14
    assert evaluate(old, EVIDENCE, today=date(2026, 6, 1)).status == Status.MET


def test_text_fact_never_crashes_a_numeric_rule():
    rule = NormalizedRule(rule_type=RuleType.THRESHOLD, field="Country of establishment", operator=">=", value=1)
    assert evaluate(rule, EVIDENCE) is None  # falls back to semantic review instead of raising


def test_lot_scope_marks_other_lot_requirements_out_of_scope():
    from app.enums import Category, MandatoryLevel
    from app.schemas import Requirement, SourceRef
    from app.services.scope import normalize_lots, out_of_scope

    def r(rid, text):
        return Requirement(requirement_id=rid, text=text, category=Category.FINANCIAL,
                           mandatory_level=MandatoryLevel.MANDATORY, sources=[SourceRef(document_id="d", page=1, excerpt="e")],
                           extraction_confidence=0.9)

    reqs = [r("A", "For Lot 1, turnover must exceed 2 500 000 EUR"), r("B", "For Lot 2, at least 5 staff"),
            r("C", "Guarantee of 80 000 EUR for Lot 1 and 90 000 EUR for Lot 2"), r("D", "Bidder must be registered")]
    assert normalize_lots(["Lot 2", 2, "2"]) == {"2"}
    skipped = out_of_scope(reqs, ["2"])
    assert set(skipped) == {"A"}  # B targets lot 2, C names both, D names no lot
    assert out_of_scope(reqs, None) == {} and out_of_scope(reqs, []) == {}  # no declared scope: nothing skipped
