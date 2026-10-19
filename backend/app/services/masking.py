"""Default masking of personal data in API responses and logs."""
import re

_PHONE = re.compile(r"(?<!\d)(\+?91[\s-]?)?([6-9]\d{9})(?!\d)")
_AADHAAR = re.compile(r"(?<!\d)(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "****"
    return "******" + digits[-4:]


def mask_name(name: str | None) -> str:
    if not name:
        return ""
    parts = name.split()
    return " ".join(p[0] + "•" * max(1, len(p) - 1) for p in parts)


def redact_text(text: str) -> str:
    """Remove phone numbers and 12-digit identifiers from free text."""
    if not text:
        return text
    text = _AADHAAR.sub("XXXX XXXX XXXX", text)
    return _PHONE.sub(lambda m: "******" + m.group(2)[-4:], text)


def redact_triage(output: dict | None) -> dict | None:
    """Staff views of a stored triage result: strip personal identifiers from free-text fields."""
    if not output:
        return output
    out = dict(output)
    for k in ("summary", "location_text"):
        if out.get(k):
            out[k] = redact_text(out[k])
    out["matched_terms"] = [m | {"term": redact_text(m.get("term", ""))} for m in out.get("matched_terms", [])]
    return out
