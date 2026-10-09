"""Orchestrates the 10-stage pipeline for one analysis. Pure functions in, plain dicts out."""
from __future__ import annotations

import logging
import time
from typing import Any

from ..adapters.embeddings import Embedder
from ..adapters.llm import LLMClient
from ..enums import MandatoryLevel, Method, Status
from ..schemas import ComplianceResult, Evidence, Requirement
from . import compliance, evidence as evidence_svc, extractor, matcher, risk, scope, scoring
from .parser import PageChunk, coverage

log = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """The analysis cannot produce a trustworthy result; the job must be FAILED, not COMPLETE."""


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
    if not reqs:  # NFR-003: never report success with silently missing sections
        detail = "; ".join(warnings[:3]) or "the documents contain no extractable text"
        raise PipelineError(f"No requirements were extracted. {detail}")
    with stage("evidence"):
        # Lot scope: requirements that only name lots the supplier is not bidding for are not scored.
        skipped = scope.out_of_scope(reqs, profile.get("bid_lots"))
        for r in reqs:
            if r.requirement_id in skipped:
                r.mandatory_level = MandatoryLevel.INFORMATIONAL
        ev: list[Evidence] = evidence_svc.build_evidence(profile)
        complete_types = set(profile.get("complete_evidence_types", []))  # FR-012
        matches = matcher.match_evidence(reqs, ev, embedder)
    with stage("classify"):
        fx = profile.get("fx_rates")
        results = compliance.classify_many(reqs, ev, matches, llm, complete_types, fx, warnings=warnings)
        for i, r in enumerate(reqs):
            if r.requirement_id in skipped:
                named, targets = skipped[r.requirement_id]
                results[i] = ComplianceResult(
                    requirement_id=r.requirement_id, status=Status.UNKNOWN, method=Method.NO_EVIDENCE, confidence=1.0,
                    rationale=(f"Applies only to Lot {', '.join(named)}; this supplier is bidding for "
                               f"Lot {', '.join(targets)}. Not assessed."))
    with stage("risk_score"):
        risks = risk.build_risks(reqs, results)
        snapshot = scoring.compute_score(reqs, results, risks)

    cov = coverage(chunks)
    if cov < 1.0:
        warnings.append(f"Parsing coverage {cov:.0%}: some pages had no extractable text.")
    return {"requirements": reqs, "evidence": ev, "matches": matches, "results": results, "risks": risks,
            "score": snapshot, "warnings": warnings, "parsing_coverage": cov, "timings": timings}
