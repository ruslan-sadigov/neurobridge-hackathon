from eval.metrics import evaluate_run, match

ANN = {"requirements": [
    {"id": "A", "page": 1, "category": "FINANCIAL", "mandatory_level": "MANDATORY", "anchors": ["turnover", "2500000"],
     "expected_status": "NOT_MET"},
    {"id": "B", "page": 1, "category": "LEGAL", "mandatory_level": "MANDATORY", "anchors": ["declaration"],
     "expected_status": "UNKNOWN"},
    {"id": "I", "page": 2, "category": "DOCUMENTATION", "mandatory_level": "INFORMATIONAL", "anchors": ["envelope"],
     "expected_status": "UNKNOWN"},
]}
CHUNKS = [{"document_id": "d", "page_number": 1, "text": "Average annual turnover must exceed 2 500 000 EUR."}]


def req(rid, text, status, level="MANDATORY", page=1, excerpt=None, evidence=(), method="DETERMINISTIC_RULE"):
    return {"requirement_id": rid, "text": text, "category": "FINANCIAL", "mandatory_level": level,
            "sources": [{"document_id": "d", "page": page, "excerpt": excerpt or text}],
            "result": {"status": status, "method": method, "supporting_evidence_ids": list(evidence), "rationale": "r"}}


def test_anchor_matching_ignores_spacing_and_is_one_to_one():
    reqs = [req("R1", "turnover must exceed 2.500.000 EUR", "NOT_MET")]
    matched, extra = match(ANN["requirements"], reqs)
    assert list(matched) == ["A"] and extra == []


def test_metrics_recall_accuracy_and_citation_validity():
    reqs = [req("R1", "Average annual turnover must exceed 2 500 000 EUR.", "MET"),
            req("R2", "invented", "UNKNOWN", excerpt="not on the page")]
    m = evaluate_run(ANN, reqs, CHUNKS)
    assert m["requirement_recall"] == 0.5 and m["missed"] == ["B"]
    assert m["compliance_accuracy"] == 0.0 and m["false_positive_met_rate"] == 1.0
    assert m["citation_validity"] == 0.5
    assert m["requirement_precision"] == 0.5


def test_unsupported_positive_rate_flags_llm_met_without_evidence():
    reqs = [req("R1", "turnover 2 500 000", "MET", method="LLM_SEMANTIC", evidence=())]
    assert evaluate_run(ANN, reqs, CHUNKS)["unsupported_positive_rate"] == 1.0


def test_acceptable_alternative_statuses_count_as_correct():
    ann = {"requirements": [{"id": "A", "page": 1, "category": "FINANCIAL", "mandatory_level": "MANDATORY",
                             "anchors": ["turnover"], "expected_status": "PARTIALLY_MET", "acceptable_statuses": ["UNKNOWN"]}]}
    for got, ok in (("PARTIALLY_MET", True), ("UNKNOWN", True), ("NOT_MET", False), ("MET", False)):
        m = evaluate_run(ann, [req("R1", "turnover must exceed", got)], CHUNKS)
        assert (m["compliance_accuracy"] == 1.0) is ok, got
    # a MET answer where only PARTIALLY_MET/UNKNOWN are accepted is not a "false MET", PARTIALLY_MET is allowed
    assert evaluate_run(ann, [req("R1", "turnover must exceed", "MET")], CHUNKS)["false_positive_met_rate"] == 0.0
