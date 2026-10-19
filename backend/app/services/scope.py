"""Server-side record scoping: which grievances a user may see. Used by every grievance endpoint."""
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Grievance, Jurisdiction, User


def jurisdiction_subtree(db: Session, root_id: str | None) -> set[str]:
    if not root_id:
        return set()
    ids = {root_id}
    frontier = [root_id]
    while frontier:
        children = db.execute(select(Jurisdiction.id).where(Jurisdiction.parent_id.in_(frontier))).scalars().all()
        frontier = [c for c in children if c not in ids]
        ids.update(frontier)
    return ids


def grievance_scope(db: Session, user: User):
    """Return a SELECT restricted to what this user may see (always tenant-isolated)."""
    q = select(Grievance).where(Grievance.tenant_id == user.tenant_id)
    if user.role == "citizen":
        return q.where(Grievance.citizen_id == user.id)
    if user.role == "officer":
        q = q.where(Grievance.department_id == user.department_id)
        if user.jurisdiction_id:
            sub = jurisdiction_subtree(db, user.jurisdiction_id)
            q = q.where(or_(Grievance.jurisdiction_id.in_(sub), Grievance.jurisdiction_id.is_(None)))
        return q
    if user.role == "nodal":
        if user.jurisdiction_id:
            sub = jurisdiction_subtree(db, user.jurisdiction_id)
            q = q.where(or_(Grievance.jurisdiction_id.in_(sub), Grievance.jurisdiction_id.is_(None)))
        return q
    if user.role in {"agent", "auditor"}:
        return q
    # hod / vendor / content / admin: no record-level grievance access
    return q.where(Grievance.id.is_(None))


def can_view(db: Session, user: User, g: Grievance) -> bool:
    if g.tenant_id != user.tenant_id:
        return False
    if user.role == "citizen":
        return g.citizen_id == user.id
    if user.role == "officer":
        in_dept = g.department_id == user.department_id or user.department_id in (g.joint_department_ids or [])
        if not in_dept:
            return False
        if user.jurisdiction_id and g.jurisdiction_id:
            return g.jurisdiction_id in jurisdiction_subtree(db, user.jurisdiction_id)
        return True
    if user.role == "nodal":
        if user.jurisdiction_id and g.jurisdiction_id:
            return g.jurisdiction_id in jurisdiction_subtree(db, user.jurisdiction_id)
        return True
    return user.role in {"agent", "auditor"}


def get_visible_grievance(db: Session, user: User, ref: str) -> Grievance:
    g = db.execute(select(Grievance).where(or_(Grievance.id == ref, Grievance.public_id == ref))).scalar_one_or_none()
    # Same 404 for "missing" and "not yours" to avoid leaking existence across users/tenants.
    if not g or not can_view(db, user, g):
        raise HTTPException(404, detail={"code": "not_found", "message": "Ticket not found."})
    return g
