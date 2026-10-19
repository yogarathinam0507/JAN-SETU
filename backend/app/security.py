"""Authentication, password hashing, tokens and server-side RBAC enforcement."""
import hashlib
import hmac
import os
import secrets
import time

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, utcnow
from .models import User

settings = get_settings()

# ---------------------------------------------------------------- RBAC matrix
# Single source of truth. Seeded into role_permissions for visibility in /admin.
ROLES = {
    "citizen": ("Citizen / beneficiary", "Files and tracks own grievances, uses the benefit navigator."),
    "agent": ("Call-centre agent", "Handles assigned interactions with masked contact details."),
    "officer": ("Department officer", "Own department and jurisdiction queue, case actions, drafts."),
    "nodal": ("Ward/zone nodal officer", "Zone-wide queue, cross-department cases, master incidents, triage."),
    "hod": ("Head of department / commissioner", "Aggregate analytics; personal data hidden by default."),
    "vendor": ("Contractor / vendor", "Assigned work orders and own scorecard only."),
    "auditor": ("QA / auditor", "Read-only review, sampling, AI evaluation, audit log."),
    "content": ("Content / language manager", "Knowledge base, schemes, translations. No grievance access."),
    "admin": ("System / tenant administrator", "Configuration, users, integrations, health. No citizen content."),
}

PERMISSIONS: dict[str, set[str]] = {
    "citizen": {"grievance:create", "grievance:read_own", "grievance:feedback", "benefits:use", "me:data"},
    "agent": {"grievance:create", "grievance:read_scoped", "interaction:work", "kb:read", "benefits:use",
              "contact:reveal", "triage:preview"},
    "officer": {"grievance:read_scoped", "grievance:act", "contact:reveal", "draft:write", "efile:work",
                "document:work", "workorder:manage", "kb:read", "triage:preview", "analytics:read"},
    "nodal": {"grievance:read_scoped", "grievance:act", "grievance:triage", "incident:manage", "contact:reveal",
              "draft:write", "efile:work", "document:work", "workorder:manage", "kb:read", "analytics:read",
              "triage:preview", "monitoring:read"},
    "hod": {"analytics:read", "grievance:read_aggregate", "monitoring:read", "interaction:supervise", "kb:read"},
    "vendor": {"workorder:own"},
    "auditor": {"audit:read", "grievance:read_scoped", "analytics:read", "ai_eval:run", "monitoring:read",
                "interaction:supervise", "kb:read"},
    "content": {"kb:read", "kb:write", "schemes:write", "translations:write"},
    "admin": {"config:write", "users:manage", "integrations:manage", "monitoring:read", "monitoring:manage",
              "analytics:read"},
}

# Roles whose grievance view is scoped to the tenant (with role-specific filters applied in queries).
STAFF_ROLES = {"agent", "officer", "nodal", "hod", "auditor", "vendor", "content", "admin"}


def has_perm(user: User, perm: str) -> bool:
    return perm in PERMISSIONS.get(user.role, set())


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def keyed_hash(value: str) -> str:
    return hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def gen_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


# ---------------------------------------------------------------- tokens
def create_token(user: User) -> str:
    # Epoch seconds directly. (Calling .timestamp() on our naive-UTC datetimes applies the machine's local
    # timezone - on an IST machine every token was born 5.5 h in the past and expired immediately.)
    now = int(time.time())
    payload = {
        "sub": user.id,
        "role": user.role,
        "tid": user.tenant_id,
        "iat": now,
        "exp": now + settings.token_ttl_minutes * 60,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


_revoked: set[str] = set()  # logout list (process-local; use Redis in multi-instance deployments)


def revoke_token(token: str) -> None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"], options={"verify_exp": False})
        _revoked.add(payload.get("jti", ""))
    except jwt.PyJWTError:
        pass


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = _token_from_request(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, detail={"code": "token_expired", "message": "Session expired. Please sign in again."})
    except jwt.PyJWTError:
        raise HTTPException(401, detail={"code": "invalid_token", "message": "Invalid session token."})
    if payload.get("jti") in _revoked:
        raise HTTPException(401, detail={"code": "token_revoked", "message": "You have signed out."})
    user = db.get(User, payload["sub"])
    if not user or not user.active or user.tenant_id != payload.get("tid"):
        raise HTTPException(401, detail={"code": "invalid_user", "message": "Account unavailable."})
    return user


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(401, detail={"code": "auth_required", "message": "Sign in required."})
    return user


def require(*perms: str):
    """Dependency factory: user must hold ALL listed permissions (enforced server-side)."""

    def dep(user: User = Depends(get_current_user)) -> User:
        missing = [p for p in perms if not has_perm(user, p)]
        if missing:
            raise HTTPException(403, detail={"code": "forbidden",
                                             "message": f"Your role ({user.role}) is not permitted to do this.",
                                             "missing": missing})
        return user

    return dep


def require_any(*perms: str):
    def dep(user: User = Depends(get_current_user)) -> User:
        if not any(has_perm(user, p) for p in perms):
            raise HTTPException(403, detail={"code": "forbidden",
                                             "message": f"Your role ({user.role}) is not permitted to do this."})
        return user

    return dep
