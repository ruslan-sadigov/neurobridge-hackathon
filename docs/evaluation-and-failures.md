# BidBridge: evaluation and failure analysis

All numbers come from `backend/eval` (`python -m eval.run_eval eval/annotations/TR_CFCU.json --runs 3`), the Turkish
CFCU/EU tender notice (5 pages, 14 annotated mandatory requirements), the synthetic CaspianTech supplier profile and
`gemini-3.5-flash-lite` at temperature 0.

> **Caveat:** the ground-truth annotation (`eval/annotations/TR_CFCU.json`) was drafted by the assistant from a manual
> read of the PDF and is marked `DRAFT`. It has **not** been reviewed by a procurement expert. All metrics are
> provisional until a human freezes it. One tender and one supplier profile is a small sample; treat results as a
> prototype measurement, not a benchmark.

## 1. Measured results (3 runs each, CFCU tender)

| Metric | v1 baseline | v2 + gap pass | v2.1 + tighter prompt | Spec target |
|---|---|---|---|---|
| Requirement recall | 69% (57-79) | 95% (93-100) | 93% (79-100) | 90% |
| Mandatory recall | 69% | 95% | 93% | 95% |
| Citation validity (quote is on the cited page) | 100% | 100% | 100% | 95% |
| Unsupported positives (MET with no evidence) | 0% | 0% | 0% | under 5% |
| MET where answer should be NOT_MET/UNKNOWN | 3% | 0% | 0% | - |
| Compliance accuracy (vs annotated status) | 87% | 85% | 84% | 85% |
| Strict precision (extracted item is in annotation) | 100% | 58% | 59% | 90% |
| Mandatory-level accuracy | 98% | 87% | 96% | - |

Reading the table:
- **Strict precision fell because the annotation is incomplete, not because the model invents text.** The extra items
  are real clauses (capacity-provider rules, multi-lot rule, submission mechanics) that the draft annotation skipped;
  citation validity stays at 100%. We deliberately did **not** add them to the ground truth after seeing the output
  (that would fit labels to the model). A human reviewer should adjudicate them.
- Recall varies between runs (79-100% in v2.1), so a single demo run can look better or worse than the average.
- Compliance accuracy is capped by two debatable labels (see failure 7).

## 2. Failure cases (all real, found by running the pipeline)

| # | Failure | Root cause | Mitigation | Status |
|---|---|---|---|---|
| 1 | Turnover thresholds in EUR/USD compared to revenue in AZN as bare numbers | Rule normalisation ignored currency | Currency-aware rules: convert with AZN/USD peg or profile `fx_rates`; otherwise UNKNOWN. Unit tests added | Fixed |
| 2 | "Delivered supplies under **at most 5** contracts..." became `projects_count <= 5`, so a supplier with 0 projects was **MET** | Extraction misread the clause; count rule too naive | Only plain "at least N projects" is deterministic; conditioned or upper-bound counts go to semantic review | Fixed |
| 3 | LLM returned NOT_MET for a signed declaration and for liquid assets purely because the profile did not mention them | Classifier treated absence as contradiction (violates spec FR-012) | `evidence_contradicts` flag: NOT_MET only if cited evidence conflicts, else UNKNOWN. Test added | Fixed |
| 4 | "Bid security USD 200,000" mapped to `annual_revenue` (MET); "no court decisions since 2010" mapped to `founded_year` (MET) | LLM mapped a requirement onto the wrong supplier field | Rule only runs if the requirement text mentions the field (keyword guard). Test added | Fixed |
| 5 | Three clauses on a dense page (EU sanctions exclusion, 90-day validity, 540-day delivery) were never extracted, in any run | Extraction under-reads dense pages (model omission, not our quote check; confirmed from raw output) | Exhaustive-extraction prompt plus a gap-filling second pass; recall 69% to 95% | Mostly fixed (variance remains) |
| 6 | 38 of 38 requirements flagged MANDATORY, including deadlines and envelope rules, inflating risks | Extraction prompt did not distinguish eligibility from process | Prompt separates eligibility conditions from tender mechanics; level accuracy 87% to 96% | Partly fixed |
| 7 | Experience requirements: annotation says NOT_MET (supplier's whole portfolio, 420k AZN, is below 2.5M EUR), pipeline says UNKNOWN | Needs cross-currency arithmetic over a fuzzy "similar contracts" condition | None; UNKNOWN is the conservative answer. Needs a human decision on the intended label | Open |
| 8 | Extra MANDATORY items (capacity-provider conditions etc.) add noise to the risk list | Real but conditional clauses; model cannot tell if they apply | Surface as lower-severity or "conditional"; needs product decision | Open |

## 3. Where the system returns UNKNOWN instead of inventing an answer

- **EU restrictive-measures exclusion, signed declaration, tender and performance guarantees, eligibility of origin:**
  the profile holds no evidence for these, so the status is UNKNOWN with a "high-impact unknown" risk, not a guess.
- **EUR turnover with no exchange rate supplied:** UNKNOWN, never a bare-number comparison.
- **LLM says MET or PARTIALLY_MET but cites no (or a made-up) evidence id:** downgraded to UNKNOWN in code.

## 4. Comparison with the current approach (to be measured)

The spec's measure is manual verification time with and without BidBridge. **Not yet measured.** Proposed 15-minute
protocol: one person reads the CFCU notice by hand and lists each qualification requirement, its page and whether
CaspianTech meets it; record time and the number of requirements they found. Compare with BidBridge (about 2 minutes
per tender, 5 pages) on found requirements and time. Do not report a figure until it has been measured.

## 5. Automated tests

20 unit tests (no API key needed): rule engine (thresholds, counts, expiry, currency, wrong-field guard), compliance
guards, risk severity, score reproducibility and critical-gap veto, schema validation, evidence retrieval, and the
evaluation metrics themselves.
