from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Tenant, User
from .security import get_optional_user


def resolve_tenant(tenant: str | None = Query(None, description="Tenant code (public endpoints)"),
                   user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)) -> Tenant:
    """Signed-in users are always bound to their own tenant; anonymous callers pass ?tenant=code."""
    if user is not None:
        t = db.get(Tenant, user.tenant_id)
        if tenant and t.code != tenant:
            raise HTTPException(403, detail={"code": "tenant_mismatch",
                                             "message": "You are signed in to a different tenant."})
        return t
    if not tenant:
        t = db.execute(select(Tenant).order_by(Tenant.code)).scalars().first()
        if not t:
            raise HTTPException(503, detail={"code": "not_seeded", "message": "No tenant configured. Run the seed script."})
        return t
    t = db.execute(select(Tenant).where(Tenant.code == tenant)).scalar_one_or_none()
    if not t:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": f"Unknown tenant '{tenant}'."})
    return t


def page_params(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)) -> tuple[int, int]:
    return page, page_size
