"""Contradiction detection: candidate generation (code) and judging (fake model)."""
from app.adapters.llm import LLMError
from app.enums import Category, MandatoryLevel, ReasonCode, Severity
from app.schemas import ContradictionBatch, NormalizedRule, PairVerdict, Requirement, SourceRef
from app.services import contradictions as con


def req(rid, text, doc="d1", page=1, level=MandatoryLevel.MANDATORY, cat=Category.COMMERCIAL):
    return Requirement(requirement_id=rid, text=text, category=cat, mandatory_level=level, normalized_rule=NormalizedRule(),
                       sources=[SourceRef(document_id=doc, page=page, excerpt=text)], extraction_confidence=0.9)


DEADLINE_A = req("A", "Tenders must be submitted by 15 March 2027 at 12:00", "tender", 1, MandatoryLevel.INFORMATIONAL)
DEADLINE_B = req("B", "The deadline for submission of tenders is 22 March 2027 at 12:00", "datasheet", 2, MandatoryLevel.INFORMATIONAL)
TURN_A = req("C", "Average annual turnover over the last three years must be at least EUR 2,000,000", "tender", 1, cat=Category.FINANCIAL)
TURN_B = req("D", "Minimum average annual turnover of EUR 3,000,000 is required", "datasheet", 2, cat=Category.FINANCIAL)


def ids(pairs):
    return {frozenset((a.requirement_id, b.requirement_id)) for a, b, _ in pairs}


def test_conflicting_values_about_the_same_thing_become_candidates():
    pairs = con.candidate_pairs([DEADLINE_A, DEADLINE_B, TURN_A, TURN_B])
    assert ids(pairs) == {frozenset("AB"), frozenset("CD")}  # deadline vs deadline, turnover vs turnover, not crossed


def test_different_lots_are_not_candidates():
    a = req("A", "For Lot 1 the performance guarantee is 5% of the contract value", "tender", 1)
    b = req("B", "For Lot 2 the performance guarantee is 10% of the contract value", "datasheet", 2)
    assert con.candidate_pairs([a, b]) == []


def test_identical_numbers_same_page_and_unrelated_text_are_not_candidates():
    same_numbers = req("B", "A bid security of EUR 50,000 is required", "datasheet", 2)
    assert con.candidate_pairs([req("A", "The bid security is EUR 50,000", "tender", 1), same_numbers]) == []
    same_page = req("B", "The deadline for submission of tenders is 22 March 2027 at 12:00", "tender", 1)
    assert con.candidate_pairs([DEADLINE_A, same_page]) == []  # same document and page
    unrelated = req("B", "Delivery must be completed within 120 calendar days", "datasheet", 2)
    assert con.candidate_pairs([DEADLINE_A, unrelated]) == []


class Judge:
    """Fake model: marks the listed pair ids as conflicts."""

    def __init__(self, conflicts=(), fail=False):
        self.calls, self.conflicts, self.fail = 0, set(conflicts), fail

    def complete_json(self, *, system, user, schema, **kw):
        self.calls += 1
        if self.fail:
            raise LLMError("down")
        pair_ids = [p.split('"')[0] for p in user.split('<pair id="')[1:]]
        return ContradictionBatch(results=[PairVerdict(pair_id=p, conflict=p in self.conflicts,
                                                       explanation="dates differ: 15 March vs 22 March") for p in pair_ids])


def test_confirmed_conflict_carries_both_citations_from_the_stored_requirements():
    judge = Judge(conflicts={"P1", "P2"})
    found = con.detect([DEADLINE_A, DEADLINE_B], judge)
    assert judge.calls == 1 and len(found) == 1
    c = found[0]
    assert [s.document_id for s in c.statements] == ["tender", "datasheet"]
    assert [s.page for s in c.statements] == [1, 2]
    assert c.statements[0].text == DEADLINE_A.text  # taken from our records, not from the model
    assert c.severity == Severity.MEDIUM  # both informational


def test_mandatory_conflict_is_high_severity_and_becomes_a_risk():
    found = con.detect([TURN_A, TURN_B], Judge(conflicts={"P1"}))
    assert found[0].severity == Severity.HIGH
    risk = con.to_risks(found)[0]
    assert risk.reason_code == ReasonCode.CONFLICTING_TENDER_TERMS and risk.severity == Severity.HIGH
    assert "clarify" in risk.recommended_action


def test_no_candidates_means_no_model_call():
    judge = Judge(conflicts={"P1"})
    assert con.detect([DEADLINE_A, req("B", "Delivery within 120 days", "d2", 2)], judge) == [] and judge.calls == 0


def test_candidates_the_model_rejects_are_dropped():
    assert con.detect([DEADLINE_A, DEADLINE_B], Judge(conflicts=())) == []


def test_model_failure_does_not_fail_the_analysis_or_invent_conflicts():
    warnings: list[str] = []
    assert con.detect([DEADLINE_A, DEADLINE_B], Judge(fail=True), warnings=warnings) == []
    assert len(warnings) == 1 and "Contradiction check failed" in warnings[0]
    assert con.detect([DEADLINE_A, DEADLINE_B], None) == []


def test_pairs_are_batched():
    reqs = [req(f"R{i}", f"Tenders must be submitted by {10 + i} March 2027 at 12:00", f"doc{i}", 1) for i in range(5)]
    judge = Judge()
    con.detect(reqs, judge, batch_size=4)  # 10 candidate pairs -> 3 calls
    assert judge.calls == 3
