# BidBridge

AI tender qualification and compliance intelligence. See `BidBridge-MVP-requirements.docx` for the full spec.

LLMs read language; application code owns state, schemas, thresholds, scoring and vetoes. UNKNOWN is preferred over guessing.

## Layout

```
backend/
  app/
    enums.py, schemas.py      canonical contracts (spec section 5)
    adapters/                 llm.py (Anthropic, swappable), embeddings.py (local multilingual / hash stub)
    services/
      parser.py               page-aware PDF parsing + OCR fallback
      extractor.py            LLM requirement extraction, quote verification, dedupe
      evidence.py             supplier profile -> addressable evidence records
      matcher.py              hybrid evidence retrieval (type boost + embeddings)
      rules.py                deterministic checks (membership, thresholds, counts, expiry)
      compliance.py           rules first, constrained LLM second, no unsupported positives
      risk.py, scoring.py     deterministic severity, weighted score, veto logic
      pipeline.py             orchestration + stage timings
    api/routes.py             REST API (spec section 9)
    db.py                     SQLAlchemy models (sqlite dev / Postgres demo)
  fixtures/                   demo supplier profile
  tests/                      unit tests for the deterministic core
```

## Run

```bash
cp .env.example .env            # add ANTHROPIC_API_KEY
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                          # no API key needed
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Optional: `docker compose up -d db` and set `DATABASE_URL=postgresql+psycopg://bidbridge:bidbridge@localhost:5432/bidbridge`.
Local embeddings: `pip install sentence-transformers` (set `EMBEDDING_BACKEND=hash` to skip the model download).
OCR: `pip install pytesseract pillow` plus the Tesseract binary with the `aze` language pack.

## Status

Backend skeleton and deterministic core done and tested. Still to build (spec section 14):
frontend dashboard, evaluation harness with annotated ground truth, a real tender fixture,
and an end-to-end test with a recorded LLM response.
