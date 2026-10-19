"""Role dashboards (KPIs, charts, work lists) and the notification feed for every signed-in role.

Every number is a live query of this deployment's database, scoped by the same server-side rules as the rest of
the API (citizen = own tickets, officer = own department, nodal = own zone, hod/admin = aggregates only).
"""
import statistics
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import (AuditLog, Category, Department, Grievance, IntegrationConfig, Interaction, Jurisdiction,
                      KnowledgeDocument, Language, MonitoredService, Scheme, TicketEvent, Tenant, TriageRecord, User,
                      Vendor, WorkOrder)
from ..security import ROLES, get_current_user
from ..services import evaluation, monitoring, workflow
from ..services.scope import grievance_scope

router = APIRouter(prefix="/api", tags=["dashboard"])

ACTIVE = workflow.OPEN_STATUSES
DONE = {"resolved", "closed"}


def kpi(key, label, value, *, unit="", tone="", hint="", link=""):
    return {"key": key, "label": label, "value": value, "unit": unit, "tone": tone, "hint": hint, "link": link}


def bars(title, counter: Counter | dict, limit=8, kind="bar"):
    items = sorted(counter.items(), key=lambda kv: -kv[1])[:limit]
    return {"type": kind, "title": title, "data": [{"label": str(k), "value": v} for k, v in items]}


def trend(rows, days=14, title="New vs resolved complaints (last 14 days)"):
    today = utcnow().date()
    labels = [(today - timedelta(days=days - 1 - k)) for k in range(days)]
    new = Counter(g.created_at.date() for g in rows)
    res = Counter(g.resolved_at.date() for g in rows if g.resolved_at)
    return {"type": "line", "title": title, "labels": [d.strftime("%d %b") for d in labels],
            "series": [{"name": "New", "values": [new.get(d, 0) for d in labels]},
                       {"name": "Resolved", "values": [res.get(d, 0) for d in labels]}]}


def _names(db, tenant_id):
    depts = {d.id: d for d in db.execute(select(Department).where(Department.tenant_id == tenant_id)).scalars()}
    cats = {c.id: c for c in db.execute(select(Category).where(Category.tenant_id == tenant_id)).scalars()}
    wards = {j.id: j.name for j in db.execute(select(Jurisdiction).where(Jurisdiction.tenant_id == tenant_id)).scalars()}
    return depts, cats, wards


def _ticket_rows(db, rows, depts, cats, wards, limit=8, officer=False):
    users = {}

    def officer_name(uid):
        if uid and uid not in users:
            u = db.get(User, uid)
            users[uid] = u.full_name if u else ""
        return users.get(uid, "")
    out = []
    for g in rows[:limit]:
        sla = workflow.sla_state(g)
        out.append({"id": g.public_id, "link": f"/officer?ticket={g.public_id}" if officer else f"/citizen/tickets/{g.public_id}",
                    "cells": [g.public_id, (cats[g.category_id].names.get("en") if g.category_id in cats else "Under review"),
                              wards.get(g.jurisdiction_id, "-"), g.priority or "-",
                              workflow.STATUS_LABELS.get(g.status, g.status).split(" - ")[0],
                              officer_name(g.assigned_officer_id) or "-", sla["label"]],
                    "tone": "bad" if sla["state"] == "breached" else "warn" if sla["state"] == "at_risk" else ""})
    return out


TICKET_COLS = ["Ticket", "Category", "Ward", "Priority", "Status", "Assigned to", "SLA"]


def _urgency(g):
    order = {"Emergency": 0, "High": 1, "Medium": 2, "Low": 3}
    return (0 if workflow.sla_state(g)["state"] == "breached" else 1, order.get(g.priority, 4),
            g.sla_due_at or g.created_at)


def _common_grievance_kpis(rows):
    now = utcnow()
    open_ = [g for g in rows if g.status in ACTIVE]
    breached = [g for g in open_ if workflow.sla_state(g)["state"] == "breached"]
    resolved = [g for g in rows if g.resolved_at]
    with_sla = [g for g in resolved if g.sla_due_at]
    met = sum(1 for g in with_sla if g.resolved_at <= g.sla_due_at)
    res_h = [(g.resolved_at - g.created_at).total_seconds() / 3600 for g in resolved]
    ratings = [g.citizen_rating for g in rows if g.citizen_rating]
    today = [g for g in rows if g.created_at >= now - timedelta(hours=24)]
    return {
        "total": kpi("total", "Total complaints", len(rows)),
        "open": kpi("open", "Open complaints", len(open_), tone="info"),
        "today": kpi("today", "Received in last 24 h", len(today)),
        "breached": kpi("breached", "SLA breached (open)", len(breached), tone="bad" if breached else "good"),
        "compliance": kpi("compliance", "SLA compliance", round(100 * met / len(with_sla), 1) if with_sla else "-",
                          unit="%" if with_sla else "", tone="good" if with_sla and met / len(with_sla) >= 0.8 else "warn",
                          hint="Resolved within SLA / resolved"),
        "avg_res": kpi("avg_res", "Average resolution time",
                       round(statistics.mean(res_h) / 24, 1) if res_h else "-", unit="days" if res_h else ""),
        "rating": kpi("rating", "Citizen satisfaction", round(statistics.mean(ratings), 1) if ratings else "-",
                      unit="/ 5" if ratings else ""),
        "resolved": kpi("resolved", "Resolved / closed", sum(1 for g in rows if g.status in DONE), tone="good"),
        "emergency": kpi("emergency", "Open emergencies", sum(1 for g in open_ if g.emergency),
                         tone="bad" if any(g.emergency for g in open_) else "good"),
        "escalated": kpi("escalated", "Escalated (open)", sum(1 for g in open_ if g.escalation_level > 0), tone="warn"),
    }


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.get(Tenant, user.tenant_id)
    depts, cats, wards = _names(db, user.tenant_id)
    role = user.role
    out = {"role": role, "role_name": ROLES[role][0], "user": user.full_name, "designation": user.designation or "",
           "tenant": tenant.name, "generated_at": iso(utcnow()), "kpis": [], "charts": [], "lists": [], "scope": ""}
    dept_label = lambda d: d.names.get("en", d.code) if d else "Under review"  # noqa: E731

    if role in {"citizen", "officer", "nodal", "auditor", "agent"}:
        rows = db.execute(grievance_scope(db, user)).scalars().all()
        k = _common_grievance_kpis(rows)

    if role == "citizen":
        mine = sorted(rows, key=lambda g: g.created_at, reverse=True)
        out["scope"] = "Your complaints"
        out["kpis"] = [kpi("total", "My complaints", len(rows), link="/citizen/tickets"), k["open"], k["resolved"], k["avg_res"]]
        out["charts"] = [bars("My complaints by status",
                              Counter(workflow.STATUS_LABELS.get(g.status, g.status).split(" - ")[0] for g in rows), kind="donut"),
                         bars("My complaints by category", Counter(cats[g.category_id].names["en"] if g.category_id in cats
                                                                   else "Under review" for g in rows))]
        out["lists"] = [{"title": "Recent complaints", "columns": TICKET_COLS,
                         "rows": _ticket_rows(db, mine, depts, cats, wards, 6)}]
        out["actions"] = [{"label": "Register a complaint", "link": "/citizen"}, {"label": "Track my complaints", "link": "/citizen/tickets"},
                          {"label": "Find government schemes", "link": "/benefits"}]
        return out

    if role == "officer":
        d = depts.get(user.department_id)
        out["scope"] = f"{dept_label(d)} - all wards"
        open_rows = sorted([g for g in rows if g.status in ACTIVE], key=_urgency)
        due24 = [g for g in open_rows if g.sla_due_at and utcnow() <= g.sla_due_at <= utcnow() + timedelta(hours=24)]
        mine = [g for g in open_rows if g.assigned_officer_id == user.id]
        out["kpis"] = [kpi("mine", "Assigned to me (open)", len(mine), tone="info", link="/officer"),
                       kpi("new", "Awaiting acceptance", sum(1 for g in open_rows if g.status in {"submitted", "reopened"}),
                           tone="warn", link="/officer"),
                       k["breached"], kpi("due24", "Due in next 24 h", len(due24), tone="warn"),
                       k["resolved"], k["compliance"], k["avg_res"], k["rating"]]
        out["charts"] = [trend(rows),
                         bars("Open complaints by ward", Counter(wards.get(g.jurisdiction_id, "Unmapped") for g in open_rows)),
                         bars("Open complaints by priority", Counter(g.priority or "-" for g in open_rows), kind="donut"),
                         bars("Complaints by category", Counter(cats[g.category_id].names["en"] for g in rows if g.category_id in cats))]
        out["lists"] = [{"title": "Most urgent open complaints", "columns": TICKET_COLS,
                         "rows": _ticket_rows(db, open_rows, depts, cats, wards, 10, officer=True)}]
        out["actions"] = [{"label": "Open my work queue", "link": "/officer"}, {"label": "Live map", "link": "/map"}]
        return out

    if role == "nodal":
        j = db.get(Jurisdiction, user.jurisdiction_id) if user.jurisdiction_id else None
        out["scope"] = f"{j.name} - all departments" if j else "Whole city - all departments"
        open_rows = sorted([g for g in rows if g.status in ACTIVE], key=_urgency)
        review = [g for g in rows if g.status == "human_review"]
        out["kpis"] = [k["open"], kpi("review", "Awaiting manual routing", len(review), tone="warn" if review else "good", link="/nodal"),
                       k["emergency"], k["breached"], k["escalated"], k["compliance"], k["today"], k["rating"]]
        out["charts"] = [trend(rows),
                         bars("Open complaints by department", Counter(dept_label(depts.get(g.department_id)) for g in open_rows)),
                         bars("Open complaints by ward", Counter(wards.get(g.jurisdiction_id, "Unmapped") for g in open_rows)),
                         bars("SLA status of open complaints",
                              Counter(workflow.sla_state(g)["label"] for g in open_rows), kind="donut")]
        out["lists"] = [{"title": "Breached and emergency complaints", "columns": TICKET_COLS,
                         "rows": _ticket_rows(db, [g for g in open_rows if g.emergency or workflow.sla_state(g)["state"] == "breached"],
                                              depts, cats, wards, 10, officer=True)}]
        out["actions"] = [{"label": "Manual routing queue", "link": "/nodal"}, {"label": "Live map", "link": "/map"}]
        return out

    if role == "agent":
        out["scope"] = "Helpline - all wards"
        since = utcnow() - timedelta(hours=24)
        inter = db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id)).scalars().all()
        today = [i for i in inter if i.queued_at and i.queued_at >= since]
        waits = [(i.started_at - i.queued_at).total_seconds() for i in inter if i.started_at and i.queued_at]
        queued = [i for i in inter if i.status == "queued"]
        mine = [i for i in inter if i.agent_id == user.id]
        out["kpis"] = [kpi("queued", "Calls / requests waiting", len(queued), tone="warn" if queued else "good", link="/agent"),
                       kpi("today", "Interactions in last 24 h", len(today)),
                       kpi("mine", "Handled by me", len(mine), tone="info"),
                       kpi("wait", "Average wait", round(statistics.mean(waits)) if waits else "-", unit="sec" if waits else ""),
                       kpi("tickets", "Complaints registered by helpline", sum(1 for g in rows if g.channel == "voice")),
                       k["open"]]
        out["charts"] = [bars("Call outcomes", Counter((i.disposition or "open").replace("_", " ") for i in inter), kind="donut"),
                         bars("Channels", Counter(i.channel.replace("_", " ") for i in inter))]
        out["lists"] = [{"title": "Waiting in queue", "columns": ["Reference", "Channel", "Language", "Waiting since"],
                         "rows": [{"id": i.public_id, "link": "/agent",
                                   "cells": [i.public_id, i.channel.replace("_", " "), i.language, iso(i.queued_at)]} for i in queued[:10]]}]
        out["actions"] = [{"label": "Open helpline desk", "link": "/agent"}, {"label": "Register complaint for caller", "link": "/citizen"}]
        return out

    if role == "auditor":
        out["scope"] = "Whole city - read only"
        since = utcnow() - timedelta(days=1)
        logs = db.scalar(select(AuditLog.id).where(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.id.desc()).limit(1))
        n24 = len(db.execute(select(AuditLog.id).where(AuditLog.tenant_id == user.tenant_id, AuditLog.created_at >= since)).all())
        ev = evaluation.summary(db, user.tenant_id)
        overrides = len(db.execute(select(TriageRecord.id).where(TriageRecord.tenant_id == user.tenant_id,
                                                                 TriageRecord.human_override.is_not(None))).all())
        qa = [i.qa_review["percent"] for i in db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id)).scalars()
              if i.qa_review]
        out["kpis"] = [kpi("audit24", "Audit events (24 h)", n24, link="/audit"),
                       kpi("routing", "Routing accuracy (test set)", ev["overall"]["category_accuracy_pct"] if ev else "-",
                           unit="%" if ev else "", link="/analytics"),
                       kpi("overrides", "Manual routing corrections", overrides),
                       kpi("qa", "Call quality score", round(statistics.mean(qa), 1) if qa else "-", unit="%" if qa else ""),
                       k["compliance"], k["breached"]]
        out["charts"] = [trend(rows), bars("Complaints by status",
                                           Counter(workflow.STATUS_LABELS.get(g.status, g.status).split(" - ")[0] for g in rows), kind="donut")]
        out["lists"] = [{"title": "Reopened complaints (sample for review)", "columns": TICKET_COLS,
                         "rows": _ticket_rows(db, [g for g in rows if g.reopen_count], depts, cats, wards, 8, officer=True)}]
        out["actions"] = [{"label": "Audit trail", "link": "/audit"}, {"label": "Reports", "link": "/analytics"}]
        _ = logs
        return out

    if role == "hod":
        rows = db.execute(select(Grievance).where(Grievance.tenant_id == user.tenant_id)).scalars().all()
        k = _common_grievance_kpis(rows)
        out["scope"] = "Whole city - aggregate figures (no personal data)"
        out["kpis"] = [k["total"], k["open"], k["breached"], k["compliance"], k["avg_res"], k["rating"], k["escalated"], k["emergency"]]
        per = {}
        for g in rows:
            name = dept_label(depts.get(g.department_id))
            r = per.setdefault(name, {"total": 0, "open": 0, "breached": 0, "res": 0, "met": 0})
            r["total"] += 1
            if g.status in ACTIVE:
                r["open"] += 1
                if workflow.sla_state(g)["state"] == "breached":
                    r["breached"] += 1
            if g.resolved_at and g.sla_due_at:
                r["res"] += 1
                r["met"] += g.resolved_at <= g.sla_due_at
        out["charts"] = [trend(rows, 30, "New vs resolved complaints (last 30 days)"),
                         bars("Open complaints by department", {k_: v["open"] for k_, v in per.items()}),
                         bars("Complaints by zone", Counter(wards.get(g.jurisdiction_id, "Unmapped") for g in rows), limit=12),
                         bars("Complaints by channel", Counter(g.channel for g in rows), kind="donut")]
        out["lists"] = [{"title": "Department performance", "columns": ["Department", "Total", "Open", "SLA breached", "SLA compliance"],
                         "rows": [{"id": n, "link": "", "tone": "bad" if v["breached"] > 3 else "",
                                   "cells": [n, v["total"], v["open"], v["breached"],
                                             f"{round(100 * v['met'] / v['res'])}%" if v["res"] else "-"]}
                                  for n, v in sorted(per.items(), key=lambda kv: -kv[1]["open"])]}]
        out["actions"] = [{"label": "Detailed reports", "link": "/analytics"}, {"label": "Live map", "link": "/map"},
                          {"label": "Service uptime", "link": "/monitoring"}]
        return out

    if role == "vendor":
        wos = db.execute(select(WorkOrder).where(WorkOrder.vendor_id == user.vendor_id)).scalars().all() if user.vendor_id else []
        v = db.get(Vendor, user.vendor_id) if user.vendor_id else None
        now = utcnow()
        open_w = [w for w in wos if w.status in {"issued", "in_progress"}]
        overdue = [w for w in open_w if w.due_at and w.due_at < now]
        out["scope"] = v.name if v else "Contractor"
        out["kpis"] = [kpi("total", "Work orders received", len(wos)), kpi("open", "Open work orders", len(open_w), tone="info", link="/vendor"),
                       kpi("overdue", "Overdue", len(overdue), tone="bad" if overdue else "good"),
                       kpi("done", "Completed", sum(1 for w in wos if w.status in {"completed", "verified"}), tone="good")]
        out["charts"] = [bars("Work orders by status", Counter(w.status.replace("_", " ") for w in wos), kind="donut")]
        out["lists"] = [{"title": "Open work orders", "columns": ["Work order", "Description", "Due", "Status"],
                         "rows": [{"id": w.public_id, "link": "/vendor", "tone": "bad" if w in overdue else "",
                                   "cells": [w.public_id, w.description, iso(w.due_at), w.status.replace("_", " ")]} for w in open_w]}]
        out["actions"] = [{"label": "My work orders", "link": "/vendor"}]
        return out

    if role == "content":
        docs = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == user.tenant_id)).scalars().all()
        latest = {}
        for d in docs:
            if d.doc_key not in latest or d.version > latest[d.doc_key].version:
                latest[d.doc_key] = d
        schemes = db.execute(select(Scheme).where(Scheme.tenant_id == user.tenant_id)).scalars().all()
        langs = db.execute(select(Language)).scalars().all()
        unver = [d for d in latest.values() if not d.verified]
        out["scope"] = "Knowledge base, schemes and languages"
        out["kpis"] = [kpi("docs", "Knowledge articles", len(latest), link="/knowledge"),
                       kpi("unverified", "Articles awaiting verification", len(unver), tone="warn" if unver else "good"),
                       kpi("schemes", "Schemes listed", sum(1 for s in schemes if not s.code.startswith("dir_"))),
                       kpi("sch_unver", "Schemes awaiting verification", sum(1 for s in schemes if not s.verified), tone="warn"),
                       kpi("langs", "Languages with full interface", sum(1 for lg in langs if lg.ui_strings))]
        out["charts"] = [bars("Articles by language", Counter(d.language for d in latest.values()), kind="donut")]
        out["lists"] = [{"title": "Articles awaiting verification", "columns": ["Article", "Language", "Version"],
                         "rows": [{"id": d.doc_key, "link": "/knowledge", "cells": [d.title, d.language, d.version]} for d in unver]}]
        out["actions"] = [{"label": "Manage knowledge base", "link": "/knowledge"}]
        return out

    if role == "admin":
        users = db.execute(select(User).where(User.tenant_id == user.tenant_id)).scalars().all()
        services = db.execute(select(MonitoredService).where(MonitoredService.tenant_id == user.tenant_id,
                                                             MonitoredService.check_mode != "planned")).scalars().all()
        summ = [monitoring.service_summary(db, s, 24) for s in services]
        down = [s for s in summ if s["last_status"] == "down"]
        integ = db.execute(select(IntegrationConfig)).scalars().all()
        out["scope"] = "System administration"
        out["kpis"] = [kpi("users", "Active user accounts", sum(1 for u in users if u.active), link="/admin"),
                       kpi("staff", "Staff accounts", sum(1 for u in users if u.role != "citizen")),
                       kpi("services", "Monitored services", len(summ), link="/monitoring"),
                       kpi("down", "Services down now", len(down), tone="bad" if down else "good"),
                       kpi("integrations", "Integrations connected", sum(1 for i in integ if i.state == "connected_tested")),
                       kpi("depts", "Departments configured", len(depts))]
        out["charts"] = [bars("User accounts by role", Counter(ROLES[u.role][0] for u in users), limit=9),
                         bars("Integrations by state", Counter(i.state.replace("_", " ") for i in integ), kind="donut")]
        out["lists"] = [{"title": "Service status (last 24 h)", "columns": ["Service", "Status", "Availability", "p95 latency"],
                         "rows": [{"id": s["id"], "link": "/monitoring", "tone": "bad" if s["last_status"] == "down" else "",
                                   "cells": [s["name"], s["last_status"], f"{s['availability_pct']}%" if s["availability_pct"] is not None else "-",
                                             f"{s['p95_ms']} ms" if s["p95_ms"] else "-"]} for s in summ]}]
        out["actions"] = [{"label": "Administration", "link": "/admin"}, {"label": "Service uptime", "link": "/monitoring"}]
        return out
    return out


# ------------------------------------------------------------------ notifications
EVENT_TITLES = {
    "created": "Complaint registered", "assigned": "Complaint assigned", "accept": "Accepted by department",
    "start": "Work started", "resolve": "Marked resolved", "confirm_closure": "Closed by citizen",
    "reject_closure": "Reopened by citizen", "reject": "Complaint rejected", "request_info": "More information requested",
    "provide_info": "Citizen replied", "escalated": "Escalated", "emergency_flag": "Emergency complaint",
    "transfer": "Transferred", "human_triage": "Routed by nodal officer", "linked_master": "Linked to similar complaints",
}


def _event_items(db, rows, user, types=None, limit=20, link_officer=False):
    if not rows:
        return []
    ids = {g.id: g for g in rows}
    q = select(TicketEvent).where(TicketEvent.grievance_id.in_(list(ids))).order_by(TicketEvent.created_at.desc())
    if types:
        q = q.where(TicketEvent.event_type.in_(types))
    if user.role == "citizen":
        q = q.where(TicketEvent.public.is_(True))
    items = []
    for e in db.execute(q.limit(limit * 3)).scalars():
        if e.actor_id == user.id or e.event_type == "notification":
            continue
        g = ids[e.grievance_id]
        tone = "bad" if e.event_type in {"escalated", "emergency_flag", "reject_closure"} else \
            "good" if e.event_type in {"resolve", "confirm_closure"} else "info"
        items.append({"id": f"ev{e.id}", "at": iso(e.created_at), "tone": tone,
                      "title": f"{EVENT_TITLES.get(e.event_type, e.event_type.replace('_', ' ').title())} - {g.public_id}",
                      "body": e.note or workflow.STATUS_LABELS.get(g.status, g.status),
                      "link": f"/officer?ticket={g.public_id}" if link_officer else f"/citizen/tickets/{g.public_id}"})
        if len(items) >= limit:
            break
    return items


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = user.role
    items = []
    if role == "citizen":
        rows = db.execute(grievance_scope(db, user)).scalars().all()
        items = _event_items(db, rows, user, {"assigned", "accept", "start", "resolve", "reject", "request_info",
                                              "escalated", "transfer", "human_triage", "linked_master"})
    elif role in {"officer", "nodal"}:
        rows = db.execute(grievance_scope(db, user).where(Grievance.created_at >= utcnow() - timedelta(days=21))).scalars().all()
        types = {"assigned", "reject_closure", "escalated", "emergency_flag", "provide_info", "transfer"}
        if role == "nodal":
            types |= {"created"}
        items = _event_items(db, rows, user, types, link_officer=True)
        if role == "nodal":
            items = [i for i in items if not i["title"].startswith("Complaint registered")
                     or "human triage" in i["body"].lower()][:20]
    elif role == "agent":
        for i in db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id, Interaction.status == "queued")
                            .order_by(Interaction.queued_at.desc()).limit(10)).scalars():
            items.append({"id": f"in{i.id}", "at": iso(i.queued_at), "tone": "warn", "link": "/agent",
                          "title": f"Waiting: {i.channel.replace('_', ' ')} - {i.public_id}",
                          "body": "A caller is waiting for the helpline."})
    elif role == "vendor" and user.vendor_id:
        for w in db.execute(select(WorkOrder).where(WorkOrder.vendor_id == user.vendor_id)
                            .order_by(WorkOrder.created_at.desc()).limit(15)).scalars():
            items.append({"id": f"wo{w.id}", "at": iso(w.created_at), "tone": "info", "link": "/vendor",
                          "title": f"Work order {w.public_id} issued", "body": w.description})
    elif role == "hod":
        rows = db.execute(select(Grievance).where(Grievance.tenant_id == user.tenant_id,
                                                  Grievance.escalation_level >= 2)).scalars().all()
        items = [dict(i, link="/analytics") for i in _event_items(db, rows, user, {"escalated"})]
    elif role in {"auditor", "admin"}:
        q = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id).order_by(AuditLog.id.desc()).limit(15)
        if role == "admin":
            q = q.where(AuditLog.action.like("admin.%") | AuditLog.action.like("monitoring.%") | AuditLog.action.like("user.%"))
        for a in db.execute(q).scalars():
            items.append({"id": f"au{a.id}", "at": iso(a.created_at), "tone": "info", "link": "/audit" if role == "auditor" else "/admin",
                          "title": a.action.replace(".", " - ").replace("_", " "), "body": f"{a.entity_type} {a.entity_id}"})
        if role == "admin":
            for s in db.execute(select(MonitoredService).where(MonitoredService.tenant_id == user.tenant_id,
                                                               MonitoredService.check_mode != "planned")).scalars():
                sm = monitoring.service_summary(db, s, 1)
                if sm["last_status"] == "down":
                    items.insert(0, {"id": f"sv{s.id}", "at": sm["last_checked_at"], "tone": "bad", "link": "/monitoring",
                                     "title": f"Service down: {s.name}", "body": "Latest health check failed."})
    elif role == "content":
        for d in db.execute(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == user.tenant_id,
                                                            KnowledgeDocument.verified.is_(False))
                            .order_by(KnowledgeDocument.created_at.desc()).limit(10)).scalars():
            items.append({"id": f"kb{d.id}", "at": iso(d.created_at), "tone": "warn", "link": "/knowledge",
                          "title": f"Verification pending: {d.title}", "body": f"Version {d.version}, {d.language}"})
    items.sort(key=lambda i: i["at"] or "", reverse=True)
    return {"items": items[:20], "generated_at": iso(utcnow())}
