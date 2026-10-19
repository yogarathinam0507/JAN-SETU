import statistics
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import (AssistantEvent, Category, Department, Grievance, Interaction, MonitoredService, Tenant, TicketEvent,
                      User)
from ..security import require
from ..services import evaluation, monitoring, workflow
from ..services.scope import grievance_scope

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
reader = require("analytics:read")


def _window(period: str, date_from: datetime | None, date_to: datetime | None) -> tuple[datetime, datetime, str]:
    end = (date_to.replace(tzinfo=None) if date_to else utcnow())
    if date_from:
        start = date_from.replace(tzinfo=None)
        label = f"{start.date()} to {end.date()}"
    else:
        days = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}.get(period, 30)
        start = end - timedelta(days=days)
        label = f"last {days} days"
    return start, end, label


def compute(db: Session, user: User, period: str, date_from, date_to, department_id, category_id, language, channel,
            priority) -> dict:
    start, end, label = _window(period, date_from, date_to)
    if user.role in {"hod", "admin"}:
        base = select(Grievance).where(Grievance.tenant_id == user.tenant_id)
        scope_label = "tenant-wide aggregates (no personal data)"
    else:
        base = grievance_scope(db, user)
        scope_label = f"records in your {user.role} scope"
    q = base.where(Grievance.created_at >= start, Grievance.created_at <= end)
    filters = []
    for col, val in ((Grievance.department_id, department_id), (Grievance.category_id, category_id),
                     (Grievance.language, language), (Grievance.channel, channel), (Grievance.priority, priority)):
        if val:
            filters.append(col == val)
    if filters:
        q = q.where(*filters)
    rows = db.execute(q).scalars().all()
    tenant = db.get(Tenant, user.tenant_id)
    n = len(rows)
    states = Counter(workflow.sla_state(g)["state"] for g in rows)
    resolved = [g for g in rows if g.resolved_at]
    with_sla = [g for g in resolved if g.sla_due_at]
    met = sum(1 for g in with_sla if g.resolved_at <= g.sla_due_at)
    fr = [(g.first_response_at - g.created_at).total_seconds() / 3600 for g in rows if g.first_response_at]
    res = [(g.resolved_at - g.created_at).total_seconds() / 3600 for g in resolved]
    dept_names = {d.id: d.names.get("en") for d in db.execute(select(Department).where(Department.tenant_id == user.tenant_id)).scalars()}
    cat_names = {c.id: c.names.get("en") for c in db.execute(select(Category).where(Category.tenant_id == user.tenant_id)).scalars()}
    ids = {g.id for g in rows}
    escalated = sum(1 for g in rows if g.escalation_level > 0)
    reopened = sum(1 for g in rows if g.reopen_count > 0)
    day_counts = Counter(g.created_at.date().isoformat() for g in rows)
    days = (end.date() - start.date()).days
    daily = [{"date": (start.date() + timedelta(days=k)).isoformat(),
              "count": day_counts.get((start.date() + timedelta(days=k)).isoformat(), 0)} for k in range(days + 1)]
    dup = workflow.duplicate_stats(db, user.tenant_id, [Grievance.id.in_(ids)] if ids else [Grievance.id.is_(None)])
    # Call centre
    inter = db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id, Interaction.queued_at >= start,
                                                 Interaction.queued_at <= end)).scalars().all()
    waits = [(i.started_at - i.queued_at).total_seconds() for i in inter if i.started_at]
    qa = [i.qa_review["percent"] for i in inter if i.qa_review]
    # Benefits
    ev = db.execute(select(AssistantEvent).where(AssistantEvent.tenant_id == user.tenant_id, AssistantEvent.created_at >= start,
                                                 AssistantEvent.created_at <= end)).scalars().all()
    services = db.execute(select(MonitoredService).where(MonitoredService.tenant_id == user.tenant_id,
                                                         MonitoredService.check_mode != "planned")).scalars().all()
    demo_rows = sum(1 for g in rows if g.is_demo)
    return {
        "meta": {"tenant": tenant.name, "window": label, "from": iso(start), "to": iso(end), "scope": scope_label,
                 "source": "Live query of persisted records in this deployment's database",
                 "data_mode": ("test data" if demo_rows == n and n else "test + live records" if demo_rows else "live records"),
                 "demo_records": demo_rows, "generated_at": iso(utcnow()),
                 "filters": {"department_id": department_id, "category_id": category_id, "language": language,
                             "channel": channel, "priority": priority}},
        "totals": {"total": n, "open": sum(1 for g in rows if g.status in workflow.OPEN_STATUSES),
                   "pending_acceptance": sum(1 for g in rows if g.status in {"submitted", "reopened"}),
                   "in_progress": sum(1 for g in rows if g.status in {"accepted", "in_progress", "info_requested"}),
                   "human_review": sum(1 for g in rows if g.status == "human_review"),
                   "resolved": sum(1 for g in rows if g.status == "resolved"),
                   "closed": sum(1 for g in rows if g.status == "closed"),
                   "rejected": sum(1 for g in rows if g.status == "rejected"),
                   "overdue": states.get("breached", 0)},
        "sla": {"compliance_pct": round(100 * met / len(with_sla), 1) if with_sla else None,
                "resolved_with_sla": len(with_sla), "resolved_within_sla": met,
                "breaches": states.get("breached", 0) + states.get("missed", 0),
                "definition": "Compliance = resolved on/before SLA due / resolved tickets that had an SLA, in the window."},
        "timings": {"avg_first_response_hours": round(statistics.mean(fr), 1) if fr else None,
                    "avg_resolution_hours": round(statistics.mean(res), 1) if res else None,
                    "median_resolution_hours": round(statistics.median(res), 1) if res else None,
                    "definition": "Hours from ticket creation to first acceptance / to resolution."},
        "rates": {"escalation_rate_pct": round(100 * escalated / n, 1) if n else None,
                  "reopen_rate_pct": round(100 * reopened / n, 1) if n else None, "escalated": escalated, "reopened": reopened},
        "distribution": {
            "department": dict(Counter(dept_names.get(g.department_id, "Unrouted (human triage)") for g in rows).most_common()),
            "category": dict(Counter(cat_names.get(g.category_id, "Unclassified") for g in rows).most_common()),
            "priority": dict(Counter(g.priority or "Not set" for g in rows)),
            "language": dict(Counter(g.language for g in rows)),
            "channel": dict(Counter(g.channel for g in rows)),
            "status": dict(Counter(g.status for g in rows)),
        },
        "daily": daily, "duplicates": dup,
        "call_centre": {"interactions": len(inter), "simulated": sum(1 for i in inter if i.simulated),
                        "avg_wait_seconds": int(statistics.mean(waits)) if waits else None,
                        "tickets_created": sum(1 for i in inter if i.grievance_id),
                        "callbacks": sum(1 for i in inter if i.callback_at or i.channel == "callback_request"),
                        "resolved_closed": sum(1 for i in inter if i.status == "closed"),
                        "qa_avg_pct": round(statistics.mean(qa), 1) if qa else None, "qa_reviewed": len(qa)},
        "benefits": {"events": len(ev), "by_kind": dict(Counter(e.kind for e in ev)),
                     "by_outcome": dict(Counter(e.outcome for e in ev)),
                     "assisted_referrals": sum(1 for e in ev if e.kind == "human_referral")},
        "uptime": [monitoring.service_summary(db, s, 24) for s in services],
        "ai_evaluation": evaluation.summary(db, user.tenant_id),
    }


@router.get("/overview")
def overview(period: str = Query("30d", pattern="^(7d|30d|90d|365d)$"), date_from: datetime | None = None,
             date_to: datetime | None = None, department_id: str | None = None, category_id: str | None = None,
             language: str | None = None, channel: str | None = None, priority: str | None = None,
             user: User = Depends(reader), db: Session = Depends(get_db)):
    return compute(db, user, period, date_from, date_to, department_id, category_id, language, channel, priority)


@router.get("/export")
def export(period: str = Query("30d", pattern="^(7d|30d|90d|365d)$"), date_from: datetime | None = None,
           date_to: datetime | None = None, department_id: str | None = None, category_id: str | None = None,
           language: str | None = None, channel: str | None = None, priority: str | None = None,
           user: User = Depends(reader), db: Session = Depends(get_db)):
    data = compute(db, user, period, date_from, date_to, department_id, category_id, language, channel, priority)
    return JSONResponse(data, headers={"Content-Disposition": 'attachment; filename="jansetu-analytics.json"'})


@router.get("/ai-eval")
def ai_eval(user: User = Depends(reader), db: Session = Depends(get_db)):
    return {"latest": evaluation.summary(db, user.tenant_id), "runs": evaluation.count_runs(db, user.tenant_id)}


@router.post("/ai-eval/run")
def ai_eval_run(user: User = Depends(require("ai_eval:run")), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    run_id = evaluation.run_eval(db, tenant)
    db.commit()
    return evaluation.summary(db, user.tenant_id, run_id)


_ = TicketEvent
