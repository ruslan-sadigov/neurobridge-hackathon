"""Transparent weighted score + veto logic (spec section 7). Pure functions, no LLM."""
from __future__ import annotations

from ..enums import Category, MandatoryLevel, ReasonCode, Recommendation, Severity, Status
from ..schemas import ComplianceResult, DimensionScore, Requirement, RiskItem, ScoreSnapshot

WEIGHTS: dict[str, float] = {
    "Mandatory compliance": 0.40, "Technical fit": 0.20, "Experience": 0.15,
    "Financial eligibility": 0.10, "Documentation readiness": 0.10, "Delivery feasibility": 0.05,
}
STATUS_POINTS: dict[Status, float] = {
    Status.MET: 1.0, Status.PARTIALLY_MET: 0.5, Status.NOT_MET: 0.0, Status.UNKNOWN: 0.25,
}
CATEGORY_DIMENSION: dict[Category, str] = {
    Category.TECHNICAL: "Technical fit", Category.EXPERIENCE: "Experience",
    Category.FINANCIAL: "Financial eligibility", Category.DOCUMENTATION: "Documentation readiness",
    Category.CERTIFICATION: "Documentation readiness", Category.DELIVERY: "Delivery feasibility",
}
LEVEL_WEIGHT = {MandatoryLevel.MANDATORY: 1.0, MandatoryLevel.PREFERRED: 0.5,
                MandatoryLevel.UNKNOWN: 0.5, MandatoryLevel.INFORMATIONAL: 0.0}


def _dim(name: str, items: list[tuple[Requirement, ComplianceResult]],
         points: dict[Status, float]) -> DimensionScore:
    weighted = [(LEVEL_WEIGHT[r.mandatory_level], c) for r, c in items if LEVEL_WEIGHT[r.mandatory_level] > 0]
    total = sum(w for w, _ in weighted)
    if total == 0:
        return DimensionScore(name=name, weight=WEIGHTS[name], score=None, coverage=None, requirement_count=0)
    score = sum(w * points[c.status] for w, c in weighted) / total
    known = sum(w for w, c in weighted if c.status != Status.UNKNOWN) / total
    return DimensionScore(name=name, weight=WEIGHTS[name], score=score, coverage=known,
                          requirement_count=len(weighted))


def decide(risks: list[RiskItem]) -> tuple[Recommendation, list[ReasonCode]]:
    """Veto: a critical mandatory gap can never be hidden by a high aggregate score."""
    critical = [k for k in risks if k.severity == Severity.CRITICAL]
    if critical:
        return Recommendation.NO_GO, sorted({k.reason_code for k in critical}, key=lambda c: c.value)
    conditional = [k for k in risks if k.severity in (Severity.HIGH, Severity.MEDIUM)]
    if conditional:
        return Recommendation.GO_WITH_CONDITIONS, sorted({k.reason_code for k in conditional},
                                                         key=lambda c: c.value)
    return Recommendation.GO, [ReasonCode.ALL_CRITICAL_MANDATORY_MET]


def compute_score(reqs: list[Requirement], results: list[ComplianceResult], risks: list[RiskItem],
                  points: dict[Status, float] | None = None) -> ScoreSnapshot:
    points = points or STATUS_POINTS
    res_by_id = {c.requirement_id: c for c in results}
    pairs = [(r, res_by_id[r.requirement_id]) for r in reqs if r.requirement_id in res_by_id]

    groups: dict[str, list] = {n: [] for n in WEIGHTS}
    for r, c in pairs:
        if r.mandatory_level == MandatoryLevel.MANDATORY:
            groups["Mandatory compliance"].append((r, c))
        dim = CATEGORY_DIMENSION.get(r.category)
        if dim:
            groups[dim].append((r, c))
    dims = [_dim(n, items, points) for n, items in groups.items()]

    # Dimensions with no requirements are dropped and weights renormalised.
    active = [d for d in dims if d.score is not None]
    wsum = sum(d.weight for d in active)
    final = 100 * sum(d.score * d.weight for d in active) / wsum if wsum else 0.0

    scored = [c for r, c in pairs if LEVEL_WEIGHT[r.mandatory_level] > 0]
    coverage = sum(1 for c in scored if c.status != Status.UNKNOWN) / len(scored) if scored else 0.0

    recommendation, codes = decide(risks)
    return ScoreSnapshot(
        dimensions=dims, final_score=round(final, 1), recommendation=recommendation, reason_codes=codes,
        overall_coverage=round(coverage, 3),
        config={"weights": WEIGHTS, "status_points": {k.value: v for k, v in points.items()},
                "level_weights": {k.value: v for k, v in LEVEL_WEIGHT.items()}})
