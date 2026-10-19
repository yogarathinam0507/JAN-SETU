"""Unified call-centre agent hub (PS2). Telephony/WhatsApp/email channels are SIMULATED unless a provider
is configured; simulated interactions are flagged and labelled everywhere."""
import random
import statistics
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, iso, utcnow
from ..models import Grievance, Interaction, Tenant, User
from ..security import require, require_any
from ..services import audit, callcentre, kb, workflow
from ..services.masking import mask_name, mask_phone
from ..services.triage import TriageError, run_triage

router = APIRouter(prefix="/api/agent", tags=["call centre"])
agent_user = require("interaction:work")


def _wait_seconds(i: Interaction) -> int:
    end = i.started_at or utcnow()
    return int((end - i.queued_at).total_seconds())


def _out(db: Session, i: Interaction, viewer: User, detail: bool = False) -> dict:
    agent = db.get(User, i.agent_id) if i.agent_id else None
    g = db.get(Grievance, i.grievance_id) if i.grievance_id else None
    d = {"id": i.id, "public_id": i.public_id, "channel": i.channel, "status": i.status, "priority": i.priority,
         "language": i.language, "caller_name": mask_name(i.caller_name), "caller_phone": mask_phone(i.caller_phone),
         "agent": agent.full_name if agent else None, "queued_at": iso(i.queued_at), "started_at": iso(i.started_at),
         "ended_at": iso(i.ended_at), "wait_seconds": _wait_seconds(i), "disposition": i.disposition,
         "callback_at": iso(i.callback_at), "grievance": g.public_id if g else None, "simulated": i.simulated,
         "practice": bool(i.simulated and any((x or {}).get("source") == "simulated-script" for x in (i.transcript or []))),
         "channel_label": ("Practice call - " if i.simulated and any((x or {}).get("source") == "simulated-script"
                                                                    for x in (i.transcript or [])) else "")
                          + i.channel.replace("_", " ")}
    if detail:
        d.update({"transcript": i.transcript, "summary": i.summary, "action_items": i.action_items,
                  "sentiment": i.sentiment, "qa_review": i.qa_review, "handoff_history": i.handoff_history,
                  "transcript_expires_at": iso(i.transcript_expires_at)})
    return d


def _get(db: Session, user: User, iid: str) -> Interaction:
    i = db.get(Interaction, iid)
    if not i or i.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Interaction not found."})
    if user.role == "agent" and i.agent_id not in (None, user.id) and i.status != "queued":
        raise HTTPException(404, detail={"code": "not_found", "message": "Interaction not found."})
    return i


@router.get("/queue")
def queue(user: User = Depends(agent_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id,
                                                Interaction.status.in_(["queued", "active", "wrap_up"]))).scalars().all()
    pr = {"Emergency": 0, "High": 1, "Medium": 2, "Low": 3}
    queued = sorted([i for i in rows if i.status == "queued"], key=lambda i: (pr.get(i.priority, 9), i.queued_at))
    mine = [i for i in rows if i.status != "queued" and i.agent_id == user.id]
    callbacks = db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id,
                                                     Interaction.callback_at.is_not(None),
                                                     Interaction.callback_at >= utcnow() - timedelta(hours=1))
                           .order_by(Interaction.callback_at)).scalars().all()
    waits = [_wait_seconds(i) for i in queued]
    return {"queued": [_out(db, i, user) for i in queued], "mine": [_out(db, i, user) for i in mine],
            "callbacks": [_out(db, i, user) for i in callbacks if i.agent_id in (None, user.id)],
            "stats": {"queued": len(queued), "longest_wait_seconds": max(waits) if waits else 0,
                      "avg_wait_seconds": int(statistics.mean(waits)) if waits else 0},
            "telephony": callcentre.telephony().status()}


class SimIn(BaseModel):
    script: int | None = Field(None, ge=0, le=len(callcentre.DEMO_CALLS) - 1)


@router.post("/simulate-call", status_code=201)
def simulate_call(body: SimIn, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    """Creates a clearly-labelled SIMULATED inbound call with a scripted transcript (no telephony involved)."""
    script = callcentre.DEMO_CALLS[body.script if body.script is not None else random.randrange(len(callcentre.DEMO_CALLS))]
    now = utcnow()
    i = Interaction(tenant_id=user.tenant_id, channel="voice", caller_name=script["caller_name"],
                    caller_phone=script["caller_phone"], language=script["language"], status="queued", simulated=True,
                    queued_at=now, transcript_expires_at=now + timedelta(days=get_settings().transcript_retention_days),
                    transcript=[{"speaker": s, "text": t, "at": iso(now), "source": "simulated-script"} for s, t in script["lines"]])
    tenant = db.get(Tenant, user.tenant_id)
    try:
        tri = run_triage(db, tenant, " ".join(t for s, t in script["lines"] if s == "caller"), persist=False)
        i.priority = tri.priority or "Medium"
    except TriageError:
        i.priority = "Medium"
    db.add(i)
    db.commit()
    return _out(db, i, user, detail=True)


class InteractionIn(BaseModel):
    channel: str = Field(pattern="^(voice|web_chat|email|whatsapp)$")
    caller_name: str = Field("", max_length=120)
    caller_phone: str = Field("", pattern=r"^$|^[6-9]\d{9}$")
    language: str = Field("en", max_length=10)
    first_message: str = Field("", max_length=2000)


@router.post("/interactions", status_code=201)
def create_interaction(body: InteractionIn, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    """Manual record of an interaction (e.g. a call on a desk phone). Channels without a configured provider are
    recorded as simulated."""
    s = get_settings()
    real = (body.channel == "whatsapp" and s.whatsapp_provider) or (body.channel == "voice" and False)
    now = utcnow()
    i = Interaction(tenant_id=user.tenant_id, channel=body.channel, caller_name=body.caller_name,
                    caller_phone=body.caller_phone, language=body.language, status="active", agent_id=user.id,
                    queued_at=now, started_at=now, simulated=not real,
                    transcript_expires_at=now + timedelta(days=s.transcript_retention_days),
                    transcript=[{"speaker": "caller", "text": body.first_message, "at": iso(now), "source": "agent-entered"}]
                    if body.first_message else [])
    db.add(i)
    db.commit()
    return _out(db, i, user, detail=True)


@router.get("/interactions/{iid}")
def get_interaction(iid: str, user: User = Depends(require_any("interaction:work", "interaction:supervise")),
                    db: Session = Depends(get_db)):
    return _out(db, _get(db, user, iid), user, detail=True)


@router.post("/interactions/{iid}/accept")
def accept(iid: str, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    if i.status != "queued":
        raise HTTPException(409, detail={"code": "not_queued", "message": "Already picked up."})
    i.status, i.agent_id, i.started_at = "active", user.id, utcnow()
    audit.record(db, actor=user, action="interaction.accept", entity_type="interaction", entity_id=i.public_id)
    db.commit()
    return _out(db, i, user, detail=True)


class LineIn(BaseModel):
    speaker: str = Field(pattern="^(caller|agent)$")
    text: str = Field(min_length=1, max_length=2000)


@router.post("/interactions/{iid}/transcript")
def add_line(iid: str, body: LineIn, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    if i.status not in {"active", "wrap_up"} or i.agent_id != user.id:
        raise HTTPException(409, detail={"code": "not_active", "message": "Accept the interaction first."})
    i.transcript = [*i.transcript, {"speaker": body.speaker, "text": body.text, "at": iso(utcnow()), "source": "agent-entered"}]
    db.commit()
    return _out(db, i, user, detail=True)


@router.get("/interactions/{iid}/assist")
def assist(iid: str, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    caller_text = " ".join(l["text"] for l in i.transcript if l["speaker"] == "caller")
    tenant = db.get(Tenant, user.tenant_id)
    triage, triage_error = None, None
    if caller_text.strip():
        try:
            triage = run_triage(db, tenant, caller_text, language_hint=i.language, persist=False).model_dump()
        except TriageError as exc:
            triage_error = str(exc)
    hits = kb.search(db, user.tenant_id, caller_text) if caller_text else []
    summary, actions = callcentre.summarize_call(i.transcript, triage, hits)
    dup = None
    if triage and triage.get("category_id"):
        probe = Grievance(tenant_id=user.tenant_id, category_id=triage["category_id"],
                          jurisdiction_id=triage.get("jurisdiction_id"), original_text=caller_text, id="probe")
        found = workflow.find_duplicate(db, probe)
        if found:
            dup = {"public_id": found[0].public_id, "status": found[0].status, **found[1]}
    next_actions = []
    if triage and triage.get("emergency"):
        next_actions.append({"action": "safety", "label": "Read the safety advice and give emergency numbers"})
    if triage and not triage.get("human_review_required"):
        next_actions.append({"action": "create_ticket", "label": f"Create ticket for {triage.get('department_name')}"})
    if hits:
        next_actions.append({"action": "share_info", "label": "Share cited information"})
    next_actions.append({"action": "callback", "label": "Schedule callback"})
    next_actions.append({"action": "handoff", "label": "Warm handoff to supervisor"})
    return {"triage": triage, "triage_error": triage_error, "knowledge": hits, "summary": summary, "action_items": actions,
            "sentiment": callcentre.sentiment(i.transcript), "duplicate_candidate": dup, "next_actions": next_actions,
            "dispositions": callcentre.DISPOSITIONS,
            "ai_label": "AI suggestions are advisory. Verify before reading to the caller; never state unverified scheme rules as fact."}


class TicketIn(BaseModel):
    text: str | None = Field(None, max_length=4000)
    location_text: str = Field("", max_length=300)
    consent_confirmed_verbally: bool = False
    link_to_existing: str | None = None


@router.post("/interactions/{iid}/create-ticket", status_code=201)
def create_ticket(iid: str, body: TicketIn, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    if i.grievance_id:
        raise HTTPException(409, detail={"code": "already_linked", "message": "This interaction already has a ticket."})
    if body.link_to_existing:
        g = db.execute(select(Grievance).where(Grievance.public_id == body.link_to_existing,
                                               Grievance.tenant_id == user.tenant_id)).scalar_one_or_none()
        if not g:
            raise HTTPException(404, detail={"code": "not_found", "message": "Ticket not found."})
        i.grievance_id = g.id
        workflow.add_event(db, g, user, "public_update", "Another caller reported the same issue via the call centre.")
        db.commit()
        return {"linked": True, "grievance": workflow.serialize(db, g, user)}
    text = (body.text or " ".join(l["text"] for l in i.transcript if l["speaker"] == "caller")).strip()
    if not text:
        raise HTTPException(422, detail={"code": "empty", "message": "No caller statement to file."})
    tenant = db.get(Tenant, user.tenant_id)
    try:
        triage = run_triage(db, tenant, text, language_hint=i.language, location_text=body.location_text).model_dump()
    except TriageError as exc:
        raise HTTPException(502, detail={"code": "triage_failed", "message": str(exc), "retry": True})
    g = workflow.create_grievance(db, tenant_id=user.tenant_id, triage=triage, text=text, actor=user, citizen=None,
                                  channel="voice" if i.channel == "voice" else i.channel, input_mode="text",
                                  transcript_confirmed=True, contact_name=i.caller_name, contact_phone=i.caller_phone,
                                  lat=None, lng=None, location_text=body.location_text,
                                  consent=body.consent_confirmed_verbally)
    i.grievance_id = g.id
    db.commit()
    return {"linked": False, "grievance": workflow.serialize(db, g, user, detail=True)}


class WrapIn(BaseModel):
    disposition: str
    summary: str = Field("", max_length=3000)
    action_items: list[str] = Field(default_factory=list, max_length=20)
    callback_at: datetime | None = None


@router.post("/interactions/{iid}/wrap")
def wrap(iid: str, body: WrapIn, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    if body.disposition not in callcentre.DISPOSITIONS:
        raise HTTPException(422, detail={"code": "invalid_disposition", "message": "Choose a valid disposition."})
    if body.disposition == "callback_scheduled" and not body.callback_at:
        raise HTTPException(422, detail={"code": "callback_time_required", "message": "Pick a callback time."})
    i.disposition, i.summary, i.action_items = body.disposition, body.summary, body.action_items
    i.sentiment = callcentre.sentiment(i.transcript)
    i.callback_at = body.callback_at.replace(tzinfo=None) if body.callback_at else None
    i.status, i.ended_at = "closed", utcnow()
    audit.record(db, actor=user, action="interaction.wrap", entity_type="interaction", entity_id=i.public_id,
                 after={"disposition": i.disposition, "callback_at": iso(i.callback_at)})
    db.commit()
    return _out(db, i, user, detail=True)


class HandoffIn(BaseModel):
    to_agent_id: str | None = None
    note: str = Field(min_length=3, max_length=500)


@router.post("/interactions/{iid}/handoff")
def handoff(iid: str, body: HandoffIn, user: User = Depends(agent_user), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    target = db.get(User, body.to_agent_id) if body.to_agent_id else None
    if body.to_agent_id and (not target or target.tenant_id != user.tenant_id or target.role != "agent"):
        raise HTTPException(422, detail={"code": "invalid_target", "message": "Choose an agent in your tenant."})
    i.handoff_history = [*i.handoff_history, {"from": user.full_name, "to": target.full_name if target else "Supervisor queue",
                                               "note": body.note, "at": iso(utcnow()),
                                               "context": "transcript + AI summary transferred"}]
    i.agent_id = target.id if target else None
    i.status = "active" if target else "queued"
    i.priority = i.priority if target else "High"
    audit.record(db, actor=user, action="interaction.handoff", entity_type="interaction", entity_id=i.public_id,
                 reason=body.note)
    db.commit()
    return _out(db, i, user, detail=True)


class RevealIn(BaseModel):
    reason: str = Field(min_length=10, max_length=300)


@router.post("/interactions/{iid}/reveal")
def reveal(iid: str, body: RevealIn, user: User = Depends(require("contact:reveal")), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    audit.record(db, actor=user, action="pii.reveal_caller", entity_type="interaction", entity_id=i.public_id,
                 reason=body.reason)
    db.commit()
    return {"caller_name": i.caller_name, "caller_phone": i.caller_phone, "audited": True}


@router.get("/agents")
def agents(user: User = Depends(agent_user), db: Session = Depends(get_db)):
    return [{"id": u.id, "name": u.full_name} for u in db.execute(
        select(User).where(User.tenant_id == user.tenant_id, User.role == "agent", User.id != user.id)).scalars()]


@router.get("/supervisor")
def supervisor(user: User = Depends(require("interaction:supervise")), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=7)
    rows = db.execute(select(Interaction).where(Interaction.tenant_id == user.tenant_id,
                                                Interaction.queued_at >= since)).scalars().all()
    waits = [_wait_seconds(i) for i in rows if i.started_at]
    per_agent = Counter(db.get(User, i.agent_id).full_name for i in rows if i.agent_id)
    reviewed = [i.qa_review["percent"] for i in rows if i.qa_review]
    return {"window": "last 7 days", "data_label": "Includes simulated interactions" if any(i.simulated for i in rows) else "",
            "total": len(rows), "simulated": sum(1 for i in rows if i.simulated),
            "by_status": dict(Counter(i.status for i in rows)), "by_channel": dict(Counter(i.channel for i in rows)),
            "by_disposition": dict(Counter(i.disposition for i in rows if i.disposition)),
            "avg_wait_seconds": int(statistics.mean(waits)) if waits else None,
            "tickets_created": sum(1 for i in rows if i.grievance_id),
            "callbacks_scheduled": sum(1 for i in rows if i.callback_at),
            "per_agent": [{"agent": k, "interactions": v} for k, v in per_agent.most_common()],
            "qa": {"reviewed": len(reviewed), "avg_percent": round(statistics.mean(reviewed), 1) if reviewed else None,
                   "rubric": callcentre.QA_RUBRIC},
            "recent": [_out(db, i, user) for i in sorted(rows, key=lambda r: r.queued_at, reverse=True)[:30]]}


class QaIn(BaseModel):
    scores: dict[str, int]
    comments: str = Field("", max_length=1000)


@router.post("/interactions/{iid}/qa")
def qa_review(iid: str, body: QaIn, user: User = Depends(require("interaction:supervise")), db: Session = Depends(get_db)):
    i = _get(db, user, iid)
    if i.status != "closed":
        raise HTTPException(409, detail={"code": "not_closed", "message": "Review closed interactions only."})
    total = max_total = 0
    for item in callcentre.QA_RUBRIC:
        v = body.scores.get(item["id"])
        if v is None or not 0 <= v <= item["max"]:
            raise HTTPException(422, detail={"code": "invalid_score", "message": f"Score '{item['id']}' must be 0-{item['max']}."})
        total += v
        max_total += item["max"]
    i.qa_review = {"scores": body.scores, "total": total, "max": max_total, "percent": round(100 * total / max_total, 1),
                   "comments": body.comments, "reviewer": user.full_name, "at": iso(utcnow())}
    audit.record(db, actor=user, action="interaction.qa_review", entity_type="interaction", entity_id=i.public_id,
                 after={"percent": i.qa_review["percent"]})
    db.commit()
    return _out(db, i, user, detail=True)
