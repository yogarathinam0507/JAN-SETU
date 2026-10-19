"""Grievance lifecycle: creation, state machine, SLA, duplicate clustering, escalation and serialization."""
import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import iso, utcnow
from ..models import (Attachment, Category, Department, DuplicateLink, EscalationRule, Grievance, Jurisdiction,
                      MasterIncident, SlaPolicy, TicketEvent, User)
from . import audit
from .geo import haversine_m
from .masking import mask_name, mask_phone, redact_text

OPEN_STATUSES = {"submitted", "human_review", "accepted", "in_progress", "info_requested", "reopened"}
STATUS_LABELS = {
    "submitted": "Submitted - awaiting department acceptance", "human_review": "In human triage queue",
    "accepted": "Accepted by department", "in_progress": "Work in progress", "info_requested": "More information requested",
    "resolved": "Resolved - awaiting your confirmation", "closed": "Closed", "rejected": "Rejected", "reopened": "Reopened",
}
DUPLICATE_RADIUS_M = 500
DUPLICATE_WINDOW_DAYS = 7
DUPLICATE_RULE = (f"R-DUP-01: same category, open, filed within {DUPLICATE_WINDOW_DAYS} days and within "
                  f"{DUPLICATE_RADIUS_M} m (GPS) - or same ward with text similarity >= 0.30 when GPS is missing")
DUPLICATE_DEFINITION = ("Linked reports = grievances attached to a master incident. Master incidents = incidents with "
                        "at least one linked report. Duplicates = linked reports minus master incidents (i.e. every "
                        "report after the first one in each incident).")

# action -> (allowed from statuses, resulting status, required permission)
TRANSITIONS = {
    "accept": ({"submitted", "reopened"}, "accepted", "grievance:act"),
    "start": ({"accepted", "info_requested"}, "in_progress", "grievance:act"),
    "request_info": ({"submitted", "accepted", "in_progress", "reopened"}, "info_requested", "grievance:act"),
    "resolve": ({"accepted", "in_progress", "info_requested", "reopened"}, "resolved", "grievance:act"),
    "reject": ({"submitted", "accepted", "in_progress", "info_requested", "reopened", "human_review"}, "rejected", "grievance:act"),
    "confirm_closure": ({"resolved"}, "closed", "grievance:feedback"),
    "reject_closure": ({"resolved", "rejected"}, "reopened", "grievance:feedback"),
    "provide_info": ({"info_requested"}, "in_progress", "grievance:feedback"),
}
REASON_REQUIRED = {"reject", "reject_closure", "request_info", "resolve", "transfer", "provide_info"}


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", (text or "").lower()) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def add_event(db: Session, g: Grievance, actor: User | None, event_type: str, note: str = "", *,
              from_status: str | None = None, to_status: str | None = None, public: bool = True,
              data: dict | None = None, at=None) -> TicketEvent:
    ev = TicketEvent(grievance_id=g.id, created_at=at or utcnow(), actor_id=actor.id if actor else None,
                     actor_role=actor.role if actor else "system", event_type=event_type, note=note,
                     from_status=from_status, to_status=to_status, public=public, data=data or {})
    db.add(ev)
    return ev


def officer_label(db: Session, officer: User | None) -> str:
    if not officer:
        return ""
    dept = db.get(Department, officer.department_id) if officer.department_id else None
    parts = [officer.full_name, officer.designation or "", dept.names.get("en", "") if dept else ""]
    return ", ".join(p for p in parts if p)


def assign_department_officer(db: Session, g: Grievance, actor: User | None = None, at=None) -> User | None:
    """Assign the ticket to the responsible officer of its department (ward-specific officer first) and
    record a public notification so the citizen sees who is handling the complaint."""
    if not g.department_id:
        return None
    q = select(User).where(User.tenant_id == g.tenant_id, User.role == "officer", User.active.is_(True),
                           User.department_id == g.department_id).order_by(User.username)
    candidates = db.execute(q).scalars().all()
    if not candidates:
        return None
    officer = candidates[0]
    if g.jurisdiction_id:
        for c in candidates:
            if c.jurisdiction_id and c.jurisdiction_id == g.jurisdiction_id:
                officer = c
                break
    g.assigned_officer_id = officer.id
    label = officer_label(db, officer)
    add_event(db, g, actor, "assigned", f"Your complaint has been assigned to {label}.",
              data={"officer": officer.full_name, "designation": officer.designation}, at=at or g.created_at)
    notify_citizen(db, g, f"Complaint {g.public_id} has been assigned to {label}.")
    return officer


def notify_citizen(db: Session, g: Grievance, message: str) -> None:
    """SMS/WhatsApp status update. Real delivery requires a configured provider; otherwise simulated & labelled."""
    s = get_settings()
    channel = "sms" if s.sms_provider else None
    add_event(db, g, None, "notification", public=False,
              note=(f"Status update queued via {channel} provider" if channel else
                    "SMS/WhatsApp update recorded (no messaging gateway configured)"),
              data={"message": message, "simulated": channel is None})


def apply_sla(db: Session, g: Grievance) -> None:
    now = g.created_at or utcnow()
    if g.priority:
        pol = db.execute(select(SlaPolicy).where(SlaPolicy.tenant_id == g.tenant_id,
                                                 SlaPolicy.priority == g.priority)).scalar_one_or_none()
        if pol:
            g.sla_policy_id = pol.id
            g.sla_due_at = now + timedelta(hours=pol.resolve_hours)
            g.first_response_due_at = now + timedelta(hours=pol.first_response_hours)
            return
    # Unrouted (human triage): first-response target only; resolution SLA starts once routed.
    g.sla_policy_id = None
    g.sla_due_at = None
    g.first_response_due_at = now + timedelta(hours=4 if g.emergency else 24)


def sla_state(g: Grievance) -> dict:
    now = utcnow()
    if not g.sla_due_at:
        return {"state": "not_started", "label": "SLA starts after routing", "remaining_seconds": None}
    end = g.resolved_at if g.status in {"resolved", "closed"} and g.resolved_at else None
    if end:
        met = end <= g.sla_due_at
        return {"state": "met" if met else "missed", "label": "Resolved within SLA" if met else "Resolved after SLA",
                "remaining_seconds": None}
    if g.status == "rejected":
        return {"state": "stopped", "label": "SLA stopped (rejected)", "remaining_seconds": None}
    remaining = (g.sla_due_at - now).total_seconds()
    total = (g.sla_due_at - g.created_at).total_seconds() or 1
    if remaining < 0:
        return {"state": "breached", "label": "SLA breached", "remaining_seconds": int(remaining)}
    if remaining / total < 0.25:
        return {"state": "at_risk", "label": "Due soon", "remaining_seconds": int(remaining)}
    return {"state": "on_track", "label": "On track", "remaining_seconds": int(remaining)}


def find_duplicate(db: Session, g: Grievance) -> tuple[Grievance, dict] | None:
    if not g.category_id:
        return None
    since = utcnow() - timedelta(days=DUPLICATE_WINDOW_DAYS)
    candidates = db.execute(select(Grievance).where(
        Grievance.tenant_id == g.tenant_id, Grievance.category_id == g.category_id, Grievance.id != g.id,
        Grievance.status.in_(OPEN_STATUSES), Grievance.created_at >= since)).scalars().all()
    best = None
    for c in candidates:
        if g.lat is not None and c.lat is not None:
            d = haversine_m(g.lat, g.lng, c.lat, c.lng)
            if d <= DUPLICATE_RADIUS_M and (best is None or d < best[1]["distance_m"] or best[1]["distance_m"] is None):
                best = (c, {"distance_m": round(d, 1), "similarity": round(jaccard(g.original_text, c.original_text), 2)})
        elif g.jurisdiction_id and g.jurisdiction_id == c.jurisdiction_id:
            sim = jaccard(g.original_text, c.original_text)
            if sim >= 0.30 and (best is None or (best[1]["distance_m"] is None and sim > best[1]["similarity"])):
                best = (c, {"distance_m": None, "similarity": round(sim, 2)})
    return best


def link_duplicate(db: Session, g: Grievance, other: Grievance, evidence: dict, actor: User | None) -> MasterIncident:
    master = db.get(MasterIncident, other.master_incident_id) if other.master_incident_id else None
    if master is None:
        cat = db.get(Category, other.category_id)
        master = MasterIncident(tenant_id=g.tenant_id, category_id=other.category_id,
                                jurisdiction_id=other.jurisdiction_id, lat=other.lat, lng=other.lng,
                                title=f"{cat.names.get('en', cat.code)} cluster" + (f" - {other.location_text}" if other.location_text else ""))
        db.add(master)
        db.flush()
        other.master_incident_id = master.id
        db.add(DuplicateLink(grievance_id=other.id, master_incident_id=master.id, rule="R-DUP-00: first report (anchor)",
                             created_by="system"))
        add_event(db, other, None, "linked_master", f"Linked to master incident {master.public_id}")
    g.master_incident_id = master.id
    db.add(DuplicateLink(grievance_id=g.id, master_incident_id=master.id, rule=DUPLICATE_RULE,
                         distance_m=evidence.get("distance_m"), similarity=evidence.get("similarity"),
                         created_by=actor.role if actor else "system"))
    add_event(db, g, None, "linked_master",
              f"Possible duplicate of {other.public_id}; linked to master incident {master.public_id}. "
              "Your complaint stays open and is tracked individually.", data=evidence)
    audit.record(db, actor=None, tenant_id=g.tenant_id, action="duplicate.link", entity_type="grievance",
                 entity_id=g.public_id, after={"master": master.public_id, "matched": other.public_id, **evidence},
                 reason=DUPLICATE_RULE)
    return master


def duplicate_stats(db: Session, tenant_id: str, base_filter=None) -> dict:
    q = select(Grievance.master_incident_id, func.count()).where(Grievance.tenant_id == tenant_id,
                                                                 Grievance.master_incident_id.is_not(None))
    if base_filter is not None:
        q = q.where(*base_filter)
    rows = db.execute(q.group_by(Grievance.master_incident_id)).all()
    linked = sum(n for _, n in rows)
    masters = len(rows)
    return {"linked_reports": linked, "master_incidents": masters, "duplicates": linked - masters,
            "definition": DUPLICATE_DEFINITION, "rule": DUPLICATE_RULE}


def create_grievance(db: Session, *, tenant_id: str, triage: dict, text: str, actor: User | None,
                     citizen: User | None, channel: str, input_mode: str, transcript_confirmed: bool,
                     contact_name: str, contact_phone: str, lat: float | None, lng: float | None,
                     location_text: str, consent: bool, is_demo: bool = False,
                     created_at=None) -> Grievance:
    if input_mode == "voice" and not transcript_confirmed:
        raise HTTPException(422, detail={"code": "transcript_not_confirmed",
                                         "message": "Please review and confirm the voice transcript before submitting."})
    if not consent:
        raise HTTPException(422, detail={"code": "consent_required",
                                         "message": "Consent to process your complaint data is required."})
    human = bool(triage.get("human_review_required"))
    g = Grievance(tenant_id=tenant_id, citizen_id=citizen.id if citizen else None,
                  created_by_id=actor.id if actor else None, channel=channel, input_mode=input_mode,
                  original_text=text, transcript_confirmed=transcript_confirmed, language=triage["language"],
                  summary=triage["summary"], category_id=None if human else triage.get("category_id"),
                  department_id=None if human else triage.get("department_id"),
                  jurisdiction_id=triage.get("jurisdiction_id"),
                  location_text=(location_text or triage.get("location_text") or "")[:300], lat=lat, lng=lng,
                  priority=triage.get("priority"), status="human_review" if human else "submitted",
                  human_review_required=human, triage_id=triage.get("triage_id"), contact_name=contact_name[:200],
                  contact_phone=contact_phone[:20], consent_at=utcnow(), emergency=bool(triage.get("emergency")),
                  is_demo=is_demo, created_at=created_at or utcnow())
    db.add(g)
    db.flush()
    apply_sla(db, g)
    add_event(db, g, actor, "created", from_status=None, to_status=g.status,
              note=("Sent to the human triage queue: " + (triage.get("human_review_reason") or "")) if human
              else f"Routed to {triage.get('department_name')} with priority {g.priority}.",
              data={"triage_id": triage.get("triage_id"), "confidence": triage.get("confidence")}, at=g.created_at)
    if g.emergency:
        add_event(db, g, None, "emergency_flag", "Emergency safety rule triggered; nodal officer alerted.",
                  data={"rules": [r["rule"] for r in triage.get("rules_applied", []) if r["rule"].startswith("R-EMG")]})
    if not human:
        assign_department_officer(db, g, None)
        dup = find_duplicate(db, g)
        if dup:
            link_duplicate(db, g, dup[0], dup[1], actor)
    audit.record(db, actor=actor, tenant_id=tenant_id, action="grievance.create", entity_type="grievance",
                 entity_id=g.public_id, after={"status": g.status, "department_id": g.department_id,
                                               "priority": g.priority, "channel": channel})
    notify_citizen(db, g, f"Your complaint {g.public_id} was received.")
    return g


def snapshot(g: Grievance) -> dict:
    return {"status": g.status, "department_id": g.department_id, "category_id": g.category_id,
            "priority": g.priority, "assigned_officer_id": g.assigned_officer_id,
            "escalation_level": g.escalation_level, "jurisdiction_id": g.jurisdiction_id,
            "joint_department_ids": list(g.joint_department_ids or [])}


def transition(db: Session, g: Grievance, action: str, actor: User, note: str = "") -> Grievance:
    if action not in TRANSITIONS:
        raise HTTPException(400, detail={"code": "unknown_action", "message": f"Unknown action '{action}'"})
    allowed_from, to_status, _perm = TRANSITIONS[action]
    if g.status not in allowed_from:
        raise HTTPException(409, detail={"code": "invalid_transition",
                                         "message": f"Cannot '{action}' a ticket that is '{g.status}'."})
    if action in REASON_REQUIRED and len(note.strip()) < 5:
        raise HTTPException(422, detail={"code": "reason_required", "message": "Please give a reason / note (min 5 characters)."})
    before = snapshot(g)
    prev = g.status
    g.status = to_status
    now = utcnow()
    if action == "accept" and not g.first_response_at:
        g.first_response_at = now
        if not g.assigned_officer_id and actor.role == "officer":
            g.assigned_officer_id = actor.id
    if action == "resolve":
        g.resolved_at = now
        g.resolution_note = note
    if action == "confirm_closure":
        g.closed_at = now
    if action == "reject_closure":
        g.reopen_count += 1
        g.resolved_at = None  # SLA clock keeps the original due date (no reset on reopen)
    if action == "reject":
        g.resolution_note = note
    add_event(db, g, actor, action, note, from_status=prev, to_status=to_status)
    audit.record(db, actor=actor, action=f"grievance.{action}", entity_type="grievance", entity_id=g.public_id,
                 before=before, after=snapshot(g), reason=note)
    notify_citizen(db, g, f"Complaint {g.public_id}: {STATUS_LABELS.get(to_status, to_status)}")
    return g


ROLE_TITLES = {"nodal": "the ward/zone nodal officer", "hod": "the head of department"}


def run_escalations(db: Session, tenant_id: str | None = None, backdate: bool = False) -> int:
    """Escalate open tickets per the configured matrix. Idempotent."""
    now = utcnow()
    q = select(Grievance).where(Grievance.status.in_(OPEN_STATUSES - {"human_review"}), Grievance.sla_due_at.is_not(None))
    if tenant_id:
        q = q.where(Grievance.tenant_id == tenant_id)
    count = 0
    rules_cache: dict[str, list[EscalationRule]] = {}
    for g in db.execute(q).scalars():
        rules = rules_cache.setdefault(g.tenant_id, db.execute(
            select(EscalationRule).where(EscalationRule.tenant_id == g.tenant_id).order_by(EscalationRule.level)).scalars().all())
        total = (g.sla_due_at - g.created_at).total_seconds() or 1
        fraction = (now - g.created_at).total_seconds() / total
        for rule in rules:
            if fraction >= rule.sla_fraction and g.escalation_level < rule.level:
                before = snapshot(g)
                g.escalation_level = rule.level
                at = g.created_at + timedelta(seconds=total * rule.sla_fraction) if backdate else None
                add_event(db, g, None, "escalated",
                          f"Escalated to {ROLE_TITLES.get(rule.role, rule.role)} (level {rule.level}) - "
                          f"target resolution time exceeded.",
                          data={"rule_level": rule.level, "elapsed_fraction": round(fraction, 2)}, at=at)
                audit.record(db, actor=None, tenant_id=g.tenant_id, action="grievance.escalate.auto",
                             entity_type="grievance", entity_id=g.public_id, before=before, after=snapshot(g),
                             reason=f"Elapsed {fraction:.2f} x SLA >= {rule.sla_fraction}")
                count += 1
    return count


def serialize(db: Session, g: Grievance, viewer: User | None, detail: bool = False) -> dict:
    owner = viewer is not None and viewer.id == g.citizen_id
    dept = db.get(Department, g.department_id) if g.department_id else None
    cat = db.get(Category, g.category_id) if g.category_id else None
    jur = db.get(Jurisdiction, g.jurisdiction_id) if g.jurisdiction_id else None
    master = db.get(MasterIncident, g.master_incident_id) if g.master_incident_id else None
    officer = db.get(User, g.assigned_officer_id) if g.assigned_officer_id else None
    lang = viewer.language if viewer else "en"
    show_pii = owner
    show_text = owner or (viewer is not None and viewer.role in {"officer", "nodal", "agent", "auditor"})
    data = {
        "id": g.id, "public_id": g.public_id, "status": g.status, "status_label": STATUS_LABELS.get(g.status, g.status),
        "channel": g.channel, "input_mode": g.input_mode, "language": g.language, "priority": g.priority,
        "emergency": g.emergency, "summary": redact_text(g.summary) if not show_pii else g.summary,
        "category": {"id": cat.id, "code": cat.code, "name": cat.names.get(lang) or cat.names.get("en")} if cat else None,
        "department": {"id": dept.id, "code": dept.code, "name": dept.names.get(lang) or dept.names.get("en")} if dept else None,
        "jurisdiction": {"id": jur.id, "name": jur.name, "demo_boundary": jur.is_demo_boundary} if jur else None,
        "location_text": g.location_text if show_text else "", "has_gps": g.lat is not None,
        "created_at": iso(g.created_at), "updated_at": iso(g.updated_at), "sla_due_at": iso(g.sla_due_at),
        "first_response_due_at": iso(g.first_response_due_at), "first_response_at": iso(g.first_response_at),
        "resolved_at": iso(g.resolved_at), "closed_at": iso(g.closed_at), "sla": sla_state(g),
        "escalation_level": g.escalation_level, "human_review_required": g.human_review_required,
        "master_incident": {"id": master.id, "public_id": master.public_id} if master else None,
        "assigned_officer": officer.full_name if officer else None,
        "assigned_officer_designation": (officer.designation or "") if officer else "",
        "assignment_notice": (f"This complaint has been assigned to {officer_label(db, officer)}." if officer else
                              ("This complaint is being reviewed by the nodal officer, who will assign it to the "
                               "responsible department." if g.status == "human_review" else "")),
        "reopen_count": g.reopen_count,
        "citizen_rating": g.citizen_rating, "is_demo": g.is_demo,
        "contact_name": g.contact_name if show_pii else mask_name(g.contact_name),
        "contact_phone": g.contact_phone if show_pii else mask_phone(g.contact_phone),
        "contact_masked": not show_pii,
        "joint_departments": [d.names.get("en") for d in (db.get(Department, i) for i in g.joint_department_ids or []) if d],
    }
    if detail:
        data["original_text"] = (g.original_text if show_pii else redact_text(g.original_text)) if show_text else None
        data["resolution_note"] = g.resolution_note
        data["citizen_feedback"] = g.citizen_feedback if (owner or (viewer and viewer.role != "citizen")) else ""
        evq = select(TicketEvent).where(TicketEvent.grievance_id == g.id).order_by(TicketEvent.created_at)
        if viewer is None or viewer.role == "citizen":
            evq = evq.where(TicketEvent.public.is_(True))
        data["events"] = [{"type": e.event_type, "note": e.note, "from": e.from_status, "to": e.to_status,
                           "actor_role": e.actor_role, "at": iso(e.created_at), "public": e.public,
                           "data": e.data if viewer and viewer.role != "citizen" else {}}
                          for e in db.execute(evq).scalars()]
        atts = db.execute(select(Attachment).where(Attachment.grievance_id == g.id)).scalars().all()
        data["attachments"] = [{"id": a.id, "kind": a.kind, "filename": a.filename, "content_type": a.content_type,
                                "size": a.size, "created_at": iso(a.created_at)} for a in atts]
        kinds = {a.kind for a in atts}
        data["photo_verification"] = ("before_and_after" if {"before", "after"} <= kinds else
                                      "after_only" if "after" in kinds else "none")
    return data
