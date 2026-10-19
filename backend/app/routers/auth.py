import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, iso, utcnow
from ..models import DataRequest, Department, Grievance, Jurisdiction, OtpChallenge, Tenant, User
from ..security import (PERMISSIONS, ROLES, create_token, gen_otp, get_current_user, hash_password, keyed_hash,
                        revoke_token, verify_password)
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
me_router = APIRouter(prefix="/api/me", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=200)


class OtpRequestIn(BaseModel):
    tenant: str
    phone: str = Field(pattern=r"^[6-9]\d{9}$", description="10-digit Indian mobile number")


class OtpVerifyIn(OtpRequestIn):
    code: str = Field(pattern=r"^\d{6}$")
    full_name: str = Field("", max_length=120)


def user_out(db: Session, u: User) -> dict:
    t = db.get(Tenant, u.tenant_id)
    d = db.get(Department, u.department_id) if u.department_id else None
    j = db.get(Jurisdiction, u.jurisdiction_id) if u.jurisdiction_id else None
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
            "designation": u.designation or "", "role_name": ROLES[u.role][0], "permissions": sorted(PERMISSIONS[u.role]), "language": u.language,
            "tenant": {"code": t.code, "name": t.name, "default_language": t.default_language},
            "department": {"id": d.id, "code": d.code, "name": d.names.get("en")} if d else None,
            "jurisdiction": {"id": j.id, "name": j.name} if j else None, "is_demo": u.is_demo}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.execute(select(User).where(User.username == body.username.strip().lower())).scalar_one_or_none()
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, detail={"code": "bad_credentials", "message": "Incorrect username or password."})
    u.last_login_at = utcnow()
    audit.record(db, actor=u, action="auth.login", entity_type="user", entity_id=u.username)
    db.commit()
    return {"token": create_token(u), "expires_in_minutes": get_settings().token_ttl_minutes, "user": user_out(db, u)}


@router.post("/otp/request")
def otp_request(body: OtpRequestIn, db: Session = Depends(get_db)):
    s = get_settings()
    t = db.execute(select(Tenant).where(Tenant.code == body.tenant)).scalar_one_or_none()
    if not t:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Unknown tenant."})
    code = gen_otp()
    db.add(OtpChallenge(tenant_id=t.id, phone_hash=keyed_hash(f"{t.id}:{body.phone}"), code_hash=keyed_hash(code),
                        purpose="citizen_login", expires_at=utcnow() + timedelta(minutes=5)))
    db.commit()
    if s.otp_provider == "demo" and not s.is_production:
        return {"sent": False, "simulated": True, "demo_otp": code,
                "message": "SMS gateway not configured on this server, so the one-time code is displayed here."}
    if s.otp_provider == "demo":
        raise HTTPException(503, detail={"code": "otp_provider_missing", "message": "OTP delivery is not configured."})
    raise HTTPException(501, detail={"code": "otp_provider_not_implemented",
                                     "message": f"OTP provider '{s.otp_provider}' adapter requires credentials."})


@router.post("/otp/verify")
def otp_verify(body: OtpVerifyIn, db: Session = Depends(get_db)):
    t = db.execute(select(Tenant).where(Tenant.code == body.tenant)).scalar_one_or_none()
    if not t:
        raise HTTPException(404, detail={"code": "tenant_not_found", "message": "Unknown tenant."})
    ch = db.execute(select(OtpChallenge).where(OtpChallenge.phone_hash == keyed_hash(f"{t.id}:{body.phone}"),
                                               OtpChallenge.used.is_(False))
                    .order_by(OtpChallenge.expires_at.desc())).scalars().first()
    if not ch or ch.expires_at < utcnow() or ch.attempts >= 5:
        raise HTTPException(401, detail={"code": "otp_expired", "message": "Code expired. Request a new one."})
    ch.attempts += 1
    if keyed_hash(body.code) != ch.code_hash:
        db.commit()
        raise HTTPException(401, detail={"code": "otp_invalid", "message": "Incorrect code."})
    ch.used = True
    username = f"{t.code}.cit.{body.phone}"
    u = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not u:
        u = User(tenant_id=t.id, username=username, full_name=body.full_name.strip() or "Citizen",
                 role="citizen", password_hash=hash_password(gen_otp() + gen_otp()), phone=body.phone,
                 language=t.default_language, is_demo=False)
        db.add(u)
        db.flush()
    u.last_login_at = utcnow()
    audit.record(db, actor=u, action="auth.otp_login", entity_type="user", entity_id=u.id)
    db.commit()
    return {"token": create_token(u), "user": user_out(db, u)}


@router.post("/logout")
def logout(request: Request, user: User = Depends(get_current_user)):
    revoke_token(request.headers.get("authorization", "")[7:])
    return {"ok": True}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    if get_settings().is_production:
        raise HTTPException(404, detail={"code": "not_found", "message": "Not available in production."})
    rows = db.execute(select(User, Tenant).join(Tenant, User.tenant_id == Tenant.id)
                      .where(User.is_demo.is_(True)).order_by(Tenant.code, User.role, User.username)).all()
    depts = {d.id: d.names.get("en", d.code) for d in db.execute(select(Department)).scalars()}
    return {"password": "Demo@1234", "note": "Test accounts for this installation. Disabled when APP_ENV=production.",
            "accounts": [{"tenant": t.code, "username": u.username, "role": u.role, "role_name": ROLES[u.role][0],
                          "full_name": u.full_name, "designation": u.designation or "",
                          "department": depts.get(u.department_id, "")} for u, t in rows]}


@me_router.get("")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(db, user)


class LangIn(BaseModel):
    language: str = Field(min_length=2, max_length=10)


@me_router.patch("/language")
def set_language(body: LangIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.language = body.language
    db.commit()
    return {"language": user.language}


@me_router.get("/export")
def export_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Data-access request: returns the signed-in user's own records."""
    from ..services.workflow import serialize
    db.add(DataRequest(tenant_id=user.tenant_id, user_id=user.id, kind="export", status="completed"))
    audit.record(db, actor=user, action="privacy.export", entity_type="user", entity_id=user.id)
    db.commit()
    gs = db.execute(select(Grievance).where(Grievance.citizen_id == user.id)).scalars().all()
    return {"profile": {"full_name": user.full_name, "phone": user.phone, "language": user.language,
                        "created_at": iso(user.created_at)},
            "grievances": [serialize(db, g, user, detail=True) for g in gs]}


class DeletionIn(BaseModel):
    reason: str = Field("", max_length=500)


@me_router.post("/deletion-request")
def deletion_request(body: DeletionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = DataRequest(tenant_id=user.tenant_id, user_id=user.id, kind="deletion", status="pending_review",
                      note=re.sub(r"\s+", " ", body.reason)[:500])
    db.add(req)
    audit.record(db, actor=user, action="privacy.deletion_request", entity_type="user", entity_id=user.id)
    db.commit()
    return {"id": req.id, "status": req.status,
            "message": "Your request is recorded and will be reviewed by the data-protection officer. Records under a "
                       "legal retention obligation may be retained; you will be informed of the outcome."}

