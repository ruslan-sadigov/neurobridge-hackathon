"""Deterministic rule engine (FR-031). Returns None when operands are missing -> caller falls back / UNKNOWN."""
from __future__ import annotations

from dataclasses import dataclass, field
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


def evaluate(rule: NormalizedRule, evidence: list[Evidence], *, complete_types: set[str] | None = None,
             today: Optional[date] = None) -> Optional[RuleOutcome]:
    complete_types = complete_types or set()
    today = today or date.today()
    if rule.rule_type == RuleType.NONE or not rule.field:
        return None
    if rule.rule_type == RuleType.MEMBERSHIP:
        return _membership(rule, evidence, complete_types, today)
    if rule.rule_type in (RuleType.THRESHOLD, RuleType.COUNT):
        return _numeric(rule, evidence)
    return None


def _membership(rule, evidence, complete_types, today) -> Optional[RuleOutcome]:
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


def _numeric(rule, evidence) -> Optional[RuleOutcome]:
    if rule.operator not in OPS or rule.value is None:
        return None
    try:
        target = float(rule.value)
    except (TypeError, ValueError):
        return None

    if rule.field == "projects_count":
        projects = [e for e in evidence if e.type == "PROJECT"]
        min_val = rule.filters.get("min_value")
        tags = [t.lower() for t in rule.filters.get("tags", [])]
        if min_val is not None:
            projects = [p for p in projects if (p.value or 0) >= float(min_val)]
        if tags:
            projects = [p for p in projects if any(t in p.text.lower() for t in tags)]
        actual: float = len(projects)
        ids = [p.evidence_id for p in projects]
    elif rule.field == "annual_revenue":
        revs = sorted((e for e in evidence if e.type == "FINANCIAL"), key=lambda e: e.metadata.get("year", 0))
        if not revs:
            return None
        actual, ids = float(revs[-1].value), [revs[-1].evidence_id]
    else:  # company facts: employees, founded_year, ...
        facts = [e for e in evidence if e.type == "COMPANY_FACT" and e.label == rule.field]
        if not facts:
            return None
        actual, ids = float(facts[0].value), [facts[0].evidence_id]

    ok = OPS[rule.operator](actual, target)
    unit = f" {rule.unit}" if rule.unit else ""
    detail = f"required {rule.field} {rule.operator} {target:g}{unit}; supplier has {actual:g}{unit}."
    if ok:
        return RuleOutcome(Status.MET, ids, detail)
    # count shortfall with some matches is PARTIAL (e.g. 1 of 2 projects)
    if rule.rule_type == RuleType.COUNT and actual > 0 and rule.operator in (">=", ">"):
        return RuleOutcome(Status.PARTIALLY_MET, ids, detail)
    return RuleOutcome(Status.NOT_MET, ids, detail)
