# BidBridge: evaluation and failure analysis

All numbers come from `backend/eval` (`python -m eval.run_eval eval/annotations/TR_CFCU.json --runs 3`), the Turkish
CFCU/EU tender notice (5 pages, 14 annotated mandatory requirements), the synthetic CaspianTech supplier profile and
`gemini-3.5-flash-lite` at temperature 0.

> **Caveat:** the ground-truth annotation (`eval/annotations/TR_CFCU.json`) was drafted by the assistant from a manual
> read of the PDF and is marked `DRAFT`. It has **not** been reviewed by a procurement expert. All metrics are
> provisional until a human freezes it. Two tenders (CFCU/EU and World Bank/Turkey) and two synthetic suppliers is a small sample; treat results as a
> prototype measurement, not a benchmark. The second annotation (`eval/annotations/TR_WB.json`) was **not blind**: the
> assistant had seen pipeline output on that tender in an early development run before annotating it.

## 1. Measured results (3 runs each, CFCU tender)

| Metric | v1 baseline | v2 + gap pass | v2.1 + tighter prompt | v3 + batched classification | v3.1 + tolerant quote matching | Spec target |
|---|---|---|---|---|---|---|
| Requirement recall | 69% (57-79) | 95% (93-100) | 93% (79-100) | 91% (86-93) | 96% (93-100) | 90% |
| Mandatory recall | 69% | 95% | 93% | 91% | 96% | 95% |
| Citation validity (quote is on the cited page) | 100% | 100% | 100% | 100% | 100% | 95% |
| Unsupported positives (MET with no evidence) | 0% | 0% | 0% | 0% | 0% | under 5% |
| MET where answer should be NOT_MET/UNKNOWN | 3% | 0% | 0% | 0% | 0% | - |
| Compliance accuracy (vs annotated status) | 87% | 85% | 84% | 90% (85-100) | 85% (85-86) | 85% |
| Strict precision (extracted item is in annotation) | 100% | 58% | 59% | 59% | 54% | 90% |
| Mandatory-level accuracy | 98% | 87% | 96% | 92% | 94% | - |

v3 cut the API requests per analysis from about 28 to 9-10 (batched classification, informational clauses skipped,
identical calls cached) with no loss in the key trust metrics. Request counts are measured; the small movements in recall
and accuracy are within the run-to-run variation seen between versions, so no accuracy claim is made for v3 over v2.1.
v3.1 (tolerant quote matching, 2 runs) recovered clauses that were being dropped; recall moved from 91% to 96%, but with
only two runs the difference between versions is suggestive, not proven.

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
| 9 | A supplier bidding only for Lot 2 was failed on Lot 1 requirements (SCADA/RTU experience, Lot 1 guarantee), giving NO_GO | The tool had no notion of which lots the supplier bids for | New `bid_lots` supplier setting: requirements that name only other lots are marked out of scope (not scored, no risk), with the reason shown. Unit test added | Fixed |
| 10 | Real requirements silently dropped, including the eligibility-of-establishment clause: the model tidied a typo in the source ("in a eligible country" became "in an eligible country"), or quoted a sentence that continues across a page break (with the page's running header in between). The strict quote check rejected both | Quote verification was an exact substring test on one page | Tolerant matcher (`services/quotes.py`): accepts a quote when 90% of its words appear contiguously per page, and stores the **page's own wording** as the citation, so excerpts stay verbatim. Invented or paraphrased quotes are still rejected (tests). Recall 91% to 96%, citation validity unchanged at 100% | Fixed |
| 11 | A PARTIALLY_MET guarantee carried reason code `FINANCIAL_THRESHOLD_NOT_MET` | Reason code was chosen by category only | PARTIALLY_MET always maps to `MANDATORY_PARTIALLY_MET`; category-specific codes are for NOT_MET only. Test added | Fixed |
| 12 | World Bank tender: a 300,000 EUR bank guarantee facility was judged NOT_MET against "liquid assets or credit lines of at least USD 2M" (3 of 3 runs) | The model treated evidence about a partial item as proof of absence | Prompt: a conflict needs a value for the SAME thing; a different or partial item gives UNKNOWN. Compliance accuracy 79% to 89%. Still wrong in 1 of 3 later runs | Mostly fixed |
| 13 | World Bank tender: joint-venture conditions (collective turnover of USD 20M with a 40% lead partner) were checked against a single supplier's revenue and failed it | No notion of bidding alone vs as a joint venture | New `bid_as: "single"` profile setting: conditions that name a joint venture and not a single bidder are marked out of scope, with the reason shown. Test added | Fixed |
| 14 | **Regression caused by fix 12 and caught by re-running CFCU:** after the prompt change, amount shortfalls were reported as PARTIALLY_MET (false MET rate 0% to 8%) | My prompt wording "UNKNOWN (or PARTIALLY_MET)" invited it | Removed that wording and defined PARTIALLY_MET (a distinct part satisfied; being below an amount is not partial). False MET back to 0% on both tenders | Fixed |
| 15 | A declaration ("certify that all software is licensed") was turned into a certificate-membership rule and failed the supplier for lacking a certificate by that name | Wrong-field mapping again, this time to `certifications` | Certificate rules only run for named certificates or standards (contain a digit or an acronym); declarations go to semantic review. Test added | Fixed |

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

## 6. Demo scenario: one real tender, two fictional suppliers

Both suppliers are fictional and labelled synthetic; the tender (CFCU/EU notice) is a real public document.

| Supplier | Profile | Result on the CFCU tender |
|---|---|---|
| CaspianTech LLC (weak) | 1.2M AZN revenue, 42 staff, ISO 9001, one project | **NO_GO**: turnover far below the 2.5-2.8M EUR threshold (critical mandatory gap) |
| Marmara Secure Systems (strong, bids Lot 2) | 4.6M EUR revenue, 85 staff, ISO 9001 and 27001, three network/security projects, signed declaration, bank guarantee facility | **GO_WITH_CONDITIONS** (score about 49): 4 MET, 2 PARTIALLY_MET, 0 NOT_MET, Lot 1 items out of scope, remaining items UNKNOWN (sanctions status, supplies origin, consortium conditions) |

Honest notes: the strong profile was designed after seeing the weak one's results and its bank-letter wording was
adjusted once (an initial "guarantee not yet issued" phrasing produced NOT_MET). It demonstrates the product's behaviour;
it is not a test of accuracy and does not enter the metrics above. The strong supplier's reason codes include
`FINANCIAL_THRESHOLD_NOT_MET` for a PARTIALLY_MET guarantee, which is imprecise naming (open issue). A key requirement
(eligibility of establishment) was dropped in this run because the model's quote did not match the page exactly,
another example of run-to-run variation.

## 7. Second tender: World Bank notice (AF-GA2.2, Turkey, 2014)

4 pages, 17 annotated requirements plus 3 informational clauses, scored against the strong synthetic supplier (bids
alone). `acceptable_statuses` in the annotation lists alternatives a reasonable reviewer would accept for ambiguous
items (for example a similar-contract requirement where the profile gives no client count: PARTIALLY_MET or UNKNOWN).

| Metric | First run (3 runs) | After fixes 12-13 (3 runs) | After fixes 14-15 (3 runs) |
|---|---|---|---|
| Requirement and mandatory recall | 92% | 90% | 94% |
| Citation validity | 100% | 100% | 100% |
| Compliance accuracy | 79% | 89% | **96%** (94-100) |
| False MET (should not be MET) | 2% | 4% | **0%** |
| Unsupported positives | 0% | 0% | 0% |
| API requests per analysis | 7 | 6 | 6 |

Remaining: B17 (eligibility under the World Bank Guidelines, an annotator-judgement item) is usually missed; category
accuracy is only 72% because the model's labels differ from mine on borderline items (bid security as COMMERCIAL vs
FINANCIAL, deadlines as DELIVERY vs COMMERCIAL), which do not affect scoring for informational clauses; B04 is still judged
NOT_MET in some runs. After the final changes the CFCU tender was re-measured (2 runs): recall 96%, citation validity
100%, false MET 0%, compliance accuracy 85% (the same two debatable experience labels).

What this second tender shows: evaluating on a different document found four failures the first one could not, and
re-running the first tender after each change caught a regression in the same session.
