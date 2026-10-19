from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db, iso
from ..deps import page_params, resolve_tenant
from ..models import Attachment, Category, Department, Grievance, Tenant, TicketEvent, TriageRecord, User
from ..security import get_current_user, get_optional_user, has_perm, require_any
from ..services import audit, workflow
from ..services.masking import redact_triage
from ..services.scope import can_view, get_visible_grievance, grievance_scope
from ..services.triage import TriageError, run_triage
from ..services.uploads import path_for, read_validated, safe_filename, store

router = APIRouter(prefix="/api", tags=["grievances"])


class TriageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str | None = Field(None, max_length=10)
    input_mode: str = Field("text", pattern="^(text|voice)$")
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    location_text: str = Field("", max_length=300)


@router.post("/triage/preview")
def triage_preview(body: TriageIn, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    """Runs the full triage pipeline and returns a structured, explainable result. Creates no ticket."""
    try:
        result = run_triage(db, tenant, body.text, language_hint=body.language, lat=body.lat, lng=body.lng,
                            location_text=body.location_text, input_mode=body.input_mode)
    except TriageError as exc:
        db.rollback()
        raise HTTPException(502 if "provider" in str(exc) else 422, detail={
            "code": "triage_failed", "message": str(exc), "retry": True,
            "fallback": "You can retry, or submit the complaint for human triage (no automatic routing)."})
    db.commit()
    return result.model_dump()


class GrievanceIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    triage_id: str | None = None
    language: str | None = None
    input_mode: str = Field("text", pattern="^(text|voice)$")
    transcript_confirmed: bool = False
    channel: str = Field("web", pattern="^(web|assistant|voice|web_chat|email|whatsapp)$")
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    location_text: str = Field("", max_length=300)
    contact_name: str = Field("", max_length=120)
    contact_phone: str = Field("", pattern=r"^$|^[6-9]\d{9}$")
    consent: bool = False
    request_human_review: bool = False
    human_review_note: str = Field("", max_length=300)


@router.post("/grievances", status_code=201)
def create(body: GrievanceIn, tenant: Tenant = Depends(resolve_tenant), user: User | None = Depends(get_optional_user),
           db: Session = Depends(get_db)):
    if user is not None and not has_perm(user, "grievance:create"):
        raise HTTPException(403, detail={"code": "forbidden", "message": "Your role cannot file grievances."})
    if user is None and not body.contact_phone:
        raise HTTPException(422, detail={"code": "phone_required",
                                         "message": "Guests must give a mobile number so the ticket can be tracked."})
    triage = None
    if body.triage_id:
        rec = db.get(TriageRecord, body.triage_id)
        if rec and rec.tenant_id == tenant.id and rec.input_text == body.text.strip():
            triage = dict(rec.output)
    if triage is None:  # text changed after preview (or no preview): re-run the pipeline
        try:
            triage = run_triage(db, tenant, body.text, language_hint=body.language, lat=body.lat, lng=body.lng,
                                location_text=body.location_text, input_mode=body.input_mode).model_dump()
        except TriageError as exc:
            if not body.request_human_review:
                raise HTTPException(502, detail={"code": "triage_failed", "message": str(exc), "retry": True,
                                                 "fallback": "Submit again with 'send to human triage' selected."})
            triage = {"language": body.language or tenant.default_language, "summary": body.text[:160],
                      "human_review_required": True, "human_review_reason": f"AI unavailable: {exc}",
                      "priority": None, "rules_applied": []}
    if body.request_human_review:
        triage["human_review_required"] = True
        triage["human_review_reason"] = "Citizen asked for human review: " + (body.human_review_note or "category disputed")
    citizen = user if user is not None and user.role == "citizen" else None
    g = workflow.create_grievance(
        db, tenant_id=tenant.id, triage=triage, text=body.text.strip(), actor=user, citizen=citizen,
        channel=body.channel if (user is None or user.role == "citizen") else ("voice" if body.channel == "web" else body.channel),
        input_mode=body.input_mode, transcript_confirmed=body.transcript_confirmed,
        contact_name=body.contact_name or (user.full_name if citizen else ""),
        contact_phone=body.contact_phone or ((user.phone or "") if citizen else ""), lat=body.lat, lng=body.lng,
        location_text=body.location_text, consent=body.consent)
    db.commit()
    return workflow.serialize(db, g, user or None, detail=True) | {"tracking_hint":
                                                                   "Keep this ticket ID. Track it any time on the Track page."}


@router.get("/grievances")
def list_grievances(user: User = Depends(require_any("grievance:read_own", "grievance:read_scoped")),
                    db: Session = Depends(get_db), status: str | None = None, department_id: str | None = None,
                    category_id: str | None = None, priority: str | None = None, q: str | None = None,
                    date_from: datetime | None = None, date_to: datetime | None = None,
                    sla: str | None = Query(None, pattern="^(breached|at_risk|on_track)$"),
                    sort: str = Query("-created_at", pattern="^-?(created_at|sla_due_at|priority)$"),
                    paging: tuple[int, int] = Depends(page_params)):
    stmt = grievance_scope(db, user)
    if status:
        statuses = status.split(",")
        stmt = stmt.where(Grievance.status.in_(statuses))
    if department_id:
        stmt = stmt.where(Grievance.department_id == department_id)
    if category_id:
        stmt = stmt.where(Grievance.category_id == category_id)
    if priority:
        stmt = stmt.where(Grievance.priority == priority)
    if date_from:
        stmt = stmt.where(Grievance.created_at >= date_from.replace(tzinfo=None))
    if date_to:
        stmt = stmt.where(Grievance.created_at <= date_to.replace(tzinfo=None))
    if q:
        like = f"%{q.strip()[:80]}%"
        stmt = stmt.where(or_(Grievance.public_id.ilike(like), Grievance.summary.ilike(like),
                              Grievance.location_text.ilike(like)))
    rows = db.execute(stmt).scalars().all()
    # Joint-action cases where this officer's department is a participant
    if user.role == "officer":
        seen = {g.id for g in rows}
        extra = db.execute(select(Grievance).where(Grievance.tenant_id == user.tenant_id,
                                                   Grievance.joint_department_ids.is_not(None))).scalars().all()
        rows += [g for g in extra if g.id not in seen and user.department_id in (g.joint_department_ids or [])
                 and (not status or g.status in status.split(","))]
    if sla:
        rows = [g for g in rows if workflow.sla_state(g)["state"] == sla]
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    pri_rank = {"Emergency": 3, "High": 2, "Medium": 1, "Low": 0, None: -1}
    if key == "priority":
        rows.sort(key=lambda g: pri_rank.get(g.priority, -1), reverse=desc)
    else:
        rows.sort(key=lambda g: getattr(g, key) or datetime.max, reverse=desc)
    page, size = paging
    total = len(rows)
    items = [workflow.serialize(db, g, user) for g in rows[(page - 1) * size: page * size]]
    return {"total": total, "page": page, "page_size": size, "items": items}


@router.get("/grievances/{ref}")
def get_grievance(ref: str, user: User = Depends(require_any("grievance:read_own", "grievance:read_scoped")),
                  db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    data = workflow.serialize(db, g, user, detail=True)
    if user.role != "citizen" and g.triage_id:
        rec = db.get(TriageRecord, g.triage_id)
        data["triage"] = redact_triage(rec.output) if rec else None
        data["triage_override"] = rec.human_override if rec else None
    if user.role in {"officer", "nodal"}:
        data["allowed_actions"] = [a for a, (frm, _, perm) in workflow.TRANSITIONS.items()
                                   if g.status in frm and perm == "grievance:act"]
    elif user.role == "citizen":
        data["allowed_actions"] = [a for a, (frm, _, perm) in workflow.TRANSITIONS.items()
                                   if g.status in frm and perm == "grievance:feedback"]
    else:
        data["allowed_actions"] = []
    return data


@router.get("/track/{public_id}")
def track(public_id: str, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    """Public tracking by ticket ID: status and public updates only - no personal data or complaint text."""
    g = db.execute(select(Grievance).where(Grievance.public_id == public_id.strip().upper(),
                                           Grievance.tenant_id == tenant.id)).scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail={"code": "not_found", "message": "No ticket with that ID in this tenant."})
    dept = db.get(Department, g.department_id) if g.department_id else None
    events = db.execute(select(TicketEvent).where(TicketEvent.grievance_id == g.id, TicketEvent.public.is_(True))
                        .order_by(TicketEvent.created_at)).scalars().all()
    return {"public_id": g.public_id, "status": g.status, "status_label": workflow.STATUS_LABELS.get(g.status),
            "department": dept.names.get("en") if dept else None, "priority": g.priority,
            "created_at": iso(g.created_at), "sla_due_at": iso(g.sla_due_at), "sla": workflow.sla_state(g),
            "escalation_level": g.escalation_level,
            "updates": [{"type": e.event_type, "to": e.to_status, "at": iso(e.created_at),
                         "note": e.note if e.event_type in {"created", "linked_master", "resolve", "escalated", "transfer",
                                                            "public_update"} else ""} for e in events],
            "note": "Sign in with the mobile number used on the complaint to see full details."}


class ActionIn(BaseModel):
    action: str = Field(max_length=40)
    note: str = Field("", max_length=2000)
    rating: int | None = Field(None, ge=1, le=5)


@router.post("/grievances/{ref}/actions")
def act(ref: str, body: ActionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    spec = workflow.TRANSITIONS.get(body.action)
    if not spec:
        raise HTTPException(400, detail={"code": "unknown_action", "message": f"Unknown action '{body.action}'."})
    if not has_perm(user, spec[2]):
        raise HTTPException(403, detail={"code": "forbidden", "message": "Your role cannot perform this action."})
    if spec[2] == "grievance:feedback" and g.citizen_id != user.id:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Only the complainant can do this."})
    if body.action == "resolve":
        cat = db.get(Category, g.category_id) if g.category_id else None
        cat_requires = bool(cat and cat.requires_photo_verification)
        has_after = db.scalar(select(func.count()).select_from(Attachment).where(
            Attachment.grievance_id == g.id, Attachment.kind == "after"))
        if cat_requires and not has_after:
            raise HTTPException(422, detail={"code": "after_photo_required",
                                             "message": "Upload an 'after' photo before resolving this category."})
    workflow.transition(db, g, body.action, user, body.note)
    if body.action == "confirm_closure" and body.rating:
        g.citizen_rating = body.rating
        g.citizen_feedback = body.note
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=1000)


@router.post("/grievances/{ref}/feedback")
def feedback(ref: str, body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    if g.citizen_id != user.id:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Only the complainant can rate this ticket."})
    if g.status not in {"resolved", "closed", "rejected"}:
        raise HTTPException(409, detail={"code": "too_early", "message": "Feedback opens once the ticket is resolved."})
    g.citizen_rating, g.citizen_feedback = body.rating, body.comment
    workflow.add_event(db, g, user, "feedback", f"Citizen rated {body.rating}/5", public=False)
    db.commit()
    return {"ok": True}


class RevealIn(BaseModel):
    reason: str = Field(min_length=10, max_length=300)


@router.post("/grievances/{ref}/reveal-contact")
def reveal_contact(ref: str, body: RevealIn, user: User = Depends(require_any("contact:reveal")),
                   db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    audit.record(db, actor=user, action="pii.reveal_contact", entity_type="grievance", entity_id=g.public_id,
                 reason=body.reason)
    workflow.add_event(db, g, user, "pii_revealed", f"Contact revealed to {user.role}: {body.reason}", public=False)
    db.commit()
    return {"contact_name": g.contact_name, "contact_phone": g.contact_phone, "audited": True}


@router.post("/grievances/{ref}/attachments", status_code=201)
async def upload_attachment(ref: str, kind: str = Form(..., pattern="^(evidence|before|after)$"),
                            file: UploadFile = File(...), user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    if user.role == "citizen" and kind == "after":
        raise HTTPException(403, detail={"code": "forbidden", "message": "Citizens upload evidence or 'before' photos."})
    if user.role not in {"citizen", "officer", "nodal", "agent"}:
        raise HTTPException(403, detail={"code": "forbidden", "message": "Your role cannot upload to tickets."})
    data, ctype = await read_validated(file, {"image/jpeg", "image/png", "application/pdf"})
    name, digest = store(data, ctype)
    att = Attachment(tenant_id=g.tenant_id, grievance_id=g.id, kind=kind, filename=safe_filename(file.filename),
                     content_type=ctype, size=len(data), storage_name=name, sha256=digest, uploaded_by=user.id)
    db.add(att)
    workflow.add_event(db, g, user, "attachment", f"{kind.title()} file added", data={"sha256": digest[:12]})
    audit.record(db, actor=user, action="attachment.upload", entity_type="grievance", entity_id=g.public_id,
                 after={"kind": kind, "sha256": digest})
    db.commit()
    return {"id": att.id, "kind": kind, "filename": att.filename, "size": att.size}


@router.get("/attachments/{att_id}")
def download_attachment(att_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    att = db.get(Attachment, att_id)
    if not att or att.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    if att.grievance_id:
        g = db.get(Grievance, att.grievance_id)
        if not can_view(db, user, g):
            raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    elif user.role not in {"officer", "nodal", "auditor", "vendor"}:
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    return FileResponse(path_for(att.storage_name), media_type=att.content_type, filename=att.filename,
                        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'})


@router.get("/grievances/{ref}/duplicates")
def duplicates(ref: str, user: User = Depends(require_any("grievance:read_scoped")), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    cand = workflow.find_duplicate(db, g)
    return {"rule": workflow.DUPLICATE_RULE, "candidate": (
        {"public_id": cand[0].public_id, **cand[1]} if cand and cand[0].id != g.id and cand[0].master_incident_id != g.master_incident_id
        else None), "master_incident": g.master_incident_id}
