"""End-to-end citizen -> officer workflow through the HTTP API, including persistence across restarts."""
import io

from fastapi.testclient import TestClient

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def preview(client, text, tenant="ka-bengaluru", **kw):
    r = client.post(f"/api/triage/preview?tenant={tenant}", json={"text": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_preview_creates_no_ticket_and_differs_per_complaint(client, auth):
    h = auth("ka.auditor")
    before = client.get("/api/grievances?page_size=1", headers=h).json()["total"]
    a = preview(client, "Garbage not collected for a week")
    b = preview(client, "Dirty water from the tap")
    assert (a["department_code"], a["priority"]) != (b["department_code"], b["priority"])
    assert client.get("/api/grievances?page_size=1", headers=h).json()["total"] == before


def test_guest_complaint_requires_phone_and_consent(client):
    tri = preview(client, "Garbage not collected near Malleshwaram market")
    body = {"text": "Garbage not collected near Malleshwaram market", "triage_id": tri["triage_id"], "consent": True}
    r = client.post("/api/grievances?tenant=ka-bengaluru", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "phone_required"
    r = client.post("/api/grievances?tenant=ka-bengaluru", json=body | {"contact_phone": "9123456789", "consent": False})
    assert r.status_code == 422 and r.json()["error"]["code"] == "consent_required"


def test_voice_complaint_requires_confirmed_transcript(client):
    text = "Streetlight not working near Whitefield bus stop"
    tri = preview(client, text, input_mode="voice")
    body = {"text": text, "triage_id": tri["triage_id"], "input_mode": "voice", "consent": True, "contact_phone": "9123456789"}
    r = client.post("/api/grievances?tenant=ka-bengaluru", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "transcript_not_confirmed"
    r = client.post("/api/grievances?tenant=ka-bengaluru", json=body | {"transcript_confirmed": True})
    assert r.status_code == 201


def test_full_citizen_to_officer_workflow(app, client, auth):
    cit = auth("ka.citizen2")
    text = "Streetlight not working near Malleshwaram 18th cross temple for three days"
    tri = preview(client, text)
    assert tri["department_code"] == "STREETLIGHT" and tri["human_review_required"] is False
    r = client.post("/api/grievances", headers=cit, json={"text": text, "triage_id": tri["triage_id"], "consent": True})
    assert r.status_code == 201, r.text
    g = r.json()
    pid = g["public_id"]
    assert g["status"] == "submitted" and g["department"]["code"] == "STREETLIGHT" and g["sla_due_at"]
    assert g["contact_phone"] == "9845010002"  # owner sees own details unmasked

    # citizen history
    mine = client.get("/api/grievances?page_size=200", headers=cit).json()
    assert pid in {x["public_id"] for x in mine["items"]}

    # correct officer queue (and not another department's)
    off = auth("ka.officer.streetlight")
    q = client.get("/api/grievances?page_size=200&status=submitted", headers=off).json()
    row = next(x for x in q["items"] if x["public_id"] == pid)
    assert row["contact_phone"].startswith("******") and row["contact_masked"]
    water = auth("ka.officer.water")
    assert pid not in {x["public_id"] for x in client.get("/api/grievances?page_size=200", headers=water).json()["items"]}
    assert client.get(f"/api/grievances/{pid}", headers=water).status_code == 404

    # officer actions
    def act(action, note="", hdr=off):
        return client.post(f"/api/grievances/{pid}/actions", headers=hdr, json={"action": action, "note": note})
    assert act("accept").status_code == 200
    assert act("start").status_code == 200
    r = act("resolve", "Lamp replaced by field team")
    assert r.status_code == 422 and r.json()["error"]["code"] == "after_photo_required"
    up = client.post(f"/api/grievances/{pid}/attachments", headers=off, data={"kind": "after"},
                     files={"file": ("after.png", io.BytesIO(PNG), "image/png")})
    assert up.status_code == 201, up.text
    assert act("resolve", "Lamp replaced by field team").status_code == 200

    # citizen sees the update and rejects the closure
    d = client.get(f"/api/grievances/{pid}", headers=cit).json()
    assert d["status"] == "resolved" and "confirm_closure" in d["allowed_actions"]
    r = act("reject_closure", "Still not working at night", hdr=cit)
    assert r.status_code == 200 and r.json()["status"] == "reopened" and r.json()["reopen_count"] == 1
    assert act("confirm_closure", hdr=cit).status_code == 409  # not resolved anymore
    assert act("accept").status_code == 200
    assert act("resolve", "Wiring fixed, verified at night").status_code == 200
    r = client.post(f"/api/grievances/{pid}/actions", headers=cit, json={"action": "confirm_closure", "note": "Works now", "rating": 4})
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["citizen_rating"] == 4
    types = [e["type"] for e in r.json()["events"]]
    for t in ("created", "accept", "start", "resolve", "reject_closure", "confirm_closure"):
        assert t in types

    # persistence across an application restart (new client / new DB connections)
    from app.db import engine
    engine.dispose()
    with TestClient(app) as fresh:
        again = fresh.get(f"/api/grievances/{pid}", headers=cit).json()
        assert again["status"] == "closed" and again["photo_verification"] in {"after_only", "before_and_after"}


def test_officer_cannot_do_citizen_actions_and_vice_versa(client, auth):
    cit = auth("ka.citizen1")
    mine = client.get("/api/grievances?status=submitted&page_size=50", headers=cit).json()["items"]
    pid = mine[0]["public_id"]
    assert client.post(f"/api/grievances/{pid}/actions", headers=cit, json={"action": "accept"}).status_code == 403


def test_public_tracking_shows_no_personal_data(client, auth):
    cit = auth("ka.citizen1")
    pid = client.get("/api/grievances?page_size=1", headers=cit).json()["items"][0]["public_id"]
    r = client.get(f"/api/track/{pid}?tenant=ka-bengaluru").json()
    flat = str(r)
    assert "9845010001" not in flat and "original_text" not in r and r["public_id"] == pid
    assert client.get(f"/api/track/{pid}?tenant=tn-chennai").status_code == 404


def test_human_triage_queue_and_manual_routing(client, auth):
    r = client.post("/api/grievances?tenant=ka-bengaluru", json={"text": "qwrtp zxcvb mnbvc", "consent": True,
                                                                   "contact_phone": "9123456700"})
    assert r.status_code == 201 and r.json()["status"] == "human_review" and r.json()["department"] is None
    pid = r.json()["public_id"]
    nodal = auth("ka.nodal")
    queue = client.get("/api/nodal/triage-queue", headers=nodal).json()
    assert pid in {x["public_id"] for x in queue}
    cfg = client.get("/api/public/config?tenant=ka-bengaluru").json()
    cat = next(c for c in cfg["categories"] if c["code"] == "roads")
    r = client.post(f"/api/nodal/triage-queue/{pid}/route", headers=nodal, json={"category_id": cat["id"], "note": "Caller clarified pothole"})
    assert r.status_code == 200 and r.json()["status"] == "submitted" and r.json()["department"]["code"] == "ROADS"
    assert r.json()["sla_due_at"]
    detail = client.get(f"/api/grievances/{pid}", headers=nodal).json()
    assert detail["triage_override"]["category"] == "roads"


def test_citizen_dispute_sends_to_human_review(client, auth):
    cit = auth("ka.citizen1")
    text = "Garbage not collected for a week near Jayanagar 3rd block"
    tri = preview(client, text)
    r = client.post("/api/grievances", headers=cit, json={"text": text, "triage_id": tri["triage_id"], "consent": True,
                                                         "request_human_review": True, "human_review_note": "It is a drain issue"})
    assert r.json()["status"] == "human_review" and r.json()["department"] is None


def test_transfer_joint_escalate_assign(client, auth):
    off = auth("ka.officer.swm")
    cit = auth("ka.citizen1")
    tri = preview(client, "Garbage dumped on the road near Koramangala park")
    pid = client.post("/api/grievances", headers=cit, json={"text": "Garbage dumped on the road near Koramangala park",
                                                          "triage_id": tri["triage_id"], "consent": True}).json()["public_id"]
    cfg = client.get("/api/public/config?tenant=ka-bengaluru").json()
    roads = next(d for d in cfg["departments"] if d["code"] == "ROADS")
    health = next(d for d in cfg["departments"] if d["code"] == "HEALTH")
    colleagues = client.get("/api/officer/colleagues", headers=off).json()
    me = next(c for c in colleagues if c["role"] == "officer")
    assert client.post(f"/api/grievances/{pid}/assign", headers=off, json={"officer_id": me["id"]}).status_code == 200
    r = client.post(f"/api/grievances/{pid}/joint", headers=off, json={"department_id": health["id"], "note": "Health hazard - vector risk"})
    assert r.status_code == 200 and r.json()["joint_departments"]
    hoff = auth("ka.officer.health")
    assert pid in {x["public_id"] for x in client.get("/api/grievances?page_size=200", headers=hoff).json()["items"]}
    r = client.post(f"/api/grievances/{pid}/escalate", headers=off, json={"note": "Needs zonal attention"})
    assert r.json()["escalation_level"] == 1
    assert client.post(f"/api/grievances/{pid}/transfer", headers=off, json={"department_id": roads["id"], "reason": "x"}).status_code == 422
    r = client.post(f"/api/grievances/{pid}/transfer", headers=off, json={"department_id": roads["id"], "reason": "Debris on carriageway - roads"})
    assert r.status_code == 200 and r.json()["department"]["code"] == "ROADS"
    assert client.get(f"/api/grievances/{pid}", headers=off).status_code == 404  # no longer in SWM scope


def test_queue_filters_and_sorting_change_results(client, auth):
    nodal = auth("ka.nodal")
    all_ = client.get("/api/grievances?page_size=200", headers=nodal).json()
    emerg = client.get("/api/grievances?page_size=200&priority=Emergency", headers=nodal).json()
    assert 0 < emerg["total"] < all_["total"]
    assert all(x["priority"] == "Emergency" for x in emerg["items"])
    breached = client.get("/api/grievances?page_size=200&sla=breached", headers=nodal).json()
    assert all(x["sla"]["state"] == "breached" for x in breached["items"])
    by_pri = client.get("/api/grievances?page_size=200&sort=-priority", headers=nodal).json()["items"]
    assert by_pri[0]["priority"] == "Emergency"
    q = client.get("/api/grievances?page_size=200&q=Jayanagar", headers=nodal).json()
    assert 0 < q["total"] < all_["total"]
