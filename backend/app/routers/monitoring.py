from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import Alert, Grievance, HealthCheck, Incident, Interaction, MonitoredService, User
from ..security import require
from ..services import audit, monitoring

router = APIRouter(prefix="/api/monitoring", tags=["service monitoring"])
reader = require("monitoring:read")
manager = require("monitoring:manage")


def _svc(db: Session, user: User, sid: str) -> MonitoredService:
    s = db.get(MonitoredService, sid)
    if not s or s.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Service not found."})
    return s


@router.get("/services")
def services(hours: int = Query(24, ge=1, le=720), user: User = Depends(reader), db: Session = Depends(get_db)):
    rows = db.execute(select(MonitoredService).where(MonitoredService.tenant_id == user.tenant_id)
                      .order_by(MonitoredService.check_mode, MonitoredService.name)).scalars().all()
    return {"window_hours": hours, "services": [monitoring.service_summary(db, s, hours) for s in rows],
            "legend": {"in_process": "Real measurement of this application", "http": "Real check of an authorized endpoint",
                       "simulated": "Demo data / Simulated", "planned": "Planned - not connected, not probed"}}


@router.get("/services/{sid}")
def service_detail(sid: str, hours: int = Query(24, ge=1, le=720), user: User = Depends(reader), db: Session = Depends(get_db)):
    s = _svc(db, user, sid)
    since = utcnow() - timedelta(hours=hours)
    checks = db.execute(select(HealthCheck).where(HealthCheck.service_id == s.id, HealthCheck.checked_at >= since)
                        .order_by(HealthCheck.checked_at)).scalars().all()
    return {"summary": monitoring.service_summary(db, s, hours), "anomaly": monitoring.anomaly(db, s),
            "risk": monitoring.risk_score(db, s),
            "series": [{"at": iso(c.checked_at), "ok": c.ok, "latency_ms": c.latency_ms, "status_code": c.status_code,
                        "error": c.error, "simulated": c.simulated} for c in checks[-500:]]}


class ServiceIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    endpoint: str = Field("", max_length=500)
    owner_team: str = Field("", max_length=200)
    environment: str = Field("production", max_length=40)
    criticality: str = Field("medium", pattern="^(low|medium|high)$")
    check_mode: str = Field(pattern="^(http|simulated|planned)$")
    expected_status: int = Field(200, ge=100, le=599)
    latency_threshold_ms: int = Field(1500, ge=50, le=60000)
    slo_target: float = Field(99.5, ge=50, le=100)
    authorization_confirmation: str = Field("", max_length=300)


@router.post("/services", status_code=201)
def add_service(body: ServiceIn, user: User = Depends(manager), db: Session = Depends(get_db)):
    authorized = False
    if body.check_mode == "http":
        if not body.endpoint.startswith("https://"):
            raise HTTPException(422, detail={"code": "https_required", "message": "HTTP checks require an https:// endpoint."})
        if len(body.authorization_confirmation.strip()) < 15:
            raise HTTPException(422, detail={"code": "authorization_required",
                                             "message": "Record who authorised monitoring of this endpoint (reference / approver)."})
        authorized = True
    s = MonitoredService(tenant_id=user.tenant_id, name=body.name, endpoint=body.endpoint, owner_team=body.owner_team,
                         environment=body.environment, criticality=body.criticality, check_mode=body.check_mode,
                         expected_status=body.expected_status, latency_threshold_ms=body.latency_threshold_ms,
                         slo_target=body.slo_target, authorized=authorized, enabled=body.check_mode != "planned",
                         notes="" if body.check_mode != "planned" else "Planned")
    db.add(s)
    db.flush()
    audit.record(db, actor=user, action="monitoring.add_service", entity_type="service", entity_id=s.id,
                 after={"name": s.name, "mode": s.check_mode, "authorized": authorized},
                 reason=body.authorization_confirmation)
    db.commit()
    return monitoring.service_summary(db, s)


class ToggleIn(BaseModel):
    enabled: bool


@router.patch("/services/{sid}")
def toggle(sid: str, body: ToggleIn, user: User = Depends(manager), db: Session = Depends(get_db)):
    s = _svc(db, user, sid)
    if s.check_mode == "planned" and body.enabled:
        raise HTTPException(409, detail={"code": "planned", "message": "Planned services cannot be enabled until configured."})
    s.enabled = body.enabled
    audit.record(db, actor=user, action="monitoring.toggle", entity_type="service", entity_id=s.id, after={"enabled": s.enabled})
    db.commit()
    return monitoring.service_summary(db, s)


@router.post("/services/{sid}/check-now")
def check_now(sid: str, user: User = Depends(manager), db: Session = Depends(get_db)):
    s = _svc(db, user, sid)
    hc = monitoring.run_check(db, s)
    db.commit()
    if not hc:
        raise HTTPException(409, detail={"code": "not_checkable", "message": "This service is planned, disabled or unauthorized."})
    return {"ok": hc.ok, "latency_ms": hc.latency_ms, "status_code": hc.status_code, "error": hc.error, "simulated": hc.simulated}


def _inc_out(db: Session, i: Incident) -> dict:
    s = db.get(MonitoredService, i.service_id)
    end = i.resolved_at or utcnow()
    return {"id": i.id, "public_id": i.public_id, "service": s.name, "status": i.status, "severity": i.severity,
            "trigger": i.trigger, "opened_at": iso(i.opened_at), "resolved_at": iso(i.resolved_at),
            "duration_minutes": round((end - i.opened_at).total_seconds() / 60, 1), "summary": i.summary,
            "hypotheses": i.hypotheses, "confirmed_root_cause": i.confirmed_root_cause, "simulated": i.simulated,
            "label": "Demo data / Simulated" if i.simulated else "Real"}


@router.get("/incidents")
def incidents(status: str | None = None, user: User = Depends(reader), db: Session = Depends(get_db)):
    q = select(Incident).where(Incident.tenant_id == user.tenant_id)
    if status:
        q = q.where(Incident.status == status)
    return [_inc_out(db, i) for i in db.execute(q.order_by(Incident.opened_at.desc()).limit(100)).scalars()]


class IncidentActionIn(BaseModel):
    action: str = Field(pattern="^(acknowledge|confirm_root_cause|resolve)$")
    note: str = Field(min_length=3, max_length=1000)


@router.post("/incidents/{iid}")
def incident_action(iid: str, body: IncidentActionIn, user: User = Depends(manager), db: Session = Depends(get_db)):
    i = db.get(Incident, iid)
    if not i or i.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Incident not found."})
    before = {"status": i.status, "root_cause": i.confirmed_root_cause}
    if body.action == "acknowledge":
        i.status = "acknowledged" if i.status == "open" else i.status
    elif body.action == "confirm_root_cause":
        i.confirmed_root_cause, i.confirmed_by = body.note, user.id
    else:
        i.status, i.resolved_at = "resolved", i.resolved_at or utcnow()
    audit.record(db, actor=user, action=f"incident.{body.action}", entity_type="incident", entity_id=i.public_id,
                 before=before, after={"status": i.status, "root_cause": i.confirmed_root_cause}, reason=body.note)
    db.commit()
    return _inc_out(db, i)


@router.get("/alerts")
def alerts(user: User = Depends(reader), db: Session = Depends(get_db)):
    rows = db.execute(select(Alert).where(Alert.tenant_id == user.tenant_id).order_by(Alert.created_at.desc()).limit(100)).scalars()
    return [{"id": a.id, "service": db.get(MonitoredService, a.service_id).name, "rule": a.rule, "message": a.message,
             "at": iso(a.created_at), "simulated": a.simulated} for a in rows]


@router.get("/traffic")
def traffic(days: int = Query(7, ge=1, le=60), user: User = Depends(reader), db: Session = Depends(get_db)):
    """Platform load trend from real persisted records (tickets + interactions per day) and a capacity-risk rule."""
    since = utcnow() - timedelta(days=days)
    g = db.execute(select(Grievance.created_at).where(Grievance.tenant_id == user.tenant_id, Grievance.created_at >= since)).scalars().all()
    i = db.execute(select(Interaction.queued_at).where(Interaction.tenant_id == user.tenant_id, Interaction.queued_at >= since)).scalars().all()
    per_day = Counter(d.date().isoformat() for d in g + i)
    days_list = [(utcnow() - timedelta(days=k)).date().isoformat() for k in range(days - 1, -1, -1)]
    series = [{"date": d, "events": per_day.get(d, 0)} for d in days_list]
    hist = [p["events"] for p in series[:-1]]
    avg = sum(hist) / len(hist) if hist else 0
    today = series[-1]["events"] if series else 0
    risk = today > 2 * avg and today >= 10
    return {"series": series, "average_per_day": round(avg, 1), "today": today,
            "capacity_risk": {"triggered": risk, "rule": "today's events > 2x trailing average and >= 10"},
            "autoscaling": "Not performed. This deployment has no permission to scale infrastructure automatically.",
            "source": "Persisted grievances and call-centre interactions (includes demo seed data if present)."}
