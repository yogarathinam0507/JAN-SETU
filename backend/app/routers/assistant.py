"""Multilingual citizen assistant and scheme navigator (PS5). Information assistance only - never an
official eligibility decision. Every factual answer cites its source or says verified information is unavailable."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db, iso, utcnow
from ..deps import resolve_tenant
from ..models import AssistantEvent, Interaction, Scheme, Tenant
from ..services import benefits, kb
from ..services.language import detect_language
from ..services.triage import TriageError, run_triage

router = APIRouter(prefix="/api", tags=["benefits & assistant"])

SERVICE_CATEGORIES = {
    "social_welfare": "Social welfare", "pensions": "Pensions", "women_child": "Women & child welfare",
    "health": "Health benefits", "education": "Education & scholarships", "labour": "Labour welfare",
    "housing": "Housing", "food": "Food & civil supplies", "agriculture": "Agriculture",
    "revenue": "Revenue & certificates", "public_works": "Public works", "energy": "Energy", "transport": "Transport",
}

PHRASES = {
    "en": {"complaint": "This sounds like a complaint about {cat}. I can file it for you - please review the details first.",
           "unknown": "I don't have verified information to answer that. You can ask a human helper or try different words.",
           "scheme": "Here is what I found about {name}. I'll ask a few questions to check if you may qualify.",
           "kb": "Here is what the knowledge base says (see source below):",
           "unclear": "I could not understand that clearly. Could you describe it in a few more words?"},
    "kn": {"complaint": "ಇದು {cat} ಕುರಿತ ದೂರು ಎನಿಸುತ್ತದೆ. ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ, ನಾನು ದೂರು ದಾಖಲಿಸಬಹುದು.",
           "unknown": "ಇದಕ್ಕೆ ಉತ್ತರಿಸಲು ಪರಿಶೀಲಿತ ಮಾಹಿತಿ ನನ್ನ ಬಳಿ ಇಲ್ಲ. ಸಹಾಯಕರೊಂದಿಗೆ ಮಾತನಾಡಬಹುದು.",
           "scheme": "{name} ಬಗ್ಗೆ ಸಿಕ್ಕ ಮಾಹಿತಿ ಇಲ್ಲಿದೆ. ನೀವು ಅರ್ಹರಾಗಿರಬಹುದೇ ಎಂದು ತಿಳಿಯಲು ಕೆಲವು ಪ್ರಶ್ನೆಗಳು.",
           "kb": "ಜ್ಞಾನ ಭಂಡಾರದಲ್ಲಿರುವ ಮಾಹಿತಿ (ಮೂಲವನ್ನು ಕೆಳಗೆ ನೋಡಿ):",
           "unclear": "ನನಗೆ ಸ್ಪಷ್ಟವಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಇನ್ನಷ್ಟು ವಿವರಿಸಬಹುದೇ?"},
    "hi": {"complaint": "यह {cat} से जुड़ी शिकायत लगती है। विवरण देखकर मैं शिकायत दर्ज कर सकता हूँ।",
           "unknown": "इसका उत्तर देने के लिए मेरे पास सत्यापित जानकारी नहीं है। आप मानव सहायक से बात कर सकते हैं।",
           "scheme": "{name} के बारे में जानकारी यहाँ है। पात्रता जाँचने के लिए कुछ प्रश्न पूछूँगा।",
           "kb": "ज्ञान आधार में यह जानकारी है (स्रोत नीचे देखें):",
           "unclear": "मैं स्पष्ट रूप से समझ नहीं पाया। कृपया थोड़ा और बताएँ।"},
    "ta": {"complaint": "இது {cat} தொடர்பான புகார் போல் தெரிகிறது. விவரங்களைச் சரிபார்த்து நான் பதிவு செய்யலாம்.",
           "unknown": "இதற்கு பதிலளிக்க சரிபார்க்கப்பட்ட தகவல் என்னிடம் இல்லை. மனித உதவியாளரிடம் பேசலாம்.",
           "scheme": "{name} பற்றிய தகவல் இதோ. நீங்கள் தகுதியானவரா என்று அறிய சில கேள்விகள்.",
           "kb": "அறிவுத் தளத்தில் உள்ள தகவல் (மூலம் கீழே):",
           "unclear": "எனக்கு தெளிவாகப் புரியவில்லை. இன்னும் கொஞ்சம் விளக்க முடியுமா?"},
}


def phrase(lang: str, key: str, **kw) -> tuple[str, bool]:
    if lang in PHRASES:
        return PHRASES[lang][key].format(**kw), False
    return PHRASES["en"][key].format(**kw), True  # translated=False -> caller shows notice


def scheme_out(s: Scheme, lang: str = "en", full: bool = False) -> dict:
    d = {"code": s.code, "name": s.names.get(lang) or s.names.get("en"), "names": s.names,
         "service_category": s.service_category, "service_category_name": SERVICE_CATEGORIES.get(s.service_category, s.service_category),
         "department": s.department, "summary": s.summary, "verified": s.verified, "version": s.version,
         "updated_at": iso(s.updated_at), "official_url": s.official_url or None,
         "label": "Verified against official source" if s.verified else "ILLUSTRATIVE seed content - needs official verification",
         "has_eligibility_check": bool(s.rules)}
    if full:
        d.update({"benefits": s.benefits, "documents": s.documents, "steps": s.steps, "questions": s.questions,
                  "source_note": s.source_note})
    return d


@router.get("/benefits/categories")
def categories():
    return [{"code": k, "name": v} for k, v in SERVICE_CATEGORIES.items()]


@router.get("/benefits/schemes")
def schemes(category: str | None = None, lang: str = "en", tenant: Tenant = Depends(resolve_tenant),
            db: Session = Depends(get_db)):
    q = select(Scheme).where(Scheme.tenant_id == tenant.id)
    if category:
        q = q.where(Scheme.service_category == category)
    return [scheme_out(s, lang) for s in db.execute(q.order_by(Scheme.service_category, Scheme.code)).scalars()]


@router.get("/benefits/schemes/{code}")
def scheme_detail(code: str, lang: str = "en", tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    s = db.execute(select(Scheme).where(Scheme.tenant_id == tenant.id, Scheme.code == code)).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail={"code": "not_found", "message": "Scheme not found."})
    return scheme_out(s, lang, full=True)


class CheckIn(BaseModel):
    answers: dict[str, str | float | int | bool | None]
    language: str = "en"


@router.post("/benefits/schemes/{code}/check")
def check(code: str, body: CheckIn, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    s = db.execute(select(Scheme).where(Scheme.tenant_id == tenant.id, Scheme.code == code)).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail={"code": "not_found", "message": "Scheme not found."})
    result = benefits.evaluate(s, body.answers)
    db.add(AssistantEvent(tenant_id=tenant.id, kind="eligibility_check", language=body.language, outcome=result["outcome"]))
    db.commit()
    return result


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: str = Field("en", max_length=10)


def _match_scheme(db: Session, tenant: Tenant, text: str) -> Scheme | None:
    low = text.lower()
    for s in db.execute(select(Scheme).where(Scheme.tenant_id == tenant.id)).scalars():
        names = [n for n in s.names.values()] + s.code.replace("_", " ").split("|")
        for n in names:
            n = (n or "").lower().strip()
            if len(n) >= 4 and n in low:
                return s
            compact = re.sub(r"\s+", "", n)
            if len(compact) >= 6 and compact in re.sub(r"\s+", "", low):
                return s
    return None


@router.post("/assistant/chat")
def chat(body: ChatIn, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    lang = body.language
    det = detect_language(body.message, lang)
    reply: dict = {"language": lang, "detected_language": det["code"], "citations": [], "actions": [],
                   "ai_mode": get_settings().ai_mode, "confidence": None}
    # 1. scheme / service questions
    s = _match_scheme(db, tenant, body.message)
    if s:
        text, untranslated = phrase(lang, "scheme", name=s.names.get(lang) or s.names.get("en"))
        reply.update({"type": "scheme", "text": text, "scheme": scheme_out(s, lang, full=True), "translation_missing": untranslated,
                      "confidence": "matched scheme name",
                      "limitations": "Scheme content is " + ("verified." if s.verified else "illustrative seed content and must be verified.")})
        reply["actions"].append({"type": "start_eligibility", "scheme": s.code})
        db.add(AssistantEvent(tenant_id=tenant.id, kind="chat", language=lang, outcome="scheme"))
        db.commit()
        return reply
    # 2. grievance-like statements
    tri = None
    try:
        tri = run_triage(db, tenant, body.message, language_hint=lang, persist=False)
    except TriageError:
        tri = None
    question_like = bool(re.search(r"\?|^(how|what|where|when|which|who|can|do|is|ಹೇಗೆ|ಏನು|कैसे|क्या|எப்படி|என்ன)\b", body.message.strip(), re.I))
    if tri and not tri.human_review_required and not question_like:
        text, untranslated = phrase(lang, "complaint", cat=tri.category_name)
        reply.update({"type": "grievance", "text": text, "triage": tri.model_dump(), "translation_missing": untranslated,
                      "confidence": tri.confidence})
        reply["actions"].append({"type": "file_grievance", "prefill": {"text": body.message, "language": lang}})
        db.add(AssistantEvent(tenant_id=tenant.id, kind="chat", language=lang, outcome="grievance_suggested"))
        db.commit()
        return reply
    # 3. knowledge base with citations
    hits = kb.search(db, tenant.id, body.message, k=3)
    if hits:
        text, untranslated = phrase(lang, "kb")
        reply.update({"type": "knowledge", "text": text, "answer_passages": [h["text"] for h in hits[:2]],
                      "citations": hits, "translation_missing": untranslated or any(h["language"] != lang for h in hits[:2]),
                      "confidence": f"retrieval score {hits[0]['score']}",
                      "limitations": "Answer is quoted from the cited document, not generated. "
                                     + ("Some sources are SAMPLE content needing verification." if any(not h["verified"] for h in hits) else "")})
        reply["actions"].append({"type": "human_help"})
        db.add(AssistantEvent(tenant_id=tenant.id, kind="chat", language=lang, outcome="kb_answer"))
        db.commit()
        return reply
    # 4. nothing verified
    key = "unclear" if tri and tri.human_review_required and "understood" in (tri.human_review_reason or "") else "unknown"
    text, untranslated = phrase(lang, key)
    reply.update({"type": "no_answer", "text": text, "translation_missing": untranslated,
                  "limitations": "No verified source matched. The assistant does not guess."})
    reply["actions"] += [{"type": "human_help"}, {"type": "file_grievance", "prefill": {"text": body.message, "language": lang}}]
    db.add(AssistantEvent(tenant_id=tenant.id, kind="chat", language=lang, outcome="no_answer"))
    db.commit()
    return reply


class CallbackIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    language: str = Field("en", max_length=10)
    topic: str = Field("", max_length=500)
    consent: bool


@router.post("/assistant/callback-request", status_code=201)
def callback_request(body: CallbackIn, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    """Assisted-service mode: a person asks a human to call back. Lands in the agent queue (a real record)."""
    if not body.consent:
        raise HTTPException(422, detail={"code": "consent_required", "message": "Consent is needed so we can call you."})
    i = Interaction(tenant_id=tenant.id, channel="callback_request", caller_name=body.name, caller_phone=body.phone,
                    language=body.language, status="queued", simulated=False, priority="Medium", queued_at=utcnow(),
                    transcript=[{"speaker": "caller", "text": body.topic or "(callback requested)", "at": iso(utcnow()),
                                 "source": "web-form"}])
    db.add(i)
    db.add(AssistantEvent(tenant_id=tenant.id, kind="human_referral", language=body.language, outcome="callback_request"))
    db.commit()
    return {"reference": i.public_id, "message": "Request received. A helper will call you. Keep this reference.",
            "note": "Call-back is placed by a human agent; telephony is not automated in this build."}
