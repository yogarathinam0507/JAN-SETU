from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import Attachment, Category, Grievance, User, Vendor, WorkOrder
from ..security import require
from ..services import audit, workflow
from ..services.uploads import read_validated, safe_filename, store

router = APIRouter(prefix="/api/vendor", tags=["vendor"])
vendor_user = require("workorder:own")


def _own(db: Session, user: User, wo_id: str) -> WorkOrder:
    wo = db.get(WorkOrder, wo_id)
    if not wo or wo.vendor_id != user.vendor_id or wo.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Work order not found."})
    return wo


def _wo_out(db: Session, wo: WorkOrder) -> dict:
    g = db.get(Grievance, wo.grievance_id)
    cat = db.get(Category, g.category_id) if g.category_id else None
    photos = db.execute(select(Attachment).where(Attachment.work_order_id == wo.id)).scalars().all()
    return {"id": wo.id, "public_id": wo.public_id, "status": wo.status, "description": wo.description, "boq": wo.boq,
            "category": cat.names.get("en") if cat else None, "location": g.location_text or "(see officer instructions)",
            "due_at": iso(wo.due_at), "created_at": iso(wo.created_at), "completed_at": iso(wo.completed_at),
            "overdue": bool(wo.due_at and wo.status in {"issued", "in_progress"} and wo.due_at < utcnow()),
            "photos": [{"id": p.id, "filename": p.filename} for p in photos], "vendor_note": wo.vendor_note}


@router.get("/work-orders")
def my_work_orders(user: User = Depends(vendor_user), db: Session = Depends(get_db)):
    rows = db.execute(select(WorkOrder).where(WorkOrder.vendor_id == user.vendor_id, WorkOrder.tenant_id == user.tenant_id)
                      .order_by(WorkOrder.created_at.desc())).scalars().all()
    return [_wo_out(db, w) for w in rows]


class ProgressIn(BaseModel):
    status: str = Field(pattern="^(in_progress|completed)$")
    note: str = Field(min_length=3, max_length=1000)


@router.post("/work-orders/{wo_id}/progress")
def progress(wo_id: str, body: ProgressIn, user: User = Depends(vendor_user), db: Session = Depends(get_db)):
    wo = _own(db, user, wo_id)
    if wo.status in {"verified", "rejected"} and body.status != "in_progress":
        raise HTTPException(409, detail={"code": "locked", "message": "This work order is already verified/rejected."})
    if body.status == "completed":
        has_photo = db.execute(select(Attachment).where(Attachment.work_order_id == wo.id)).first()
        if not has_photo:
            raise HTTPException(422, detail={"code": "photo_required", "message": "Upload a completion photo first."})
        wo.completed_at = utcnow()
    before = wo.status
    wo.status, wo.vendor_note = body.status, body.note
    g = db.get(Grievance, wo.grievance_id)
    workflow.add_event(db, g, user, "work_order_progress", f"{wo.public_id}: {body.status} - {body.note}", public=False)
    audit.record(db, actor=user, action="workorder.progress", entity_type="work_order", entity_id=wo.public_id,
                 before={"status": before}, after={"status": wo.status}, reason=body.note)
    db.commit()
    return _wo_out(db, wo)


@router.post("/work-orders/{wo_id}/photo", status_code=201)
async def completion_photo(wo_id: str, file: UploadFile = File(...), note: str = Form(""),
                           user: User = Depends(vendor_user), db: Session = Depends(get_db)):
    wo = _own(db, user, wo_id)
    data, ctype = await read_validated(file, {"image/jpeg", "image/png"})
    name, digest = store(data, ctype)
    att = Attachment(tenant_id=wo.tenant_id, grievance_id=wo.grievance_id, work_order_id=wo.id, kind="after",
                     filename=safe_filename(file.filename), content_type=ctype, size=len(data), storage_name=name,
                     sha256=digest, uploaded_by=user.id, meta={"note": note[:300]})
    db.add(att)
    g = db.get(Grievance, wo.grievance_id)
    workflow.add_event(db, g, user, "attachment", f"Vendor completion photo for {wo.public_id}", public=False)
    db.commit()
    return {"id": att.id, "filename": att.filename}


@router.get("/scorecard")
def scorecard(user: User = Depends(vendor_user), db: Session = Depends(get_db)):
    v = db.get(Vendor, user.vendor_id)
    rows = db.execute(select(WorkOrder).where(WorkOrder.vendor_id == v.id)).scalars().all()
    done = [w for w in rows if w.completed_at]
    on_time = [w for w in done if w.due_at and w.completed_at <= w.due_at]
    rejected = [w for w in rows if w.status == "rejected"]
    reopened = sum(1 for w in rows if db.get(Grievance, w.grievance_id).reopen_count > 0)
    return {"vendor": v.name, "label": "",
            "work_orders": len(rows), "completed": len(done),
            "on_time_pct": round(100 * len(on_time) / len(done), 1) if done else None,
            "rejected_after_verification": len(rejected), "linked_tickets_reopened": reopened,
            "definition": "On-time % = completed on/before due date / completed. Computed from persisted work orders."}
