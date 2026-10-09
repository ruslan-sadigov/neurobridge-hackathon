"""Cross-document contradiction detection (spec FR-055, P1).

Two stages, so the model is only asked about pairs that could plausibly conflict:
1. Candidate pairs, found by code at no API cost: two requirements from different pages or documents that talk about
   the same thing (high content-word overlap) but state different numbers or dates, excluding different lots.
2. One batched LLM call judges the candidates. The model only returns a verdict and a short explanation; the
   statements and their citations come from the stored requirements, never from the model.

The tool surfaces potential conflicts with both sources. It does not decide which statement is right, and a later
document that amends an earlier one is still surfaced, because the bidder should confirm which applies.
"""
from __future__ import annotations

import logging
import re

from ..adapters.llm import LLMClient, LLMError
from ..config import get_settings
from ..enums import MandatoryLevel, ReasonCode, Severity
from ..schemas import Contradiction, ContradictionBatch, ContradictionStatement, Requirement, RiskItem
from .scope import LOT_RE

log = logging.getLogger(__name__)

MIN_OVERLAP = 0.3  # Jaccard overlap of content words for two statements to count as "about the same thing"
STOP = set("""the and for that this with shall must will should may can not are was were has have had its their his her
you your all any each per from into onto upon than then there these those which who whom whose such other also only
both either neither more most less least within without under over between about after before during while where when
what whether bidder bidders tenderer tenderers contract contracting authority tender tenders bid bids""".split())
NUM_RE = re.compile(r"\d[\d.,]*\d|\d")

JUDGE_SYSTEM = (
    "You receive several <pair> blocks, each with two statements (a and b) taken from the same tender package. "
    "For EACH pair decide whether the statements CONFLICT: they cannot both be true for the same bidder, lot and "
    "situation, typically because they give different values, dates, durations or obligations for the same thing. "
    "They do NOT conflict if they concern different lots, items, certificates or situations, if both can be satisfied "
    "at once, or if they say the same thing in different words. Do not decide which statement is right, and do not "
    "treat an amendment as resolving the conflict: if two statements differ, report the conflict. Explain a conflict "
    "in one short sentence that names the differing values. Return one result per pair, with pair_id copied exactly."
)


def _stem(w: str) -> str:
    return w[:5]


def _content_words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[^\W\d_]{3,}", text.lower()) if w not in STOP}


def _numbers(text: str) -> set[str]:
    return {re.sub(r"[.,]", "", n) for n in NUM_RE.findall(text)}


def _place(r: Requirement) -> tuple[str, int]:
    s = r.sources[0]
    return s.document_id, s.page


def candidate_pairs(reqs: list[Requirement], max_pairs: int | None = None) -> list[tuple[Requirement, Requirement, float]]:
    """Plausible conflicts, most similar first. Pure code, no API calls."""
    max_pairs = max_pairs or get_settings().contradiction_max_pairs
    words = {r.requirement_id: _content_words(r.text) for r in reqs}
    nums = {r.requirement_id: _numbers(r.text) for r in reqs}
    lots = {r.requirement_id: set(LOT_RE.findall(r.text)) for r in reqs}
    out: list[tuple[Requirement, Requirement, float]] = []
    for i, a in enumerate(reqs):
        for b in reqs[i + 1:]:
            if _place(a) == _place(b):  # same page: restatements of one sentence, not separate sources
                continue
            la, lb = lots[a.requirement_id], lots[b.requirement_id]
            if la and lb and not (la & lb):  # Lot 1 vs Lot 2 may legitimately differ
                continue
            na, nb = nums[a.requirement_id], nums[b.requirement_id]
            if not (na or nb) or na == nb:  # a conflict needs a differing number or date
                continue
            wa, wb = words[a.requirement_id], words[b.requirement_id]
            if not wa or not wb:
                continue
            score = len(wa & wb) / len(wa | wb)
            if score >= MIN_OVERLAP:
                out.append((a, b, score))
    out.sort(key=lambda t: -t[2])
    return out[:max_pairs]


def _statement(r: Requirement) -> ContradictionStatement:
    s = r.sources[0]
    return ContradictionStatement(requirement_id=r.requirement_id, text=r.text, document_id=s.document_id,
                                  page=s.page, excerpt=s.excerpt)


def detect(reqs: list[Requirement], llm: LLMClient | None, batch_size: int = 8,
           warnings: list[str] | None = None) -> list[Contradiction]:
    warnings = warnings if warnings is not None else []
    if llm is None:
        return []
    pairs = candidate_pairs(reqs)
    found: list[Contradiction] = []
    for i in range(0, len(pairs), batch_size):
        chunk = pairs[i:i + batch_size]
        user = "\n".join(
            f'<pair id="P{i + k + 1}">\n<a source="{a.sources[0].document_id} p{a.sources[0].page}">{a.text}</a>\n'
            f'<b source="{b.sources[0].document_id} p{b.sources[0].page}">{b.text}</b>\n</pair>'
            for k, (a, b, _) in enumerate(chunk))
        try:
            batch = llm.complete_json(system=JUDGE_SYSTEM, user=user, schema=ContradictionBatch,
                                      model=get_settings().classification_model)
        except LLMError as e:  # never invent conflicts, and never fail the whole analysis for an optional feature
            warnings.append(f"Contradiction check failed for {len(chunk)} candidate pair(s): {e}")
            continue
        verdicts = {v.pair_id: v for v in batch.results}
        for k, (a, b, _) in enumerate(chunk):
            v = verdicts.get(f"P{i + k + 1}")
            if v is None or not v.conflict:
                continue
            mandatory = MandatoryLevel.MANDATORY in (a.mandatory_level, b.mandatory_level)
            found.append(Contradiction(
                contradiction_id=f"CON-{len(found) + 1:03d}", statements=[_statement(a), _statement(b)],
                explanation=v.explanation[:400], severity=Severity.HIGH if mandatory else Severity.MEDIUM))
    return found


def to_risks(cons: list[Contradiction]) -> list[RiskItem]:
    """A conflict becomes a risk so it shows up with the other risks and affects the recommendation (conditions)."""
    return [RiskItem(
        requirement_id=c.statements[0].requirement_id, severity=c.severity, reason_code=ReasonCode.CONFLICTING_TENDER_TERMS,
        explanation=f"Conflicting tender terms ({c.contradiction_id}): {c.explanation}",
        recommended_action="Ask the buyer to clarify which statement applies before submitting.") for c in cons]
