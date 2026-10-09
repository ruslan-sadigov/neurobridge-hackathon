"""LLM call reduction: batched classification, skipped informational clauses, persistent cache."""
import json
from pathlib import Path

from app.adapters.embeddings import HashingEmbedder
from app.adapters.llm import CachedLLM, LLMError
from app.enums import Category, MandatoryLevel, Method, Status
from app.schemas import BatchClassification, BatchItem, ClassificationResult, NormalizedRule, Requirement, SourceRef
from app.services import compliance
from app.services.evidence import build_evidence
from app.services.matcher import match_evidence

PROFILE = json.loads((Path(__file__).parent.parent / "fixtures" / "supplier_caspiantech.json").read_text())
EVIDENCE = build_evidence(PROFILE)


def req(rid, text="Provide managed network services", cat=Category.TECHNICAL, level=MandatoryLevel.MANDATORY):
    return Requirement(requirement_id=rid, text=text, category=cat, mandatory_level=level,
                       normalized_rule=NormalizedRule(), sources=[SourceRef(document_id="d", page=1, excerpt="e")],
                       extraction_confidence=0.9)


class BatchLLM:
    """Fake model: counts calls and answers each item in the prompt with a configurable verdict."""

    def __init__(self, verdict=None, drop=(), fail=False):
        self.calls = 0
        self.verdict = verdict or (lambda rid: dict(status=Status.UNKNOWN, rationale="not mentioned",
                                                    evidence_ids=[], evidence_contradicts=False, confidence=0.5))
        self.drop, self.fail = set(drop), fail

    def complete_json(self, *, system, user, schema, **kw):
        self.calls += 1
        if self.fail:
            raise LLMError("boom")
        ids = [p.split('"')[0] for p in user.split('<item id="')[1:]]
        return BatchClassification(results=[BatchItem(requirement_id=i, **self.verdict(i)) for i in ids if i not in self.drop])


def run(reqs, llm, batch_size=3):
    matches = match_evidence(reqs, EVIDENCE, HashingEmbedder())
    warnings: list[str] = []
    out = compliance.classify_many(reqs, EVIDENCE, matches, llm, batch_size=batch_size, warnings=warnings)
    return out, warnings


def test_requirements_are_classified_in_batches():
    reqs = [req(f"R{i}") for i in range(7)]
    llm = BatchLLM()
    out, _ = run(reqs, llm, batch_size=3)
    assert llm.calls == 3  # 7 requirements, 3 per call: 3 + 3 + 1
    assert [r.requirement_id for r in out] == [r.requirement_id for r in reqs]  # order preserved
    assert all(r.status == Status.UNKNOWN and r.method == Method.LLM_SEMANTIC for r in out)


def test_informational_clauses_make_no_llm_call():
    reqs = [req("A", level=MandatoryLevel.INFORMATIONAL), req("B", level=MandatoryLevel.INFORMATIONAL)]
    llm = BatchLLM()
    out, _ = run(reqs, llm)
    assert llm.calls == 0
    assert all(r.status == Status.UNKNOWN for r in out)


def test_guards_apply_per_requirement_inside_a_batch():
    good = next(e.evidence_id for e in EVIDENCE if e.type == "CERTIFICATE")

    def verdict(rid):
        if rid == "R1":  # supported positive
            return dict(status=Status.MET, rationale="ok", evidence_ids=[good], evidence_contradicts=False, confidence=0.9)
        if rid == "R2":  # made-up evidence id -> unsupported positive
            return dict(status=Status.MET, rationale="ok", evidence_ids=["EVD-FAKE"], evidence_contradicts=False, confidence=0.9)
        # R3: NOT_MET merely because the evidence does not mention it
        return dict(status=Status.NOT_MET, rationale="absent", evidence_ids=[good], evidence_contradicts=False, confidence=0.9)

    reqs = [req("R1", "ISO 9001 certificate", Category.CERTIFICATION), req("R2", "ISO 9001 certificate", Category.CERTIFICATION),
            req("R3", "ISO 27001 certificate", Category.CERTIFICATION)]
    out, _ = run(reqs, BatchLLM(verdict), batch_size=3)
    assert [r.status for r in out] == [Status.MET, Status.UNKNOWN, Status.UNKNOWN]
    assert out[0].supporting_evidence_ids == [good]


def test_missing_verdict_and_failed_call_become_unknown_with_warning():
    reqs = [req("R1"), req("R2"), req("R3")]
    out, _ = run(reqs, BatchLLM(drop={"R2"}))
    assert out[1].status == Status.UNKNOWN and "no verdict" in out[1].rationale

    out, warnings = run(reqs, BatchLLM(fail=True))
    assert all(r.status == Status.UNKNOWN for r in out)
    assert len(warnings) == 1 and "failed" in warnings[0]


def test_cache_replays_identical_calls(tmp_path):
    class Counting:
        calls = 0

        def complete_json(self, **kw):
            Counting.calls += 1
            return ClassificationResult(status=Status.UNKNOWN, rationale="x", confidence=0.5)

    llm = CachedLLM(Counting(), tmp_path)
    kw = dict(system="s", user="u", schema=ClassificationResult, model="m")
    first = llm.complete_json(**kw)
    second = llm.complete_json(**kw)
    assert first == second and Counting.calls == 1 and (llm.hits, llm.misses) == (1, 1)
    llm.complete_json(**{**kw, "user": "different"})
    assert Counting.calls == 2  # any change in the prompt is a miss


def test_cache_does_not_store_failures(tmp_path):
    class Failing:
        def complete_json(self, **kw):
            raise LLMError("down")

    llm = CachedLLM(Failing(), tmp_path)
    try:
        llm.complete_json(system="s", user="u", schema=ClassificationResult)
    except LLMError:
        pass
    assert list(tmp_path.glob("*.json")) == []
