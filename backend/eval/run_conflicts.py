"""Measure contradiction detection on the synthetic package: planted conflicts found, decoys wrongly flagged.

  python -m eval.run_conflicts eval/annotations/SYN_conflicts.json --runs 3     # calls the LLM
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ["LLM_CACHE"] = "false"  # measure real behaviour, never replayed answers

from .metrics import norm  # noqa: E402


def blob(statement: dict) -> str:
    return norm(statement["text"] + " " + statement["excerpt"])


def matches(con: dict, pair: dict) -> bool:
    """True if one statement contains all anchors of side a and the other all anchors of side b (either order)."""
    s1, s2 = blob(con["statements"][0]), blob(con["statements"][1])
    a, b = [norm(x) for x in pair["a"]], [norm(x) for x in pair["b"]]
    return ((all(x in s1 for x in a) and all(x in s2 for x in b))
            or (all(x in s2 for x in a) and all(x in s1 for x in b)))


def score(annotation: dict, cons: list[dict]) -> dict:
    found = [c["id"] for c in annotation["planted_conflicts"] if any(matches(k, c) for k in cons)]
    decoys = [d["id"] for d in annotation["decoys"] if any(matches(k, d) for k in cons)]
    explained = {k["contradiction_id"] for p in annotation["planted_conflicts"] + annotation["decoys"]
                 for k in cons if matches(k, p)}
    other = [k["contradiction_id"] for k in cons if k["contradiction_id"] not in explained]
    n = len(annotation["planted_conflicts"])
    return {"planted_found": found, "recall": round(len(found) / n, 3), "decoys_flagged": decoys,
            "other_flagged": other, "precision": round(len(found) / len(cons), 3) if cons else None, "n_flagged": len(cons)}


def run_once(annotation: dict) -> tuple[list[dict], list[str]]:
    from app.adapters.embeddings import get_embedder
    from app.adapters.llm import get_llm
    from app.services.parser import parse_pdf
    from app.services.pipeline import run_analysis

    chunks = []
    for f in annotation["tender_files"]:
        p = Path(f)
        chunks += parse_pdf(p.stem, p.read_bytes())
    profile = json.loads(Path(annotation["supplier_file"]).read_text(encoding="utf-8"))
    res = run_analysis(chunks, profile, get_llm(), get_embedder())
    return [c.model_dump(mode="json") for c in res["contradictions"]], res["warnings"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("annotation")
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    annotation = json.loads(Path(args.annotation).read_text(encoding="utf-8"))
    from app.adapters.llm import REQUEST_COUNT

    out = Path("eval/results/SYN_conflicts_runs.json")
    all_runs: list[dict] = []
    for i in range(args.runs):
        before = REQUEST_COUNT["n"]
        try:
            cons, warnings = run_once(annotation)
            error = next((w for w in warnings if "failed" in w), None)  # a failed model call makes the run invalid
        except Exception as e:  # e.g. quota exhausted: record it, never score it
            cons, error = [], str(e)[:200]
        run = {"api_requests": REQUEST_COUNT["n"] - before}
        if error:
            run.update(valid=False, error=error)
            print(f"run {i + 1}: INVALID (not scored): {error[:120]}")
        else:
            run.update(valid=True, contradictions=cons, score=score(annotation, cons))
            print(f"run {i + 1}: {json.dumps(run['score'])}")
        all_runs.append(run)
        out.write_text(json.dumps(all_runs, ensure_ascii=False, indent=1), encoding="utf-8")  # saved after every run
    valid = [r for r in all_runs if r["valid"]]
    print(f"valid runs: {len(valid)}/{len(all_runs)}")

if __name__ == "__main__":
    main()
