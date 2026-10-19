# Test results

Run on 19 Oct 2026 in the build sandbox (Python 3.13, Chromium via Playwright), with `TZ=Asia/Kolkata` to reproduce an Indian server clock (this exposed the earlier "session expired" bug, now fixed and covered by `test_token_is_valid_on_a_machine_in_ist`).

| Suite | Database | Passed | Failed | Skipped/Blocked |
|---|---|---|---|---|
| Unit + API + browser e2e (`pytest tests`) | SQLite | 254 | 0 | 0 |
| Unit + API (`pytest tests/unit tests/api`) | PostgreSQL 16 | 225 | 0 | 0 |
| Docker image / compose | - | not run | - | blocked: no Docker daemon in build sandbox |

## Tests per file (SQLite run)

| File | Passed |
|---|---|
| `tests/api/test_dashboard.py` (dashboards for every role, notifications, auto-assignment, synthetic data, IST tokens) | 20 |
| `tests/api/test_grievance_flow.py` | 10 |
| `tests/api/test_maps.py` | 9 |
| `tests/api/test_modules.py` | 23 |
| `tests/api/test_security.py` | 25 |
| `tests/e2e/test_ui.py` (sign-in-first, every role dashboard, filing with assigned officer, maps, themes, text size, mobile) | 29 |
| `tests/unit/test_language_i18n.py` | 21 |
| `tests/unit/test_rules.py` | 12 |
| `tests/unit/test_triage.py` | 105 |

Not automatable headless: microphone dictation and speech output (Web Speech API) - check manually in Chrome or Edge. Map tiles could not be fetched from the sandbox (outbound tile hosts blocked); pins, wards and the fallback notice were verified.

## Manual acceptance checklist (master prompt section 12)

| # | Check | Result | How verified |
|---|---|---|---|
| 1 | Streetlight → electrical/street lighting | Pass | `test_acceptance_routes_correctly` |
| 2 | Transformer sparking → Emergency + safety message | Pass | `test_emergency_safety_message_and_rules`, demo screenshot |
| 3 | Dirty water → water/sanitation | Pass | acceptance tests + e2e `test_citizen_files_complaint_sees_assigned_officer_and_officer_sees_it` |
| 4 | Garbage → solid waste | Pass | acceptance tests |
| 5 | Pothole → roads | Pass | acceptance tests |
| 6 | Gibberish → no auto-assignment | Pass | unit + e2e `test_human_review_for_unclear_complaint` |
| 7 | Ticket in correct officer queue and citizen history | Pass | `test_full_citizen_to_officer_workflow`, e2e |
| 8 | Status change visible to citizen after refresh | Pass | `test_full_citizen_to_officer_workflow` |
| 9 | SLA timers / escalations use configured policy | Pass | `test_sla_from_policy_table`, `test_escalation_matrix` |
| 10 | Duplicate counts consistent | Pass | duplicate + analytics consistency tests |
| 11 | Dashboard filters change data | Pass | `test_analytics_filters_change_data...`, e2e `test_analytics_filters_change_data` |
| 12 | Language selection changes UI strings and AI reply language | Pass for en/kn/hi/ta UI strings and assistant fixed replies; free-text answers are quoted in the source language with a visible notice (no MT provider) | e2e `test_language_switch_changes_interface_and_rtl`, `test_assistant_scheme_grievance_kb_and_unknown` |
| 13 | Agent creates ticket from call | Pass | `test_simulated_call_to_ticket_and_wrap` |
| 14 | Draft letter edit/save, never sent | Pass | `test_draft_generate_edit_never_sends` |
| 15 | Monitoring distinguishes real vs simulated | Pass | `test_monitoring_labels_real_vs_simulated`, e2e |
| 16 | Benefit answers cite sources / safe on uncertainty | Pass | assistant + eligibility tests |
| 17 | Mobile layout, form errors, empty states, failed AI | Pass | e2e mobile tests (375 px); AI failure path via `test_llm_failure_is_surfaced_not_masked` (UI retry/human-fallback path reviewed manually) |
| 18 | No public link points to localhost | Pass | `test_no_localhost_links_in_public_content` |
| 19 | Unauthorized roles blocked | Pass | `tests/api/test_security.py` |
| 20 | Data persists after backend restart | Pass | engine disposed + new client in `test_full_citizen_to_officer_workflow`; e2e server uses on-disk DB |

## Not tested (needs external services)

Real LLM, STT, translation, OCR, SMS/WhatsApp, telephony, SSO, government portals - see `EXTERNAL_DEPENDENCIES.md`. The LLM adapter is exercised only with mocked responses.
