# BidBridge API contract (v0.1)

For the frontend. Interactive docs: `GET /docs` (Swagger). Machine-readable schema: `docs/api-examples/openapi.json`.
Every example in `docs/api-examples/*.json` is a **real response** from the running API (CFCU tender, CaspianTech
supplier), captured by replaying a stored analysis, so field names and shapes are exact.

Base URL: `http://localhost:8000` locally. All bodies are JSON except the upload (multipart). No auth in the MVP.

## Typical flow

```
POST /analyses                          -> { analysis_id }
POST /analyses/{id}/documents           -> upload 1-10 PDFs (multipart, field name "files")
POST /analyses/{id}/supplier            -> body: supplier profile JSON
POST /analyses/{id}/run                 -> starts the analysis (background). Add ?sync=true to wait for it
GET  /analyses/{id}                     -> poll until status is COMPLETE or FAILED (every 2-3 s)
GET  /analyses/{id}/requirements        -> compliance matrix (filterable)
GET  /analyses/{id}/risks               -> ranked risks
GET  /analyses/{id}/score               -> dimensions + recommendation
GET  /documents/{doc_id}/pages/{n}      -> page text for source drill-down
GET  /documents/{doc_id}/file           -> original PDF
DELETE /analyses/{id}                   -> remove the analysis and its files
```

A full analysis of a 5-page tender took about 1 minute (62 s measured) on the free Gemini tier; longer documents take longer, so use the background mode and poll.
`GET /health` returns `{"status":"ok"}`.

## Endpoints

| Method and path | Request | Response | Example |
|---|---|---|---|
| `POST /analyses` | none | `{analysis_id, status:"PENDING"}` | `01_create_analysis.json` |
| `POST /analyses/{id}/documents` | multipart `files` (PDF, max 10 files, max 50 MB each) | `{documents:[{document_id, filename, size, checksum}]}` | `02_upload_documents.json` |
| `POST /analyses/{id}/supplier` | supplier profile JSON (see below) | `{ok, company_name}` | `03_attach_supplier.json` |
| `POST /analyses/{id}/run` | optional `?sync=true` | `{analysis_id, status:"PENDING"}` | `04_run.json` |
| `GET /analyses/{id}` | none | summary, counts, recommendation | `05_get_analysis.json` |
| `GET /analyses/{id}/requirements` | optional `status`, `category`, `mandatory_level` query filters (exact match) | array of requirement + result | `06_...`, `07_...` |
| `GET /analyses/{id}/risks` | none | array of risks, most severe first | `08_risks.json` |
| `GET /analyses/{id}/score` | none | score snapshot | `09_score.json` |
| `GET /documents/{doc_id}/pages/{n}` | none | `{document_id, page, text, extraction_method}` | `10_document_page.json` |
| `GET /documents/{doc_id}/file` | none | the PDF (`application/pdf`) | - |
| `DELETE /analyses/{id}` | none | `{deleted: id}` | - |

### Error responses

`{"detail": "<message>"}` with: `400` (no documents or no supplier before `run`; wrong file count), `404` (unknown
analysis, document, page, or score not computed yet), `413` (file too large), `415` (not a PDF).

### Job status

`analysis.status` is one of `PENDING`, `RUNNING`, `COMPLETE`, `FAILED`. On `FAILED`, `error` holds the message; the
analysis never returns partial results as success. `summary.warnings` (array of strings) lists non-fatal problems, for
example dropped requirements or parsing coverage below 100%. **Show warnings to the user.**
`summary.parsing_coverage` is 0-1 (share of pages with usable text).

## Enums (exact strings)

| Field | Values |
|---|---|
| `status` (compliance) | `MET`, `PARTIALLY_MET`, `NOT_MET`, `UNKNOWN` |
| `category` | `LEGAL`, `FINANCIAL`, `TECHNICAL`, `EXPERIENCE`, `CERTIFICATION`, `PERSONNEL`, `DOCUMENTATION`, `DELIVERY`, `COMMERCIAL`, `CONTRACTUAL` |
| `mandatory_level` | `MANDATORY`, `PREFERRED`, `INFORMATIONAL`, `UNKNOWN` |
| `risk severity` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `recommendation` | `GO`, `GO_WITH_CONDITIONS`, `NO_GO` |
| `method` | `DETERMINISTIC_RULE` (code checked it), `LLM_SEMANTIC` (model judged it), `NO_EVIDENCE` |
| `reason_code` | `ALL_CRITICAL_MANDATORY_MET`, `MANDATORY_CERTIFICATION_MISSING`, `MANDATORY_EVIDENCE_UNKNOWN`, `EXPERIENCE_THRESHOLD_NOT_MET`, `FINANCIAL_THRESHOLD_NOT_MET`, `DOCUMENT_REQUIRED_MISSING`, `DELIVERY_CONSTRAINT_RISK`, `CONFLICTING_TENDER_TERMS`, `MANDATORY_REQUIREMENT_NOT_MET`, `MANDATORY_PARTIALLY_MET` |

## Key shapes

**`GET /analyses/{id}`**: `{analysis_id, status, error, summary:{warnings, timings, parsing_coverage, requirement_count},
documents:[{document_id, filename, pages}], counts:{total, mandatory, MET, PARTIALLY_MET, NOT_MET, UNKNOWN},
recommendation, final_score}`. `recommendation` and `final_score` are `null` until the run completes. This one call
is enough for the above-the-fold summary.

**Requirement (`/requirements` item):**

```
requirement_id, text, category, mandatory_level, extraction_confidence (0-1),
normalized_rule: {rule_type, field, operator, value, unit, filters}      // may be all null
sources: [{document_id, page, section, excerpt}]                         // tender source (always at least one)
result:  {status, method, supporting_evidence_ids[], rationale, confidence (0-1),
          risk_severity (or null), reason_code (or null)}
evidence_candidates: [{evidence:{evidence_id, type, label, value, text, ...}, score}]   // top supplier evidence
```

`evidence_candidates` are retrieval candidates; the evidence that actually supports the status is the subset whose
`evidence_id` appears in `result.supporting_evidence_ids`. Show candidates only as "closest evidence" when the status
is `UNKNOWN`. `confidence` is diagnostic only; never display it as a probability of compliance.

**Source drill-down:** open `sources[0]` by calling `GET /documents/{document_id}/pages/{page}` and highlight
`excerpt` inside `text`, or link to `GET /documents/{document_id}/file` (PDF) at that page.

**Risk:** `{requirement_id, severity, explanation, recommended_action, reason_code}`. Join to the requirement by
`requirement_id`.

**Score:** `{final_score (0-100), recommendation, reason_codes[], overall_coverage (0-1), dimensions:[{name, weight,
score (0-1 or null), coverage (0-1 or null), requirement_count}], config:{weights, status_points, level_weights}}`.
A dimension with no requirements has `score: null`. **`overall_coverage` and each dimension's `coverage` are the share
of requirements that are not `UNKNOWN`. Show it next to the score (e.g. "18% verified")**, because UNKNOWN counts as a
low score, not as met.

## Supplier profile (POST body)

See `backend/fixtures/supplier_caspiantech.json`. Fields: `company_name`, `founded_year`, `employees`,
`annual_revenue: {"2025": 1200000, "currency": "AZN"}`, `certifications` (strings or `{name, evidence_id,
issued_date, expiry_date}`), `projects: [{name, year, value, currency, tags[]}]`, `documents: [{type, name,
evidence_id}]`, optional `complete_evidence_types: ["CERTIFICATE"]` (declares a category complete, so a missing item
becomes `NOT_MET` instead of `UNKNOWN`), and optional `fx_rates: {"EUR": 1.95}` (AZN per 1 unit; USD 1.70 is built in).

## Display rules the product depends on

- The recommendation comes from code, not from the model. Never recompute or override it in the UI.
- A critical mandatory gap forces `NO_GO` even when `final_score` is high; show the `reason_codes`.
- Show `UNKNOWN` as its own state ("needs evidence"), distinct from `NOT_MET`.
- Always show the tender source (document, page, excerpt) for every finding. For `MET`/`PARTIALLY_MET`, show the
  supporting evidence too.
- Present results as decision support, not legal advice.

## Deployment notes for the frontend

- Allowed browser origins are controlled by the backend env var `CORS_ORIGINS` (comma-separated); set it to the
  deployed frontend URL.
- The API holds the LLM key; the frontend never needs it.
- Uploaded files and the SQLite database live on the server's local disk, so on hosts with an ephemeral filesystem
  they disappear on redeploy. Use a persistent volume or Postgres for anything that must survive.
- Background jobs run in-process; do not run more than one server worker unless the job runner is changed.
