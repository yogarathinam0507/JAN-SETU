"""PS2 call centre, PS3 e-Office, PS4 monitoring, PS5 benefits/assistant, analytics, audit, health."""
from app.data.lexicon import EVAL_DATASET
import io

from pypdf import PdfWriter


def make_pdf(text: str) -> bytes:
    """Minimal one-page PDF with a text layer (built by hand so the test needs no extra libraries)."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


_ = PdfWriter


# ---------------------------------------------------------------- PS2
def test_simulated_call_to_ticket_and_wrap(client, auth):
    a = auth("ka.agent1")
    i = client.post("/api/agent/simulate-call", headers=a, json={"script": 3}).json()
    assert i["simulated"] is True and i["channel_label"].startswith("Practice call") and i["practice"] is True and i["priority"] == "Emergency"
    assert i["caller_phone"].startswith("******")
    q = client.get("/api/agent/queue", headers=a).json()
    assert i["id"] in {x["id"] for x in q["queued"]} and q["telephony"]["state"] == "simulated"
    assert client.post(f"/api/agent/interactions/{i['id']}/accept", headers=a).status_code == 200
    client.post(f"/api/agent/interactions/{i['id']}/transcript", headers=a, json={"speaker": "agent", "text": "Please move away from the transformer."})
    assist = client.get(f"/api/agent/interactions/{i['id']}/assist", headers=a).json()
    assert assist["triage"]["category_code"] == "power_hazard" and assist["triage"]["emergency"]
    assert any(n["action"] == "create_ticket" for n in assist["next_actions"])
    r = client.post(f"/api/agent/interactions/{i['id']}/create-ticket", headers=a, json={"location_text": "2nd Main Koramangala"})
    assert r.status_code == 422  # verbal consent required
    r = client.post(f"/api/agent/interactions/{i['id']}/create-ticket", headers=a,
                    json={"location_text": "2nd Main Koramangala", "consent_confirmed_verbally": True})
    assert r.status_code == 201 and r.json()["grievance"]["department"]["code"] == "ELEC_EMG"
    assert r.json()["grievance"]["channel"] == "voice"
    assert client.post(f"/api/agent/interactions/{i['id']}/create-ticket", headers=a, json={}).status_code == 409
    assert client.post(f"/api/agent/interactions/{i['id']}/wrap", headers=a, json={"disposition": "nope"}).status_code == 422
    assert client.post(f"/api/agent/interactions/{i['id']}/wrap", headers=a, json={"disposition": "callback_scheduled"}).status_code == 422
    w = client.post(f"/api/agent/interactions/{i['id']}/wrap", headers=a, json={"disposition": "grievance_registered",
                                                                              "summary": assist["summary"], "action_items": assist["action_items"]})
    assert w.status_code == 200 and w.json()["status"] == "closed" and w.json()["disposition"] == "grievance_registered"
    hod = auth("ka.hod")
    r = client.post(f"/api/agent/interactions/{i['id']}/qa", headers=hod, json={"scores": {"greeting": 2}})
    assert r.status_code == 422
    scores = {k: 2 for k in ("greeting", "verification", "accuracy", "empathy", "resolution", "closure")}
    r = client.post(f"/api/agent/interactions/{i['id']}/qa", headers=hod, json={"scores": scores | {"accuracy": 1}})
    assert r.json()["qa_review"]["percent"] == round(100 * 11 / 12, 1)
    sup = client.get("/api/agent/supervisor", headers=hod).json()
    assert sup["simulated"] >= 1 and sup["qa"]["reviewed"] >= 1


def test_scheme_query_call_gets_cited_knowledge(client, auth):
    a = auth("ka.agent1")
    i = client.post("/api/agent/simulate-call", headers=a, json={"script": 2}).json()
    client.post(f"/api/agent/interactions/{i['id']}/accept", headers=a)
    assist = client.get(f"/api/agent/interactions/{i['id']}/assist", headers=a).json()
    assert assist["knowledge"] and assist["knowledge"][0]["title"].startswith("Gruha Lakshmi")
    assert assist["knowledge"][0]["label"].startswith("SAMPLE")


def test_handoff_and_callback_request(client, auth):
    a = auth("ka.agent1")
    i = client.post("/api/agent/interactions", headers=a, json={"channel": "web_chat", "first_message": "Need help with ration card"}).json()
    assert i["simulated"] is True
    r = client.post(f"/api/agent/interactions/{i['id']}/handoff", headers=a, json={"note": "Needs supervisor"})
    assert r.json()["status"] == "queued" and r.json()["handoff_history"]
    cb = client.post("/api/assistant/callback-request?tenant=ka-bengaluru",
                     json={"name": "Asha", "phone": "9123456781", "consent": True, "topic": "pension"})
    assert cb.status_code == 201
    q = client.get("/api/agent/queue", headers=a).json()
    assert any(x["channel"] == "callback_request" and not x["simulated"] for x in q["queued"])


# ---------------------------------------------------------------- PS3
def test_draft_generate_edit_never_sends(client, auth):
    off = auth("ka.officer.streetlight")
    pid = client.get("/api/grievances?page_size=1", headers=off).json()["items"][0]["public_id"]
    tpls = client.get("/api/templates", headers=off).json()
    kn = next(t for t in tpls if t["language"] == "kn")
    assert "SAMPLE" in kn["label"]
    d = client.post("/api/drafts/generate", headers=off, json={"template_id": kn["id"], "grievance_ref": pid}).json()
    assert pid in d["content"] and "ಬೀದಿ" in d["content"] and d["status"] == "draft" and "never sends" in d["notice"]
    r = client.put(f"/api/drafts/{d['id']}", headers=off, json={"content": d["content"] + "\nEdited by officer.", "status": "ready_for_manual_dispatch"})
    assert r.json()["version"] == 2 and r.json()["status"] == "ready_for_manual_dispatch"
    assert client.put(f"/api/drafts/{d['id']}", headers=off, json={"content": "x" * 20, "status": "sent"}).status_code == 422
    listed = client.get(f"/api/drafts?grievance_ref={pid}", headers=off).json()
    assert listed[0]["content"].endswith("Edited by officer.")


def test_efile_routing_with_audit(client, auth):
    off = auth("ka.officer.roads")
    f = client.post("/api/efiles", headers=off, json={"subject": "Resurfacing estimate for Whitefield main road"}).json()
    nodal_id = next(c["id"] for c in client.get("/api/officer/colleagues", headers=auth("ka.nodal")).json() if c["role"] == "nodal")
    r = client.post(f"/api/efiles/{f['id']}/move", headers=off, json={"action": "forward", "to_user_id": nodal_id, "note": "For approval"})
    assert r.status_code == 200 and r.json()["status"] == "in_review"
    cfg = client.get("/api/public/config?tenant=ka-bengaluru").json()
    swd = next(d for d in cfg["departments"] if d["code"] == "SWD")
    n = auth("ka.nodal")
    r = client.post(f"/api/efiles/{f['id']}/move", headers=n, json={"action": "send_to_department", "to_department_id": swd["id"], "note": "Drain work first"})
    assert r.json()["department"].startswith("Storm") and len(r.json()["movements"]) == 3
    r = client.post(f"/api/efiles/{f['id']}/move", headers=n, json={"action": "close", "note": "Done"})
    assert r.json()["status"] == "closed"
    assert client.post(f"/api/efiles/{f['id']}/move", headers=n, json={"action": "close", "note": "again"}).status_code == 409


def test_document_upload_extraction_summary_search(client, auth):
    off = auth("ka.officer.water")
    pdf = make_pdf("Order No. BWS/2026/114 dated 12-10-2026 sanctions Rs. 4,50,000 for pipeline repair in Indiranagar.")
    r = client.post("/api/documents", headers=off, files={"file": ("order.pdf", io.BytesIO(pdf), "application/pdf")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["extraction_status"] == "extracted:pypdf"
    assert "12-10-2026" in body["metadata"]["dates"] and any("4,50,000" in a for a in body["metadata"]["amounts"])
    img = client.post("/api/documents", headers=off, files={"file": ("scan.png", io.BytesIO(b"\x89PNG" + b"0" * 20), "image/png")})
    assert img.json()["extraction_status"] == "ocr_not_configured" and img.json()["ocr_note"]
    hits = client.get("/api/documents?q=pipeline", headers=off).json()
    assert hits and hits[0]["filename"] == "order.pdf"


def test_vendor_work_order_cycle(client, auth):
    v = auth("ka.vendor")
    wos = client.get("/api/vendor/work-orders", headers=v).json()
    assert wos
    wo = wos[0]
    assert client.post(f"/api/vendor/work-orders/{wo['id']}/progress", headers=v, json={"status": "completed", "note": "done"}).status_code == 422
    client.post(f"/api/vendor/work-orders/{wo['id']}/photo", headers=v, files={"file": ("done.jpg", io.BytesIO(b"\xff\xd8\xff" + b"0" * 30), "image/jpeg")})
    r = client.post(f"/api/vendor/work-orders/{wo['id']}/progress", headers=v, json={"status": "completed", "note": "Pothole filled"})
    assert r.json()["status"] == "completed"
    off = auth("ka.officer.roads")
    r = client.post(f"/api/work-orders/{wo['id']}/verify", headers=off, json={"accept": True, "note": "Inspected OK"})
    assert r.json()["status"] == "verified"
    sc = client.get("/api/vendor/scorecard", headers=v).json()
    assert sc["completed"] >= 1 and sc["vendor"] == "Sri Sai Infra Works"
    assert client.get("/api/vendor/work-orders", headers=auth("tn.vendor")).json() == [] or \
        wo["id"] not in {w["id"] for w in client.get("/api/vendor/work-orders", headers=auth("tn.vendor")).json()}


# ---------------------------------------------------------------- PS4
def test_monitoring_labels_real_vs_simulated(client, auth):
    h = auth("ka.admin")
    s = client.get("/api/monitoring/services", headers=h).json()["services"]
    modes = {x["check_mode"] for x in s}
    assert {"in_process", "simulated", "planned"} <= modes
    for x in s:
        if x["check_mode"] == "simulated":
            assert x["data_label"] == "Synthetic probe (test data)" and x["endpoint"] == "(synthetic probe)"
        if x["check_mode"] == "planned":
            assert x["checks"] == 0 and not x["enabled"]
    seva = next(x for x in s if x["name"].startswith("Seva Sindhu"))
    assert "awaiting authorization" in seva["name"] and seva["check_mode"] == "planned" and seva["last_status"] == "no data"
    real = next(x for x in s if x["check_mode"] == "in_process")
    r = client.post(f"/api/monitoring/services/{real['id']}/check-now", headers=h).json()
    assert r["ok"] and r["simulated"] is False
    assert client.post(f"/api/monitoring/services/{seva['id']}/check-now", headers=h).status_code == 409


def test_monitoring_http_requires_authorization(client, auth):
    h = auth("ka.admin")
    r = client.post("/api/monitoring/services", headers=h, json={"name": "Portal", "endpoint": "https://example.gov.in", "check_mode": "http"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "authorization_required"


def test_incidents_hypotheses_need_operator(client, auth):
    h = auth("ka.admin")
    incs = client.get("/api/monitoring/incidents", headers=h).json()
    assert incs and all(i["simulated"] for i in incs)
    i = incs[0]
    assert all("operator must confirm" in x["status"] for x in i["hypotheses"])
    r = client.post(f"/api/monitoring/incidents/{i['id']}", headers=h, json={"action": "confirm_root_cause", "note": "Upstream maintenance window"})
    assert r.json()["confirmed_root_cause"] == "Upstream maintenance window"
    d = client.get(f"/api/monitoring/services/{client.get('/api/monitoring/services', headers=h).json()['services'][0]['id']}", headers=h).json()
    assert "anomaly" in d and "risk" in d


def test_health_endpoints_and_metrics(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/health/ready").json()["database"] == "ok"
    d = client.get("/api/diagnostics").json()
    assert d["ai_mode"] == "rule_based_demo" and d["providers"]["sms"] == "simulated"
    m = client.get("/metrics").text
    assert "jansetu_grievances_total" in m and "jansetu_uptime_seconds" in m


# ---------------------------------------------------------------- PS5
def test_assistant_scheme_grievance_kb_and_unknown(client):
    q = "/api/assistant/chat?tenant=ka-bengaluru"
    r = client.post(q, json={"message": "Who can get Gruha Lakshmi?", "language": "en"}).json()
    assert r["type"] == "scheme" and r["scheme"]["verified"] is False and "ILLUSTRATIVE" in r["scheme"]["label"]
    r = client.post(q, json={"message": "ಗೃಹ ಲಕ್ಷ್ಮಿ ಯೋಜನೆ ಯಾರಿಗೆ?", "language": "kn"}).json()
    assert r["type"] == "scheme" and not r["translation_missing"]
    r = client.post(q, json={"message": "Garbage not collected for a week near my house", "language": "en"}).json()
    assert r["type"] == "grievance" and r["actions"][0]["type"] == "file_grievance"
    r = client.post(q, json={"message": "How long will my complaint take?", "language": "en"}).json()
    assert r["type"] == "knowledge" and r["citations"] and r["citations"][0]["title"].startswith(("Service-level", "How grievance"))
    r = client.post(q, json={"message": "What is the capital of Mongolia?", "language": "en"}).json()
    assert r["type"] == "no_answer" and {"type": "human_help"} in r["actions"]
    r = client.post(q, json={"message": "What is the capital of Mongolia?", "language": "sat"}).json()
    assert r["translation_missing"] is True


def test_eligibility_check_api_never_decides_on_unverified_content(client):
    base = "/api/benefits/schemes/gruha_lakshmi"
    d = client.get(base + "?tenant=ka-bengaluru").json()
    assert d["official_url"] is None and d["questions"]
    r = client.post(base + "/check?tenant=ka-bengaluru", json={"answers": {"resident": "yes"}}).json()
    assert r["outcome"] == "more_information_required" and r["missing_questions"]
    r = client.post(base + "/check?tenant=ka-bengaluru", json={"answers": {"resident": "yes", "gender": "yes", "head_of_household": "yes", "income_tax": "no"}}).json()
    assert r["outcome"] == "not_enough_verified_information" and "information assistance" in r["disclaimer"]
    cats = {s["service_category"] for s in client.get("/api/benefits/schemes?tenant=ka-bengaluru").json()}
    for c in ("health", "education", "labour", "housing", "food", "agriculture", "revenue", "social_welfare"):
        assert c in cats


def test_scheme_cannot_be_marked_verified_without_source(client, auth):
    h = auth("ka.content")
    r = client.put("/api/knowledge/schemes/shakti", headers=h, json={"verified": True})
    assert r.status_code == 422
    r = client.put("/api/knowledge/schemes/shakti", headers=h, json={"verified": True, "official_url": "https://example.gov.in/shakti"})
    assert r.status_code == 200 and r.json()["version"] == 2


def test_kb_versioning_and_citations(client, auth):
    h = auth("ka.content")
    v1 = client.post("/api/knowledge/documents", headers=h, json={"title": "Tree pruning policy", "doc_key": "tree-pruning",
                                                                 "body": "Requests for tree pruning near power lines are handled within 7 days by the parks department."}).json()
    v2 = client.post("/api/knowledge/documents", headers=h, json={"title": "Tree pruning policy", "doc_key": "tree-pruning",
                                                                 "body": "Requests for tree pruning near power lines are handled within 5 working days by the parks department.",
                                                                 "verified": True, "source_url": "https://example.gov.in/trees"}).json()
    assert v2["version"] == v1["version"] + 1
    docs = client.get("/api/knowledge/documents?include_history=true", headers=h).json()
    old = next(d for d in docs if d["id"] == v1["id"])
    assert old["status"] == "superseded"
    res = client.get("/api/knowledge/search?q=tree pruning power lines", headers=h).json()["results"]
    assert res[0]["version"] == v2["version"] and "5 working days" in res[0]["text"] and res[0]["verified"]
    client.post(f"/api/knowledge/documents/{v2['id']}/status", headers=h, json={"status": "inactive", "reason": "withdrawn"})
    res = client.get("/api/knowledge/search?q=tree pruning power lines", headers=h).json()["results"]
    assert all(r["document_id"] != v2["id"] for r in res)
    assert client.post("/api/knowledge/documents", headers=auth("ka.agent1"), json={"title": "x" * 5, "body": "y" * 30}).status_code == 403


def test_kb_pdf_upload(client, auth):
    h = auth("ka.content")
    pdf = make_pdf("Seva helpline guidance for pension status enquiries takes three working days.")
    r = client.post("/api/knowledge/documents/upload", headers=h, data={"title": "Pension status guidance", "language": "en"},
                    files={"file": ("p.pdf", io.BytesIO(pdf), "application/pdf")})
    assert r.status_code == 201 and r.json()["extraction_status"] == "extracted:pypdf" and r.json()["chunks"] >= 1


# ---------------------------------------------------------------- analytics / audit / evidence
def test_analytics_filters_change_data_and_metrics_are_consistent(client, auth):
    h = auth("ka.hod")
    all_ = client.get("/api/analytics/overview?period=90d", headers=h).json()
    assert all_["meta"]["data_mode"] in {"test data", "test + live records"} and all_["meta"]["source"]
    w7 = client.get("/api/analytics/overview?period=7d", headers=h).json()
    assert w7["totals"]["total"] < all_["totals"]["total"]
    cfg = client.get("/api/public/config?tenant=ka-bengaluru").json()
    water = next(d for d in cfg["departments"] if d["code"] == "WATER")
    f = client.get(f"/api/analytics/overview?period=90d&department_id={water['id']}", headers=h).json()
    assert 0 < f["totals"]["total"] < all_["totals"]["total"]
    assert list(f["distribution"]["department"]) == [water["names"]["en"]]
    kn = client.get("/api/analytics/overview?period=90d&language=kn", headers=h).json()
    assert set(kn["distribution"]["language"]) == {"kn"}
    rng = client.get("/api/analytics/overview?date_from=2020-01-01T00:00:00&date_to=2020-01-02T00:00:00", headers=h).json()
    assert rng["totals"]["total"] == 0 and rng["meta"]["window"].startswith("2020-01-01")
    d = all_["duplicates"]
    assert d["duplicates"] == d["linked_reports"] - d["master_incidents"]
    nodal = client.get("/api/nodal/master-incidents", headers=auth("ka.nodal")).json()["stats"]
    assert nodal["definition"] == d["definition"]
    assert sum(all_["distribution"]["status"].values()) == all_["totals"]["total"]
    exp = client.get("/api/analytics/export?period=90d", headers=h)
    assert exp.status_code == 200 and "attachment" in exp.headers["content-disposition"] and exp.json()["totals"] == all_["totals"]


def test_ai_eval_is_measured_with_denominator(client, auth):
    r = client.post("/api/analytics/ai-eval/run", headers=auth("ka.auditor")).json()
    assert r["overall"]["n"] == len(EVAL_DATASET) and r["by_language"]["kn"]["n"] == sum(1 for x in EVAL_DATASET if x[0] == "kn")
    assert "not evidence of real-world accuracy" in r["caveat"]
    assert client.post("/api/analytics/ai-eval/run", headers=auth("ka.hod")).status_code == 403


def test_audit_chain_and_sampling(client, auth):
    h = auth("ka.auditor")
    assert client.get("/api/audit/verify-chain", headers=h).json()["valid"] is True
    logs = client.get("/api/audit/logs?action=grievance", headers=h).json()
    assert logs["total"] > 0 and all(l["action"].startswith("grievance") for l in logs["items"])
    s = client.get("/api/audit/closure-sample?size=5&seed=1", headers=h).json()
    assert s["sample_size"] <= 5 and all("qa_flags" in x for x in s["items"])


def test_admin_config_changes_are_audited(client, auth):
    h = auth("ka.admin")
    ov = client.get("/api/admin/overview", headers=h).json()
    low = next(s for s in ov["sla_policies"] if s["priority"] == "Low")
    assert client.put(f"/api/admin/sla/{low['id']}", headers=h, json={"first_response_hours": 200, "resolve_hours": 100}).status_code == 422
    r = client.put(f"/api/admin/sla/{low['id']}", headers=h, json={"first_response_hours": 48, "resolve_hours": 160})
    assert r.json()["resolve_hours"] == 160
    r = client.patch("/api/admin/integrations/telephony", headers=h, json={"state": "connected_tested", "notes": "trust me"})
    assert r.status_code == 422  # cannot claim tested without test evidence
    logs = client.get("/api/audit/logs?action=config", headers=auth("ka.auditor")).json()["items"]
    assert any(l["action"] == "config.sla" for l in logs)


def test_evidence_and_integrations_public(client):
    ev = client.get("/api/public/evidence").json()
    statuses = {f["status"] for f in ev["features"]}
    assert statuses <= {"Working", "Demo/Simulated", "Planned/Requires External Credentials"} and len(ev["features"]) > 40
    integ = client.get("/api/public/integrations?tenant=ka-bengaluru").json()
    states = {i["code"]: i["state"] for i in integ["integrations"]}
    assert states["telephony"] == "simulated" and states["digilocker"] == "planned" and states["seva_sindhu"] == "planned"


def test_privacy_notice_and_data_export(client, auth):
    p = client.get("/api/public/privacy?tenant=ka-bengaluru").json()
    assert "Not a compliance claim" in p["status"]
    h = auth("ka.citizen1")
    exp = client.get("/api/me/export", headers=h).json()
    assert exp["profile"]["phone"] == "9845010001" and exp["grievances"]
    r = client.post("/api/me/deletion-request", headers=h, json={"reason": "test"}).json()
    assert r["status"] == "pending_review"


def test_spa_routes_and_api_404(client):
    for path in ("/", "/citizen", "/citizen/tickets", "/benefits", "/agent", "/officer", "/nodal", "/vendor", "/admin", "/analytics",
                 "/monitoring", "/knowledge", "/audit", "/integrations", "/evidence", "/login", "/health", "/privacy"):
        r = client.get(path)
        assert r.status_code == 200 and "<div id=\"app\"" in r.text, path
    assert client.get("/api/nope").status_code == 404
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/api/docs").status_code == 200
