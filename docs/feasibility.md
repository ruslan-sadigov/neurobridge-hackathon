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

## 2. Running cost (estimates, not measured billing)

Measured structure of a run on the 5-page CFCU notice: about 28 LLM calls (6 extraction calls with the gap pass,
about 22 per-requirement classification calls) and about 26-29 extracted requirements. Rough token estimate from page
text length: **about 30-40K input tokens and 5K output tokens per 5-page tender**, which scales roughly linearly with
page count. Only 4 of the 26 results came from deterministic rules; the other requirements were mostly UNKNOWN or
judged by the LLM.

- **Prototype/hackathon:** free tier (15 requests/min, 250K tokens/min, 500 requests/day on the key we used). A run
  takes about 2-3 minutes at the configured spacing and uses about 28 of the 500 daily requests, so about 15 tender
  analyses per day.
- **Production:** cost per tender = input tokens x input price + output tokens x output price. Flash-lite class models
  are priced for high volume, but **we have not priced it**: check Google's current pricing page and multiply by the
  token counts above, then re-measure with the token usage the pipeline already logs (`model_run`).
- **Levers if cost or quota matters:** cache extraction by file checksum (spec NFR-008), skip the gap pass on short
  documents, batch classification (several requirements per call), and run deterministic rules first (already done).

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
