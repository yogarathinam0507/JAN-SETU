"""Language detection, registry honesty and interface-string coverage."""
import json
import re
from pathlib import Path

import pytest

from app.services.language import LANGUAGES, detect_language, looks_like_gibberish

ROOT = Path(__file__).resolve().parents[2]
I18N = ROOT / "frontend" / "i18n"


@pytest.mark.parametrize("text,code", [
    ("ಬೀದಿ ದೀಪ ಕೆಟ್ಟಿದೆ", "kn"), ("தெரு விளக்கு எரியவில்லை", "ta"), ("स्ट्रीट लाइट खराब है", "hi"),
    ("వీధి దీపం పనిచేయడం లేదు", "te"), ("തെരുവ് വിളക്ക്", "ml"), ("রাস্তার আলো", "bn"), ("ગટર", "gu"),
    ("ਗਲੀ ਦੀ ਬੱਤੀ", "pa"), ("ରାସ୍ତା ଆଲୁଅ", "or"), ("گلی کی بتی", "ur"), ("Streetlight not working", "en"),
])
def test_script_detection(text, code):
    assert detect_language(text)["code"] == code


def test_shared_script_respects_user_selection():
    assert detect_language("पाणी येत नाही", "mr")["code"] == "mr"


def test_transliteration_flag():
    d = detect_language("current illa neeru barthilla")
    assert d["code"] == "en" and d["transliterated_from"] == "kn"


def test_gibberish_detection():
    assert looks_like_gibberish("asdkj qwe zzkx plmnb")
    assert looks_like_gibberish("??")
    assert not looks_like_gibberish("No water for two days")


def test_registry_has_25_languages_with_honest_tiers():
    codes = [l[0] for l in LANGUAGES]
    assert len(codes) == 25 and len(set(codes)) == 25
    eighth = [l for l in LANGUAGES if l[5]]
    assert len(eighth) == 22
    for code in ("pi", "pra"):
        row = next(l for l in LANGUAGES if l[0] == code)
        assert row[6] is True and row[5] is False and row[7] == "content_assisted"
    rtl = {l[0] for l in LANGUAGES if l[4] == "rtl"}
    assert rtl == {"ur", "sd", "ks"}
    supported = {l[0] for l in LANGUAGES if l[9] and l[10]}
    assert supported == {"en", "kn", "hi", "ta"}  # only languages with UI strings AND triage keywords


def test_language_api_reports_current_support(client):
    data = client.get("/api/public/languages").json()
    assert data["count"] == 25
    by = {l["code"]: l for l in data["languages"]}
    assert by["kn"]["current_support"] == "ui+triage+browser_voice"
    assert by["sat"]["current_support"] == "registry_only"


def _js_keys() -> set[str]:
    keys = set()
    for f in (ROOT / "frontend" / "js").rglob("*.js"):
        keys |= set(re.findall(r"t\('([a-z_]+\.[A-Za-z0-9_]+)'", f.read_text(encoding="utf-8")))
    return keys - {"jansetu.prefill", "jansetu.token", "jansetu.user"}


def test_every_ui_key_has_english_string():
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    missing = _js_keys() - set(en)
    assert not missing, missing


@pytest.mark.parametrize("lang", ["kn", "hi", "ta"])
def test_translations_only_use_known_keys_and_cover_citizen_flow(lang):
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    tr = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
    assert set(tr) <= set(en)
    essential = ["nav.file", "citizen.title", "citizen.submit", "citizen.consent_text", "citizen.transcript_confirm",
                 "citizen.your_ticket", "status.resolved", "priority.Emergency", "home.emergency_desc", "benefits.disclaimer"]
    for k in essential:
        assert tr.get(k) and tr[k] != en[k], f"{lang}:{k} not translated"
    for k, v in tr.items():  # placeholders preserved
        assert set(re.findall(r"\{(\w+)\}", v)) == set(re.findall(r"\{(\w+)\}", en[k])), k


def test_kannada_templates_available_for_karnataka(client, auth):
    h = auth("ka.officer.streetlight")
    langs = {t["language"] for t in client.get("/api/templates", headers=h).json()}
    assert "kn" in langs
