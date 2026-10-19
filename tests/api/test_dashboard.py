"""Role dashboards, notifications, automatic officer assignment, synthetic located data and token time handling."""
import os
import time
from collections import Counter

import jwt
import pytest

ROLES = ["ka.citizen1", "ka.officer.water", "ka.nodal", "ka.agent1", "ka.hod", "ka.vendor", "ka.auditor", "ka.content", "ka.admin",
         "tn.citizen1", "tn.officer.swm", "tn.nodal", "tn.hod", "tn.admin"]


@pytest.mark.parametrize("username", ROLES)
def test_every_role_signs_in_and_gets_a_dashboard(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": "Demo@1234"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    # The token must be accepted immediately (regression: "session expired" right after sign-in).
    me = client.get("/api/me", headers=h)
    assert me.status_code == 200 and me.json()["username"] == username
    d = client.get("/api/dashboard", headers=h).json()
    assert d["role"] == me.json()["role"] and len(d["kpis"]) >= 4
    assert all({"label", "value"} <= set(k) for k in d["kpis"])
    assert d["lists"] and d["actions"]
    n = client.get("/api/notifications", headers=h)
    assert n.status_code == 200 and isinstance(n.json()["items"], list)


def test_token_is_valid_on_a_machine_in_ist(client, monkeypatch):
    """Tokens are stamped from epoch seconds, never from naive local datetimes."""
    os.environ["TZ"] = "Asia/Kolkata"
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        r = client.post("/api/auth/login", json={"username": "ka.officer.water", "password": "Demo@1234"}).json()
        claims = jwt.decode(r["token"], options={"verify_signature": False})
        assert abs(claims["iat"] - time.time()) < 60 and claims["exp"] > time.time() + 3600
        assert client.get("/api/me", headers={"Authorization": f"Bearer {r['token']}"}).status_code == 200
    finally:
        os.environ.pop("TZ", None)
        if hasattr(time, "tzset"):
            time.tzset()


def test_dashboards_are_scoped(client, auth):
    off = client.get("/api/dashboard", headers=auth("ka.officer.water")).json()
    assert off["scope"].startswith("BWSSB")
    cats = next(c for c in off["charts"] if c["title"] == "Complaints by category")
    assert {x["label"] for x in cats["data"]} <= {"Contaminated / dirty water", "No water / supply problem", "Sewage overflow / manhole"}
    hod = client.get("/api/dashboard", headers=auth("ka.hod")).json()
    assert "no personal data" in hod["scope"]
    # hod list rows carry department aggregates only (no ticket ids, names or phones)
    assert all(not str(r["cells"][0]).startswith("GRV") for r in hod["lists"][0]["rows"])
    cit = client.get("/api/dashboard", headers=auth("ka.citizen1")).json()
    mine = client.get("/api/grievances?page_size=100", headers=auth("ka.citizen1")).json()
    assert cit["kpis"][0]["value"] == mine["total"]


def test_new_complaint_is_auto_assigned_to_named_officer_and_citizen_is_notified(client, auth):
    cit = auth("ka.citizen2")
    text = "Water pipeline burst near the temple, water wasting, Jayanagar"
    r = client.post("/api/grievances", headers=cit, json={"text": text, "consent": True, "lat": 12.926, "lng": 77.584})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["department"]["code"] == "WATER"
    assert g["assigned_officer"] == "Smt. Kavya Shetty"
    assert g["assigned_officer_designation"] == "Assistant Executive Engineer (Water Supply)"
    assert "assigned to Smt. Kavya Shetty" in g["assignment_notice"]
    detail = client.get(f"/api/grievances/{g['public_id']}", headers=cit).json()
    assert any(e["type"] == "assigned" and "Kavya Shetty" in e["note"] for e in detail["events"])
    # The officer sees it in the queue and gets a notification
    note = client.get("/api/notifications", headers=auth("ka.officer.water")).json()["items"]
    assert any(g["public_id"] in i["title"] for i in note)
    # The citizen is notified when the officer accepts it
    client.post(f"/api/grievances/{g['public_id']}/actions", headers=auth("ka.officer.water"), json={"action": "accept", "note": ""})
    cn = client.get("/api/notifications", headers=cit).json()["items"]
    assert any(g["public_id"] in i["title"] and "Accepted" in i["title"] for i in cn)


def test_unclear_complaint_is_not_assigned_and_says_so(client, auth):
    r = client.post("/api/grievances", headers=auth("ka.citizen2"), json={"text": "asdkj qwe zzkx plmnb", "consent": True}).json()
    assert r["status"] == "human_review" and r["assigned_officer"] is None
    assert "nodal officer" in r["assignment_notice"]


def test_synthetic_complaints_are_varied_located_and_assigned(client, auth):
    rows = client.get("/api/map/live?status=all", headers=auth("ka.nodal")).json()["markers"]
    assert len(rows) >= 80
    cats = Counter(m["category_code"] for m in rows)
    assert len(cats) >= 12 and cats.most_common(1)[0][1] / len(rows) < 0.25  # not "everything is streetlight"
    cfg = client.get("/api/map/config?tenant=ka-bengaluru").json()
    def inside(m):
        return any(min(p[0] for p in w["polygon"]) <= m["lat"] <= max(p[0] for p in w["polygon"]) and
                   min(p[1] for p in w["polygon"]) <= m["lng"] <= max(p[1] for p in w["polygon"]) for w in cfg["wards"])
    assert all(inside(m) for m in rows)
    statuses = Counter(m["status"] for m in rows)
    assert {"submitted", "in_progress", "closed"} <= set(statuses)


def test_no_demo_wording_in_names(client, auth):
    accts = client.get("/api/auth/demo-accounts").json()["accounts"]
    assert all("(demo)" not in a["full_name"] for a in accts)
    officers = [a for a in accts if a["role"] == "officer"]
    assert officers and all(a["designation"] for a in officers)
    tenants = client.get("/api/public/tenants").json()
    assert all("demo" not in t["name"].lower() for t in tenants)
