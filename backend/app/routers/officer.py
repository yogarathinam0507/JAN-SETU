"""e-Office & officer workflow (PS3): queue summary, assignment, transfer, joint action, drafts, e-files,
documents and contractor work orders."""
import math
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, iso, utcnow
from ..models import (Attachment, Category, Department, DocumentTemplate, Draft, FileMovement, Grievance, OfficerFile,
                      Tenant, User, Vendor, WorkOrder)
from ..security import require, require_any
from ..services import audit, drafting, workflow
from ..services.kb import tokenize
from ..services.scope import get_visible_grievance, grievance_scope
from ..services.uploads import read_validated, safe_filename, store
from ..services.kb import extract_text

router = APIRouter(prefix="/api", tags=["officer / e-office"])
act_user = require("grievance:act")


@router.get("/officer/summary")
def summary(user: User = Depends(require_any("grievance:read_scoped")), db: Session = Depends(get_db)):
    rows = db.execute(grievance_scope(db, user)).scalars().all()
    open_rows = [g for g in rows if g.status in workflow.OPEN_STATUSES]
    sla = Counter(workflow.sla_state(g)["state"] for g in open_rows)
    by_officer = Counter((db.get(User, g.assigned_officer_id).full_name if g.assigned_officer_id else "Unassigned")
                         for g in open_rows)
    return {"scope": {"role": user.role, "department": user.department_id, "jurisdiction": user.jurisdiction_id},
            "total": len(rows), "open": len(open_rows), "by_status": dict(Counter(g.status for g in rows)),
            "overdue": sla.get("breached", 0), "at_risk": sla.get("at_risk", 0),
            "emergency_open": sum(1 for g in open_rows if g.emergency),
            "human_review": sum(1 for g in rows if g.status == "human_review"),
            "escalated_open": sum(1 for g in open_rows if g.escalation_level > 0),
            "workload": [{"officer": k, "open": v} for k, v in by_officer.most_common()],
            "data_note": "Computed live from persisted tickets in your scope."}


@router.get("/officer/colleagues")
def colleagues(user: User = Depends(act_user), db: Session = Depends(get_db)):
    q = select(User).where(User.tenant_id == user.tenant_id, User.role.in_(["officer", "nodal"]), User.active.is_(True))
    if user.role == "officer":
        q = q.where(User.department_id == user.department_id)
    return [{"id": u.id, "name": u.full_name, "role": u.role, "department_id": u.department_id}
            for u in db.execute(q.order_by(User.full_name)).scalars()]


class AssignIn(BaseModel):
    officer_id: str
    note: str = Field("", max_length=500)


@router.post("/grievances/{ref}/assign")
def assign(ref: str, body: AssignIn, user: User = Depends(act_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    target = db.get(User, body.officer_id)
    if not target or target.tenant_id != user.tenant_id or target.role != "officer" or target.department_id != g.department_id:
        raise HTTPException(422, detail={"code": "invalid_assignee", "message": "Assignee must be an officer of the ticket's department."})
    before = workflow.snapshot(g)
    action = "reassign" if g.assigned_officer_id else "assign"
    g.assigned_officer_id = target.id
    workflow.add_event(db, g, user, action, f"Assigned to {target.full_name}. {body.note}".strip(), public=False)
    audit.record(db, actor=user, action=f"grievance.{action}", entity_type="grievance", entity_id=g.public_id,
                 before=before, after=workflow.snapshot(g), reason=body.note)
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


class TransferIn(BaseModel):
    department_id: str
    reason: str = Field(min_length=5, max_length=500)


@router.post("/grievances/{ref}/transfer")
def transfer(ref: str, body: TransferIn, user: User = Depends(act_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    dept = db.get(Department, body.department_id)
    if not dept or dept.tenant_id != user.tenant_id:
        raise HTTPException(422, detail={"code": "invalid_department", "message": "Unknown department."})
    if dept.id == g.department_id:
        raise HTTPException(422, detail={"code": "same_department", "message": "Ticket is already with that department."})
    if g.status in {"closed", "rejected", "resolved"}:
        raise HTTPException(409, detail={"code": "invalid_transition", "message": "Closed tickets cannot be transferred."})
    before = workflow.snapshot(g)
    old = db.get(Department, g.department_id) if g.department_id else None
    g.department_id, g.assigned_officer_id, g.status = dept.id, None, "submitted"
    workflow.add_event(db, g, user, "transfer", f"Referred from {old.names['en'] if old else 'triage'} to "
                                                f"{dept.names['en']}: {body.reason}", from_status=before["status"],
                       to_status="submitted")
    workflow.assign_department_officer(db, g, user, at=utcnow())
    audit.record(db, actor=user, action="grievance.transfer", entity_type="grievance", entity_id=g.public_id,
                 before=before, after=workflow.snapshot(g), reason=body.reason)
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


class JointIn(BaseModel):
    department_id: str
    note: str = Field(min_length=5, max_length=500)


@router.post("/grievances/{ref}/joint")
def add_joint(ref: str, body: JointIn, user: User = Depends(act_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    dept = db.get(Department, body.department_id)
    if not dept or dept.tenant_id != user.tenant_id or dept.id == g.department_id:
        raise HTTPException(422, detail={"code": "invalid_department", "message": "Choose a different department."})
    before = workflow.snapshot(g)
    g.joint_department_ids = sorted(set(g.joint_department_ids or []) | {dept.id})
    workflow.add_event(db, g, user, "joint_action", f"Joint action requested with {dept.names['en']}: {body.note}")
    audit.record(db, actor=user, action="grievance.joint_action", entity_type="grievance", entity_id=g.public_id,
                 before=before, after=workflow.snapshot(g), reason=body.note)
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


class NoteIn(BaseModel):
    note: str = Field(min_length=5, max_length=1000)


@router.post("/grievances/{ref}/escalate")
def escalate(ref: str, body: NoteIn, user: User = Depends(act_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    if g.status not in workflow.OPEN_STATUSES:
        raise HTTPException(409, detail={"code": "invalid_transition", "message": "Only open tickets can be escalated."})
    before = workflow.snapshot(g)
    g.escalation_level += 1
    workflow.add_event(db, g, user, "escalated", f"Manually escalated to level {g.escalation_level}: {body.note}")
    audit.record(db, actor=user, action="grievance.escalate.manual", entity_type="grievance", entity_id=g.public_id,
                 before=before, after=workflow.snapshot(g), reason=body.note)
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


@router.post("/grievances/{ref}/public-update")
def public_update(ref: str, body: NoteIn, user: User = Depends(act_user), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    workflow.add_event(db, g, user, "public_update", body.note)
    workflow.notify_citizen(db, g, f"Update on {g.public_id}: {body.note[:120]}")
    audit.record(db, actor=user, action="grievance.public_update", entity_type="grievance", entity_id=g.public_id,
                 after={"note": body.note})
    db.commit()
    return workflow.serialize(db, g, user, detail=True)


# ------------------------------------------------------------------ drafts (never sent / signed)
@router.get("/templates")
def templates(user: User = Depends(require("draft:write")), db: Session = Depends(get_db)):
    dept = db.get(Department, user.department_id) if user.department_id else None
    q = select(DocumentTemplate).where(DocumentTemplate.tenant_id == user.tenant_id)
    if dept:
        q = q.where(or_(DocumentTemplate.department_code == "", DocumentTemplate.department_code == dept.code))
    return [{"id": t.id, "title": t.title, "doc_type": t.doc_type, "language": t.language, "department_code": t.department_code,
             "label": "Approved template" if t.approved else "SAMPLE template - not yet approved by the authority"}
            for t in db.execute(q.order_by(DocumentTemplate.doc_type, DocumentTemplate.language)).scalars()]


class DraftGenIn(BaseModel):
    template_id: str
    grievance_ref: str | None = None
    efile_id: str | None = None
    use_llm: bool = False


def _draft_out(d: Draft) -> dict:
    return {"id": d.id, "content": d.content, "status": d.status, "version": d.version, "language": d.language,
            "generator": d.generator, "updated_at": iso(d.updated_at), "grievance_id": d.grievance_id,
            "efile_id": d.officer_file_id,
            "notice": "Draft only. The platform never sends or digitally signs documents. Dispatch manually after approval."}


@router.post("/drafts/generate", status_code=201)
def generate_draft(body: DraftGenIn, user: User = Depends(require("draft:write")), db: Session = Depends(get_db)):
    t = db.get(DocumentTemplate, body.template_id)
    if not t or t.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Template not found."})
    tenant = db.get(Tenant, user.tenant_id)
    fields = {"date": utcnow().strftime("%d-%m-%Y"), "officer_name": user.full_name, "authority": tenant.name}
    g = None
    if body.grievance_ref:
        g = get_visible_grievance(db, user, body.grievance_ref)
        dept = db.get(Department, g.department_id) if g.department_id else None
        cat = db.get(Category, g.category_id) if g.category_id else None
        fields.update({"ticket_id": g.public_id, "citizen_name": g.contact_name or "Citizen",
                       "category": (cat.names.get(t.language) or cat.names.get("en")) if cat else "your complaint",
                       "department": (dept.names.get(t.language) or dept.names.get("en")) if dept else "",
                       "location": g.location_text or "-", "filed_on": g.created_at.strftime("%d-%m-%Y"),
                       "status": workflow.STATUS_LABELS.get(g.status, g.status),
                       "resolution": g.resolution_note or "[describe action taken]"})
    content, generator = drafting.generate_draft(t.body, fields, use_llm=body.use_llm and get_settings().ai_mode == "llm")
    if body.use_llm and get_settings().ai_mode != "llm":
        generator = "template (LLM not configured)"
    d = Draft(tenant_id=user.tenant_id, grievance_id=g.id if g else None, officer_file_id=body.efile_id,
              template_id=t.id, language=t.language, content=content, generator=generator, created_by=user.id)
    db.add(d)
    db.flush()
    audit.record(db, actor=user, action="draft.generate", entity_type="draft", entity_id=d.id,
                 after={"template": t.title, "generator": generator})
    db.commit()
    return _draft_out(d)


@router.get("/drafts")
def list_drafts(grievance_ref: str | None = None, user: User = Depends(require("draft:write")), db: Session = Depends(get_db)):
    q = select(Draft).where(Draft.tenant_id == user.tenant_id)
    if grievance_ref:
        g = get_visible_grievance(db, user, grievance_ref)
        q = q.where(Draft.grievance_id == g.id)
    else:
        q = q.where(Draft.created_by == user.id)
    return [_draft_out(d) for d in db.execute(q.order_by(Draft.updated_at.desc()).limit(50)).scalars()]


class DraftUpdateIn(BaseModel):
    content: str = Field(min_length=10, max_length=20000)
    status: str = Field("draft", pattern="^(draft|ready_for_manual_dispatch)$")


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: str, body: DraftUpdateIn, user: User = Depends(require("draft:write")), db: Session = Depends(get_db)):
    d = db.get(Draft, draft_id)
    if not d or d.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Draft not found."})
    before = {"version": d.version, "status": d.status}
    d.content, d.status, d.version, d.updated_at = body.content, body.status, d.version + 1, utcnow()
    audit.record(db, actor=user, action="draft.save", entity_type="draft", entity_id=d.id, before=before,
                 after={"version": d.version, "status": d.status})
    db.commit()
    return _draft_out(d)


# ------------------------------------------------------------------ e-files and routing
def _efile_out(db: Session, f: OfficerFile, detail: bool = False) -> dict:
    dept = db.get(Department, f.department_id)
    holder = db.get(User, f.current_holder_id) if f.current_holder_id else None
    g = db.get(Grievance, f.grievance_id) if f.grievance_id else None
    out = {"id": f.id, "public_id": f.public_id, "subject": f.subject, "status": f.status, "priority": f.priority,
           "department": dept.names.get("en") if dept else None, "department_id": f.department_id,
           "current_holder": holder.full_name if holder else "Department pool", "current_holder_id": f.current_holder_id,
           "grievance": g.public_id if g else None, "created_at": iso(f.created_at), "updated_at": iso(f.updated_at)}
    if detail:
        moves = db.execute(select(FileMovement).where(FileMovement.file_id == f.id).order_by(FileMovement.created_at)).scalars()
        out["movements"] = [{"action": m.action, "note": m.note, "at": iso(m.created_at),
                             "from": (db.get(User, m.from_user_id).full_name if m.from_user_id else None),
                             "to": (db.get(User, m.to_user_id).full_name if m.to_user_id else None),
                             "to_department": (db.get(Department, m.to_department_id).names.get("en") if m.to_department_id else None)}
                            for m in moves]
        docs = db.execute(select(Attachment).where(Attachment.officer_file_id == f.id)).scalars()
        out["documents"] = [{"id": a.id, "filename": a.filename, "extraction_status": a.extraction_status,
                             "summary": a.meta.get("summary", "")} for a in docs]
    return out


def _efile_visible(user: User, f: OfficerFile) -> bool:
    return f.tenant_id == user.tenant_id and (user.role == "nodal" or f.department_id == user.department_id
                                              or f.current_holder_id == user.id)


@router.get("/efiles")
def list_efiles(user: User = Depends(require("efile:work")), db: Session = Depends(get_db)):
    q = select(OfficerFile).where(OfficerFile.tenant_id == user.tenant_id)
    if user.role == "officer":
        q = q.where(or_(OfficerFile.department_id == user.department_id, OfficerFile.current_holder_id == user.id))
    return [_efile_out(db, f) for f in db.execute(q.order_by(OfficerFile.updated_at.desc())).scalars()]


class EfileIn(BaseModel):
    subject: str = Field(min_length=5, max_length=300)
    grievance_ref: str | None = None
    priority: str = Field("Medium", pattern="^(Low|Medium|High|Emergency)$")


@router.post("/efiles", status_code=201)
def create_efile(body: EfileIn, user: User = Depends(require("efile:work")), db: Session = Depends(get_db)):
    if not user.department_id:
        raise HTTPException(422, detail={"code": "no_department", "message": "Only department staff can open files."})
    g = get_visible_grievance(db, user, body.grievance_ref) if body.grievance_ref else None
    f = OfficerFile(tenant_id=user.tenant_id, subject=body.subject, department_id=user.department_id,
                    current_holder_id=user.id, grievance_id=g.id if g else None, priority=body.priority, created_by=user.id)
    db.add(f)
    db.flush()
    db.add(FileMovement(file_id=f.id, to_user_id=user.id, to_department_id=user.department_id, action="opened",
                        note="File opened"))
    audit.record(db, actor=user, action="efile.create", entity_type="efile", entity_id=f.public_id, after={"subject": f.subject})
    db.commit()
    return _efile_out(db, f, detail=True)


@router.get("/efiles/{file_id}")
def get_efile(file_id: str, user: User = Depends(require("efile:work")), db: Session = Depends(get_db)):
    f = db.get(OfficerFile, file_id)
    if not f or not _efile_visible(user, f):
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    return _efile_out(db, f, detail=True)


class MoveIn(BaseModel):
    action: str = Field(pattern="^(forward|return|send_to_department|close)$")
    to_user_id: str | None = None
    to_department_id: str | None = None
    note: str = Field(min_length=3, max_length=1000)


@router.post("/efiles/{file_id}/move")
def move_efile(file_id: str, body: MoveIn, user: User = Depends(require("efile:work")), db: Session = Depends(get_db)):
    f = db.get(OfficerFile, file_id)
    if not f or not _efile_visible(user, f):
        raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    if f.status == "closed":
        raise HTTPException(409, detail={"code": "closed", "message": "File is closed."})
    before = {"holder": f.current_holder_id, "department": f.department_id, "status": f.status}
    mv = FileMovement(file_id=f.id, from_user_id=user.id, from_department_id=f.department_id, action=body.action, note=body.note)
    if body.action in {"forward", "return"}:
        to = db.get(User, body.to_user_id or "")
        if not to or to.tenant_id != user.tenant_id or to.role not in {"officer", "nodal", "hod"}:
            raise HTTPException(422, detail={"code": "invalid_recipient", "message": "Choose a staff recipient."})
        f.current_holder_id, mv.to_user_id = to.id, to.id
        f.status = "returned" if body.action == "return" else "in_review"
    elif body.action == "send_to_department":
        dept = db.get(Department, body.to_department_id or "")
        if not dept or dept.tenant_id != user.tenant_id:
            raise HTTPException(422, detail={"code": "invalid_department", "message": "Unknown department."})
        f.department_id, f.current_holder_id, mv.to_department_id = dept.id, None, dept.id
        f.status = "in_review"
    else:
        f.status = "closed"
    f.updated_at = utcnow()
    db.add(mv)
    audit.record(db, actor=user, action=f"efile.{body.action}", entity_type="efile", entity_id=f.public_id, before=before,
                 after={"holder": f.current_holder_id, "department": f.department_id, "status": f.status}, reason=body.note)
    db.commit()
    return _efile_out(db, f, detail=True)


# ------------------------------------------------------------------ documents: upload, extraction, summary, search
@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), efile_id: str | None = Form(None),
                          user: User = Depends(require("document:work")), db: Session = Depends(get_db)):
    data, ctype = await read_validated(file, {"application/pdf", "text/plain", "image/jpeg", "image/png"})
    if efile_id:
        f = db.get(OfficerFile, efile_id)
        if not f or not _efile_visible(user, f):
            raise HTTPException(404, detail={"code": "not_found", "message": "File not found."})
    name, digest = store(data, ctype)
    text, status = extract_text(file.filename or "", ctype, data)
    meta = drafting.extract_metadata(text) if text else {}
    meta["summary"] = drafting.summarize(text) if text else ""
    meta["department_id"] = user.department_id
    att = Attachment(tenant_id=user.tenant_id, officer_file_id=efile_id, kind="document", filename=safe_filename(file.filename),
                     content_type=ctype, size=len(data), storage_name=name, sha256=digest, extracted_text=text[:200000],
                     extraction_status=status, meta=meta, uploaded_by=user.id)
    db.add(att)
    audit.record(db, actor=user, action="document.upload", entity_type="document", entity_id=digest[:16],
                 after={"filename": att.filename, "extraction": status})
    db.commit()
    return {"id": att.id, "filename": att.filename, "extraction_status": status, "summary": meta["summary"],
            "metadata": {k: v for k, v in meta.items() if k not in {"summary", "department_id"}},
            "ocr_note": "Image OCR requires a configured OCR provider." if status == "ocr_not_configured" else None}


@router.get("/documents")
def search_documents(q: str = "", user: User = Depends(require("document:work")), db: Session = Depends(get_db)):
    rows = db.execute(select(Attachment).where(Attachment.tenant_id == user.tenant_id, Attachment.kind == "document")
                      .order_by(Attachment.created_at.desc()).limit(500)).scalars().all()
    if user.role == "officer":
        rows = [a for a in rows if a.meta.get("department_id") == user.department_id or a.uploaded_by == user.id]
    terms = tokenize(q)
    results = []
    for a in rows:
        if terms:
            toks = tokenize(a.extracted_text + " " + a.filename)
            tf = Counter(toks)
            score = sum(math.log(1 + tf[t]) for t in set(terms) if t in tf)
            if score <= 0:
                continue
        else:
            score = 0
        results.append((score, a))
    results.sort(key=lambda x: x[0], reverse=True)
    return [{"id": a.id, "filename": a.filename, "score": round(s, 2), "extraction_status": a.extraction_status,
             "summary": a.meta.get("summary", ""), "metadata": {k: v for k, v in a.meta.items() if k in {"dates", "amounts", "references", "word_count"}},
             "uploaded_at": iso(a.created_at)} for s, a in results[:30]]


# ------------------------------------------------------------------ contractor work orders
@router.get("/vendors")
def vendors(user: User = Depends(require("workorder:manage")), db: Session = Depends(get_db)):
    return [{"id": v.id, "name": v.name, "label": "Sample vendor" if v.is_sample else ""}
            for v in db.execute(select(Vendor).where(Vendor.tenant_id == user.tenant_id)).scalars()]


class WorkOrderIn(BaseModel):
    vendor_id: str
    description: str = Field(min_length=5, max_length=1000)
    due_days: int = Field(3, ge=1, le=90)
    boq: list[dict] = Field(default_factory=list, max_length=50)


@router.post("/grievances/{ref}/work-orders", status_code=201)
def create_work_order(ref: str, body: WorkOrderIn, user: User = Depends(require("workorder:manage")), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    v = db.get(Vendor, body.vendor_id)
    if not v or v.tenant_id != user.tenant_id:
        raise HTTPException(422, detail={"code": "invalid_vendor", "message": "Unknown vendor."})
    boq = [{"item": str(i.get("item", ""))[:120], "qty": float(i.get("qty", 0) or 0), "unit": str(i.get("unit", ""))[:20]}
           for i in body.boq]
    wo = WorkOrder(tenant_id=user.tenant_id, grievance_id=g.id, vendor_id=v.id, description=body.description, boq=boq,
                   due_at=utcnow() + timedelta(days=body.due_days), created_by=user.id)
    db.add(wo)
    db.flush()
    workflow.add_event(db, g, user, "work_order", f"Work order {wo.public_id} issued to {v.name}", public=False)
    audit.record(db, actor=user, action="workorder.create", entity_type="work_order", entity_id=wo.public_id,
                 after={"vendor": v.name, "grievance": g.public_id})
    db.commit()
    return {"id": wo.id, "public_id": wo.public_id, "status": wo.status, "due_at": iso(wo.due_at)}


@router.get("/grievances/{ref}/work-orders")
def grievance_work_orders(ref: str, user: User = Depends(require("workorder:manage")), db: Session = Depends(get_db)):
    g = get_visible_grievance(db, user, ref)
    return [{"id": w.id, "public_id": w.public_id, "status": w.status, "vendor": db.get(Vendor, w.vendor_id).name,
             "due_at": iso(w.due_at), "completed_at": iso(w.completed_at), "vendor_note": w.vendor_note}
            for w in db.execute(select(WorkOrder).where(WorkOrder.grievance_id == g.id)).scalars()]


class VerifyWoIn(BaseModel):
    accept: bool
    note: str = Field(min_length=3, max_length=500)


@router.post("/work-orders/{wo_id}/verify")
def verify_work_order(wo_id: str, body: VerifyWoIn, user: User = Depends(require("workorder:manage")), db: Session = Depends(get_db)):
    wo = db.get(WorkOrder, wo_id)
    if not wo or wo.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Work order not found."})
    g = get_visible_grievance(db, user, wo.grievance_id)
    if wo.status != "completed":
        raise HTTPException(409, detail={"code": "not_completed", "message": "Vendor has not marked it completed."})
    wo.status = "verified" if body.accept else "rejected"
    workflow.add_event(db, g, user, "work_order_verified" if body.accept else "work_order_rejected",
                       f"{wo.public_id}: {body.note}", public=False)
    audit.record(db, actor=user, action=f"workorder.{wo.status}", entity_type="work_order", entity_id=wo.public_id,
                 reason=body.note)
    db.commit()
    return {"id": wo.id, "status": wo.status}
