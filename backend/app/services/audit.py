"""Tamper-evident audit log (each entry hashes the previous entry's hash)."""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import AuditLog, User


def _digest(entry: AuditLog) -> str:
    payload = json.dumps({
        "tenant": entry.tenant_id, "actor": entry.actor_id, "role": entry.actor_role, "action": entry.action,
        "type": entry.entity_type, "id": entry.entity_id, "before": entry.before, "after": entry.after,
        "reason": entry.reason, "at": entry.created_at.isoformat(), "prev": entry.prev_hash,
    }, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def record(db: Session, *, actor: User | None, action: str, entity_type: str, entity_id: str,
           tenant_id: str | None = None, before: dict | None = None, after: dict | None = None,
           reason: str = "") -> AuditLog:
    last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    entry = AuditLog(
        tenant_id=tenant_id or (actor.tenant_id if actor else None),
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else "system",
        action=action, entity_type=entity_type, entity_id=str(entity_id),
        before=before, after=after, reason=reason or "", created_at=utcnow(),
        prev_hash=last.hash if last else "",
    )
    entry.hash = _digest(entry)
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session) -> dict:
    prev = ""
    count = 0
    for entry in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        count += 1
        if entry.prev_hash != prev or _digest(entry) != entry.hash:
            return {"valid": False, "checked": count, "broken_at_id": entry.id}
        prev = entry.hash
    return {"valid": True, "checked": count, "broken_at_id": None}
