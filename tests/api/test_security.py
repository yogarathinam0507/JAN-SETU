"""Authorization, tenant isolation, PII masking, uploads, headers and 'no localhost' guarantees."""
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def first_ticket(client, h):
    return client.get("/api/grievances?page_size=1", headers=h).json()["items"][0]["public_id"]


def test_unauthenticated_access_denied(client):
    assert client.get("/api/grievances").status_code == 401
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/audit/logs").status_code == 401


def test_bad_credentials(client):
    r = client.post("/api/auth/login", json={"username": "ka.admin", "password": "wrong-password"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "bad_credentials"


def test_citizen_cannot_read_another_citizens_ticket(client, auth):
    other = first_ticket(client, auth("ka.citizen2"))
    r = client.get(f"/api/grievances/{other}", headers=auth("ka.citizen1"))
    assert r.status_code == 404
    mine = client.get("/api/grievances?page_size=200", headers=auth("ka.citizen1")).json()["items"]
    assert other not in {x["public_id"] for x in mine}


def test_tenant_isolation(client, auth):
    tn_ticket = first_ticket(client, auth("tn.auditor"))
    for user in ("ka.auditor", "ka.nodal", "ka.agent1"):
        assert client.get(f"/api/grievances/{tn_ticket}", headers=auth(user)).status_code == 404
    ka_ids = {x["public_id"] for x in client.get("/api/grievances?page_size=200", headers=auth("ka.auditor")).json()["items"]}
    assert tn_ticket not in ka_ids
    r = client.get("/api/public/config?tenant=tn-chennai", headers=auth("ka.citizen1"))
    assert r.status_code == 403


def test_roles_without_content_access(client, auth):
    for user in ("ka.admin", "ka.content", "ka.vendor", "ka.hod"):
        r = client.get("/api/grievances", headers=auth(user))
        assert r.status_code == 403, user
    t = first_ticket(client, auth("ka.auditor"))
    assert client.get(f"/api/grievances/{t}", headers=auth("ka.admin")).status_code == 403


@pytest.mark.parametrize("user,path", [
    ("ka.citizen1", "/api/admin/overview"), ("ka.officer.water", "/api/admin/overview"), ("ka.agent1", "/api/audit/logs"),
    ("ka.officer.water", "/api/nodal/triage-queue"), ("ka.citizen1", "/api/agent/queue"), ("ka.vendor", "/api/officer/summary"),
    ("ka.content", "/api/monitoring/services"), ("ka.citizen1", "/api/analytics/overview"), ("ka.officer.water", "/api/vendor/work-orders"),
    ("ka.agent1", "/api/knowledge/reindex"),
])
def test_server_side_rbac(client, auth, user, path):
    method = client.post if path.endswith("reindex") else client.get
    assert method(path, headers=auth(user)).status_code == 403


def test_auditor_is_read_only(client, auth):
    h = auth("ka.auditor")
    t = first_ticket(client, h)
    assert client.post(f"/api/grievances/{t}/actions", headers=h, json={"action": "accept"}).status_code == 403


def test_phone_masked_and_reveal_is_audited(client, auth):
    off = auth("ka.officer.water")
    items = client.get("/api/grievances?page_size=50", headers=off).json()["items"]
    t = items[0]
    assert re.fullmatch(r"\*{6}\d{4}", t["contact_phone"])
    assert client.post(f"/api/grievances/{t['public_id']}/reveal-contact", headers=off, json={"reason": "short"}).status_code == 422
    r = client.post(f"/api/grievances/{t['public_id']}/reveal-contact", headers=off, json={"reason": "Need to call for site access"})
    assert r.status_code == 200 and r.json()["audited"] and len(r.json()["contact_phone"]) == 10
    logs = client.get("/api/audit/logs?action=pii", headers=auth("ka.auditor")).json()["items"]
    assert any(l["entity_id"] == t["public_id"] and l["reason"] == "Need to call for site access" for l in logs)


def test_auditor_view_redacts_phone_numbers_in_text(client, auth):
    h = auth("ka.auditor")
    r = client.post("/api/grievances?tenant=ka-bengaluru", json={"text": "Garbage not collected, call me 9876501234", "consent": True,
                                                                   "contact_phone": "9876501234"})
    pid = r.json()["public_id"]
    d = client.get(f"/api/grievances/{pid}", headers=h).json()
    assert "9876501234" not in str(d)


def test_upload_validation(client, auth):
    h = auth("ka.citizen1")
    t = first_ticket(client, h)
    fake = client.post(f"/api/grievances/{t}/attachments", headers=h, data={"kind": "evidence"},
                       files={"file": ("x.png", io.BytesIO(b"MZ\x90\x00not-a-png"), "image/png")})
    assert fake.status_code == 415
    exe = client.post(f"/api/grievances/{t}/attachments", headers=h, data={"kind": "evidence"},
                      files={"file": ("x.exe", io.BytesIO(b"MZ\x90"), "application/octet-stream")})
    assert exe.status_code == 415
    after = client.post(f"/api/grievances/{t}/attachments", headers=h, data={"kind": "after"},
                        files={"file": ("x.png", io.BytesIO(b"\x89PNG" + b"0" * 10), "image/png")})
    assert after.status_code == 403  # citizens cannot upload resolution photos


def test_security_headers(client):
    r = client.get("/citizen")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert "unsafe-inline" not in r.headers["content-security-policy"]
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_logout_revokes_token(client, auth):
    h = auth("ka.citizen1")
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/me", headers=h).status_code == 401


def test_otp_login_demo_mode_is_labelled(client):
    r = client.post("/api/auth/otp/request", json={"tenant": "ka-bengaluru", "phone": "9988776655"}).json()
    assert r["simulated"] is True and "SMS gateway not configured" in r["message"]
    bad = client.post("/api/auth/otp/verify", json={"tenant": "ka-bengaluru", "phone": "9988776655", "code": "000000"})
    if r["demo_otp"] != "000000":
        assert bad.status_code == 401
    ok = client.post("/api/auth/otp/verify", json={"tenant": "ka-bengaluru", "phone": "9988776655", "code": r["demo_otp"]})
    assert ok.status_code in (200, 401)  # 401 only if the wrong-code attempt above consumed it - verify fresh code:
    r2 = client.post("/api/auth/otp/request", json={"tenant": "ka-bengaluru", "phone": "9988776655"}).json()
    ok = client.post("/api/auth/otp/verify", json={"tenant": "ka-bengaluru", "phone": "9988776655", "code": r2["demo_otp"]})
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "citizen"


def test_no_localhost_links_in_public_content(client):
    offenders = []
    for folder in ("frontend", "backend/app"):
        for f in (ROOT / folder).rglob("*"):
            if f.suffix in {".js", ".html", ".json", ".css", ".py"} and f.is_file():
                if re.search(r"https?://(localhost|127\.0\.0\.1)", f.read_text(encoding="utf-8", errors="ignore")):
                    offenders.append(str(f))
    assert not offenders, offenders
    ds = client.get("/api/public/benchmark/dataset").json()
    assert ds["self_url"].startswith("https://jansetu.example.org/")
    assert all(i["text"] for i in ds["items"])  # no blank benchmark records


def test_no_unverified_claims_in_ui():
    text = " ".join(f.read_text(encoding="utf-8") for f in (ROOT / "frontend").rglob("*") if f.suffix in {".js", ".html", ".json"})
    for phrase in ("DARPG Compliant", "Live IMD", "94.2%", "95.4%", "96.4%", "0% Error", "Ward 12", "TrustShield 94"):
        assert phrase not in text, phrase


def test_validation_errors_are_structured(client):
    r = client.post("/api/triage/preview?tenant=ka-bengaluru", json={"text": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error" and r.json()["error"]["fields"]
