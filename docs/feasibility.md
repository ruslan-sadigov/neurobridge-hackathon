# BidBridge: feasibility

## 1. What the prototype needs to run

| Need | Detail | Status |
|---|---|---|
| Tender documents | Text-based PDFs (all 4 test tenders had a native text layer; OCR fallback exists for scans, Azerbaijani OCR untested) | Public sources identified (World Bank, EBRD, ADB, TED, national portals); licence and reuse terms must be checked per source |
| Supplier data | One structured JSON profile: company facts, certificates, revenue, past projects, documents. Absence of data yields UNKNOWN, never a guess | Synthetic profile only; real onboarding (upload CV/certificates, extract facts) is the next product step |
| LLM | Any provider with JSON output behind an adapter. Tested with Gemini `gemini-3.5-flash-lite` (free tier) | Anthropic adapter implemented but not run (no key) |
| Embeddings | Multilingual model for supplier-evidence retrieval. Runs locally; prototype currently uses a hash stub (the supplier has few evidence records) | Real multilingual model untested on Azerbaijani |
| Storage | SQLite for development, Postgres for the demo; original PDFs on disk or S3-compatible storage | Implemented |
| Infrastructure | One small Python API server. No GPU, no queue | Implemented |

## 2. Running cost (measured on one run, priced from Google's published rates)

**Measurement:** one full analysis of the 5-page CFCU notice (17,500 characters) against the strong demo supplier,
cache off, `gemini-3.5-flash-lite`, using the token counts returned by the API itself:

| Call type | Requests | Input tokens | Output tokens |
|---|---|---|---|
| Requirement extraction (3 two-page windows, two passes, plus 1 retry after invalid JSON) | 7 | 19,185 | 7,441 |
| Batched classification (6 requirements per request) | 4 | 6,425 | 2,047 |
| **Total** | **11** | **25,610** | **9,488** |

The API reported 0 thinking tokens for this model. Wall-clock time was **62 seconds**; the analysis produced 31
requirements and a GO_WITH_CONDITIONS recommendation. The failed attempt's tokens are included because they are billed.

**Price:** Google's pricing page (updated 2026-10-07) lists `gemini-3.5-flash-lite` at **$0.30 per 1M input tokens and
$2.50 per 1M output tokens** (output includes thinking tokens) on the paid tier.

| | Calculation | Cost |
|---|---|---|
| One 5-page tender | 25,610 x $0.30/M + 9,488 x $2.50/M | **about $0.031** (3 US cents) |
| Per page | $0.031 / 5 | about $0.006 |
| 100-page bidding document | linear extrapolation, **not tested** | about $0.63 |
| 1,000 five-page tenders | linear | about $31 |

Request counts across three earlier runs were 9-10 (one run had 11 because of a retry), down from about 28 before the
call reduction (batched classification, informational clauses skipped, identical calls cached on disk so a repeat run
costs nothing). The extrapolation to longer documents assumes extraction and classification scale with page count;
longer documents also have more requirements, so verify it before quoting it.

- **Prototype/hackathon:** free tier (15 requests/min, 250K tokens/min, 500 requests/day on the key we used): about
  10 requests per analysis means about 50 analyses a day, at about a minute each. **Privacy caveat from the same
  pricing page: free-tier content is used to improve Google's products.** That is acceptable for public tenders and
  fictional suppliers, but real client documents should only go through a paid account. Check the paid tier's data
  terms before relying on them.
- **Production:** at a few cents per tender the model cost is small next to the bid team's time; the real costs are
  hosting (two small always-on containers) and the human review the product is meant to support.
- **Levers if cost or quota matters:** extraction is about 75% of output tokens, so the gap-filling pass is the main
  cost lever (skip it on short documents); batch size can go above 6; caching already removes repeat runs.

## 3. Risks and limits (honest)

- **Small evaluation:** one annotated tender, one synthetic supplier, assistant-drafted labels not yet reviewed by an
  expert. See `evaluation-and-failures.md`.
- **Run-to-run variance:** recall ranged 79-100% between identical runs even at temperature 0. Production use needs
  repeated extraction or voting, and a "possibly incomplete" warning.
- **Decision support, not eligibility advice.** The score prioritises work; critical gaps always veto the recommendation.
- **Short documents tested:** the test tenders are 3-5 page notices, not 100-page bidding documents. Long-document
  behaviour (page windows, tables, cross-document contradictions) is untested.
- **Language:** English tested; Azerbaijani extraction and OCR not yet tested.
- **Data licensing:** public tender documents still need per-source terms checked before storage or reuse.

## 4. Clear next steps

1. Expert review and freeze of the CFCU annotation; annotate 2-3 more tenders (including a longer World Bank bidding
   document and one Azerbaijani-language tender).
2. Measure the manual baseline (time and found requirements) to substantiate the time-saving claim.
3. Real supplier onboarding: extract facts from uploaded certificates and past-project documents with page-level
   provenance, so profiles stop being hand-written JSON.
4. Switch embeddings to a multilingual model and test Azerbaijani retrieval.
5. Handle conditional clauses (consortium, capacity-provider rules) as their own risk type.
6. Pilot with one real bid team on a live tender and compare their hand-made compliance matrix with BidBridge's.
