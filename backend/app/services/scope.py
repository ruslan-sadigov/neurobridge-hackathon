"""Lot scope: a tender may be split into lots and a supplier usually bids for some of them.

Requirements that name only lots the supplier is NOT bidding for cannot disqualify the bid, so they are marked
out of scope instead of being scored. A requirement that names no lot, or names at least one targeted lot, stays in.
"""
from __future__ import annotations

import re

from ..schemas import Requirement

LOT_RE = re.compile(r"\blot\s*(\d+)\b", re.I)


def normalize_lots(values) -> set[str]:
    """['Lot 2', 2, '2'] -> {'2'}"""
    out: set[str] = set()
    for v in values or []:
        m = re.search(r"\d+", str(v))
        if m:
            out.add(m.group(0))
    return out


JV_RE = re.compile(r"\b(?:jv|joint[- ]venture)", re.I)
SINGLE_RE = re.compile(r"\bsingle\b", re.I)


def jv_only(reqs: list[Requirement], bid_as: str | None) -> set[str]:
    """Ids of requirements that apply only to joint-venture bids, when the supplier bids alone (bid_as == "single").

    A condition that names a joint venture and does not also address a single bidder is a JV-only condition.
    """
    if str(bid_as or "").lower() != "single":
        return set()
    return {r.requirement_id for r in reqs if JV_RE.search(r.text) and not SINGLE_RE.search(r.text)}


def out_of_scope(reqs: list[Requirement], bid_lots) -> dict[str, tuple[list[str], list[str]]]:
    """requirement_id -> (lots the requirement names, lots the supplier bids for). Empty if no scope is declared."""
    targets = normalize_lots(bid_lots)
    if not targets:
        return {}
    result: dict[str, tuple[list[str], list[str]]] = {}
    for r in reqs:
        named = set(LOT_RE.findall(r.text))
        if named and not (named & targets):
            result[r.requirement_id] = (sorted(named), sorted(targets))
    return result
