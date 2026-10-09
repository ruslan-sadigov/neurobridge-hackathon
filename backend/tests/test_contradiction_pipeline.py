"""Wiring test: the full pipeline on the synthetic conflict package, with a scripted fake model (no API calls)."""
import re
from pathlib import Path

import pytest

from app.adapters.embeddings import HashingEmbedder
from app.enums import Category, MandatoryLevel, ReasonCode, Recommendation, Severity
from app.schemas import (BatchClassification, ContradictionBatch, ExtractedRequirement, ExtractionResult, NormalizedRule,
                         PairVerdict)
from app.services.parser import parse_pdf
from app.services.pipeline import run_analysis

TENDERS = Path(__file__).parent.parent / "fixtures" / "tenders"
FILES = sorted(TENDERS.glob("SYN_conflict_tender_*.pdf"))


class ScriptedLLM:
    """Extraction: one requirement per numbered line. Classification: UNKNOWN. Judge: only deadline/turnover/validity conflict."""

    def __init__(self):
        self.schemas = []

    def complete_json(self, *, system, user, schema, **kw):
        self.schemas.append(schema.__name__)
        if schema is ExtractionResult:
            if "<already_extracted>" in user:
                return ExtractionResult()
            lines = re.findall(r"^\d\. (.+)$", user, re.M)
            return ExtractionResult(requirements=[ExtractedRequirement(
                text=t, category=Category.COMMERCIAL, mandatory_level=MandatoryLevel.MANDATORY,
                normalized_rule=NormalizedRule(), supporting_quote=t, extraction_confidence=0.9) for t in lines])
        if schema is BatchClassification:
            return BatchClassification()
        assert schema is ContradictionBatch
        pairs = re.findall(r'<pair id="(P\d+)">\s*<a [^>]*>(.*?)</a>\s*<b [^>]*>(.*?)</b>', user, re.S)
        flagged = ("March 2027", "turnover", "valid for")
        return ContradictionBatch(results=[PairVerdict(pair_id=pid, conflict=any(k in a for k in flagged),
                                                       explanation="the two documents state different values")
                                           for pid, a, b in pairs])


@pytest.mark.skipif(len(FILES) != 2, reason="run `python -m eval.make_synthetic_conflict_tender` first")
def test_pipeline_surfaces_conflicts_as_risks_and_conditions():
    chunks = []
    for f in FILES:
        chunks += parse_pdf(f.stem, f.read_bytes())
    llm = ScriptedLLM()
    res = run_analysis(chunks, {"company_name": "X", "fx_rates": {}}, llm, HashingEmbedder())

    cons = res["contradictions"]
    assert len(cons) == 3  # deadline, turnover, validity; the ISO pair was rejected by the judge
    docs = {s.document_id for c in cons for s in c.statements}
    assert docs == {f.stem for f in FILES}  # every conflict cites one statement from each document
    assert all(len(c.statements) == 2 and c.statements[0].page == 1 for c in cons)

    conflict_risks = [k for k in res["risks"] if k.reason_code == ReasonCode.CONFLICTING_TENDER_TERMS]
    assert len(conflict_risks) == 3
    assert {k.severity for k in conflict_risks} <= {Severity.HIGH, Severity.MEDIUM}
    assert res["score"].recommendation in (Recommendation.GO_WITH_CONDITIONS, Recommendation.NO_GO)
    assert ReasonCode.CONFLICTING_TENDER_TERMS in res["score"].reason_codes or res["score"].recommendation == Recommendation.NO_GO
    assert llm.schemas.count("ContradictionBatch") == 1  # all candidate pairs judged in ONE call


def test_contradiction_detection_can_be_switched_off(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "contradiction_detection", False)
    chunks = []
    for f in FILES:
        chunks += parse_pdf(f.stem, f.read_bytes())
    llm = ScriptedLLM()
    res = run_analysis(chunks, {"company_name": "X"}, llm, HashingEmbedder())
    assert res["contradictions"] == [] and "ContradictionBatch" not in llm.schemas
