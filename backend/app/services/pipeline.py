"""Orchestrates the 10-stage pipeline for one analysis. Pure functions in, plain dicts out."""
from __future__ import annotations

import logging
import time
from typing import Any

from ..adapters.embeddings import Embedder
from ..adapters.llm import LLMClient
from ..schemas import Evidence, Requirement
from . import compliance, evidence as evidence_svc, extractor, matcher, risk, scoring
from .parser import PageChunk, coverage

log = logging.getLogger(__name__)


def run_analysis(chunks: list[PageChunk], profile: dict[str, Any], llm: LLMClient, embedder: Embedder) -> dict[str, Any]:
    timings: dict[str, float] = {}

    def stage(name: str):
        class _T:
            def __enter__(self_):
                self_.t = time.time()

            def __exit__(self_, *a):
                timings[name] = round(time.time() - self_.t, 2)
                log.info("stage %s took %.2fs", name, timings[name])
        return _T()

    with stage("extract"):
        reqs, warnings = extractor.extract_requirements(chunks, llm)
    with stage("evidence"):
        ev: list[Evidence] = evidence_svc.build_evidence(profile)
        complete_types = set(profile.get("complete_evidence_types", []))  # FR-012
        matches = matcher.match_evidence(reqs, ev, embedder)
    with stage("classify"):
        results = [compliance.classify(r, ev, matches[r.requirement_id], llm, complete_types) for r in reqs]
    with stage("risk_score"):
        risks = risk.build_risks(reqs, results)
        snapshot = scoring.compute_score(reqs, results, risks)

    cov = coverage(chunks)
    if cov < 1.0:
        warnings.append(f"Parsing coverage {cov:.0%}: some pages had no extractable text.")
    return {"requirements": reqs, "evidence": ev, "matches": matches, "results": results, "risks": risks,
            "score": snapshot, "warnings": warnings, "parsing_coverage": cov, "timings": timings}
