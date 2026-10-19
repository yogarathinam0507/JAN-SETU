import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BACKEND_DIR, get_settings
from ..data.lexicon import EVAL_DATASET, EVAL_DATASET_NAME, LEXICON_VERSION
from ..db import get_db, iso
from ..deps import resolve_tenant
from ..models import Category, Department, IntegrationConfig, Jurisdiction, Language, SlaPolicy, Tenant
from ..services.callcentre import telephony

router = APIRouter(prefix="/api/public", tags=["public"])


def public_base(request: Request) -> str:
    """Absolute links come from PUBLIC_BASE_URL; otherwise from the incoming request host (never 'localhost' literals)."""
    configured = get_settings().public_base_url.rstrip("/")
    return configured or str(request.base_url).rstrip("/")


@router.get("/tenants")
def tenants(db: Session = Depends(get_db)):
    return [{"code": t.code, "name": t.name, "state": t.state, "default_language": t.default_language,
             "languages": t.languages, "branding": t.branding, "emergency_contacts": t.emergency_contacts}
            for t in db.execute(select(Tenant).order_by(Tenant.code)).scalars()]


@router.get("/config")
def tenant_config(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    depts = db.execute(select(Department).where(Department.tenant_id == tenant.id, Department.active.is_(True))
                       .order_by(Department.code)).scalars().all()
    cats = db.execute(select(Category).where(Category.tenant_id == tenant.id, Category.active.is_(True))
                      .order_by(Category.code)).scalars().all()
    wards = db.execute(select(Jurisdiction).where(Jurisdiction.tenant_id == tenant.id).order_by(Jurisdiction.kind,
                                                                                                 Jurisdiction.name)).scalars().all()
    slas = db.execute(select(SlaPolicy).where(SlaPolicy.tenant_id == tenant.id)).scalars().all()
    return {
        "tenant": {"code": tenant.code, "name": tenant.name, "state": tenant.state, "default_language": tenant.default_language,
                   "languages": tenant.languages, "branding": tenant.branding, "emergency_contacts": tenant.emergency_contacts},
        "departments": [{"id": d.id, "code": d.code, "names": d.names, "parent_body": d.parent_body, "contact": d.contact,
                         "name_verified": d.name_verified} for d in depts],
        "categories": [{"id": c.id, "code": c.code, "names": c.names, "family": c.family, "department_id": c.department_id,
                        "default_priority": c.default_priority} for c in cats],
        "jurisdictions": [{"id": j.id, "code": j.code, "name": j.name, "kind": j.kind, "parent_id": j.parent_id,
                           "demo_boundary": j.is_demo_boundary} for j in wards],
        "sla_policies": [{"priority": s.priority, "first_response_hours": s.first_response_hours,
                          "resolve_hours": s.resolve_hours} for s in sorted(slas, key=lambda s: s.resolve_hours)],
        "ai_mode": get_settings().ai_mode,
    }


@router.get("/languages")
def languages(db: Session = Depends(get_db)):
    rows = db.execute(select(Language)).scalars().all()
    tier_name = {"voice_text": "Tier 1 - Voice + Text", "text_translation": "Tier 2 - Text + Translation",
                 "content_assisted": "Tier 3 - Content / Assisted only"}
    order = {"voice_text": 0, "text_translation": 1, "content_assisted": 2}
    return {
        "count": len(rows),
        "note": "Planned tier is the target. 'Current support' is what this build implements and tests today. "
                "Languages are not marked supported until they pass the per-language tests.",
        "languages": [{"code": l.code, "name": l.name, "native_name": l.native_name, "script": l.script,
                       "direction": l.direction, "eighth_schedule": l.eighth_schedule, "classical": l.classical,
                       "planned_tier": tier_name[l.planned_tier], "current_support": l.current_support,
                       "speech_code": l.speech_code, "ui_strings": l.ui_strings, "triage_keywords": l.triage_keywords,
                       "notes": l.notes}
                      for l in sorted(rows, key=lambda l: (order[l.planned_tier], not l.ui_strings, l.name))],
    }


@router.get("/privacy")
def privacy(tenant: Tenant = Depends(resolve_tenant)):
    s = get_settings()
    return {
        "status": "DRAFT for review by the organisation's legal / security / data-protection team. Not a compliance claim.",
        "controller": f"{tenant.name} (to be confirmed by the deploying authority)",
        "what_we_collect": ["Complaint text or confirmed voice transcript", "Category, location text, optional GPS pin",
                            "Optional photos/documents you upload", "Name and mobile number for updates (optional for guests)",
                            "Ticket history, feedback and ratings", "Technical logs (no complaint content in logs)"],
        "why": ["To register, route and resolve your grievance", "To send status updates", "To measure service quality "
                "in aggregate", "To meet audit and legal obligations"],
        "ai_processing": f"Complaints are classified by the {s.ai_mode.replace('_', ' ')} pipeline. Low-confidence or "
                         "unclear complaints are reviewed by a human. AI never makes final decisions on benefits.",
        "voice": "Browser speech recognition may be processed by your browser vendor's service. Audio is not stored by "
                 "this platform; only the transcript you confirm is saved.",
        "sharing": "Shared only with the department(s) responsible for your complaint and authorised supervisors. "
                   "Phone numbers and names are masked for staff by default.",
        "retention": {"transcripts_days": s.transcript_retention_days,
                      "grievances": "Retained per the authority's records-retention schedule (to be configured)."},
        "your_rights": ["Access/export your data (My data > Export)", "Request correction or deletion (reviewed by the DPO)",
                        "Withdraw consent for optional processing", "Raise a grievance with the data-protection officer"],
        "training": "Citizen records are not used to train AI models by default.",
    }


@router.get("/integrations")
def integrations(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    rows = db.execute(select(IntegrationConfig).where((IntegrationConfig.tenant_id == tenant.id) |
                                                      (IntegrationConfig.tenant_id.is_(None)))
                      .order_by(IntegrationConfig.kind, IntegrationConfig.name)).scalars().all()
    return {"states": {"connected_tested": "Connected and tested", "configured_unverified": "Configured but unverified",
                       "simulated": "Simulated", "planned": "Planned"},
            "telephony": telephony().status(),
            "integrations": [{"code": r.code, "name": r.name, "kind": r.kind, "state": r.state, "adapter": r.adapter,
                              "last_verified_at": iso(r.last_verified_at), "notes": r.notes} for r in rows]}


@router.get("/evidence")
def evidence():
    data = json.loads((BACKEND_DIR / "app" / "data" / "feature_evidence.json").read_text(encoding="utf-8"))
    return data


@router.get("/benchmark/dataset")
def benchmark_dataset(request: Request):
    """Public labelled triage evaluation dataset (demo). Link is built from PUBLIC_BASE_URL / request host."""
    return {"name": EVAL_DATASET_NAME, "lexicon_version": LEXICON_VERSION, "records": len(EVAL_DATASET),
            "self_url": f"{public_base(request)}/api/public/benchmark/dataset",
            "note": "Synthetic demo examples written for regression testing. Not production data.",
            "items": [{"language": l, "text": t, "expected_category": c, "expected_priority": p}
                      for l, t, c, p in EVAL_DATASET]}
