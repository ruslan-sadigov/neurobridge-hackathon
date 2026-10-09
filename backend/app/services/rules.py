"""Deterministic rule engine (FR-031). Returns None when operands are missing -> caller falls back / UNKNOWN."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from datetime import date
from typing import Any, Callable, Optional

from ..enums import RuleType, Status
from ..schemas import Evidence, NormalizedRule

OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
}


@dataclass
class RuleOutcome:
    status: Status
    evidence_ids: list[str] = field(default_factory=list)
    rationale: str = ""


def _norm(s: Any) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


# Only the AZN/USD peg is built in. Any other currency (EUR, ...) must be supplied by the supplier
# profile ("fx_rates": {"EUR": <AZN per 1 EUR>}); otherwise the check is UNKNOWN, never a bare-number compare.
DEFAULT_FX: dict[str, float] = {"AZN": 1.0, "USD": 1.70}


# The LLM may map a requirement onto the wrong supplier field (e.g. "bid security 200,000" -> annual_revenue).
# A rule only runs deterministically when the requirement text actually talks about that field.
FIELD_KEYWORDS: dict[str, str] = {
    "annual_revenue": r"turnover|revenue|sales",
    "employees": r"staff|employee|personnel|headcount|workforce",
    "founded_year": r"founded|established|incorporat|years? (of|in) (experience|operation|business)|in operation",
    "projects_count": r"contract|project|reference|deliver|install|complet",
}


def field_matches_text(rule: NormalizedRule, text: str) -> bool:
    pattern = FIELD_KEYWORDS.get(rule.field or "")
    return True if pattern is None else bool(re.search(pattern, text, re.I))


def _currency(unit: Any) -> str | None:
    u = str(unit or "").strip().upper()
    return u if len(u) == 3 and u.isalpha() else None


def _convert(amount: float, src: str, dst: str, fx: dict[str, float]) -> float | None:
    if src == dst:
        return amount
    if src not in fx or dst not in fx:
        return None
    return amount * fx[src] / fx[dst]


def evaluate(rule: NormalizedRule, evidence: list[Evidence], *, complete_types: set[str] | None = None,
             today: Optional[date] = None, fx_rates: dict[str, float] | None = None) -> Optional[RuleOutcome]:
    complete_types = complete_types or set()
    fx = {**DEFAULT_FX, **(fx_rates or {})}
    today = today or date.today()
    if rule.rule_type == RuleType.NONE or not rule.field:
        return None
    if rule.rule_type == RuleType.MEMBERSHIP:
        return _membership(rule, evidence, complete_types, today)
    if rule.rule_type in (RuleType.THRESHOLD, RuleType.COUNT):
        return _numeric(rule, evidence, fx)
    return None


def _membership(rule, evidence, complete_types, today) -> Optional[RuleOutcome]:
    # A certificate rule only makes sense for a named certificate or standard ("ISO 27001", "CMMI", "PCI DSS").
    # The model sometimes turns a declaration ("certify that all software is licensed") into one; leave those to
    # semantic review instead of failing the supplier for lacking a "certificate" with that name.
    if not re.search(r"\d|[A-Z]{2,}", str(rule.value or "")):
        return None
    wanted = _norm(rule.value)
    certs = [e for e in evidence if e.type == "CERTIFICATE"]
    hits = [e for e in certs if wanted and wanted in _norm(e.value)]
    if hits:
        valid = [e for e in hits if not e.expiry_date or date.fromisoformat(e.expiry_date) >= today]
        if valid:
            return RuleOutcome(Status.MET, [e.evidence_id for e in valid], f"{rule.value} certificate present and valid.")
        return RuleOutcome(Status.NOT_MET, [e.evidence_id for e in hits], f"{rule.value} certificate found but expired.")
    # Absence only means NOT_MET if the profile is declared complete for this category (FR-012).
    if "CERTIFICATE" in complete_types:
        have = ", ".join(str(e.value) for e in certs) or "none"
        return RuleOutcome(Status.NOT_MET, [], f"{rule.value} was required; supplier profile contains: {have}.")
    return None


def _numeric(rule, evidence, fx) -> Optional[RuleOutcome]:
    if rule.operator not in OPS or rule.value is None:
        return None
    try:
        target = float(rule.value)
    except (TypeError, ValueError):
        return None

    unit_label: str | None = None
    if rule.field == "projects_count":
        # Only a plain "at least N projects" is deterministic. Similarity wording, value or tag constraints
        # need semantic judgement, and an upper bound on project count is meaningless.
        meaningful = {k for k, v in rule.filters.items() if v not in (None, "", [], {})}
        if meaningful - {"lot"} or rule.operator not in (">=", ">", "=="):
            return None
        projects = [e for e in evidence if e.type == "PROJECT"]
        actual: float = len(projects)
        ids = [p.evidence_id for p in projects]
    elif rule.field == "annual_revenue":
        revs = sorted((e for e in evidence if e.type == "FINANCIAL"), key=lambda e: e.metadata.get("year", 0))
        if not revs:
            return None
        actual, ids = float(revs[-1].value), [revs[-1].evidence_id]
        want_cur, have_cur = _currency(rule.unit), revs[-1].metadata.get("currency")
        if want_cur and have_cur:  # compare in the supplier's currency, or give up -> UNKNOWN
            converted = _convert(target, want_cur, have_cur, fx)
            if converted is None:
                return None
            target = converted
            unit_label = f" {have_cur}"
    else:  # company facts: employees, founded_year, ...
        facts = [e for e in evidence if e.type == "COMPANY_FACT" and e.label == rule.field]
        if not facts:
            return None
        try:
            actual, ids = float(facts[0].value), [facts[0].evidence_id]
        except (TypeError, ValueError):  # a text fact (e.g. a country) cannot be compared numerically
            return None

    ok = OPS[rule.operator](actual, target)
    unit = unit_label if unit_label is not None else (f" {rule.unit}" if rule.unit else "")
    detail = f"required {rule.field} {rule.operator} {target:,.0f}{unit}; supplier has {actual:,.0f}{unit}."
    if ok:
        return RuleOutcome(Status.MET, ids, detail)
    # count shortfall with some matches is PARTIAL (e.g. 1 of 2 projects)
    if rule.rule_type == RuleType.COUNT and actual > 0 and rule.operator in (">=", ">"):
        return RuleOutcome(Status.PARTIALLY_MET, ids, detail)
    return RuleOutcome(Status.NOT_MET, ids, detail)
