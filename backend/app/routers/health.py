import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Grievance, HealthCheck, Interaction, TriageRecord

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    return {"status": "ok", "service": "jansetu-api", "version": get_settings().app_version}


@router.get("/api/health/ready")
def ready(db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok", "db_latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "not_ready", "database": type(exc).__name__}, status_code=503)


@router.get("/api/diagnostics")
def diagnostics(db: Session = Depends(get_db)):
    from ..main import JOB_STATUS, uptime_seconds
    s = get_settings()
    t0 = time.perf_counter()
    db.execute(text("SELECT 1"))
    db_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "version": s.app_version, "environment": s.app_env, "uptime_seconds": uptime_seconds(),
        "database": {"engine": db.bind.dialect.name, "latency_ms": db_ms},
        "ai_mode": s.ai_mode, "background_jobs_enabled": s.enable_background_jobs,
        "jobs": {k: {"ok": v.get("ok"), "seconds_since_last_run": round(time.time() - v["last_run"])}
                 for k, v in JOB_STATUS.items()},
        "providers": {"llm": s.llm_provider or "not configured", "stt": s.stt_provider or "browser only / not configured",
                      "translation": s.translation_provider or "not configured", "ocr": s.ocr_provider or "not configured",
                      "otp": s.otp_provider, "sms": s.sms_provider or "simulated", "whatsapp": s.whatsapp_provider or "simulated"},
    }


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=True)
def metrics(db: Session = Depends(get_db)):
    """Prometheus exposition format (scrape target for an external Prometheus, if configured)."""
    from ..main import uptime_seconds
    lines = ["# HELP jansetu_uptime_seconds Process uptime", "# TYPE jansetu_uptime_seconds gauge",
             f"jansetu_uptime_seconds {uptime_seconds()}",
             "# HELP jansetu_grievances_total Grievances by status", "# TYPE jansetu_grievances_total gauge"]
    for status, n in db.execute(select(Grievance.status, func.count()).group_by(Grievance.status)).all():
        lines.append(f'jansetu_grievances_total{{status="{status}"}} {n}')
    lines += ["# HELP jansetu_triage_records_total Triage pipeline runs", "# TYPE jansetu_triage_records_total counter",
              f"jansetu_triage_records_total {db.scalar(select(func.count()).select_from(TriageRecord))}",
              "# HELP jansetu_interactions_total Call-centre interactions", "# TYPE jansetu_interactions_total gauge",
              f"jansetu_interactions_total {db.scalar(select(func.count()).select_from(Interaction))}",
              "# HELP jansetu_health_checks_total Stored health checks", "# TYPE jansetu_health_checks_total counter",
              f"jansetu_health_checks_total {db.scalar(select(func.count()).select_from(HealthCheck))}"]
    return "\n".join(lines) + "\n"
