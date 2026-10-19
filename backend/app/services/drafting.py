"""Draft letters/notices from department templates, document summarization and metadata extraction.
Drafts are always editable and are NEVER sent or signed by the system."""
import re
from collections import Counter

from ..db import utcnow
from . import llm
from .kb import tokenize


def fill_template(body: str, fields: dict) -> str:
    def rep(m):
        key = m.group(1)
        return str(fields.get(key, f"[{key}]"))
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", rep, body)


def generate_draft(template_body: str, fields: dict, use_llm: bool = False) -> tuple[str, str]:
    text = fill_template(template_body, fields)
    if use_llm:
        try:
            polished = llm.generate_text(
                "You polish Indian government response letters. Keep every fact, reference number and date exactly. "
                "Do not add facts. Return only the letter.", text)
            return polished, "template+llm"
        except llm.LLMError:
            return text, "template (LLM unavailable - not polished)"
    return text, "template"


def summarize(text: str, max_sentences: int = 4) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text or "") if len(s.strip()) > 20]
    if not sentences:
        return (text or "")[:400]
    freq = Counter(tokenize(text))
    scored = [(sum(freq[t] for t in tokenize(s)) / (len(tokenize(s)) + 1), i, s) for i, s in enumerate(sentences)]
    top = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda x: x[1])
    return " ".join(s for _, _, s in top)


DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b", re.I)
AMOUNT_RE = re.compile(r"(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d+)?", re.I)
REF_RE = re.compile(r"\b(?:No\.|Ref(?:erence)?\.?|Order No\.?|G\.O\.?)\s*[:\-]?\s*([A-Z0-9/\-]{4,})", re.I)


def extract_metadata(text: str) -> dict:
    return {
        "dates": sorted(set(DATE_RE.findall(text or "")))[:10],
        "amounts": sorted(set(AMOUNT_RE.findall(text or "")))[:10],
        "references": sorted(set(REF_RE.findall(text or "")))[:10],
        "word_count": len((text or "").split()),
        "extracted_at": utcnow().isoformat(timespec="seconds") + "Z",
    }
