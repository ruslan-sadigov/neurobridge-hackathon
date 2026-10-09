"""Run the pipeline on an annotated tender and score it.

  python -m eval.run_eval eval/annotations/TR_CFCU.json --runs 3        # calls the LLM (~25-40 calls per run)
  python -m eval.run_eval eval/annotations/TR_CFCU.json --replay eval/results/TR_CFCU_runs.json   # no LLM calls
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .metrics import aggregate, evaluate_run


def run_once(annotation: dict) -> tuple[list[dict], list[dict]]:
    from app.adapters.embeddings import get_embedder
    from app.adapters.llm import get_llm
    from app.services.parser import parse_pdf
    from app.services.pipeline import run_analysis

    tender = Path(annotation["tender_file"])
    chunks = parse_pdf(tender.stem, tender.read_bytes())
    profile = json.loads(Path(annotation["supplier_file"]).read_text(encoding="utf-8"))
    res = run_analysis(chunks, profile, get_llm(), get_embedder())
    by_id = {c.requirement_id: c for c in res["results"]}
    reqs = [{**r.model_dump(mode="json"), "result": by_id[r.requirement_id].model_dump(mode="json")}
            for r in res["requirements"]]
    chunk_dicts = [{"document_id": c.document_id, "page_number": c.page_number, "text": c.text} for c in chunks]
    return reqs, chunk_dicts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("annotation")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--replay", help="score stored runs instead of calling the LLM")
    args = ap.parse_args()

    annotation = json.loads(Path(args.annotation).read_text(encoding="utf-8"))
    if annotation["annotation_status"].startswith("DRAFT"):
        print("WARNING: annotations are still DRAFT - metrics are provisional until a human freezes them.\n")

    stored = json.loads(Path(args.replay).read_text(encoding="utf-8")) if args.replay else None
    runs_data = stored["runs"] if stored else []
    if not stored:
        for i in range(args.runs):
            print(f"run {i + 1}/{args.runs} ...", flush=True)
            reqs, chunks = run_once(annotation)
            runs_data.append({"requirements": reqs, "chunks": chunks})
        out = Path("eval/results") / f"{Path(args.annotation).stem}_runs.json"
        out.write_text(json.dumps({"runs": runs_data}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("saved", out)

    per_run = [evaluate_run(annotation, r["requirements"], r["chunks"]) for r in runs_data]
    agg = aggregate(per_run)
    print(json.dumps({k: v for k, v in agg.items()}, indent=1))
    last = per_run[-1]
    print("\nmissed (last run):", last["missed"])
    print("wrong statuses (last run):", json.dumps(last["status_wrong"], indent=1))
    print("unmatched extracted (last run):", json.dumps(last["unmatched_extracted"], indent=1))
    report = Path("eval/results") / f"{Path(args.annotation).stem}_report.json"
    report.write_text(json.dumps({"aggregate": agg, "per_run": per_run}, indent=1), encoding="utf-8")
    print("report ->", report)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
