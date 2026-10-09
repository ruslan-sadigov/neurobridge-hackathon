"""Verify that a quote returned by the model really comes from the tender, and cite the tender's own words.

LLMs often "tidy" a quote slightly (fix a typo in the source, change punctuation) or quote a sentence that runs
across a page break. A strict substring check rejects those and silently loses real requirements. This matcher
accepts a quote when almost all of its words appear, in order and contiguously, in the page text, and then returns
the PAGE's own wording as the excerpt, so every stored citation stays verbatim and checkable.

A quote that is not in the document (invented or heavily rewritten) is still rejected.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from .parser import PageChunk

MIN_WORDS = 4  # shorter quotes are too weak to verify
MIN_MATCH = 0.9  # share of the quote's words that must be found in the page text
MAX_SPAN = 1.25  # the matched region may be at most this many times the quote length (keeps it contiguous)


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _norm_word(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())


def locate_quote(quote: str, pages: list[PageChunk]) -> tuple[PageChunk, str] | None:
    """Return (page, excerpt) or None. Excerpt is taken from the page text, never from the model's quote,
    except for an exact match where the two are the same up to whitespace and case."""
    q_exact = _ws(quote)
    if not q_exact:
        return None
    for p in pages:  # 1. exact match on one page (keeps current behaviour)
        if q_exact in _ws(p.text):
            return p, quote.strip()

    q = [w for w in (_norm_word(x) for x in quote.split()) if w]
    if len(q) < MIN_WORDS:
        return None

    # 2. tolerant match over the whole window, so a sentence crossing a page break can be found
    stream: list[tuple[str, int, int, int]] = []  # (word, start, end, page index)
    for pi, p in enumerate(pages):
        for m in re.finditer(r"\S+", p.text):
            w = _norm_word(m.group(0))
            if w:
                stream.append((w, m.start(), m.end(), pi))
    blocks = [b for b in SequenceMatcher(None, [t[0] for t in stream], q, autojunk=False).get_matching_blocks() if b.size]
    if not blocks or sum(b.size for b in blocks) < MIN_MATCH * len(q):
        return None
    # Contiguity is checked per page: a sentence that continues on the next page is interrupted by that page's
    # running header, which must not count as a gap inside the quote.
    by_page: dict[int, list[int]] = {}
    for b in blocks:
        for i in range(b.a, b.a + b.size):
            by_page.setdefault(stream[i][3], []).append(i)
    for idxs in by_page.values():
        if idxs[-1] - idxs[0] + 1 > MAX_SPAN * len(idxs) + 2:
            return None

    # cite the page that holds most of the matched words; the excerpt is that page's own text
    page_idx = max(by_page, key=lambda k: len(by_page[k]))
    start, end = stream[by_page[page_idx][0]][1], stream[by_page[page_idx][-1]][2]
    return pages[page_idx], re.sub(r"\s+", " ", pages[page_idx].text[start:end]).strip()
