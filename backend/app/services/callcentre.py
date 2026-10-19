"""Call-centre helpers (PS2): telephony adapter boundary, simulated sessions, summaries, QA rubric."""
import re
from abc import ABC, abstractmethod

from ..config import get_settings

DISPOSITIONS = {
    "grievance_registered": "Grievance registered",
    "information_provided": "Information provided (cited)",
    "status_enquiry": "Status enquiry answered",
    "callback_scheduled": "Callback scheduled",
    "transferred_to_supervisor": "Warm handoff to supervisor",
    "referred_emergency": "Referred to emergency services",
    "dropped": "Call dropped / no response",
    "out_of_scope": "Out of scope - referred",
}

QA_RUBRIC = [
    {"id": "greeting", "label": "Greeting and self-identification", "max": 2},
    {"id": "verification", "label": "Caller identity / consent confirmed without exposing PII", "max": 2},
    {"id": "accuracy", "label": "Information given matches a cited, verified source", "max": 2},
    {"id": "empathy", "label": "Courtesy and empathy", "max": 2},
    {"id": "resolution", "label": "Correct action / ticket / disposition", "max": 2},
    {"id": "closure", "label": "Next steps and ticket ID read back", "max": 2},
]

# Demo scripts for the clearly-labelled simulated call session.
DEMO_CALLS = [
    {"language": "kn", "caller_name": "Shivakumar B.", "caller_phone": "9000000101", "lines": [
        ("caller", "ನಮಸ್ಕಾರ, ನಮ್ಮ ರಸ್ತೆಯಲ್ಲಿ ಬೀದಿ ದೀಪ ಮೂರು ದಿನಗಳಿಂದ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ."),
        ("caller", "Jayanagar 4th Block ಹತ್ತಿರ, ರಾತ್ರಿ ತುಂಬಾ ಕತ್ತಲು."),
    ]},
    {"language": "en", "caller_name": "Meera Joshi", "caller_phone": "9000000102", "lines": [
        ("caller", "Hello, dirty water is coming from the tap in Indiranagar since yesterday."),
        ("caller", "My children are falling sick, please send someone urgently."),
    ]},
    {"language": "hi", "caller_name": "Rajesh Verma", "caller_phone": "9000000103", "lines": [
        ("caller", "नमस्ते, मुझे गृह लक्ष्मी योजना के बारे में जानकारी चाहिए।"),
        ("caller", "Gruha Lakshmi scheme eligibility kya hai?"),
    ]},
    {"language": "en", "caller_name": "Asha Thomas", "caller_phone": "9000000104", "lines": [
        ("caller", "There is a transformer sparking near the houses on 2nd Main, Koramangala!"),
        ("caller", "People are standing very close, it is dangerous."),
    ]},
]

POS = {"thank", "thanks", "good", "resolved", "great", "ಧನ್ಯವಾದ", "धन्यवाद", "நன்றி"}
NEG = {"angry", "worst", "urgent", "urgently", "sick", "dangerous", "again", "no one", "nobody", "terrible", "useless",
       "frustrated", "complain", "complaint", "since"}


def sentiment(lines: list[dict]) -> str:
    text = " ".join(l["text"].lower() for l in lines if l.get("speaker") == "caller")
    pos = sum(text.count(w) for w in POS)
    neg = sum(text.count(w) for w in NEG)
    if neg >= pos + 2:
        return "distressed"
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def summarize_call(lines: list[dict], triage: dict | None, kb_hits: list[dict]) -> tuple[str, list[str]]:
    caller_text = " ".join(l["text"] for l in lines if l.get("speaker") == "caller")
    parts = []
    if triage and triage.get("category_name"):
        parts.append(f"Caller reported: {triage['category_name']}"
                     + (f" at {triage['location_text']}" if triage.get("location_text") else "")
                     + f" (priority {triage.get('priority')}).")
    elif caller_text:
        parts.append("Caller query: " + (caller_text[:200] + ("..." if len(caller_text) > 200 else "")))
    if kb_hits:
        parts.append("Information referenced: " + "; ".join(f"{h['title']} v{h['version']}" for h in kb_hits[:2]) + ".")
    actions = []
    if triage and triage.get("emergency"):
        actions.append("Advise caller to contact emergency services; flag ticket as Emergency.")
    if triage and triage.get("category_code") and not triage.get("human_review_required"):
        actions.append(f"Create grievance for {triage.get('department_name')} (check duplicates first).")
    elif triage and triage.get("human_review_required"):
        actions.append("Route to human triage - category unclear.")
    if kb_hits:
        actions.append("Share cited source with caller; note it may need official verification.")
    if re.search(r"call (me )?back|callback|later", caller_text, re.I):
        actions.append("Schedule a callback.")
    return " ".join(parts) or "No content captured.", actions or ["Confirm caller need and choose a disposition."]


class TelephonyProvider(ABC):
    """Adapter boundary for SIP/WebRTC/Asterisk or an approved CPaaS provider."""
    name = "abstract"
    simulated = False

    @abstractmethod
    def status(self) -> dict: ...


class SimulatedTelephony(TelephonyProvider):
    name = "simulated"
    simulated = True

    def status(self) -> dict:
        return {"provider": self.name, "state": "simulated",
                "message": "No telephony provider configured. Calls in the agent hub are clearly-labelled simulations."}


def telephony() -> TelephonyProvider:
    s = get_settings()
    _ = s  # real providers would be selected from TELEPHONY_PROVIDER here
    return SimulatedTelephony()
