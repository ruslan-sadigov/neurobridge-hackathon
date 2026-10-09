"""Hybrid evidence retrieval (FR-030): structured type boost + embedding similarity."""
from __future__ import annotations

import numpy as np

from ..adapters.embeddings import Embedder
from ..enums import Category
from ..schemas import Evidence, Requirement

CATEGORY_TYPES: dict[Category, set[str]] = {
    Category.CERTIFICATION: {"CERTIFICATE", "DOCUMENT"},
    Category.FINANCIAL: {"FINANCIAL"},
    Category.EXPERIENCE: {"PROJECT"},
    Category.DOCUMENTATION: {"DOCUMENT", "CERTIFICATE"},
    Category.LEGAL: {"DOCUMENT", "COMPANY_FACT"},
    Category.PERSONNEL: {"COMPANY_FACT", "DOCUMENT"},
}
TYPE_BOOST = 0.15


def match_evidence(reqs: list[Requirement], evidence: list[Evidence], embedder: Embedder,
                   top_k: int = 3) -> dict[str, list[tuple[Evidence, float]]]:
    if not reqs or not evidence:
        return {r.requirement_id: [] for r in reqs}
    ev_vecs = embedder.embed([f"{e.label}. {e.text}" for e in evidence])
    req_vecs = embedder.embed([r.text for r in reqs])
    sims = req_vecs @ ev_vecs.T
    out: dict[str, list[tuple[Evidence, float]]] = {}
    for i, r in enumerate(reqs):
        boost_types = CATEGORY_TYPES.get(r.category, set())
        scores = np.array([sims[i, j] + (TYPE_BOOST if evidence[j].type in boost_types else 0.0)
                           for j in range(len(evidence))])
        order = np.argsort(-scores)[:top_k]
        out[r.requirement_id] = [(evidence[j], float(scores[j])) for j in order if scores[j] > 0.05]
    return out
