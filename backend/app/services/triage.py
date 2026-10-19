"""Complaint understanding & triage pipeline.

input -> language detection -> (translation if configured) -> classification -> entity/location extraction
-> deterministic urgency/safety rules -> confidence evaluation -> department/jurisdiction routing
-> SLA calculation -> schema validation against registries -> structured response (ticket created only
after the citizen confirms).
"""
import math
import re
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..data.lexicon import EMERGENCY_RULES, LEXICON, LEXICON_VERSION, RISK_RULES
from ..db import iso, utcnow
from ..models import Category, Department, SlaPolicy, Tenant, TriageRecord
from . import llm
from .geo import extract_location_text, resolve_jurisdiction
from .language import detect_language, looks_like_gibberish

PRIORITIES = ["Low", "Medium", "High", "Emergency"]
EMERGENCY_CATEGORY_BOOST = {"R-EMG-01": "power_hazard", "R-EMG-02": "power_hazard", "R-EMG-03": "fire",
                            "R-EMG-04": "fire", "R-EMG-05": "storm_drain"}


class TriageError(Exception):
    pass


class TriageOutput(BaseModel):
    """Structured triage schema. Anything the pipeline/LLM returns must validate against this."""
    language: str = Field(min_length=2, max_length=10)
    language_detection: dict
    department_id: str | None
    department_code: str | None
    department_name: str | None
    category_id: str | None
    category_code: str | None
    category_name: str | None
    subcategory: str | None = None
    priority: Literal["Low", "Medium", "High", "Emergency"] | None
    confidence: float = Field(ge=0.0, le=1.0)
    location_text: str = ""
    coordinates: dict | None = None
    jurisdiction_id: str | None = None
    jurisdiction_name: str | None = None
    jurisdiction_method: str
    summary: str
    recommended_action: str
    sla_policy_id: str | None
    sla_hours: float | None
    sla_due_preview: str | None
    reasoning_summary: list[str]
    matched_terms: list[dict]
    rules_applied: list[dict]
    evidence_sources: list[str]
    human_review_required: bool
    human_review_reason: str | None = None
    emergency: bool = False
    safety_message: str | None = None
    provider: str
    model_version: str
    ai_mode_label: str
    triage_id: str | None = None

    @field_validator("summary")
    @classmethod
    def _summary_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("summary must not be empty")
        return v


def _matches(pattern: str, text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(pattern, text, flags=re.IGNORECASE)]


def classify_rule_based(text: str) -> dict:
    """Deterministic, explainable scoring over the versioned lexicon."""
    scores: dict[str, float] = {}
    matched: list[dict] = []
    for code, patterns in LEXICON.items():
        for pattern, weight, lang in patterns:
            found = _matches(pattern, text)
            if found:
                scores[code] = scores.get(code, 0.0) + weight
                matched.append({"category": code, "term": found[0], "weight": weight, "lexicon_language": lang})
    emergency_hits = []
    for rule_id, pattern, label in EMERGENCY_RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            emergency_hits.append({"rule": rule_id, "label": label})
            boost = EMERGENCY_CATEGORY_BOOST.get(rule_id)
            if boost and boost in scores:
                scores[boost] += 3.0
            elif boost:
                scores[boost] = 3.0
    risk_hits = [{"rule": r, "label": label} for r, p, label in RISK_RULES if re.search(p, text, flags=re.IGNORECASE)]
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return {"category": None, "confidence": 0.0, "scores": {}, "matched": matched,
                "emergency": emergency_hits, "risk": risk_hits, "runner_up": None}
    top, s1 = ranked[0]
    s2 = ranked[1][1] if len(ranked) > 1 else 0.0
    strength = 1 - math.exp(-s1 / 2.0)
    margin = (s1 - s2) / s1
    confidence = round(strength * (0.6 + 0.4 * margin), 2)
    return {"category": top, "confidence": confidence, "scores": dict(ranked), "matched": matched,
            "emergency": emergency_hits, "risk": risk_hits, "runner_up": ranked[1][0] if len(ranked) > 1 else None}


def _llm_classify(text: str, categories: list[Category], language: str) -> dict:
    codes = {c.code: c.names.get("en", c.code) for c in categories}
    system = ("You classify Indian municipal citizen complaints. Reply ONLY with JSON: "
              '{"category_code": one of the allowed codes or "unknown", "confidence": 0..1, '
              '"location_text": string, "summary_en": string (<=200 chars), "reasons": [short strings]}. '
              "Never invent departments, wards, phone numbers or SLA values.")
    user = f"Allowed codes: {codes}\nLanguage: {language}\nComplaint: {text}"
    data = llm.chat_json(system, user)
    if not isinstance(data, dict) or "category_code" not in data or "confidence" not in data:
        raise llm.LLMError("LLM output failed schema validation (missing keys)")
    if data["category_code"] != "unknown" and data["category_code"] not in codes:
        raise llm.LLMError("LLM returned a category that is not in the registry")
    try:
        conf = float(data["confidence"])
    except (TypeError, ValueError) as exc:
        raise llm.LLMError("LLM confidence is not a number") from exc
    if not 0 <= conf <= 1:
        raise llm.LLMError("LLM confidence out of range")
    return data


def run_triage(db: Session, tenant: Tenant, text: str, *, language_hint: str | None = None,
               lat: float | None = None, lng: float | None = None, location_text: str = "",
               input_mode: str = "text", persist: bool = True) -> TriageOutput:
    settings = get_settings()
    text = (text or "").strip()
    if not text:
        raise TriageError("Complaint text is empty")
    if len(text) > 4000:
        raise TriageError("Complaint text is too long (max 4000 characters)")

    detection = detect_language(text, language_hint)
    language = detection["code"] if detection["code"] != "und" else (language_hint or tenant.default_language)
    reasons: list[str] = []
    rules: list[dict] = []
    evidence = [f"lexicon:{LEXICON_VERSION}", f"sla-policy-table:tenant={tenant.code}",
                f"department-registry:tenant={tenant.code}"]

    categories = db.execute(select(Category).where(Category.tenant_id == tenant.id, Category.active.is_(True))).scalars().all()
    by_code = {c.code: c for c in categories}

    rb = classify_rule_based(text)
    provider, model_version = "rule-based-demo", LEXICON_VERSION
    ai_mode_label = "Automatic routing engine (lexicon classifier with safety rules)"
    category_code, confidence = rb["category"], rb["confidence"]
    llm_summary = None
    if settings.ai_mode == "llm":
        provider, model_version = settings.llm_provider, settings.llm_model
        ai_mode_label = f"LLM classifier ({settings.llm_model}) validated against registry + deterministic safety rules"
        try:
            out = _llm_classify(text, categories, language)
        except llm.LLMError as exc:
            # Never fall back silently: surface the failure to the caller.
            raise TriageError(f"AI provider error: {exc}") from exc
        category_code = None if out["category_code"] == "unknown" else out["category_code"]
        confidence = round(float(out["confidence"]), 2)
        llm_summary = out.get("summary_en")
        reasons += [str(r)[:160] for r in out.get("reasons", [])][:5]
        if out.get("location_text") and not location_text:
            location_text = str(out["location_text"])[:200]

    human_reason = None
    gib = looks_like_gibberish(text)
    if gib:
        human_reason = "Text could not be understood (looks like gibberish or is too short)."
        category_code, confidence = None, 0.0
    elif category_code is None:
        if detection["code"] not in {"en", "hi", "kn", "ta"} and not settings.translation_provider:
            human_reason = (f"Detected language '{detection['code']}' has no triage support in this build and no "
                            "translation provider is configured.")
        else:
            human_reason = "No known complaint category matched this text."
    elif category_code not in by_code:
        human_reason = f"Category '{category_code}' is not configured for this tenant."
        category_code = None

    threshold = settings.triage_confidence_threshold
    if category_code and confidence < threshold:
        human_reason = f"Confidence {confidence:.2f} is below the auto-routing threshold {threshold:.2f}."
    rules.append({"rule": "R-CONF-01", "label": f"Auto-route only if confidence >= {threshold:.2f}",
                  "outcome": "auto-route" if (category_code and not human_reason) else "human review"})

    if rb["matched"] and provider == "rule-based-demo":
        top_terms = [m for m in rb["matched"] if m["category"] == category_code][:4]
        if top_terms:
            reasons.append("Key words in the description: " + ", ".join(f"'{m['term']}'" for m in top_terms))
        if rb["runner_up"]:
            ru = by_code.get(rb["runner_up"])
            ru_name = ru.names.get("en", rb["runner_up"]) if ru else rb["runner_up"]
            reasons.append(f"Also considered: {ru_name}" if category_code else
                           f"Description is unclear (closest match: {ru_name}) - a nodal officer will review it")

    cat = by_code.get(category_code) if category_code else None
    dept = db.get(Department, cat.department_id) if cat else None

    # Priority: category default, then deterministic risk and safety rules (never lowered).
    priority = cat.default_priority if cat else None
    if cat:
        rules.append({"rule": "R-PRI-00", "label": f"Category default priority = {cat.default_priority}", "outcome": priority})
    for hit in rb["risk"]:
        if priority in {"Low", "Medium"}:
            priority = "High"
            rules.append({"rule": hit["rule"], "label": hit["label"], "outcome": "raised to High"})
        else:
            rules.append({"rule": hit["rule"], "label": hit["label"], "outcome": "no change"})
    emergency = bool(rb["emergency"])
    safety_message = None
    if emergency:
        priority = "Emergency"
        for hit in rb["emergency"]:
            rules.append({"rule": hit["rule"], "label": hit["label"], "outcome": "Emergency priority"})
        contacts = ", ".join(f"{c['label']}: {c['number']}" for c in tenant.emergency_contacts) or "local emergency services"
        safety_message = ("Possible danger to life or property. Stay away from the hazard. This portal is NOT an "
                          f"emergency service - if anyone is at risk, call {contacts} now.")
        if not cat:
            human_reason = (human_reason or "") + " Emergency keywords detected; a nodal officer must route this immediately."

    # Location & jurisdiction (never a default ward)
    loc = location_text or extract_location_text(text)
    jur, jur_method = resolve_jurisdiction(db, tenant.id, lat, lng, f"{loc} {text}")
    if not jur:
        reasons.append("Ward/zone not determined - add a GPS pin or a known locality name.")

    sla = None
    if priority:
        sla = db.execute(select(SlaPolicy).where(SlaPolicy.tenant_id == tenant.id,
                                                 SlaPolicy.priority == priority)).scalar_one_or_none()
    human_required = human_reason is not None
    if cat and not human_required:
        action = f"Route to {dept.names.get('en', dept.code)} queue" + (f" ({jur.name})" if jur else " (ward to be confirmed)")
    elif emergency:
        action = "Escalate to nodal officer for immediate manual routing"
    else:
        action = "Send to human triage queue (no automatic assignment)"

    snippet = text if len(text) <= 160 else text[:157] + "..."
    if llm_summary:
        summary = llm_summary[:300]
    elif cat:
        summary = f"{cat.names.get('en', cat.code)}" + (f" at {loc}" if loc else "") + f" - \"{snippet}\""
    else:
        summary = f"Unclassified report - \"{snippet}\""

    payload = {
        "language": language, "language_detection": detection,
        "department_id": dept.id if (dept and not human_required) else None,
        "department_code": dept.code if dept else None,
        "department_name": (dept.names.get(language) or dept.names.get("en")) if dept else None,
        "category_id": cat.id if cat else None, "category_code": cat.code if cat else None,
        "category_name": (cat.names.get(language) or cat.names.get("en")) if cat else None,
        "subcategory": None, "priority": priority, "confidence": confidence,
        "location_text": loc, "coordinates": {"lat": lat, "lng": lng} if lat is not None and lng is not None else None,
        "jurisdiction_id": jur.id if jur else None, "jurisdiction_name": jur.name if jur else None,
        "jurisdiction_method": jur_method, "summary": summary, "recommended_action": action,
        "sla_policy_id": sla.id if sla else None, "sla_hours": sla.resolve_hours if sla else None,
        "sla_due_preview": iso(utcnow() + timedelta(hours=sla.resolve_hours)) if sla else None,
        "reasoning_summary": reasons, "matched_terms": rb["matched"] if provider == "rule-based-demo" else [],
        "rules_applied": rules, "evidence_sources": evidence, "human_review_required": human_required,
        "human_review_reason": human_reason.strip() if human_reason else None, "emergency": emergency,
        "safety_message": safety_message, "provider": provider, "model_version": model_version,
        "ai_mode_label": ai_mode_label,
    }
    try:
        result = TriageOutput(**payload)
    except ValidationError as exc:
        raise TriageError(f"Triage output failed schema validation: {exc.errors()[0]['msg']}") from exc
    # Registry validation (the pipeline may not invent IDs)
    if result.department_id and not db.get(Department, result.department_id):
        raise TriageError("Triage referenced an unknown department")

    if not persist:
        return result
    rec = TriageRecord(tenant_id=tenant.id, input_text=text, input_language=language, output=result.model_dump(),
                       provider=provider, model_version=model_version, confidence=confidence,
                       rules_applied=rules, valid=True)
    db.add(rec)
    db.flush()
    result.triage_id = rec.id
    rec.output = result.model_dump()
    return result
