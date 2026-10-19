import random

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, iso
from ..models import Attachment, AuditLog, Grievance, User
from ..security import require
from ..services import audit, workflow

router = APIRouter(prefix="/api/audit", tags=["audit & QA"])
auditor = require("audit:read")


@router.get("/logs")
def logs(action: str | None = None, entity_type: str | None = None, actor_role: str | None = None,
         page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
         user: User = Depends(auditor), db: Session = Depends(get_db)):
    q = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if actor_role:
        q = q.where(AuditLog.actor_role == actor_role)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars()
    return {"total": total, "page": page, "items": [
        {"id": r.id, "at": iso(r.created_at), "actor_role": r.actor_role, "actor_id": (r.actor_id or "")[:8],
         "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id, "before": r.before, "after": r.after,
         "reason": r.reason, "hash": r.hash[:16]} for r in rows]}


@router.get("/verify-chain")
def verify(user: User = Depends(auditor), db: Session = Depends(get_db)):
    return audit.verify_chain(db) | {"note": "Recomputes every entry's SHA-256 over its content and the previous hash."}


@router.get("/closure-sample")
def closure_sample(size: int = Query(10, ge=1, le=50), seed: int | None = None, user: User = Depends(auditor),
                   db: Session = Depends(get_db)):
    rows = db.execute(select(Grievance).where(Grievance.tenant_id == user.tenant_id,
                                              Grievance.status.in_(["resolved", "closed"]))).scalars().all()
    rng = random.Random(seed)
    sample = rng.sample(rows, min(size, len(rows)))
    out = []
    for g in sample:
        kinds = {a.kind for a in db.execute(select(Attachment).where(Attachment.grievance_id == g.id)).scalars()}
        flags = []
        if "after" not in kinds:
            flags.append("No 'after' photo")
        if g.resolved_at and (g.resolved_at - g.created_at).total_seconds() < 600:
            flags.append("Resolved within 10 minutes of filing")
        if g.reopen_count:
            flags.append(f"Reopened {g.reopen_count}x")
        if g.citizen_rating is not None and g.citizen_rating <= 2:
            flags.append(f"Low citizen rating ({g.citizen_rating})")
        out.append(workflow.serialize(db, g, user) | {"qa_flags": flags})
    return {"population": len(rows), "sample_size": len(out), "seed": seed, "items": out,
            "method": "Uniform random sample of resolved/closed tickets; flags are rule-based prompts for manual review."}
