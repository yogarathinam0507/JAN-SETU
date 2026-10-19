# Baseline report (Phase 1)

## What could be inspected
- **Existing site:** only the rendered `/citizen` page at `https://rodic-ai.onrender.com/citizen` (fetched 18 Oct 2026). **No source code, configuration, database or exports were supplied**, so the stack, APIs and database of the old system could not be inventoried. Script references and API endpoints were not visible in the rendered page.
- **Audit PDFs:** both read in full - *Rodic AI Audit and Karnataka Expansion Strategy* (scorecard 62/100) and *JanSetu Review and Karnataka Expansion Plan* (11 pages).

## Observed on the live page (confirms the audits)
- Pre-filled AI triage before any input: streetlight category, "Municipal Electrical Services (TANGEDCO / GCC)", Medium, 48 h, "Ward 12, Zone 4", Rule #104.
- Unverified claims: "TrustShield 94.2% Live", "GCC 1913 Integrated", "DARPG CPGRAMS compliant", "94.2% AI Precision Rate".
- Hardcoded Chennai / Ward 12 data, three languages only, "0 duplicates" next to a 15-report cluster, typo "Roundtana".
- No login, roles or consent notice visible.

## Decision
Because no code was available and the documented defects were architectural (static responses, no persistence path visible, no RBAC, no tenancy), the platform was **rebuilt** rather than patched. Preserved ideas: three-persona design, TrustShield explainability, master-incident clustering, before/after photo verification, contractor scorecard, benchmark corpus, Tamil-first support (now tenant-configurable, Kannada-first for Karnataka).

## Mandatory defect -> fix mapping
| # | Defect | Fix | Evidence |
|---|---|---|---|
| 1 | Same triage for every complaint | Per-text pipeline; no default department | `test_unrelated_complaints_do_not_share_one_canned_answer` |
| 2 | Pre-filled triage panel | Empty state until submit | e2e `test_triage_panel_empty_before_input` |
| 3 | Silent canned fallback | Errors surfaced with retry + human-triage option | `test_llm_failure_is_surfaced_not_masked` |
| 4 | Unvalidated AI output | Pydantic schema + registry validation | `test_llm_output_outside_registry_is_rejected` |
| 5 | Voice dispatched without confirmation | Editable transcript; API rejects unconfirmed voice | `test_voice_complaint_requires_confirmed_transcript` |
| 6 | Empty officer table | Queue reads persisted rows | e2e `test_officer_table_loads_rows` |
| 7 | localhost links | Config/request-derived URLs; repo scan test | `test_no_localhost_links_in_public_content` |
| 8 | Blank benchmark records | 48 complete labelled records, public endpoint | same test |
| 9 | Conflicting accuracy figures | Only measured numbers with denominators and caveat | `test_ai_eval_is_measured_with_denominator` |
| 10-11 | Unlabelled synthetic data / false "Live" claims | Labels everywhere; banned-phrase test | `test_no_unverified_claims_in_ui` |
| 12 | Inconsistent duplicate counts | One definition used by nodal + analytics | `test_duplicates_cluster_within_radius_and_stats_are_consistent` |
| 13 | Exposed phone numbers | Masked by default; audited reveal; redaction | `test_phone_masked_and_reveal_is_audited` |
| 14 | Hardcoded Chennai | Tenant registry; Karnataka + Chennai tenants | `test_tenant_isolation` |
| 15 | Non-working controls | Filters/ranges/export/refresh tested | `test_analytics_filters_change_data...`, e2e dashboard test |
| 16 | Mobile usability | Responsive CSS; no horizontal scroll at 375 px | e2e mobile tests |
| 17 | No consent/privacy | Consent checkbox, privacy page (draft for legal review), export/deletion | `test_privacy_notice_and_data_export` |
| 18 | Fabricated integrations/compliance | `/integrations` states; admin cannot claim "tested" without evidence | `test_admin_config_changes_are_audited` |
