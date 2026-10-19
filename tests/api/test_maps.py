"""Live map, field-team live location sharing, citizen tracking, first-start bootstrap and config parsing."""
from datetime import timedelta


def test_map_config_is_public_and_has_tenant_center(client):
    c = client.get("/api/map/config?tenant=ka-bengaluru").json()
    assert c["tile_url"].startswith("https://") and "{z}" in c["tile_url"]
    assert 12.8 < c["center"]["lat"] < 13.1 and 77.4 < c["center"]["lng"] < 77.9
    assert c["wards"] and all(w["demo_boundary"] for w in c["wards"])
    t = client.get("/api/map/config?tenant=tn-chennai").json()
    assert 12.9 < t["center"]["lat"] < 13.2


def test_live_map_scope_and_roles(client, auth):
    nodal = client.get("/api/map/live", headers=auth("ka.nodal")).json()
    assert nodal["markers"] and all(m["lat"] is not None for m in nodal["markers"])
    assert {m["status"] for m in nodal["markers"]} <= {"submitted", "accepted", "in_progress", "info_requested", "reopened"}
    off = client.get("/api/map/live", headers=auth("ka.officer.streetlight")).json()
    assert off["markers"] and {m["category_code"] for m in off["markers"]} == {"streetlight"}
    allm = client.get("/api/map/live?status=all", headers=auth("ka.nodal")).json()
    assert len(allm["markers"]) >= len(nodal["markers"])
    cat = client.get("/api/map/live?status=all&category=garbage", headers=auth("ka.nodal")).json()
    assert cat["markers"] and all(m["category_code"] == "garbage" for m in cat["markers"])
    hod = client.get("/api/map/live", headers=auth("ka.hod")).json()
    assert hod["markers"] and all(m["location"] == "" for m in hod["markers"])  # no free-text location for aggregate role
    assert client.get("/api/map/live", headers=auth("ka.citizen1")).status_code == 403
    assert client.get("/api/map/live", headers=auth("ka.admin")).status_code == 403
    tn_ids = {m["id"] for m in client.get("/api/map/live?status=all", headers=auth("tn.nodal")).json()["markers"]}
    assert not tn_ids & {m["id"] for m in allm["markers"]}  # tenant isolation


def test_field_location_sharing_lifecycle(client, auth):
    off = auth("ka.officer.roads")
    assert client.put("/api/field/location", headers=auth("ka.citizen1"), json={"lat": 12.9, "lng": 77.6}).status_code == 403
    assert client.put("/api/field/location", headers=off, json={"lat": 120, "lng": 77.6}).status_code == 422
    r = client.put("/api/field/location", headers=off, json={"lat": 12.971, "lng": 77.751, "accuracy_m": 12, "status_note": "live GPS"})
    assert r.status_code == 200 and r.json()["ttl_minutes"] == 15
    team = client.get("/api/map/live", headers=auth("ka.nodal")).json()["team"]
    me = next(p for p in team if p["role"] == "officer" and p["department"] and p["department"].startswith("Roads"))
    assert me["lat"] == 12.971 and me["accuracy_m"] == 12
    # other-department officers do not see this officer; tenant TN does not see it either
    water_team = client.get("/api/map/live", headers=auth("ka.officer.water")).json()["team"]
    assert all(p["user_id"] != me["user_id"] for p in water_team)
    assert all(p["user_id"] != me["user_id"] for p in client.get("/api/map/live", headers=auth("tn.nodal")).json()["team"])
    # stale positions disappear after the TTL
    from app.db import SessionLocal, utcnow
    from app.models import FieldLocation
    with SessionLocal() as db:
        loc = db.get(FieldLocation, me["user_id"])
        loc.updated_at = utcnow() - timedelta(minutes=20)
        db.commit()
    assert all(p["user_id"] != me["user_id"] for p in client.get("/api/map/live", headers=auth("ka.nodal")).json()["team"])
    assert client.delete("/api/field/location", headers=off).json()["ok"]
    logs = client.get("/api/audit/logs?action=field", headers=auth("ka.auditor")).json()["items"]
    assert {"field.location_sharing_started", "field.location_sharing_stopped"} <= {l["action"] for l in logs}


def test_citizen_sees_only_approximate_officer_distance(client, auth):
    cit = auth("ka.citizen1")
    text = "Garbage not collected near Koramangala 5th block market"
    tri = client.post("/api/triage/preview?tenant=ka-bengaluru", json={"text": text, "lat": 12.9352, "lng": 77.6245}).json()
    g = client.post("/api/grievances", headers=cit, json={"text": text, "triage_id": tri["triage_id"], "consent": True,
                                                         "lat": 12.9352, "lng": 77.6245}).json()
    pid = g["public_id"]
    tr = client.get(f"/api/grievances/{pid}/tracking", headers=cit).json()
    assert tr["lat"] == 12.9352 and tr["officer_distance_km"] is None
    off = auth("ka.officer.swm")
    client.post(f"/api/grievances/{pid}/actions", headers=off, json={"action": "accept"})
    client.post(f"/api/grievances/{pid}/actions", headers=off, json={"action": "start"})
    client.put("/api/field/location", headers=off, json={"lat": 12.9452, "lng": 77.6245})
    tr = client.get(f"/api/grievances/{pid}/tracking", headers=cit).json()
    assert 1.0 <= tr["officer_distance_km"] <= 1.2 and tr["officer_sharing"]
    assert "lat" not in str({k: v for k, v in tr.items() if k.startswith("officer")})  # no officer coordinates
    mine = client.get("/api/map/mine", headers=cit).json()["markers"]
    assert any(m["id"] == pid and m["officer_distance_km"] for m in mine)
    assert client.get(f"/api/grievances/{pid}/tracking", headers=auth("ka.citizen2")).status_code == 404
    client.delete("/api/field/location", headers=off)


def test_vendor_map_shows_only_own_work_orders(client, auth):
    v = client.get("/api/map/live?status=all", headers=auth("ka.vendor")).json()
    wo_tickets = {w["id"] for w in client.get("/api/vendor/work-orders", headers=auth("ka.vendor")).json()}
    assert len(v["markers"]) <= len(wo_tickets)


def test_csp_allows_only_configured_tile_host(client):
    csp = client.get("/").headers["content-security-policy"]
    assert "img-src 'self' data: blob: https://*.basemaps.cartocdn.com https://tile.openstreetmap.org" in csp
    assert "script-src 'self'" in csp
    # OpenStreetMap / CARTO tile policies need a Referer: the origin must be sent cross-site.
    assert client.get("/").headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_bootstrap_creates_and_seeds_empty_database(tmp_path, monkeypatch):
    """Regression for 'Could not reach the server (500)': a brand-new database must work without manual setup."""
    import subprocess
    import sys
    from pathlib import Path
    backend = Path(__file__).resolve().parents[2] / "backend"
    env = {"DATABASE_URL": f"sqlite:///{tmp_path / 'fresh.db'}", "UPLOAD_DIR": str(tmp_path / "up"), "ENABLE_BACKGROUND_JOBS": "false",
           "SECRET_KEY": "x" * 40, "PATH": __import__("os").environ["PATH"]}
    code = ("from fastapi.testclient import TestClient\nfrom app.main import app\n"
            "with TestClient(app) as c:\n  r=c.get('/api/public/tenants'); print(r.status_code, len(r.json()))\n"
            "  r=c.post('/api/auth/login', json={'username':'ka.nodal','password':'Demo@1234'}); print(r.status_code)")
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    lines = out.stdout.strip().splitlines()
    assert lines[-2] == "200 2" and lines[-1] == "200"


def test_bootstrap_never_seeds_in_production(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    backend = Path(__file__).resolve().parents[2] / "backend"
    env = {"DATABASE_URL": f"sqlite:///{tmp_path / 'prod.db'}", "APP_ENV": "production", "SECRET_KEY": "p" * 48,
           "ENABLE_BACKGROUND_JOBS": "false", "PATH": __import__("os").environ["PATH"]}
    code = ("from app.bootstrap import init_db\nprint(init_db())")
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, env=env, capture_output=True, text=True, timeout=120)
    assert "'migrated': True" in out.stdout and "'seeded': False" in out.stdout, out.stderr[-1500:]


def test_database_url_normalisation(monkeypatch):
    from app.config import BACKEND_DIR, Settings
    assert Settings(database_url="postgres://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgresql://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"
    rel = Settings(database_url="sqlite:///./data/x.db").database_url
    assert rel == f"sqlite:///{(BACKEND_DIR / 'data' / 'x.db').resolve()}"
    assert Settings(database_url="sqlite:////abs/x.db").database_url == "sqlite:////abs/x.db"
