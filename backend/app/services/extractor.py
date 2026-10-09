"""LLM requirement extraction (spec stages 3-4). Provenance is attached by the app, never by the model."""
from __future__ import annotations

import re

from ..adapters.llm import LLMClient, LLMError
from ..config import get_settings
from ..schemas import ExtractionResult, Requirement, SourceRef
from .parser import PageChunk

EXTRACT_SYSTEM = """Extract bidder requirements from the tender text. Rules:
- Only extract statements that impose a requirement on the bidder; skip descriptive/background text.
- mandatory_level: MANDATORY only for eligibility/qualification/compliance conditions the bidder must satisfy
  (legal status, exclusion grounds, financial capacity, experience, certifications, staffing, required documents/guarantees).
  Tender-process mechanics (submission deadline, language, envelope marking, how to submit, document purchase,
  validity period, number of lots one may bid for) are INFORMATIONAL. PREFERRED = should/advantage. UNKNOWN if unclear.
- category: one of LEGAL, FINANCIAL, TECHNICAL, EXPERIENCE, CERTIFICATION, PERSONNEL, DOCUMENTATION, DELIVERY, COMMERCIAL, CONTRACTUAL.
- normalized_rule: when measurable, fill rule_type (membership|threshold|count|date|boolean), field, operator (contains|>=|>|<=|<|==), value, unit.
  Supported fields: certifications (membership/contains), annual_revenue (threshold), employees (threshold),
  founded_year (threshold). Use projects_count (operator >= only) ONLY for a plain minimum number of projects with no
  similarity, value, tag or sector condition; otherwise rule_type = none. Never invent a rule for an upper bound.
  Put the currency code (EUR, USD, AZN) in unit for money thresholds.
- Be EXHAUSTIVE: output one item per distinct condition, obligation, guarantee, exclusion ground, threshold,
  period or limit that applies to the bidder or its tender. Do not merge separate conditions and do not skip
  boilerplate-looking clauses (eligibility/origin rules, exclusion lists, guarantees, validity, delivery periods).
- supporting_quote must be copied VERBATIM from the text. Keep the original language; do not translate."""

WINDOW_PAGES = 2  # pages per LLM call; overlap handled by dedup

GAP_SYSTEM = EXTRACT_SYSTEM + """

SECOND PASS: a first pass already extracted the requirements listed in <already_extracted>. Re-read the
document text and return ONLY additional requirements that are NOT yet covered. Return an empty list if none."""


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _locate(quote: str, pages: list[PageChunk]) -> PageChunk | None:
    q = _ws(quote)
    for p in pages:
        if q and q in _ws(p.text):
            return p
    return None


def extract_requirements(chunks: list[PageChunk], llm: LLMClient, start_index: int = 1) -> tuple[list[Requirement], list[str]]:
    """Returns (requirements, warnings). Quotes that cannot be found on any page are rejected (citation validity)."""
    s = get_settings()
    reqs: list[Requirement] = []
    warnings: list[str] = []
    by_doc: dict[str, list[PageChunk]] = {}
    for c in chunks:
        if c.text:
            by_doc.setdefault(c.document_id, []).append(c)

    n = start_index
    for doc_id, pages in by_doc.items():
        for i in range(0, len(pages), WINDOW_PAGES):
            window = pages[i:i + WINDOW_PAGES]
            body = "\n\n".join(f'<document id="{doc_id}" page="{p.page_number}">\n{p.text}\n</document>' for p in window)
            try:
                result = llm.complete_json(system=EXTRACT_SYSTEM, user=body, schema=ExtractionResult,
                                           model=s.extraction_model)
            except LLMError as e:  # explicit failure visibility (NFR-003)
                warnings.append(f"{doc_id} pages {window[0].page_number}-{window[-1].page_number}: {e}")
                continue
            items = list(result.requirements)
            if s.extraction_gap_pass:  # recall: LLMs under-extract dense pages, so ask for what is missing
                known = "\n".join(f"- {it.text}" for it in items) or "(none)"
                try:
                    more = llm.complete_json(system=GAP_SYSTEM, schema=ExtractionResult, model=s.extraction_model,
                                             user=f"<already_extracted>\n{known}\n</already_extracted>\n\n{body}")
                    items += more.requirements
                except LLMError as e:  # the first pass still stands; surface the failure
                    warnings.append(f"{doc_id} pages {window[0].page_number}-{window[-1].page_number}: gap pass failed: {e}")
            for item in items:
                page = _locate(item.supporting_quote, window)
                if page is None:
                    warnings.append(f"{doc_id}: dropped requirement with unverifiable quote: {item.text[:60]}")
                    continue
                reqs.append(Requirement(
                    requirement_id=f"REQ-{n:03d}", text=item.text, category=item.category,
                    mandatory_level=item.mandatory_level, normalized_rule=item.normalized_rule,
                    sources=[SourceRef(document_id=doc_id, page=page.page_number, excerpt=item.supporting_quote)],
                    extraction_confidence=item.extraction_confidence))
                n += 1
    return dedupe(reqs), warnings


def dedupe(reqs: list[Requirement]) -> list[Requirement]:
    """Merge near-identical requirements (same normalized text), keeping all source references (FR-024)."""
    merged: dict[str, Requirement] = {}
    for r in reqs:
        key = re.sub(r"\W+", " ", r.text.lower()).strip()
        if key in merged:
            merged[key].sources.extend(r.sources)
        else:
            merged[key] = r
    return list(merged.values())
