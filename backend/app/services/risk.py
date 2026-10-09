"""Deterministic risk engine (FR-040/041)."""
from __future__ import annotations

from ..enums import Category, MandatoryLevel, ReasonCode, Severity, Status
from ..schemas import ComplianceResult, Requirement, RiskItem

# High-impact categories: an UNKNOWN here is HIGH, not MEDIUM.
HIGH_IMPACT = {Category.LEGAL, Category.FINANCIAL, Category.CERTIFICATION, Category.EXPERIENCE,
               Category.DOCUMENTATION}


def severity_for(req: Requirement, status: Status) -> Severity | None:
    """Documented rules:
    mandatory NOT_MET -> CRITICAL; mandatory PARTIALLY_MET -> HIGH;
    mandatory UNKNOWN -> HIGH (high-impact category) else MEDIUM;
    preferred NOT_MET -> LOW; everything else -> no risk."""
    mand = req.mandatory_level == MandatoryLevel.MANDATORY
    if mand and status == Status.NOT_MET:
        return Severity.CRITICAL
    if mand and status == Status.PARTIALLY_MET:
        return Severity.HIGH
    if mand and status == Status.UNKNOWN:
        return Severity.HIGH if req.category in HIGH_IMPACT else Severity.MEDIUM
    if req.mandatory_level == MandatoryLevel.PREFERRED and status == Status.NOT_MET:
        return Severity.LOW
    return None


ACTIONS = {
    Status.NOT_MET: "Obtain the missing qualification/document, find a partner, or do not bid.",
    Status.PARTIALLY_MET: "Close the remaining gap or prepare a justified clarification request.",
    Status.UNKNOWN: "Add the supporting evidence to the supplier profile or ask the buyer to clarify.",
}


def build_risks(reqs: list[Requirement], results: list[ComplianceResult]) -> list[RiskItem]:
    by_id = {r.requirement_id: r for r in reqs}
    order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
    risks: list[RiskItem] = []
    for res in results:
        sev = severity_for(by_id[res.requirement_id], res.status)
        res.risk_severity = sev
        if sev is None:
            continue
        risks.append(RiskItem(
            requirement_id=res.requirement_id, severity=sev, explanation=res.rationale,
            recommended_action=ACTIONS[res.status],
            reason_code=res.reason_code or ReasonCode.MANDATORY_EVIDENCE_UNKNOWN))
    return sorted(risks, key=lambda r: order[r.severity])
