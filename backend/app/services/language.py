"""Language registry data and script-based language detection (no external service required)."""
import re

from ..data.lexicon import TRANSLIT_HINTS

# Unicode script blocks -> default language code for that script.
SCRIPT_RANGES = [
    ("kn", 0x0C80, 0x0CFF), ("ta", 0x0B80, 0x0BFF), ("te", 0x0C00, 0x0C7F), ("ml", 0x0D00, 0x0D7F),
    ("hi", 0x0900, 0x097F), ("bn", 0x0980, 0x09FF), ("pa", 0x0A00, 0x0A7F), ("gu", 0x0A80, 0x0AFF),
    ("or", 0x0B00, 0x0B7F), ("ur", 0x0600, 0x06FF), ("mni", 0xABC0, 0xABFF), ("sat", 0x1C50, 0x1C7F),
]

# 22 Eighth-Schedule languages + English + Pali + Prakrit = 25.
# current_support describes what THIS build actually implements and tests - not the plan.
LANGUAGES = [
    # code, name, native, script, dir, eighth, classical, planned_tier, speech_code, ui, keywords
    ("en", "English", "English", "Latin", "ltr", False, False, "voice_text", "en-IN", True, True),
    ("kn", "Kannada", "ಕನ್ನಡ", "Kannada", "ltr", True, True, "voice_text", "kn-IN", True, True),
    ("hi", "Hindi", "हिन्दी", "Devanagari", "ltr", True, False, "voice_text", "hi-IN", True, True),
    ("ta", "Tamil", "தமிழ்", "Tamil", "ltr", True, True, "voice_text", "ta-IN", True, True),
    ("te", "Telugu", "తెలుగు", "Telugu", "ltr", True, True, "voice_text", "te-IN", False, False),
    ("ml", "Malayalam", "മലയാളം", "Malayalam", "ltr", True, True, "voice_text", "ml-IN", False, False),
    ("mr", "Marathi", "मराठी", "Devanagari", "ltr", True, True, "voice_text", "mr-IN", False, False),
    ("bn", "Bengali", "বাংলা", "Bengali", "ltr", True, True, "voice_text", "bn-IN", False, False),
    ("gu", "Gujarati", "ગુજરાતી", "Gujarati", "ltr", True, False, "voice_text", "gu-IN", False, False),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ", "Gurmukhi", "ltr", True, False, "voice_text", "pa-IN", False, False),
    ("or", "Odia", "ଓଡ଼ିଆ", "Odia", "ltr", True, True, "voice_text", "or-IN", False, False),
    ("ur", "Urdu", "اردو", "Perso-Arabic", "rtl", True, False, "voice_text", "ur-IN", False, False),
    ("as", "Assamese", "অসমীয়া", "Bengali-Assamese", "ltr", True, True, "text_translation", "", False, False),
    ("kok", "Konkani", "कोंकणी", "Devanagari", "ltr", True, False, "text_translation", "", False, False),
    ("mai", "Maithili", "मैथिली", "Devanagari", "ltr", True, False, "text_translation", "", False, False),
    ("ne", "Nepali", "नेपाली", "Devanagari", "ltr", True, False, "text_translation", "", False, False),
    ("sd", "Sindhi", "سنڌي", "Perso-Arabic", "rtl", True, False, "text_translation", "", False, False),
    ("mni", "Manipuri (Meitei)", "ꯃꯤꯇꯩꯂꯣꯟ", "Meitei Mayek", "ltr", True, False, "text_translation", "", False, False),
    ("brx", "Bodo", "बड़ो", "Devanagari", "ltr", True, False, "text_translation", "", False, False),
    ("doi", "Dogri", "डोगरी", "Devanagari", "ltr", True, False, "text_translation", "", False, False),
    ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "Ol Chiki", "ltr", True, False, "text_translation", "", False, False),
    ("ks", "Kashmiri", "کٲشُر", "Perso-Arabic", "rtl", True, False, "text_translation", "", False, False),
    ("sa", "Sanskrit", "संस्कृतम्", "Devanagari", "ltr", True, True, "content_assisted", "", False, False),
    ("pi", "Pali", "पालि", "Devanagari (varies)", "ltr", False, True, "content_assisted", "", False, False),
    ("pra", "Prakrit", "प्राकृत", "Devanagari (varies)", "ltr", False, True, "content_assisted", "", False, False),
]


def current_support(ui: bool, keywords: bool) -> str:
    if ui and keywords:
        return "ui+triage+browser_voice"
    return "registry_only"


def detect_language(text: str, hint: str | None = None) -> dict:
    """Detect language from Unicode script; flag romanised (transliterated) Indic text."""
    counts: dict[str, int] = {}
    latin = 0
    for ch in text:
        cp = ord(ch)
        if ch.isascii() and ch.isalpha():
            latin += 1
            continue
        for code, lo, hi in SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    total = latin + sum(counts.values())
    if total == 0:
        return {"code": hint or "und", "confidence": 0.0, "method": "no-letters", "transliterated_from": None}
    best, best_n = max(counts.items(), key=lambda kv: kv[1]) if counts else ("en", 0)
    if best_n > latin:
        code = best
        # Devanagari is shared (hi, mr, ne, kok, sa...). Respect the user's selection when it uses that script.
        if code == "hi" and hint in {"mr", "ne", "kok", "mai", "brx", "doi", "sa", "pi", "pra"}:
            code = hint
        if code == "bn" and hint == "as":
            code = "as"
        if code == "ur" and hint in {"sd", "ks"}:
            code = hint
        return {"code": code, "confidence": round(best_n / total, 2), "method": "unicode-script", "transliterated_from": None}
    words = set(re.findall(r"[a-z]+", text.lower()))
    translit = None
    best_hits = 0
    for lang, hints in TRANSLIT_HINTS.items():
        hits = len(words & set(hints))
        if hits > best_hits:
            translit, best_hits = lang, hits
    return {"code": "en", "confidence": round(latin / total, 2), "method": "unicode-script",
            "transliterated_from": translit if best_hits >= 1 else None}


def looks_like_gibberish(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 4:
        return True
    words = re.findall(r"\w+", text)
    if not words:
        return True
    latin_words = [w for w in words if w.isascii()]
    if latin_words and len(latin_words) == len(words):
        vowelless = [w for w in latin_words if len(w) > 3 and not re.search(r"[aeiouy]", w.lower())]
        if len(vowelless) / len(latin_words) > 0.4:
            return True
    return False
