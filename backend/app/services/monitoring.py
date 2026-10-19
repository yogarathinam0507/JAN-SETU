"""Service health monitoring (PS4).

check modes:
  in_process - this application's own DB/app health (real measurement)
  http       - real HTTP check, ONLY for services explicitly marked authorized=True
  simulated  - synthetic demo data; every record is flagged simulated=True and labelled in the UI
  planned    - listed for planning only; never probed
"""
import hashlib
import random
import statistics
import time
from datetime import timedelta, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db import iso, utcnow
from ..models import Alert, HealthCheck, Incident, MonitoredService

FAIL_STREAK_FOR_INCIDENT = 3


def _sim_rng(svc: MonitoredService, ts) -> random.Random:
    bucket = int(ts.replace(tzinfo=timezone.utc).timestamp() // 60)
    seed = int(hashlib.sha256(f"{svc.id}:{bucket}".encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def simulated_check(svc: MonitoredService, ts) -> dict:
    rng = _sim_rng(svc, ts)
    profile = (svc.notes or "")
    base = 280 if "fast" in profile else 650
    latency = max(40.0, rng.gauss(base, base * 0.18))
    # Deterministic incident windows for demo realism (clearly simulated).
    hour = ts.hour
    degraded = "degrade-evening" in profile and 19 <= hour < 20
    outage = "outage-night" in profile and hour == 2 and ts.minute < 35  # >=3 checks at a 10-min cadence
    if degraded:
        latency *= 3.2
    if outage or rng.random() < 0.01:
        return {"ok": False, "status_code": 503 if outage else 500, "latency_ms": None,
                "error": "Upstream unavailable (HTTP 503)" if outage else "HTTP 502 Bad Gateway"}
    return {"ok": latency < svc.latency_threshold_ms * 2, "status_code": 200, "latency_ms": round(latency, 1),
            "error": "" if latency < svc.latency_threshold_ms * 2 else "Request timed out"}


def run_check(db: Session, svc: MonitoredService) -> HealthCheck | None:
    if not svc.enabled or svc.check_mode == "planned":
        return None
    now = utcnow()
    if svc.check_mode == "simulated":
        r = simulated_check(svc, now)
        hc = HealthCheck(service_id=svc.id, checked_at=now, simulated=True, **r)
    elif svc.check_mode == "in_process":
        t0 = time.perf_counter()
        try:
            db.execute(text("SELECT 1"))
            hc = HealthCheck(service_id=svc.id, checked_at=now, ok=True, status_code=200,
                             latency_ms=round((time.perf_counter() - t0) * 1000, 2))
        except Exception as exc:  # noqa: BLE001
            hc = HealthCheck(service_id=svc.id, checked_at=now, ok=False, error=type(exc).__name__)
    elif svc.check_mode == "http":
        if not svc.authorized or not svc.endpoint.startswith(("http://", "https://")):
            return None  # never probe endpoints without explicit authorization
        t0 = time.perf_counter()
        try:
            resp = httpx.get(svc.endpoint, timeout=10.0, follow_redirects=False)
            ms = round((time.perf_counter() - t0) * 1000, 1)
            ok = resp.status_code == svc.expected_status and ms < svc.latency_threshold_ms * 2
            hc = HealthCheck(service_id=svc.id, checked_at=now, ok=ok, status_code=resp.status_code, latency_ms=ms,
                             error="" if ok else f"Unexpected status {resp.status_code}" if resp.status_code != svc.expected_status else "Slow response")
        except httpx.HTTPError as exc:
            hc = HealthCheck(service_id=svc.id, checked_at=now, ok=False, error=type(exc).__name__)
    else:
        return None
    db.add(hc)
    db.flush()
    evaluate_rules(db, svc)
    return hc


def recent_checks(db: Session, service_id: str, limit: int = 60) -> list[HealthCheck]:
    rows = db.execute(select(HealthCheck).where(HealthCheck.service_id == service_id)
                      .order_by(HealthCheck.checked_at.desc()).limit(limit)).scalars().all()
    return list(reversed(rows))


def evaluate_rules(db: Session, svc: MonitoredService) -> None:
    checks = recent_checks(db, svc.id, 10)
    if not checks:
        return
    sim = svc.check_mode == "simulated"
    open_inc = db.execute(select(Incident).where(Incident.service_id == svc.id,
                                                 Incident.status.in_(["open", "acknowledged"]))).scalars().first()
    last = checks[-FAIL_STREAK_FOR_INCIDENT:]
    if len(last) == FAIL_STREAK_FOR_INCIDENT and all(not c.ok for c in last) and not open_inc:
        inc = Incident(tenant_id=svc.tenant_id, service_id=svc.id, severity="critical" if svc.criticality == "high" else "major",
                       trigger=f"{FAIL_STREAK_FOR_INCIDENT} consecutive failed checks", opened_at=last[0].checked_at,
                       simulated=sim)
        db.add(inc)
        db.flush()
        inc.summary, inc.hypotheses = summarize_incident(db, svc, inc)
        db.add(Alert(tenant_id=svc.tenant_id, service_id=svc.id, incident_id=inc.id, rule="R-MON-01 fail streak",
                     message=f"{svc.name}: {inc.trigger}", simulated=sim, created_at=last[-1].checked_at))
    elif open_inc and checks[-1].ok and len(checks) >= 2 and checks[-2].ok:
        open_inc.status = "resolved"
        open_inc.resolved_at = checks[-1].checked_at
        db.add(Alert(tenant_id=svc.tenant_id, service_id=svc.id, incident_id=open_inc.id, rule="R-MON-00 recovered",
                     message=f"{svc.name}: recovered", simulated=sim, created_at=checks[-1].checked_at))
    lat = [c.latency_ms for c in checks[-3:] if c.latency_ms is not None]
    if len(lat) == 3 and all(x > svc.latency_threshold_ms for x in lat):
        exists = db.execute(select(Alert).where(Alert.service_id == svc.id, Alert.rule == "R-MON-02 latency",
                                                Alert.created_at >= utcnow() - timedelta(minutes=30))).scalars().first()
        if not exists:
            db.add(Alert(tenant_id=svc.tenant_id, service_id=svc.id, rule="R-MON-02 latency",
                         message=f"{svc.name}: latency above {svc.latency_threshold_ms} ms for 3 checks", simulated=sim,
                         created_at=checks[-1].checked_at))


def anomaly(db: Session, svc: MonitoredService) -> dict:
    checks = recent_checks(db, svc.id, 60)
    lat = [c.latency_ms for c in checks if c.latency_ms is not None]
    if len(lat) < 20:
        return {"status": "insufficient_data", "points": len(lat), "message": "Need at least 20 latency points."}
    hist, latest = lat[:-1], lat[-1]
    mu, sd = statistics.mean(hist), statistics.pstdev(hist) or 1.0
    z = (latest - mu) / sd
    return {"status": "anomalous" if abs(z) >= 3 else "normal", "z_score": round(z, 2), "baseline_ms": round(mu, 1),
            "latest_ms": latest, "points": len(lat), "method": "z-score vs previous points (|z| >= 3)"}


def risk_score(db: Session, svc: MonitoredService) -> dict:
    checks = recent_checks(db, svc.id, 60)
    if len(checks) < 30:
        return {"status": "insufficient_data", "points": len(checks),
                "message": "Predictive risk needs at least 30 checks of history."}
    recent = checks[-20:]
    err = sum(1 for c in recent if not c.ok) / len(recent)
    lat = [c.latency_ms for c in checks if c.latency_ms is not None]
    half = len(lat) // 2
    trend = (statistics.mean(lat[half:]) - statistics.mean(lat[:half])) / (statistics.mean(lat[:half]) or 1) if half else 0
    score = min(100, round(err * 250 + max(0.0, trend) * 60))
    return {"status": "ok", "score": score, "level": "high" if score >= 60 else "elevated" if score >= 30 else "low",
            "inputs": {"error_rate_last_20": round(err, 2), "latency_trend": round(trend, 2)},
            "method": "Heuristic: 250 x error-rate + 60 x positive latency trend (capped at 100). Not a trained model."}


def summarize_incident(db: Session, svc: MonitoredService, inc: Incident) -> tuple[str, list[dict]]:
    checks = recent_checks(db, svc.id, 30)
    fails = [c for c in checks if not c.ok]
    codes = sorted({c.status_code for c in fails if c.status_code})
    errors = sorted({c.error for c in fails if c.error})
    lat = [c.latency_ms for c in checks if c.latency_ms is not None]
    summary = (f"{svc.name}: {len(fails)} of last {len(checks)} checks failed. Status codes: {codes or 'none'}. "
               f"Errors: {', '.join(errors) or 'none'}.")
    hyps = []
    if any(c and c >= 500 for c in codes):
        hyps.append({"hypothesis": "Application or upstream server error (HTTP 5xx)", "evidence": f"codes {codes}"})
    if any("Timeout" in e or "timeout" in e for e in errors):
        hyps.append({"hypothesis": "Network path or upstream saturation (timeouts)", "evidence": ", ".join(errors)})
    if any("Connect" in e for e in errors):
        hyps.append({"hypothesis": "Service unreachable (DNS/connection refused)", "evidence": ", ".join(errors)})
    if len(lat) >= 6 and statistics.mean(lat[-3:]) > 1.5 * statistics.mean(lat[:3]):
        hyps.append({"hypothesis": "Resource saturation - latency rose before failures", "evidence": "latency trend"})
    if not hyps:
        hyps.append({"hypothesis": "Insufficient signal - inspect application logs", "evidence": "no dominant pattern"})
    for h in hyps:
        h["status"] = "hypothesis - operator must confirm"
    return summary, hyps


def service_summary(db: Session, svc: MonitoredService, hours: int = 24) -> dict:
    since = utcnow() - timedelta(hours=hours)
    checks = db.execute(select(HealthCheck).where(HealthCheck.service_id == svc.id, HealthCheck.checked_at >= since)
                        .order_by(HealthCheck.checked_at)).scalars().all()
    n = len(checks)
    up = sum(1 for c in checks if c.ok)
    lat = [c.latency_ms for c in checks if c.latency_ms is not None]
    last = checks[-1] if checks else None
    return {
        "id": svc.id, "name": svc.name, "endpoint": svc.endpoint if svc.check_mode != "simulated" else "(synthetic probe)",
        "owner_team": svc.owner_team, "environment": svc.environment, "criticality": svc.criticality,
        "check_mode": svc.check_mode, "authorized": svc.authorized, "enabled": svc.enabled, "slo_target": svc.slo_target,
        "data_label": {"simulated": "Synthetic probe (test data)", "in_process": "Real (this application)",
                       "http": "Real HTTP check (authorized endpoint)", "planned": "Planned - not monitored"}[svc.check_mode],
        "window_hours": hours, "checks": n, "availability_pct": round(100 * up / n, 2) if n else None,
        "p50_ms": round(statistics.median(lat), 1) if lat else None,
        "p95_ms": round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 1) if lat else None,
        "last_status": ("up" if last.ok else "down") if last else "no data", "last_checked_at": iso(last.checked_at) if last else None,
        "slo_met": (100 * up / n >= svc.slo_target) if n else None, "notes": svc.notes if svc.check_mode == "planned" else "",
    }


def seed_history(db: Session, svc: MonitoredService, hours: int = 48, step_min: int = 10) -> None:
    """Backfill synthetic history for SIMULATED services only."""
    assert svc.check_mode == "simulated"
    start = utcnow() - timedelta(hours=hours)
    t = start
    while t < utcnow():
        r = simulated_check(svc, t)
        db.add(HealthCheck(service_id=svc.id, checked_at=t, simulated=True, **r))
        t += timedelta(minutes=step_min)
    db.flush()
    # replay incident rules over the backfill
    checks = recent_checks(db, svc.id, 10_000)
    streak = []
    open_inc = None
    for c in checks:
        streak = streak + [c] if not c.ok else []
        if len(streak) >= FAIL_STREAK_FOR_INCIDENT and not open_inc:
            open_inc = Incident(tenant_id=svc.tenant_id, service_id=svc.id, severity="major", simulated=True,
                                trigger=f"{FAIL_STREAK_FOR_INCIDENT} consecutive failed checks", opened_at=streak[0].checked_at,
                                summary=f"{svc.name}: service unavailable",
                                hypotheses=[{"hypothesis": "Upstream unavailability (HTTP 503)", "evidence": "synthetic",
                                             "status": "hypothesis - operator must confirm"}])
            db.add(open_inc)
            db.flush()
            db.add(Alert(tenant_id=svc.tenant_id, service_id=svc.id, incident_id=open_inc.id, rule="R-MON-01 fail streak",
                         message=f"{svc.name}: {open_inc.trigger}", simulated=True, created_at=c.checked_at))
        if c.ok and open_inc:
            open_inc.status = "resolved"
            open_inc.resolved_at = c.checked_at
            db.add(Alert(tenant_id=svc.tenant_id, service_id=svc.id, incident_id=open_inc.id, rule="R-MON-00 recovered",
                         message=f"{svc.name}: recovered", simulated=True, created_at=c.checked_at))
            open_inc = None
