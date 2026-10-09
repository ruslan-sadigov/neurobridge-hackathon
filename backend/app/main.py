import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="BidBridge API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
# Also serve everything under /api, so the app works behind a reverse proxy (e.g. DigitalOcean App Platform
# routing /api to this service) whether or not the proxy strips the prefix.
app.include_router(router, prefix="/api", include_in_schema=False)


@app.get("/health")
@app.get("/api/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}
