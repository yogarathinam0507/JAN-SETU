"""Single source for the feature evidence matrix -> backend/app/data/feature_evidence.json and docs/FEATURE_EVIDENCE_MATRIX.md.
Usage: python scripts/feature_matrix.py "<test summary line>" """
import json
import sys
from datetime import date
from pathlib import Path

W, S, P = "Working", "Demo/Simulated", "Planned/Requires External Credentials"
F = [
 # PS1
 ("PS1", "Typed complaint filing with confirm-before-submit wizard", W, "tests/api/test_grievance_flow.py; e2e test_guest_files_complaint", "frontend/js/pages/citizen.js"),
 ("PS1", "Browser voice input with editable transcript + mandatory confirmation", W, "API rejects unconfirmed voice tickets (test_voice_complaint_requires_confirmed_transcript). Speech quality depends on the browser.", "frontend/js/voice.js"),
 ("PS1", "Server-side STT (Bhashini / AI4Bharat / Whisper)", P, "Adapter setting STT_PROVIDER; not connected", "app/config.py"),
 ("PS1", "Language detection (Unicode script + transliteration hints)", W, "tests/unit/test_language_i18n.py", "app/services/language.py"),
 ("PS1", "Category / department / urgency classification", S, "Transparent rule-based demo classifier (labelled in UI); 48-example labelled eval set; LLM adapter tested with mocks only", "app/services/triage.py"),
 ("PS1", "LLM classification via OpenAI-compatible provider", P, "Adapter + schema/registry validation implemented and unit-tested with mocks; needs LLM_* credentials", "app/services/llm.py"),
 ("PS1", "Structured triage schema validation + registry checks", W, "test_output_validates_against_schema, test_llm_output_outside_registry_is_rejected", "app/services/triage.py"),
 ("PS1", "Human triage queue for unclear / low-confidence / disputed complaints", W, "test_human_triage_queue_and_manual_routing, test_citizen_dispute_sends_to_human_review", "app/routers/nodal.py"),
 ("PS1", "AI failure surfaced with retry + human fallback (no canned default)", W, "test_llm_failure_is_surfaced_not_masked", "app/routers/grievances.py"),
 ("PS1", "Empty routing-details panel until a complaint is analysed", W, "e2e test_routing_panel_empty_before_input", "frontend/js/pages/citizen.js"),
 ("PS1", "Routing details for citizens (category, department, priority, ward, key words); full rules/confidence for staff", W, "Rendered from each triage result; unit tests assert rules_applied", "frontend/js/pages/citizen.js"),
 ("PS1", "Deterministic emergency rules + safety message", W, "test_emergency_safety_message_and_rules", "app/data/lexicon.py"),
 ("PS1", "Configurable SLA policy and escalation matrix with audit", W, "test_sla_from_policy_table, test_escalation_matrix, admin SLA test", "app/services/workflow.py"),
 ("PS1", "Duplicate clustering into master incidents (500 m / ward + text rule) with unlink + audit", W, "test_duplicates_cluster_within_radius_and_stats_are_consistent", "app/services/workflow.py"),
 ("PS1", "Ward/zone mapping from GPS or locality name (no default ward)", S, "Logic works and is tested; ward boundaries are demo rectangles - load official GIS", "app/services/geo.py"),
 ("PS1", "Ticket ID, citizen history, officer queue, status updates, persistence", W, "test_full_citizen_to_officer_workflow (incl. restart)", "app/routers/grievances.py"),
 ("PS1", "Reject closure / reopen with reason; feedback & rating", W, "test_full_citizen_to_officer_workflow", "app/services/workflow.py"),
 ("PS1", "Before/after photo verification; after-photo required per category", W, "test_full_citizen_to_officer_workflow (after_photo_required)", "app/routers/grievances.py"),
 ("PS1", "Cross-department transfer and joint-action cases", W, "test_transfer_joint_escalate_assign", "app/routers/officer.py"),
 ("PS1", "Public tracking by ticket ID (no personal data)", W, "test_public_tracking_shows_no_personal_data", "app/routers/grievances.py"),
 ("PS1", "Citizen mobile OTP sign-in", S, "Works end to end; OTP shown on screen in demo mode (no SMS gateway)", "app/routers/auth.py"),
 ("PS1", "SMS / WhatsApp status updates", S, "Recorded as simulated notification events", "app/services/workflow.py"),
 # PS2
 ("PS2", "Unified queue (voice, web chat, email, WhatsApp, callback requests)", S, "Queue, priority ordering and wait times work; external channels are simulated records", "app/routers/agent.py"),
 ("PS2", "Simulated inbound call session (scripted transcript)", S, "Clearly labelled SIMULATED in UI and API", "app/services/callcentre.py"),
 ("PS2", "Real telephony (SIP / WebRTC / Asterisk / CPaaS)", P, "TelephonyProvider adapter boundary only", "app/services/callcentre.py"),
 ("PS2", "Agent assist: triage, cited knowledge, summary, action items, sentiment, duplicate check", W, "test_simulated_call_to_ticket_and_wrap", "app/routers/agent.py"),
 ("PS2", "One-click ticket creation from call with verbal-consent check", W, "test_simulated_call_to_ticket_and_wrap", "app/routers/agent.py"),
 ("PS2", "Disposition codes, callback scheduling, warm handoff", W, "test_handoff_and_callback_request", "app/routers/agent.py"),
 ("PS2", "Supervisor dashboard and transparent QA rubric", W, "test_simulated_call_to_ticket_and_wrap (QA scoring)", "app/routers/agent.py"),
 ("PS2", "Caller phone masking with audited reveal", W, "test_phone_masked_and_reveal_is_audited", "app/routers/agent.py"),
 ("PS2", "Live speech transcription during calls", P, "Needs telephony + STT provider", ""),
 # PS3
 ("PS3", "Role-specific officer dashboard, department/jurisdiction queues", W, "test_full_citizen_to_officer_workflow, scope tests", "app/services/scope.py"),
 ("PS3", "Accept / assign / reassign / transfer / request info / escalate / resolve / reject / reopen", W, "API tests", "app/routers/officer.py"),
 ("PS3", "Template-based draft letters & notices (Kannada/Tamil/English), editable, never sent/signed", W, "test_draft_generate_edit_never_sends", "app/routers/officer.py"),
 ("PS3", "LLM polishing of drafts", P, "Optional; needs LLM credentials", "app/services/drafting.py"),
 ("PS3", "Document upload, PDF text extraction, summary, metadata, search", W, "test_document_upload_extraction_summary_search", "app/routers/officer.py"),
 ("PS3", "OCR for scanned images", P, "OCR_PROVIDER not configured; status shown honestly", "app/services/kb.py"),
 ("PS3", "e-File routing (forward / return / send to department / close) with history", W, "test_efile_routing_with_audit", "app/routers/officer.py"),
 ("PS3", "Digital signature / state e-Office connectors", P, "Listed on /integrations as planned", ""),
 ("PS3", "Tamper-evident audit log of consequential actions", W, "test_audit_chain_and_sampling", "app/services/audit.py"),
 ("PS3", "Contractor work orders, completion photos, verification, scorecard", W, "test_vendor_work_order_cycle", "app/routers/vendor.py"),
 # PS4
 ("PS4", "Service registry (owner, environment, criticality, SLO)", W, "test_monitoring_labels_real_vs_simulated", "app/routers/monitoring.py"),
 ("PS4", "Real health check of this application (in-process)", W, "check-now test", "app/services/monitoring.py"),
 ("PS4", "HTTP checks only for explicitly authorized endpoints", W, "test_planned_and_unauthorized_services_are_never_probed, authorization_required test", "app/services/monitoring.py"),
 ("PS4", "Demo government services with synthetic history", S, "Every record flagged simulated and labelled 'Demo data / Simulated'", "app/services/monitoring.py"),
 ("PS4", "Seva Sindhu / Kaveri 2.0 / Kutumba monitoring", P, "Listed as planned; never probed", "app/seed.py"),
 ("PS4", "Availability, latency percentiles, SLO, incidents, alert history", W, "monitoring API tests", "app/routers/monitoring.py"),
 ("PS4", "Anomaly detection (z-score) and heuristic risk score", W, "test_anomaly_needs_history; labelled as heuristics", "app/services/monitoring.py"),
 ("PS4", "AI-assisted incident summary with operator-confirmed root cause", W, "test_incidents_hypotheses_need_operator", "app/services/monitoring.py"),
 ("PS4", "Prometheus /metrics endpoint", W, "test_health_endpoints_and_metrics", "app/routers/health.py"),
 ("PS4", "Grafana dashboards / auto-scaling", P, "Not configured; auto-scaling deliberately not performed", ""),
 # PS5
 ("PS5", "Multilingual assistant (scheme match, complaint detection, cited KB answers, honest no-answer)", W, "test_assistant_scheme_grievance_kb_and_unknown", "app/routers/assistant.py"),
 ("PS5", "Scheme navigator with eligibility questions (information only)", W, "test_eligibility_check_api_never_decides_on_unverified_content", "app/services/benefits.py"),
 ("PS5", "Karnataka scheme content (Gruha Lakshmi, Anna Bhagya, Gruha Jyothi, Shakti, Yuva Nidhi)", S, "Illustrative seed, verified=False, no official URLs until a content manager verifies", "app/data/seed_data.py"),
 ("PS5", "Versioned knowledge base with ingestion, chunking, BM25 retrieval, citations, deactivation", W, "test_kb_versioning_and_citations, test_kb_pdf_upload", "app/services/kb.py"),
 ("PS5", "Vector search (Qdrant/FAISS) + embeddings", P, "Planned; BM25 used", ""),
 ("PS5", "Grievance filing from the assistant with context carried over", W, "assistant returns file_grievance action; UI prefill", "frontend/js/pages/benefits.js"),
 ("PS5", "Assisted-service mode and human callback requests", W, "test_handoff_and_callback_request", "frontend/js/pages/benefits.js"),
 ("PS5", "Machine translation of answers", P, "TRANSLATION_PROVIDER not configured; UI says when an answer is not in the user's language", ""),
 # Platform
 ("Platform", "Server-side RBAC for 9 roles", W, "tests/api/test_security.py", "app/security.py"),
 ("Platform", "Tenant isolation (Karnataka / Chennai from one codebase)", W, "test_tenant_isolation", "app/services/scope.py"),
 ("Platform", "PII masking by default; audited reveal; redaction in staff views", W, "security tests", "app/services/masking.py"),
 ("Platform", "25-language registry with honest current-support tiers", W, "test_registry_has_25_languages_with_honest_tiers", "app/services/language.py"),
 ("Platform", "Interface strings: English, Kannada, Hindi, Tamil (others fall back to English, banner shown)", W, "i18n coverage tests; frontend/i18n/coverage.json", "frontend/i18n"),
 ("Platform", "RTL layout for Urdu / Sindhi / Kashmiri", W, "dir=rtl set by app.js; e2e test", "frontend/js/app.js"),
 ("Platform", "Analytics from persisted data with working filters, ranges, export, source/window labels", W, "test_analytics_filters_change_data_and_metrics_are_consistent", "app/routers/analytics.py"),
 ("Platform", "Measured AI-triage evaluation by language/category with denominators", W, "test_ai_eval_is_measured_with_denominator", "app/services/evaluation.py"),
 ("Platform", "Privacy notice (draft for legal review), data export, deletion requests", W, "test_privacy_notice_and_data_export", "app/routers/auth.py"),
 ("Platform", "DigiLocker / Aadhaar e-KYC / e-Kuber / state SSO / staff MFA", P, "Not connected; local password + demo OTP only", ""),
 ("Platform", "OpenAPI docs, health/readiness/diagnostics endpoints", W, "test_spa_routes_and_api_404, health tests", "app/main.py"),
 ("Platform", "Security headers (CSP without inline scripts), rate limiting, upload validation", W, "test_security_headers, test_upload_validation", "app/main.py"),
 ("Platform", "First-start auto setup: migrations + demo data on an empty database (fixes the 500 error)", W, "test_bootstrap_creates_and_seeds_empty_database", "app/bootstrap.py"),
 ("Platform", "Light / dark / system theme switch, remembered per device", W, "e2e test_theme_toggle_light_dark_and_persists", "frontend/js/app.js"),
 ("Platform", "Multi-account login: several users signed in on one device, instant switching", W, "e2e test_multi_account_switch_and_sign_out", "frontend/js/core.js"),
 ("Platform", "Sign-in-first portal: every page except sign-in and policy pages requires login; citizen OTP or user ID, department login", W, "e2e test_site_opens_on_sign_in_page_and_guards_every_page, test_staff_password_login_lands_on_dashboard", "frontend/js/app.js"),
 ("Platform", "Test-account list on the sign-in page (collapsed)", S, "Seeded test accounts only; endpoint disabled when APP_ENV=production", "frontend/js/pages/login.js"),
 ("Platform", "Role dashboards with live KPIs, charts and work lists for all 9 roles", W, "test_every_role_signs_in_and_gets_a_dashboard, e2e test_every_role_has_a_dashboard", "app/routers/dashboard.py"),
 ("Platform", "Role-aware notification bell (assignments, escalations, status changes, queue, alerts)", W, "test_new_complaint_is_auto_assigned_to_named_officer_and_citizen_is_notified", "app/routers/dashboard.py"),
 ("PS1", "Automatic assignment to the named department officer with a citizen notice (name, designation, department)", W, "test_new_complaint_is_auto_assigned_to_named_officer_and_citizen_is_notified, e2e test_citizen_files_complaint_sees_assigned_officer_and_officer_sees_it", "app/services/workflow.py"),
 ("Platform", "Synthetic located test complaints (about 95 per city, inside ward boundaries, 22 categories, varied status/age)", S, "test_synthetic_complaints_are_varied_located_and_assigned", "app/seed.py"),
 ("Platform", "Sessions valid regardless of server time zone (fix for 'session expired' on IST machines)", W, "test_token_is_valid_on_a_machine_in_ist; full suite run with TZ=Asia/Kolkata", "app/security.py"),
 ("Platform", "Formal government-portal layout: accessibility strip (text size, theme, language), navy menu, footer, SVG icons, no emoji", W, "e2e test_no_emoji_or_demo_wording_on_login_page, test_text_size_buttons", "frontend/css/app.css"),
 ("PS5", "Continuous voice dictation with Speak-in language and clear error messages; Read-aloud (text-to-speech)", W, "Browser Web Speech API; needs Chrome/Edge for dictation (verified manually, not automatable headless)", "frontend/js/voice.js"),
 ("PS1", "Map location picker (tap / drag pin / GPS) when filing", W, "e2e test_citizen_map_pin_from_gps", "frontend/js/pages/citizen.js"),
 ("PS1", "Citizen live tracking: progress, map, approximate officer distance", W, "test_citizen_sees_only_approximate_officer_distance", "app/routers/maps.py"),
 ("PS3", "Live operations map for staff (priority pins, auto-refresh, ward overlay, filters)", W, "test_live_map_scope_and_roles, e2e test_live_map_shows_pins_and_team_sharing", "frontend/js/pages/livemap.js"),
 ("PS3", "Field-team live location sharing (GPS or set on map) with TTL and audit", W, "test_field_location_sharing_lifecycle", "frontend/js/fieldshare.js"),
 ("Platform", "Map tiles: CARTO basemap (light/dark) with automatic OpenStreetMap fallback; Referer sent so tile servers do not block", S, "Public tile services; use a licensed/government tile server in production via MAP_TILE_URL", "app/config.py"),
 ("Platform", "Mobile-responsive UI", W, "e2e test_mobile_layout_has_no_horizontal_scroll", "frontend/css/app.css"),
]


def main(summary: str):
    root = Path(__file__).resolve().parent.parent
    data = {"description": "Every feature is marked Working (implemented and covered by tests or direct verification), "
                           "Demo/Simulated (works but uses synthetic data or a simulated channel, labelled in the UI), or "
                           "Planned/Requires External Credentials (adapter or plan only).",
            "updated": date.today().isoformat(), "test_summary": summary,
            "features": [{"ps": a, "feature": b, "status": c, "evidence": d, "where": e} for a, b, c, d, e in F]}
    (root / "backend" / "app" / "data" / "feature_evidence.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = ["# Feature evidence matrix", "", data["description"], "", f"Updated: {data['updated']} · Tests: {summary}", "",
             "| PS | Feature | Status | Evidence | Where |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | **{c}** | {d} | `{e}` |" if e else f"| {a} | {b} | **{c}** | {d} | |" for a, b, c, d, e in F]
    counts = {s: sum(1 for f in F if f[2] == s) for s in (W, S, P)}
    lines += ["", "Totals: " + ", ".join(f"{k}: {v}" for k, v in counts.items())]
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "FEATURE_EVIDENCE_MATRIX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "see docs/TEST_RESULTS.md")
