"""Live maps: complaint locations for staff, live field-team positions, and citizen ticket tracking.
Positions are only ever shared by the field user's own browser (opt-in), expire after a TTL, and are
never shown to citizens - citizens only see an approximate distance of the assigned officer."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, iso, utcnow
from ..deps import resolve_tenant
from ..models import (Category, Department, FieldLocation, Grievance, Jurisdiction, Tenant, User, WorkOrder)
from ..security import get_current_user
from ..services import audit, workflow
from ..services.geo import haversine_m
from ..services.scope import get_visible_grievance, grievance_scope

router = APIRouter(prefix="/api", tags=["maps & live tracking"])
MAP_ROLES = {"officer", "nodal", "hod", "auditor", "vendor", "agent"}
SHARE_ROLES = {"officer", "nodal", "vendor"}
PRI_RANK = {"Emergency": 3, "High": 2, "Medium": 1, "Low": 0}


def _center(db: Session, tenant: Tenant) -> dict:
    pts = [p for j in db.execute(select(Jurisdiction).where(Jurisdiction.tenant_id == tenant.id,
                                                            Jurisdiction.polygon.is_not(None))).scalars() for p in j.polygon]
    if not pts:
        return {"lat": 20.59, "lng": 78.96, "zoom": 5}
    return {"lat": sum(p[0] for p in pts) / len(pts), "lng": sum(p[1] for p in pts) / len(pts), "zoom": 12}


@router.get("/map/config")
def map_config(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    s = get_settings()
    wards = db.execute(select(Jurisdiction).where(Jurisdiction.tenant_id == tenant.id, Jurisdiction.kind == "ward")).scalars()
    return {"tile_url": s.map_tile_url, "tile_url_dark": s.map_tile_url_dark, "fallback_tile_url": s.map_fallback_tile_url, "attribution": s.map_attribution, "center": _center(db, tenant),
            "field_ttl_minutes": s.field_location_ttl_minutes,
            "wards": [{"id": w.id, "name": w.name, "polygon": w.polygon, "demo_boundary": w.is_demo_boundary}
                      for w in wards if w.polygon]}


def _marker(db: Session, g: Grievance, user: User, cats: dict, depts: dict) -> dict:
    pii_ok = user.role in {"officer", "nodal", "agent", "auditor"}
    cat = cats.get(g.category_id)
    return {"id": g.public_id, "lat": g.lat, "lng": g.lng, "status": g.status, "priority": g.priority,
            "emergency": g.emergency, "category": cat.names.get(user.language) or cat.names.get("en") if cat else "Unclassified",
            "category_code": cat.code if cat else None,
            "department": depts.get(g.department_id).names.get("en") if g.department_id in depts else None,
            "location": g.location_text if pii_ok else "", "created_at": iso(g.created_at), "updated_at": iso(g.updated_at),
            "sla": workflow.sla_state(g)["state"], "escalation_level": g.escalation_level,
            "master_incident": bool(g.master_incident_id), "assigned": bool(g.assigned_officer_id)}


@router.get("/map/live")
def live_map(status: str = Query("open", pattern="^(open|all|closed)$"), category: str | None = None,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Complaint markers in the caller's scope + live field-team positions. Poll every few seconds."""
    if user.role not in MAP_ROLES:
        raise HTTPException(403, detail={"code": "forbidden", "message": "The live map is for staff accounts."})
    if user.role in {"hod"}:
        q = select(Grievance).where(Grievance.tenant_id == user.tenant_id)
    elif user.role == "vendor":
        ids = select(WorkOrder.grievance_id).where(WorkOrder.vendor_id == user.vendor_id)
        q = select(Grievance).where(Grievance.tenant_id == user.tenant_id, Grievance.id.in_(ids))
    else:
        q = grievance_scope(db, user)
    q = q.where(Grievance.lat.is_not(None), Grievance.lng.is_not(None))
    if status == "open":
        q = q.where(Grievance.status.in_(workflow.OPEN_STATUSES))
    elif status == "closed":
        q = q.where(Grievance.status.in_(["resolved", "closed", "rejected"]))
    rows = db.execute(q).scalars().all()
    cats = {c.id: c for c in db.execute(select(Category).where(Category.tenant_id == user.tenant_id)).scalars()}
    depts = {d.id: d for d in db.execute(select(Department).where(Department.tenant_id == user.tenant_id)).scalars()}
    if category:
        rows = [g for g in rows if cats.get(g.category_id) and cats[g.category_id].code == category]
    markers = sorted((_marker(db, g, user, cats, depts) for g in rows),
                     key=lambda m: (PRI_RANK.get(m["priority"], -1), m["created_at"]), reverse=True)
    unlocated = db.execute(grievance_scope(db, user).where(Grievance.lat.is_(None), Grievance.status.in_(workflow.OPEN_STATUSES))).scalars().all() \
        if user.role not in {"hod", "vendor"} else []
    return {"generated_at": iso(utcnow()), "markers": markers, "team": _team(db, user), "unlocated_open": len(unlocated),
            "note": "Markers come from GPS pins citizens/agents attached to complaints. Field positions are shared live "
                    "by staff browsers and disappear after the TTL."}


def _team(db: Session, user: User) -> list[dict]:
    ttl = get_settings().field_location_ttl_minutes
    since = utcnow() - timedelta(minutes=ttl)
    rows = db.execute(select(FieldLocation, User).join(User, FieldLocation.user_id == User.id)
                      .where(FieldLocation.tenant_id == user.tenant_id, FieldLocation.updated_at >= since)).all()
    out = []
    for loc, u in rows:
        if user.role == "officer" and not (u.department_id == user.department_id or u.role in {"nodal", "vendor"} or u.id == user.id):
            continue
        if user.role == "vendor" and u.id != user.id:
            continue
        dept = db.get(Department, u.department_id) if u.department_id else None
        out.append({"user_id": u.id, "name": u.full_name, "role": u.role, "department": dept.names.get("en") if dept else None,
                    "lat": loc.lat, "lng": loc.lng, "accuracy_m": loc.accuracy_m, "note": loc.status_note,
                    "updated_at": iso(loc.updated_at), "me": u.id == user.id,
                    "age_seconds": int((utcnow() - loc.updated_at).total_seconds())})
    return out


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(None, ge=0, le=100000)
    heading: float | None = None
    status_note: str = Field("", max_length=120)


@router.put("/field/location")
def share_location(body: LocationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in SHARE_ROLES:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Only field staff can share a live location."})
    loc = db.get(FieldLocation, user.id)
    first = loc is None
    if first:
        loc = FieldLocation(user_id=user.id, tenant_id=user.tenant_id, lat=body.lat, lng=body.lng)
        db.add(loc)
    loc.lat, loc.lng, loc.accuracy_m, loc.heading = body.lat, body.lng, body.accuracy_m, body.heading
    loc.status_note, loc.updated_at = body.status_note, utcnow()
    if first:
        audit.record(db, actor=user, action="field.location_sharing_started", entity_type="user", entity_id=user.id)
    db.commit()
    return {"ok": True, "updated_at": iso(loc.updated_at), "ttl_minutes": get_settings().field_location_ttl_minutes}


@router.delete("/field/location")
def stop_sharing(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    loc = db.get(FieldLocation, user.id)
    if loc:
        db.delete(loc)
        audit.record(db, actor=user, action="field.location_sharing_stopped", entity_type="user", entity_id=user.id)
        db.commit()
    return {"ok": True}


@router.get("/map/mine")
def my_map(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Citizen view: own complaints with pins, plus approximate distance of the assigned officer when shared."""
    if user.role != "citizen":
        raise HTTPException(403, detail={"code": "forbidden", "message": "Citizen accounts only."})
    rows = db.execute(select(Grievance).where(Grievance.citizen_id == user.id, Grievance.lat.is_not(None))).scalars().all()
    cats = {c.id: c for c in db.execute(select(Category).where(Category.tenant_id == user.tenant_id)).scalars()}
    return {"markers": [_marker(db, g, user, cats, {}) | {"officer_distance_km": _officer_distance(db, g)} for g in rows]}


def _officer_distance(db: Session, g: Grievance) -> float | None:
    if not g.assigned_officer_id or g.status not in {"accepted", "in_progress"} or g.lat is None:
        return None
    loc = db.get(FieldLocation, g.assigned_officer_id)
    if not loc or loc.updated_at < utcnow() - timedelta(minutes=get_settings().field_location_ttl_minutes):
        return None
    return round(haversine_m(g.lat, g.lng, loc.lat, loc.lng) / 1000, 1)


@router.get("/grievances/{ref}/tracking")
def ticket_tracking(ref: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Location + live progress for one ticket (citizen owner or staff in scope)."""
    g = get_visible_grievance(db, user, ref)
    return {"public_id": g.public_id, "lat": g.lat, "lng": g.lng, "status": g.status,
            "officer_distance_km": _officer_distance(db, g),
            "officer_sharing": _officer_distance(db, g) is not None, "updated_at": iso(g.updated_at)}
