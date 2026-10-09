"""Flatten a structured supplier profile into individually addressable evidence records (FR-011)."""
from __future__ import annotations

from typing import Any

from ..schemas import Evidence


def build_evidence(profile: dict[str, Any]) -> list[Evidence]:
    ev: list[Evidence] = []
    name = profile.get("company_name", "supplier")

    for key in ("founded_year", "employees"):
        if key in profile:
            ev.append(Evidence(evidence_id=f"EVD-F-{key}", type="COMPANY_FACT", label=key,
                               value=profile[key], text=f"{name} {key}: {profile[key]}"))

    # Free-form facts, e.g. {"label": "Country of establishment", "value": "Turkey", "text": "..."}.
    for i, f in enumerate(profile.get("facts", []), 1):
        ev.append(Evidence(evidence_id=f.get("evidence_id", f"EVD-FACT-{i:03d}"), type="COMPANY_FACT",
                           label=f["label"], value=f.get("value"),
                           text=f.get("text") or f"{name} {f['label']}: {f.get('value')}"))

    for i, c in enumerate(profile.get("certifications", []), 1):
        item = c if isinstance(c, dict) else {"name": c}
        ev.append(Evidence(evidence_id=item.get("evidence_id", f"EVD-C-{i:03d}"), type="CERTIFICATE",
                           label=f"{item['name']} Certificate", value=item["name"],
                           text=f"Certificate: {item['name']}",
                           issued_date=item.get("issued_date"), expiry_date=item.get("expiry_date")))

    rev = profile.get("annual_revenue") or {}
    cur = rev.get("currency")
    for year, amount in rev.items():
        if year == "currency":
            continue
        ev.append(Evidence(evidence_id=f"EVD-R-{year}", type="FINANCIAL", label=f"Revenue {year}",
                           value=amount, text=f"Annual revenue {year}: {amount} {cur}",
                           metadata={"year": int(year), "currency": cur}))

    for i, p in enumerate(profile.get("projects", []), 1):
        tags = ", ".join(p.get("tags", []))
        ev.append(Evidence(evidence_id=p.get("evidence_id", f"EVD-P-{i:03d}"), type="PROJECT", label=p["name"],
                           value=p.get("value"),
                           text=(f"Project {p['name']} ({p.get('year')}), value {p.get('value')} {p.get('currency')}, {tags}"
                                 + (f". {p['description']}" if p.get("description") else "")),
                           metadata={k: v for k, v in p.items() if k != "name"}))

    for d in profile.get("documents", []):
        ev.append(Evidence(evidence_id=d["evidence_id"], type="DOCUMENT", label=d["name"], value=d["name"],
                           text=f"Document ({d.get('type')}): {d['name']}"
                                + (f". {d['description']}" if d.get("description") else "")))

    seen: set[str] = set()  # keep the first record when ids repeat
    out: list[Evidence] = []
    for e in ev:
        if e.evidence_id not in seen:
            seen.add(e.evidence_id)
            out.append(e)
    return out
