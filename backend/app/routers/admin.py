"""Tenant administration: users, departments, categories, SLA, escalation, languages, integrations.
Admins configure the system but have no access to citizen grievance content."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import (Category, DataRequest, Department, EscalationRule, IntegrationConfig, Jurisdiction, Language,
                      SlaPolicy, Tenant, User, Vendor)
from ..security import ROLES, hash_password, require
from ..services import audit

router = APIRouter(prefix="/api/admin", tags=["admin"])
cfg = require("config:write")


@router.get("/overview")
def overview(user: User = Depends(cfg), db: Session = Depends(get_db)):
    t = db.get(Tenant, user.tenant_id)
    tid = t.id

    def all_(model, *order):
        return db.execute(select(model).where(model.tenant_id == tid).order_by(*order)).scalars().all()
    return {
        "tenant": {"id": t.id, "code": t.code, "name": t.name, "state": t.state, "default_language": t.default_language,
                   "languages": t.languages, "emergency_contacts": t.emergency_contacts, "branding": t.branding},
        "departments": [{"id": d.id, "code": d.code, "names": d.names, "active": d.active, "name_verified": d.name_verified,
                         "contact": d.contact} for d in all_(Department, Department.code)],
        "categories": [{"id": c.id, "code": c.code, "names": c.names, "department_id": c.department_id,
                        "default_priority": c.default_priority, "active": c.active,
                        "requires_photo_verification": c.requires_photo_verification} for c in all_(Category, Category.code)],
        "sla_policies": [{"id": s.id, "priority": s.priority, "first_response_hours": s.first_response_hours,
                          "resolve_hours": s.resolve_hours} for s in all_(SlaPolicy, SlaPolicy.resolve_hours)],
        "escalation_rules": [{"id": e.id, "level": e.level, "role": e.role, "sla_fraction": e.sla_fraction,
                              "description": e.description} for e in all_(EscalationRule, EscalationRule.level)],
        "jurisdictions": [{"id": j.id, "code": j.code, "name": j.name, "kind": j.kind, "demo_boundary": j.is_demo_boundary}
                          for j in all_(Jurisdiction, Jurisdiction.kind, Jurisdiction.name)],
        "users": [{"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role, "active": u.active,
                   "department_id": u.department_id, "jurisdiction_id": u.jurisdiction_id,
                   "last_login_at": iso(u.last_login_at), "is_demo": u.is_demo}
                  for u in all_(User, User.role, User.username) if u.role != "citizen"],
        "citizen_accounts": sum(1 for u in all_(User, User.username) if u.role == "citizen"),
        "roles": [{"code": k, "name": v[0], "description": v[1]} for k, v in ROLES.items()],
        "vendors": [{"id": v.id, "name": v.name, "is_sample": v.is_sample} for v in all_(Vendor, Vendor.name)],
        "data_requests": [{"id": r.id, "kind": r.kind, "status": r.status, "created_at": iso(r.created_at)}
                          for r in all_(DataRequest, DataRequest.created_at)],
        "languages_registered": db.query(Language).count(),
    }


class UserIn(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,60}$")
    full_name: str = Field(min_length=2, max_length=120)
    role: str
    password: str = Field(min_length=10, max_length=200)
    department_id: str | None = None
    jurisdiction_id: str | None = None


@router.post("/users", status_code=201)
def create_user(body: UserIn, user: User = Depends(require("users:manage")), db: Session = Depends(get_db)):
    if body.role not in ROLES or body.role == "citizen":
        raise HTTPException(422, detail={"code": "invalid_role", "message": "Choose a staff role."})
    if body.role in {"officer"} and not body.department_id:
        raise HTTPException(422, detail={"code": "department_required", "message": "Officers need a department."})
    for ref, model in ((body.department_id, Department), (body.jurisdiction_id, Jurisdiction)):
        if ref:
            obj = db.get(model, ref)
            if not obj or obj.tenant_id != user.tenant_id:
                raise HTTPException(422, detail={"code": "invalid_reference", "message": "Unknown department/jurisdiction."})
    if db.execute(select(User).where(User.username == body.username)).scalar_one_or_none():
        raise HTTPException(409, detail={"code": "exists", "message": "Username already exists."})
    u = User(tenant_id=user.tenant_id, username=body.username, full_name=body.full_name, role=body.role,
             password_hash=hash_password(body.password), department_id=body.department_id,
             jurisdiction_id=body.jurisdiction_id, is_demo=False)
    db.add(u)
    db.flush()
    audit.record(db, actor=user, action="user.create", entity_type="user", entity_id=u.username, after={"role": u.role})
    db.commit()
    return {"id": u.id, "username": u.username, "role": u.role}


class ActiveIn(BaseModel):
    active: bool
    reason: str = Field(min_length=3, max_length=300)


@router.patch("/users/{uid}")
def set_active(uid: str, body: ActiveIn, user: User = Depends(require("users:manage")), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u or u.tenant_id != user.tenant_id or u.id == user.id:
        raise HTTPException(404, detail={"code": "not_found", "message": "User not found (or is yourself)."})
    u.active = body.active
    audit.record(db, actor=user, action="user.set_active", entity_type="user", entity_id=u.username,
                 after={"active": u.active}, reason=body.reason)
    db.commit()
    return {"id": u.id, "active": u.active}


class SlaIn(BaseModel):
    first_response_hours: float = Field(gt=0, le=720)
    resolve_hours: float = Field(gt=0, le=4320)


@router.put("/sla/{sid}")
def update_sla(sid: str, body: SlaIn, user: User = Depends(cfg), db: Session = Depends(get_db)):
    s = db.get(SlaPolicy, sid)
    if not s or s.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Policy not found."})
    if body.first_response_hours > body.resolve_hours:
        raise HTTPException(422, detail={"code": "invalid", "message": "First response must be <= resolution time."})
    before = {"first": s.first_response_hours, "resolve": s.resolve_hours}
    s.first_response_hours, s.resolve_hours = body.first_response_hours, body.resolve_hours
    audit.record(db, actor=user, action="config.sla", entity_type="sla_policy", entity_id=s.priority, before=before,
                 after={"first": s.first_response_hours, "resolve": s.resolve_hours},
                 reason="Applies to tickets created after this change")
    db.commit()
    return {"id": s.id, "priority": s.priority, "first_response_hours": s.first_response_hours, "resolve_hours": s.resolve_hours}


class EscIn(BaseModel):
    sla_fraction: float = Field(gt=0, le=10)
    role: str = Field(pattern="^(nodal|hod)$")


@router.put("/escalation/{eid}")
def update_escalation(eid: str, body: EscIn, user: User = Depends(cfg), db: Session = Depends(get_db)):
    e = db.get(EscalationRule, eid)
    if not e or e.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Rule not found."})
    before = {"fraction": e.sla_fraction, "role": e.role}
    e.sla_fraction, e.role = body.sla_fraction, body.role
    e.description = f"Escalate to {body.role} when {body.sla_fraction:g} x SLA has elapsed"
    audit.record(db, actor=user, action="config.escalation", entity_type="escalation_rule", entity_id=str(e.level),
                 before=before, after={"fraction": e.sla_fraction, "role": e.role})
    db.commit()
    return {"id": e.id, "level": e.level, "sla_fraction": e.sla_fraction, "role": e.role}


class CategoryIn(BaseModel):
    department_id: str | None = None
    default_priority: str | None = Field(None, pattern="^(Low|Medium|High|Emergency)$")
    active: bool | None = None
    requires_photo_verification: bool | None = None


@router.patch("/categories/{cid}")
def update_category(cid: str, body: CategoryIn, user: User = Depends(cfg), db: Session = Depends(get_db)):
    c = db.get(Category, cid)
    if not c or c.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Category not found."})
    changes = body.model_dump(exclude_none=True)
    if "department_id" in changes:
        d = db.get(Department, changes["department_id"])
        if not d or d.tenant_id != user.tenant_id:
            raise HTTPException(422, detail={"code": "invalid_department", "message": "Unknown department."})
    before = {k: getattr(c, k) for k in changes}
    for k, v in changes.items():
        setattr(c, k, v)
    audit.record(db, actor=user, action="config.category", entity_type="category", entity_id=c.code, before=before, after=changes)
    db.commit()
    return {"id": c.id, **changes}


class IntegrationIn(BaseModel):
    state: str = Field(pattern="^(connected_tested|configured_unverified|simulated|planned)$")
    notes: str = Field(min_length=5, max_length=1000)


@router.patch("/integrations/{code}")
def update_integration(code: str, body: IntegrationIn, user: User = Depends(require("integrations:manage")),
                       db: Session = Depends(get_db)):
    r = db.execute(select(IntegrationConfig).where(IntegrationConfig.code == code,
                                                   (IntegrationConfig.tenant_id == user.tenant_id) |
                                                   (IntegrationConfig.tenant_id.is_(None)))).scalars().first()
    if not r:
        raise HTTPException(404, detail={"code": "not_found", "message": "Integration not found."})
    if body.state == "connected_tested" and "test" not in body.notes.lower():
        raise HTTPException(422, detail={"code": "evidence_required",
                                         "message": "Describe the test evidence (e.g. 'tested on <date> against <endpoint>')."})
    before = {"state": r.state}
    r.state, r.notes = body.state, body.notes
    r.last_verified_at = utcnow() if body.state == "connected_tested" else r.last_verified_at
    audit.record(db, actor=user, action="integration.state", entity_type="integration", entity_id=code, before=before,
                 after={"state": r.state}, reason=body.notes)
    db.commit()
    return {"code": r.code, "state": r.state}
