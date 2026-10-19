# External integrations, credentials and approvals still required

| Item | Current state | What is needed | Where to plug in |
|---|---|---|---|
| LLM for classification/drafting | Planned (adapter implemented, mocked in tests) | Approved provider + data-residency decision; set `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`; run `/api/analytics/ai-eval/run` and review | `app/services/llm.py` |
| Server-side speech-to-text / TTS | Planned | Bhashini / AI4Bharat / Whisper credentials; per-language benchmark | `STT_PROVIDER` |
| Machine translation | Planned | Bhashini or approved MT | `TRANSLATION_PROVIDER` |
| OCR | Planned | OCR service for scanned documents | `OCR_PROVIDER`, `app/services/kb.py:extract_text` |
| SMS OTP + status SMS | Simulated | DLT-registered sender, templates, provider credentials | `OTP_PROVIDER`, `SMS_PROVIDER` |
| WhatsApp | Simulated | WhatsApp Business API account, approved templates | `WHATSAPP_PROVIDER` |
| Telephony / IVR | Simulated | SIP trunk or CPaaS, Asterisk/WebRTC gateway, callback URLs | `app/services/callcentre.py:TelephonyProvider` |
| Vector search | Planned | Qdrant/FAISS + embedding model | `app/services/kb.py:search` |
| DigiLocker, Aadhaar e-KYC | Planned | Government onboarding (AUA/KUA etc.) | new identity adapter |
| Staff SSO / MFA (e.g. KSDC) | Planned | State IdP details | `app/security.py` |
| e-Office, digital signature | Planned | State e-Office API access, DSC/eSign provider | new adapters |
| CPGRAMS / state grievance portals | Planned | API access and data-sharing agreement | new adapter |
| Seva Sindhu, Kaveri 2.0, Kutumba, TN e-Sevai monitoring | Planned, never probed | Written authorization + agreed health endpoints; add via `/monitoring` as "http" | `app/services/monitoring.py` |
| Grafana | Planned | Point Prometheus at `/metrics` | - |
| GIS ward boundaries | Demo rectangles | Official boundary layers (GeoJSON) | `jurisdictions.polygon` |
| Department names, helplines | Seeded, `name_verified=false` | Verify against official lists | `/admin`, `/knowledge` translations |
| Scheme rules, amounts, documents, links | Illustrative, `verified=false` | Content manager verifies against current government orders and adds official URLs | `/knowledge` → Scheme content |
| Kannada / Hindi / Tamil UI strings | Machine-assisted drafts | Native-speaker review; remaining 21 languages | `scripts/i18n_*.py` → `scripts/build_i18n.py` |
| Privacy notice, retention, DPIA | Draft | Legal / DPO review | `/api/public/privacy` |
