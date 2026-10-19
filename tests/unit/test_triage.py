"""Triage pipeline: the mandatory acceptance dataset, the 'same answer for every complaint' regression,
human-review fallback, safety rules, schema validation and honest AI-provider failure handling."""
import pytest
from sqlalchemy import select

from app.data.lexicon import EVAL_DATASET
from app.db import SessionLocal
from app.models import Tenant
from app.services import triage as triage_mod
from app.services.llm import LLMError
from app.services.triage import TriageError, TriageOutput, run_triage

ACCEPTANCE = [
    ("Streetlight not working for three days", "streetlight", "STREETLIGHT", "Medium"),
    ("Transformer sparking near houses", "power_hazard", "ELEC_EMG", "Emergency"),
    ("Dirty water from the tap", "water_quality", "WATER", "High"),
    ("Garbage not collected for a week", "garbage", "SWM", "Medium"),
    ("Large pothole after rain", "roads", "ROADS", "Medium"),
    ("Mosquito breeding in stagnant water", "mosquito", "HEALTH", "Medium"),
    ("Stray dogs attacking people", "stray_animals", "VET", "High"),
]


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(params=["ka-bengaluru", "tn-chennai"])
def tenant(request, db):
    return db.execute(select(Tenant).where(Tenant.code == request.param)).scalar_one()


@pytest.mark.parametrize("text,cat,dept,priority", ACCEPTANCE)
def test_acceptance_routes_correctly(db, tenant, text, cat, dept, priority):
    r = run_triage(db, tenant, text, persist=False)
    assert r.category_code == cat
    assert r.department_code == dept
    assert r.priority == priority
    assert r.human_review_required is False
    assert r.department_id is not None
    assert r.sla_policy_id is not None


def test_gibberish_goes_to_human_review(db, tenant):
    r = run_triage(db, tenant, "asdkj qwe zzkx plmnb", persist=False)
    assert r.human_review_required is True
    assert r.department_id is None
    assert r.priority is None
    assert "understood" in r.human_review_reason


def test_unrelated_text_is_not_auto_assigned(db, tenant):
    r = run_triage(db, tenant, "What is the cricket score today", persist=False)
    assert r.human_review_required is True and r.department_id is None


def test_unrelated_complaints_do_not_share_one_canned_answer(db, tenant):
    """Regression for the audited defect: every complaint received the same department/priority/SLA."""
    results = [run_triage(db, tenant, text, persist=False) for text, *_ in ACCEPTANCE]
    assert len({r.category_code for r in results}) == len(ACCEPTANCE)
    assert len({r.department_code for r in results}) >= 6
    assert len({r.priority for r in results}) >= 3
    assert len({r.summary for r in results}) == len(ACCEPTANCE)


@pytest.mark.parametrize("lang,text,expected_cat,expected_pri", EVAL_DATASET)
def test_labelled_eval_dataset(db, lang, text, expected_cat, expected_pri):
    t = db.execute(select(Tenant).where(Tenant.code == "ka-bengaluru")).scalar_one()
    r = run_triage(db, t, text, language_hint=lang, persist=False)
    got = "human_review" if r.human_review_required else r.category_code
    assert got == expected_cat
    if expected_pri:
        assert r.priority == expected_pri
    if lang != "en":
        assert r.language == lang


def test_emergency_safety_message_and_rules(db, tenant):
    r = run_triage(db, tenant, "Live wire hanging near the bus stop", persist=False)
    assert r.emergency is True and r.priority == "Emergency"
    assert "NOT an emergency service" in r.safety_message
    assert "112" in r.safety_message
    assert any(x["rule"].startswith("R-EMG") for x in r.rules_applied)


def test_risk_rule_raises_priority(db, tenant):
    r = run_triage(db, tenant, "Street lamp near the school is broken", persist=False)
    assert r.category_code == "streetlight" and r.priority == "High"
    assert any(x["rule"] == "R-RISK-01" for x in r.rules_applied)


def test_low_confidence_routes_to_human(db, tenant, monkeypatch):
    monkeypatch.setattr(triage_mod.get_settings(), "triage_confidence_threshold", 0.99)
    r = run_triage(db, tenant, "Garbage not collected for a week", persist=False)
    assert r.human_review_required and r.department_id is None
    assert "below the auto-routing threshold" in r.human_review_reason


def test_ward_is_never_defaulted(db, tenant):
    r = run_triage(db, tenant, "Garbage not collected for a week", persist=False)
    assert r.jurisdiction_id is None and r.jurisdiction_method == "not-determined"


def test_ward_from_gps_in_demo_boundary(db):
    t = db.execute(select(Tenant).where(Tenant.code == "ka-bengaluru")).scalar_one()
    r = run_triage(db, t, "Garbage not collected", lat=12.925, lng=77.583, persist=False)
    assert r.jurisdiction_name == "Jayanagar" and "demo boundary" in r.jurisdiction_method


def test_ward_from_locality_name(db):
    t = db.execute(select(Tenant).where(Tenant.code == "ka-bengaluru")).scalar_one()
    r = run_triage(db, t, "Pothole on Indiranagar 100 feet road", persist=False)
    assert r.jurisdiction_name == "Indiranagar"


def test_output_validates_against_schema(db, tenant):
    r = run_triage(db, tenant, "Dirty water from the tap", persist=False)
    TriageOutput(**r.model_dump())  # round-trip validation
    for key in ("language", "department_id", "category_id", "priority", "confidence", "location_text", "coordinates",
                "jurisdiction_id", "summary", "recommended_action", "sla_policy_id", "reasoning_summary",
                "evidence_sources", "human_review_required"):
        assert key in r.model_dump()


def test_empty_and_oversized_input_rejected(db, tenant):
    with pytest.raises(TriageError):
        run_triage(db, tenant, "   ", persist=False)
    with pytest.raises(TriageError):
        run_triage(db, tenant, "a" * 4001, persist=False)


def test_unsupported_language_without_translation_goes_to_human(db, tenant):
    r = run_triage(db, tenant, "మా వీధిలో నీరు రావడం లేదు", persist=False)  # Telugu
    assert r.language == "te"
    assert r.human_review_required
    assert "translation provider" in r.human_review_reason


def test_llm_failure_is_surfaced_not_masked(db, tenant, monkeypatch):
    s = triage_mod.get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai_compatible")
    monkeypatch.setattr(s, "llm_api_key", "x")
    monkeypatch.setattr(s, "llm_model", "test-model")

    def boom(*a, **k):
        raise LLMError("timeout")
    monkeypatch.setattr(triage_mod.llm, "chat_json", boom)
    with pytest.raises(TriageError, match="AI provider error"):
        run_triage(db, tenant, "Dirty water from the tap", persist=False)


def test_llm_output_outside_registry_is_rejected(db, tenant, monkeypatch):
    s = triage_mod.get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai_compatible")
    monkeypatch.setattr(s, "llm_api_key", "x")
    monkeypatch.setattr(s, "llm_model", "test-model")
    monkeypatch.setattr(triage_mod.llm, "chat_json", lambda *a, **k: {"category_code": "ward_12_magic", "confidence": 0.99})
    with pytest.raises(TriageError):
        run_triage(db, tenant, "Dirty water from the tap", persist=False)


def test_llm_valid_output_is_used_with_safety_rules(db, tenant, monkeypatch):
    s = triage_mod.get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai_compatible")
    monkeypatch.setattr(s, "llm_api_key", "x")
    monkeypatch.setattr(s, "llm_model", "test-model")
    monkeypatch.setattr(triage_mod.llm, "chat_json", lambda *a, **k: {
        "category_code": "power_hazard", "confidence": 0.9, "location_text": "2nd Main", "summary_en": "Transformer sparking", "reasons": ["sparks"]})
    r = run_triage(db, tenant, "Transformer sparking near houses", persist=False)
    assert r.provider == "openai_compatible" and r.priority == "Emergency" and r.location_text == "2nd Main"


def test_triage_record_persisted_for_audit(db, tenant):
    from app.models import TriageRecord
    r = run_triage(db, tenant, "Garbage not collected for a week")
    rec = db.get(TriageRecord, r.triage_id)
    assert rec.provider == "rule-based-demo" and rec.output["category_code"] == "garbage" and rec.rules_applied


def test_ward_from_indic_locality_name(db):
    t = db.execute(select(Tenant).where(Tenant.code == "ka-bengaluru")).scalar_one()
    r = run_triage(db, t, "ಜಯನಗರದಲ್ಲಿ ಬೀದಿ ದೀಪ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ", persist=False)
    assert r.jurisdiction_name == "Jayanagar" and r.category_code == "streetlight"
