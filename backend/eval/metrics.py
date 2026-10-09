"""Evaluation metrics against a manually annotated tender (spec section 11). Pure functions, no LLM calls."""
from __future__ import annotations

import re
from typing import Any


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _page_text(chunks: list[dict], doc_id: str, page: int) -> str:
    return " ".join(norm(c["text"]) for c in chunks if c["document_id"] == doc_id and c["page_number"] == page)


def match(annotations: list[dict], reqs: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """One-to-one match of annotated items to extracted requirements by page + anchors."""
    used: set[str] = set()
    matched: dict[str, dict] = {}
    for a in annotations:
        for r in reqs:
            if r["requirement_id"] in used:
                continue
            for src in r["sources"]:
                blob = norm(r["text"] + " " + src["excerpt"])
                if src["page"] == a["page"] and all(norm(x) in blob for x in a["anchors"]):
                    matched[a["id"]] = r
                    used.add(r["requirement_id"])
                    break
            if a["id"] in matched:
                break
    return matched, [r for r in reqs if r["requirement_id"] not in used]


def evaluate_run(annotation: dict, reqs: list[dict], chunks: list[dict]) -> dict[str, Any]:
    """reqs: requirement dicts, each with a nested "result" (ComplianceResult)."""
    anns = annotation["requirements"]
    scored = [a for a in anns if a["mandatory_level"] != "INFORMATIONAL"]
    mandatory = [a for a in anns if a["mandatory_level"] == "MANDATORY"]
    matched, extra = match(anns, reqs)

    found = [a for a in scored if a["id"] in matched]
    missed = [a["id"] for a in scored if a["id"] not in matched]
    mand_found = [a for a in mandatory if a["id"] in matched]

    level_ok = sum(1 for a in anns if a["id"] in matched and matched[a["id"]]["mandatory_level"] == a["mandatory_level"])
    level_total = sum(1 for a in anns if a["id"] in matched)
    cat_ok = sum(1 for a in anns if a["id"] in matched and matched[a["id"]]["category"] == a["category"])

    status_rows = [(a, matched[a["id"]]) for a in scored if a["id"] in matched]
    status_ok = [a["id"] for a, r in status_rows if r["result"]["status"] == a["expected_status"]]
    status_wrong = [{"id": a["id"], "expected": a["expected_status"], "got": r["result"]["status"],
                     "why": r["result"]["rationale"][:140]} for a, r in status_rows
                    if r["result"]["status"] != a["expected_status"]]

    # citation validity: the cited excerpt really occurs on the cited page
    valid = total = 0
    for r in reqs:
        for s in r["sources"]:
            total += 1
            if norm(s["excerpt"]) and norm(s["excerpt"]) in _page_text(chunks, s["document_id"], s["page"]):
                valid += 1

    positives = [r for r in reqs if r["result"]["status"] in ("MET", "PARTIALLY_MET")]
    unsupported = [r for r in positives
                   if not r["result"]["supporting_evidence_ids"] and r["result"]["method"] != "DETERMINISTIC_RULE"]
    false_met = [a["id"] for a, r in status_rows
                 if r["result"]["status"] in ("MET", "PARTIALLY_MET") and a["expected_status"] in ("NOT_MET", "UNKNOWN")]

    def ratio(n, d):
        return round(n / d, 3) if d else None

    return {
        "n_extracted": len(reqs), "n_annotated_scored": len(scored),
        "requirement_recall": ratio(len(found), len(scored)),
        "mandatory_recall": ratio(len(mand_found), len(mandatory)),
        "requirement_precision": ratio(len(reqs) - len(extra), len(reqs)),
        "mandatory_level_accuracy": ratio(level_ok, level_total),
        "category_accuracy": ratio(cat_ok, level_total),
        "citation_validity": ratio(valid, total),
        "compliance_accuracy": ratio(len(status_ok), len(status_rows)),
        "false_positive_met_rate": ratio(len(false_met), len(status_rows)),
        "unsupported_positive_rate": ratio(len(unsupported), len(positives)),
        "missed": missed, "status_wrong": status_wrong,
        "unmatched_extracted": [{"id": r["requirement_id"], "page": r["sources"][0]["page"], "text": r["text"][:110],
                                 "level": r["mandatory_level"]} for r in extra],
    }


def aggregate(runs: list[dict]) -> dict[str, Any]:
    keys = [k for k, v in runs[0].items() if isinstance(v, (int, float)) or v is None]
    out = {}
    for k in keys:
        vals = [r[k] for r in runs if r[k] is not None]
        out[k] = {"mean": round(sum(vals) / len(vals), 3), "min": min(vals), "max": max(vals)} if vals else None
    return out
