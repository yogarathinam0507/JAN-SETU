"""SLA, escalation, duplicate clustering, eligibility logic, masking and monitoring rules."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal, utcnow
from app.models import Grievance, MonitoredService, Scheme, Tenant
from app.services import benefits, monitoring, workflow
from app.services.masking import mask_phone, redact_text
from app.services.triage import run_triage


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture()
def ka(db):
    return db.execute(select(Tenant).where(Tenant.code == "ka-bengaluru")).scalar_one()


def make(db, tenant, text, lat=None, lng=None, created=None):
    tri = run_triage(db, tenant, text, lat=lat, lng=lng).model_dump()
    return workflow.create_grievance(db, tenant_id=tenant.id, triage=tri, text=text, actor=None, citizen=None,
                                     channel="web", input_mode="text", transcript_confirmed=False, contact_name="T",
                                     contact_phone="9123456780", lat=lat, lng=lng, location_text="", consent=True,
                                     created_at=created)


def test_sla_from_policy_table(db, ka):
    g = make(db, ka, "Transformer sparking near houses")
    assert g.priority == "Emergency"
    assert round((g.sla_due_at - g.created_at).total_seconds() / 3600) == 4
    assert round((g.first_response_due_at - g.created_at).total_seconds() / 3600) == 1
    g2 = make(db, ka, "Garbage not collected for a week")
    assert round((g2.sla_due_at - g2.created_at).total_seconds() / 3600) == 72


def test_human_review_ticket_has_no_resolution_sla(db, ka):
    g = make(db, ka, "asdkj qwe zzkx plmnb")
    assert g.status == "human_review" and g.sla_due_at is None and g.department_id is None
    assert workflow.sla_state(g)["state"] == "not_started"


def test_escalation_matrix(db, ka):
    g = make(db, ka, "Dirty water from the tap", created=utcnow() - timedelta(hours=30))  # High = 24h
    workflow.run_escalations(db, ka.id)
    assert g.escalation_level == 1
    g.created_at = utcnow() - timedelta(hours=40)
    g.sla_due_at = g.created_at + timedelta(hours=24)
    workflow.run_escalations(db, ka.id)
    assert g.escalation_level == 2
    before = g.escalation_level
    workflow.run_escalations(db, ka.id)  # idempotent
    assert g.escalation_level == before


def test_duplicates_cluster_within_radius_and_stats_are_consistent(db, ka):
    a = make(db, ka, "Fallen tree branch blocking road", lat=12.9700, lng=77.7500)
    b = make(db, ka, "Fallen tree branch on the road again", lat=12.9705, lng=77.7503)  # ~65 m
    c = make(db, ka, "Fallen tree branch far away", lat=12.9900, lng=77.7500)          # ~2.2 km
    assert a.master_incident_id and a.master_incident_id == b.master_incident_id
    assert c.master_incident_id is None
    stats = workflow.duplicate_stats(db, ka.id)
    assert stats["duplicates"] == stats["linked_reports"] - stats["master_incidents"]
    linked = db.execute(select(Grievance).where(Grievance.tenant_id == ka.id, Grievance.master_incident_id.is_not(None))).scalars().all()
    assert stats["linked_reports"] == len(linked)
    assert stats["master_incidents"] == len({g.master_incident_id for g in linked})


def test_different_category_is_never_a_duplicate(db, ka):
    a = make(db, ka, "Garbage not collected", lat=12.9701, lng=77.7501)
    b = make(db, ka, "Streetlight not working", lat=12.9701, lng=77.7501)
    assert not (a.master_incident_id and a.master_incident_id == b.master_incident_id)


def test_state_machine_rejects_invalid_transition(db, ka):
    from fastapi import HTTPException
    g = make(db, ka, "Garbage not collected")
    with pytest.raises(HTTPException):
        workflow.transition(db, g, "confirm_closure", None, "")
    with pytest.raises(HTTPException):  # reason required
        workflow.transition(db, g, "reject", None, "")


def test_eligibility_outcomes(db, ka):
    s = db.execute(select(Scheme).where(Scheme.tenant_id == ka.id, Scheme.code == "gruha_lakshmi")).scalar_one()
    assert benefits.evaluate(s, {})["outcome"] == "more_information_required"
    ok = {"resident": "yes", "gender": "yes", "head_of_household": "yes", "income_tax": "no"}
    r = benefits.evaluate(s, ok)
    assert r["preliminary_rule_check"] == "potentially_eligible"
    assert r["outcome"] == "not_enough_verified_information"  # unverified seed content is never presented as decided
    excluded = benefits.evaluate(s, ok | {"income_tax": "yes"})
    assert excluded["preliminary_rule_check"] == "likely_not_eligible"
    s.verified = True
    assert benefits.evaluate(s, ok)["outcome"] == "potentially_eligible"
    s.verified = False


def test_numeric_rule(db, ka):
    s = db.execute(select(Scheme).where(Scheme.tenant_id == ka.id, Scheme.code == "gruha_jyothi")).scalar_one()
    r = benefits.evaluate(s, {"resident": "yes", "domestic": "yes", "avg_units": 350})
    assert r["preliminary_rule_check"] == "likely_not_eligible"


def test_masking():
    assert mask_phone("9876543210") == "******3210"
    assert "9876543210" not in redact_text("call me on 9876543210 or 1234 5678 9012")
    assert "XXXX XXXX XXXX" in redact_text("aadhaar 1234 5678 9012")


def test_planned_and_unauthorized_services_are_never_probed(db, ka, monkeypatch):
    called = []
    monkeypatch.setattr(monitoring.httpx, "get", lambda *a, **k: called.append(a))
    planned = db.execute(select(MonitoredService).where(MonitoredService.tenant_id == ka.id,
                                                        MonitoredService.check_mode == "planned")).scalars().first()
    assert monitoring.run_check(db, planned) is None
    s = MonitoredService(tenant_id=ka.id, name="x", endpoint="https://example.gov.in/health", check_mode="http",
                         authorized=False, enabled=True)
    db.add(s)
    db.flush()
    assert monitoring.run_check(db, s) is None
    assert called == []


def test_simulated_checks_are_flagged_and_incident_rule(db, ka):
    s = MonitoredService(tenant_id=ka.id, name="sim", check_mode="simulated", enabled=True, notes="")
    db.add(s)
    db.flush()
    hc = monitoring.run_check(db, s)
    assert hc.simulated is True
    from app.models import HealthCheck, Incident
    for k in range(3):
        db.add(HealthCheck(service_id=s.id, ok=False, error="x", simulated=True, checked_at=utcnow() + timedelta(seconds=k + 1)))
    db.flush()
    monitoring.evaluate_rules(db, s)
    inc = db.execute(select(Incident).where(Incident.service_id == s.id)).scalars().first()
    assert inc and inc.simulated and all(h["status"].startswith("hypothesis") for h in inc.hypotheses)


def test_anomaly_needs_history(db, ka):
    s = MonitoredService(tenant_id=ka.id, name="new", check_mode="simulated", enabled=True)
    db.add(s)
    db.flush()
    assert monitoring.anomaly(db, s)["status"] == "insufficient_data"
    assert monitoring.risk_score(db, s)["status"] == "insufficient_data"
