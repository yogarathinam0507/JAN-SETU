from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import Category, DuplicateLink, Grievance, MasterIncident, TriageRecord, User
from ..security import require
from ..services import audit, workflow
from ..services.masking import redact_triage
from ..services.scope import get_visible_grievance, grievance_scope

router = APIRouter(prefix="/api/nodal", tags=["nodal"])
nodal_user = require("grievance:triage")


@router.get("/triage-queue")
def triage_queue(user: User = Depends(nodal_user), db: Session = Depends(get_db)):
    rows = db.execute(grievance_scope(db, user).where(Grievance.status == "human_review")
                      .order_by(Grievance.emergency.desc(), Grievance.created_at)).scalars().all()
    out = []
    for g in rows:
        d = workflow.serialize(db, g, user, detail=True)
        rec = db.get(TriageRecord, g.triage_id) if g.triage_id else None
        d["triage"] = redact_triage(rec.output) if rec else None
        out.append(d)
    return out


class RouteIn(BaseModel):
    category_id: str
    priority: str | None = Field(None, pattern="^(Low|Medium|High|Emergency)$")
    note: str = Field(min_length=5, max_length=500)


@router.post("/triage-queue/{ref}/route")
def route(ref: str, body: RouteIn, user: User = Depends(nodal_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    if g.status != "human_review":
        raise HTTPException(409, detail={"code": "not_in_triage", "message": "Ticket is not in the triage queue."})
    cat = db.get(Category, body.category_id)
    if not cat or cat.tenant_id != user.tenant_id:
        raise HTTPException(422, detail={"code": "invalid_category", "message": "Unknown category."})
    before = workflow.snapshot(g)
    g.category_id, g.department_id = cat.id, cat.department_id
    g.priority = body.priority or ("Emergency" if g.emergency else cat.default_priority)
    g.status, g.human_review_required = "submitted", False
    workflow.apply_sla(db, g)
    if g.triage_id:
        rec = db.get(TriageRecord, g.triage_id)
        if rec:
            rec.human_override = {"by": user.id, "role": user.role, "category": cat.code, "priority": g.priority,
                                  "note": body.note}
    workflow.add_event(db, g, user, "human_triage", f"Routed by nodal officer to {cat.names['en']} ({g.priority}).",
                       from_status="human_review", to_status="submitted")
    workflow.assign_department_officer(db, g, user, at=utcnow())
    audit.record(db, actor=user, action="grievance.human_triage", entity_type="grievance", entity_id=g.public_id,
                 before=before, after=workflow.snapshot(g), reason=body.note)
    dup = workflow.find_duplicate(db, g)
    if dup:
        workflow.link_duplicate(db, g, dup[0], dup[1], user)
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


@router.get("/master-incidents")
def masters(user: User = Depends(require("incident:manage")), db: Session = Depends(get_db)):
    rows = db.execute(select(MasterIncident).where(MasterIncident.tenant_id == user.tenant_id)
                      .order_by(MasterIncident.created_at.desc())).scalars().all()
    out = []
    for m in rows:
        linked = db.execute(select(Grievance).where(Grievance.master_incident_id == m.id)).scalars().all()
        if not linked:
            continue
        cat = db.get(Category, m.category_id)
        out.append({"id": m.id, "public_id": m.public_id, "title": m.title, "status": m.status,
                    "category": cat.names.get("en") if cat else None, "linked_reports": len(linked),
                    "open_reports": sum(1 for g in linked if g.status in workflow.OPEN_STATUSES),
                    "channels": sorted({g.channel for g in linked}), "created_at": iso(m.created_at),
                    "tickets": [{"public_id": g.public_id, "status": g.status} for g in linked]})
    return {"items": out, "stats": workflow.duplicate_stats(db, user.tenant_id)}


class UnlinkIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@router.post("/grievances/{ref}/unlink")
def unlink(ref: str, body: UnlinkIn, user: User = Depends(require("incident:manage")), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    if not g.master_incident_id:
        raise HTTPException(409, detail={"code": "not_linked", "message": "Ticket is not linked to a master incident."})
    before = workflow.snapshot(g) | {"master": g.master_incident_id}
    for link in db.execute(select(DuplicateLink).where(DuplicateLink.grievance_id == g.id,
                                                       DuplicateLink.active.is_(True))).scalars():
        link.active = False
    g.master_incident_id = None
    workflow.add_event(db, g, user, "unlinked_master", f"Removed from master incident: {body.reason}")
    audit.record(db, actor=user, action="duplicate.unlink", entity_type="grievance", entity_id=g.public_id,
                 before=before, after={"master": None}, reason=body.reason)
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


@router.get("/escalations")
def escalations(user: User = Depends(nodal_user), db: Session = Depends(get_db)):
    rows = db.execute(grievance_scope(db, user).where(Grievance.escalation_level > 0,
                                                      Grievance.status.in_(workflow.OPEN_STATUSES))
                      .order_by(Grievance.escalation_level.desc(), Grievance.sla_due_at)).scalars().all()
    return [workflow.serialize(db, g, user) for g in rows]


@router.get("/cross-department")
def cross_department(user: User = Depends(nodal_user), db: Session = Depends(get_db)):
    rows = db.execute(grievance_scope(db, user)).scalars().all()
    return [workflow.serialize(db, g, user) for g in rows if g.joint_department_ids]


@router.post("/run-escalations")
def run_escalations_now(user: User = Depends(nodal_user), db: Session = Depends(get_db)):
    n = workflow.run_escalations(db, user.tenant_id)
    db.commit()
    return {"escalated": n}
