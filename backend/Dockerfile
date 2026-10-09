FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY fixtures ./fixtures

# Run as a non-root user. /data holds uploads and the SQLite file; mount a volume there to persist it.
RUN useradd --create-home --uid 1000 bidbridge \
    && mkdir -p /data && chown -R bidbridge:bidbridge /data /app
USER bidbridge

# Container defaults (override in the host's environment settings):
#  - hash embeddings: the multilingual model (sentence-transformers) is not installed in this image
#  - SQLite + uploads on /data; use DATABASE_URL=postgresql+psycopg://... for a managed database
ENV EMBEDDING_BACKEND=hash \
    DATABASE_URL=sqlite:////data/bidbridge.db \
    STORAGE_DIR=/data/storage \
    PORT=8080

# Secrets (GEMINI_API_KEY / ANTHROPIC_API_KEY), LLM_PROVIDER, GEMINI_MODEL and CORS_ORIGINS are NOT baked in.

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/health')"

# One worker only: analyses run as in-process background tasks.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
