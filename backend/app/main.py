"""JanSetu / Rodic InfraAI integrated platform - FastAPI application entry point."""
import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_DIR, get_settings
from .db import SessionLocal
from .routers import (admin, agent, analytics, assistant, audit_routes, auth, dashboard, grievances, health, knowledge, maps,
                      monitoring, nodal, officer, public, vendor)

settings = get_settings()
logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("jansetu")
FRONTEND_DIR = PROJECT_DIR / "frontend"
STARTED_AT = time.time()
JOB_STATUS: dict[str, dict] = {}


def _tile_origin(url: str) -> str:
    from urllib.parse import urlparse
    u = urlparse(url.replace("{s}", "a"))
    host = u.netloc.replace("a.", "*.", 1) if "{s}" in url else u.netloc
    return f"{u.scheme}://{host}" if u.scheme and host else ""


TILE_ORIGIN = " ".join(sorted({o for o in (_tile_origin(settings.map_tile_url), _tile_origin(settings.map_tile_url_dark),
                                                _tile_origin(settings.map_fallback_tile_url)) if o}))


async def _loop(name: str, interval: int, fn):
    while True:
        try:
            result = await asyncio.to_thread(fn)
            JOB_STATUS[name] = {"last_run": time.time(), "ok": True, "result": result}
        except Exception as exc:  # noqa: BLE001
            JOB_STATUS[name] = {"last_run": time.time(), "ok": False, "error": type(exc).__name__}
            log.warning("job %s failed: %s", name, exc)
        await asyncio.sleep(interval)


def _escalation_job():
    from .services.workflow import run_escalations
    with SessionLocal() as db:
        n = run_escalations(db)
        db.commit()
        return n


def _monitoring_job():
    from sqlalchemy import select

    from .models import MonitoredService
    from .services.monitoring import run_check
    with SessionLocal() as db:
        n = 0
        for svc in db.execute(select(MonitoredService).where(MonitoredService.enabled.is_(True))).scalars():
            if run_check(db, svc):
                n += 1
        db.commit()
        return n


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and (settings.secret_key in {"change-me-in-env", ""} or len(settings.secret_key) < 32):
        raise RuntimeError("Refusing to start in production without a strong SECRET_KEY (>= 32 chars).")
    from .bootstrap import init_db
    init_db()
    tasks = []
    if settings.enable_background_jobs:
        tasks.append(asyncio.create_task(_loop("escalation", settings.escalation_interval_seconds, _escalation_job)))
        tasks.append(asyncio.create_task(_loop("monitoring", settings.monitoring_interval_seconds, _monitoring_job)))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="JanSetu Integrated Citizen Services Platform API", version=settings.app_version,
              docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json", lifespan=lifespan,
              description="Grievance redressal (PS1), unified call centre (PS2), e-Office (PS3), service uptime (PS4) "
                          "and benefit navigation (PS5). All simulated components are labelled as such.")

if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                       allow_credentials=False, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        limit = settings.auth_rate_limit_per_minute if path.startswith("/api/auth/") else settings.rate_limit_per_minute
        key = f"{ip}:{'auth' if path.startswith('/api/auth/') else 'api'}"
        now = time.time()
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"error": {"code": "rate_limited", "message": "Too many requests. Please wait a minute."}},
                                status_code=429, headers={"Retry-After": "60"})
        q.append(now)
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Tile servers (OpenStreetMap usage policy) require a Referer; send only the origin cross-site.
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "microphone=(self), geolocation=(self), camera=()"
    if not path.startswith("/api/docs") and not path.startswith("/api/redoc"):
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; img-src 'self' data: blob: {TILE_ORIGIN}; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        log.info("%s %s %s %.0fms", request.method, path, response.status_code, (time.perf_counter() - t0) * 1000)
    return response


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse({"error": detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errs = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse({"error": {"code": "validation_error", "message": "Please check the highlighted fields.",
                                   "fields": errs}}, status_code=422)


for r in (health, auth, public, grievances, officer, nodal, agent, assistant, knowledge, monitoring, analytics,
          audit_routes, admin, vendor, maps, dashboard):
    app.include_router(r.router)
app.include_router(auth.me_router)

# ------------------------------------------------------------------ frontend (no build step)
SPA_ROUTES = {"", "citizen", "citizen/tickets", "benefits", "agent", "officer", "nodal", "vendor", "admin", "analytics",
              "monitoring", "knowledge", "audit", "integrations", "evidence", "login", "health", "privacy", "assist", "map",
              "dashboard", "my", "file", "track", "help", "accessibility", "terms"}

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str):
    clean = full_path.strip("/")
    if clean.startswith("api/"):
        raise HTTPException(404, detail={"code": "not_found", "message": "Unknown API route."})
    if clean in SPA_ROUTES or clean.startswith("citizen/tickets/"):
        return FileResponse(FRONTEND_DIR / "index.html", headers={"Cache-Control": "no-cache"})
    raise HTTPException(404, detail={"code": "not_found", "message": "Page not found."})


def uptime_seconds() -> int:
    return int(time.time() - STARTED_AT)


_ = Path  # keep import for type tools
