"""
TechTaru DocIQ — FastAPI Application Entry Point
================================================
OpenAI Structured Outputs (strict JSON schema) + Pydantic v2 + FastAPI
Deterministic heuristic engine when no API key is configured.

Run locally:
    uvicorn app.main:app --reload --port 8000

API docs:
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""

import time
import logging
from collections import deque, defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.routes import extract, history, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("⚡  Starting TechTaru DocIQ…")
    await init_db()
    logger.info("✅  SQLite database ready")
    yield
    logger.info("🛑  Shutting down…")


app = FastAPI(
    title="TechTaru DocIQ API",
    description="""
## ⚡ TechTaru DocIQ — Structured Document Intelligence

Production-grade unstructured document extraction via **OpenAI Structured
Outputs** (strict JSON schema mode) with Pydantic v2 validation, per-field
confidence scoring and a deterministic heuristic fallback engine.

### Supported Document Types
| Type | Examples |
|------|---------|
| **RESUME** | CVs, LinkedIn exports |
| **INVOICE** | Bills, purchase orders |
| **CONTRACT** | NDAs, SaaS agreements |
| **BUSINESS_CARD** | Contact cards |
| **CUSTOM** | Any user-defined schema |

### Key Design Choices
- **Structured Outputs (`response_format: json_schema`, strict)**: the model is
  API-forced to fill every field — zero regex
- **Pydantic v2 `model_validator`**: cross-field validation (arithmetic, date logic)
- **Exponential backoff**: 429 / 5xx retries with 1s → 2s → 4s delay
- **Per-field confidence scores**: separate structured call for quality transparency
- **Async file processing**: PDF/DOCX/OCR run in thread pool — event loop unblocked
- **Rate limiting**: sliding-window limiter per client IP on extract endpoints
    """,
    version=settings.app_version,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Process-Time-Ms"] = f"{ms:.1f}"
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({ms:.0f}ms)")
    return response


# ── Sliding-window rate limiter (extract endpoints only) ─────────────────────
_RATE_WINDOW_SECONDS = 60.0
_hit_log: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method == "POST" and "/api/v1/extract" in request.url.path:
        client_ip = request.client.host if request.client else "unknown"
        limit = settings.rate_limit_per_minute
        now = time.monotonic()
        hits = _hit_log[client_ip]
        while hits and now - hits[0] > _RATE_WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded: max {limit} extraction requests per minute. "
                                   f"Try again shortly."},
            )
        hits.append(now)
    return await call_next(request)


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)[:200]},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(extract.router, prefix="/api/v1", tags=["Extraction"])
app.include_router(history.router, prefix="/api/v1", tags=["History & Export"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
