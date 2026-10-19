# JanSetu - Citizen Services Platform (live maps, multi-login, light/dark)

## ▶ Quick start (Windows, macOS, Linux)

You need **Python 3.10 or newer** (python.org). Then, inside this folder:

| Windows | macOS / Linux |
|---|---|
| double-click **`start.bat`** (or run `python start.py`) | `python3 start.py` (or `./start.sh`) |

The first start installs the dependencies into `.venv`, creates `.env`, **creates the database and loads demo data automatically**, and opens **http://127.0.0.1:8000** in your browser. Stop it with Ctrl+C.

> **"Could not reach the server / Request failed (500)"** happened because the earlier build needed a separate bash setup step that never ran (for example on Windows), so the database tables did not exist. The app now sets up its own database on first start. Always open the address printed in the terminal; opening `index.html` as a file does not work.

### Sign in

The portal now **opens on the sign-in page**; every other page needs an account (only the privacy, accessibility, terms and help pages are public).

- **Citizens:** *Citizen login* → mobile number + one-time code (no SMS gateway is configured, so the code is shown on screen), or user ID + password.
- **Department staff:** *Department login* → user ID + password.
- **Test accounts:** open *Test accounts for this installation* on the sign-in page and click a row. Password for all: **`Demo@1234`**. The list is disabled when `APP_ENV=production`.
- **Multi-login:** account menu (top right) → *Add another account*; switch with one click; *Sign out* / *Sign out of all accounts*.

| Role | Karnataka (`ka-bengaluru`) | Name / designation |
|---|---|---|
| Citizen | `ka.citizen1`, `ka.citizen2` | Lakshmi Narayan, Ravi Shankar |
| Department officer | `ka.officer.water` | Smt. Kavya Shetty, Assistant Executive Engineer (Water Supply) |
| | `ka.officer.streetlight` | Sri. Raghavendra Rao, Assistant Engineer (Street Lighting) |
| | `ka.officer.swm`, `ka.officer.roads`, `ka.officer.elec_emg`, ... | one named officer for each of the 17 departments |
| Nodal officer | `ka.nodal`, `ka.nodal.south` | Smt. Kavitha Rao, Joint Commissioner; Sri. Arun Prasad (South Zone) |
| Helpline | `ka.agent1`, `ka.agent2` | Helpline Executives |
| Commissioner | `ka.hod` | Sri. Vinod Krishnan |
| Contractor | `ka.vendor` | Sri Sai Infra Works |
| Auditor / content / admin | `ka.auditor`, `ka.content`, `ka.admin` | |

Chennai uses the same pattern with `tn.` (for example `tn.officer.water` = Tmt. P. Meenakshi). All names are fictitious.

### What changed in this version (v4)

- **"Session expired" after every login is fixed.** Token times were computed from the server's local clock; on an IST machine every token was already 5.5 hours old. Tokens now use epoch seconds, saved sessions are validated silently on load, and the full test suite runs with `TZ=Asia/Kolkata`.
- **Government-portal design:** accessibility strip (skip link, A- / A / A+ text size, theme, language), header with helpline, tricolour line, navy menu bar, formal footer (policies, helplines, emergency numbers). SVG icons; no emoji. Light / dark / system themes kept. No "demo" banners or problem-statement labels.
- **Dashboards for every role** (`/dashboard`, `GET /api/dashboard`): live KPIs, charts and work lists - citizen, officer, nodal, helpline, commissioner, contractor, auditor, content manager and administrator.
- **Automatic assignment to a named officer.** A routed complaint is assigned to the department's officer, and the citizen sees *"This complaint has been assigned to Smt. Kavya Shetty, Assistant Executive Engineer (Water Supply), BWSSB..."* on the confirmation, the ticket page and in notifications. Unclear complaints go to the nodal officer, who routes them (then they are auto-assigned too).
- **Notifications bell** (`GET /api/notifications`): role-aware feed (assignments, acceptance, work started, resolution, escalations, helpline queue, work orders, service alerts).
- **Synthetic test data for location testing:** about 95 complaints per city across 22 categories, each with a GPS point inside its ward boundary (11 Bengaluru wards, 9 Chennai wards), spread over 60 days with realistic statuses, officers, ratings and SLA breaches. The previous build's "everything is a streetlight" problem came from too few seeded examples; the classifier vocabulary was also widened (new categories: electricity billing, encroachment, noise, dead animal).
- **Maps fixed:** the "Access blocked" tiles happened because the app stripped the `Referer` header that OpenStreetMap's tile policy requires. The referrer policy is now `strict-origin-when-cross-origin`, the default basemap is CARTO (light and a real dark basemap), and the map falls back to OpenStreetMap automatically if a provider fails.
- **Voice:** continuous dictation (keeps listening through pauses until you press Stop, appends to typed text), a separate *Speak in* language selector, and clear error messages (microphone blocked, no speech, unsupported language). **Read aloud** (text-to-speech) on the assignment notice, ticket status and assistant answers, using the best available Indian-language voice. Dictation needs Chrome or Edge.

> **Upgrading from an earlier build:** just start the app again. If the database still holds the old test data, it is replaced automatically with the new named officers and synthetic complaints (never in production). Saved sign-ins from the old build are cleared silently - sign in again.

> **Phones and GPS:** browsers only allow GPS on `https://` sites or on `localhost`. To test live GPS from a phone, deploy the app (see `render.yaml`) or use an HTTPS tunnel. On a laptop, use **Set on map**.

## 1. Stack

- **Backend:** Python 3.10+ · FastAPI · SQLAlchemy 2 · Alembic migrations · Pydantic v2 · PyJWT · pypdf
- **Database:** SQLite for the quick local demo, PostgreSQL for deployment. The full unit and API suite passes on both, with PostgreSQL 16 tested.
- **Frontend:** a no-build single-page app in plain ES modules with no inline scripts (it runs under a strict CSP) and hand-written SVG charts. FastAPI serves it, so one process runs everything. The README explains why the React/Vite option was not used: it needs no Node toolchain, has no CDN dependency and is simple to audit.
- **AI:** a provider-neutral pipeline. Offline, it uses a transparent, versioned rule/lexicon classifier that is labelled as a demo, plus deterministic safety rules. Set `LLM_*` and the OpenAI-compatible adapter is used instead, with the same schema and registry validation. Retrieval uses a local BM25 index with citations. Vector store, STT, translation and OCR are adapter settings.
- **Background jobs:** in-process asyncio loops for SLA escalation and health checks. No Redis is needed. Set `ENABLE_BACKGROUND_JOBS=false` if you use an external scheduler instead.

Architecture details: `docs/ARCHITECTURE.md`.

## 2. Run locally (manual commands)

`python start.py` does all of this for you. The manual route needs Python 3.10 or newer.

```bash
cd rodic-jansetu-platform
./scripts/setup.sh        # venv + deps + .env (random SECRET_KEY) + alembic upgrade + demo seed
./scripts/run.sh          # http://127.0.0.1:8000
```

Manual equivalent:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env                 # then set SECRET_KEY to a long random value
cd backend
alembic upgrade head                 # create schema (migrations in backend/migrations)
python -m app.seed                   # deterministic demo data (refuses when APP_ENV=production)
uvicorn app.main:app --port 8000
```

To reset the demo data, run `./scripts/reset_demo.sh`, which calls `python -m app.seed --reset`.

### PostgreSQL / Docker

```bash
cp .env.example .env    # set SECRET_KEY; optionally POSTGRES_PASSWORD
docker compose up --build            # API + PostgreSQL 16, migrates and seeds, port 8000
```

To run without Docker, install `backend/requirements-postgres.txt` and set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/jansetu`.

The Docker files are included but were **not executed in the build environment**, which had no Docker daemon. PostgreSQL itself was tested directly.

## 3. URLs and test accounts

Open `http://127.0.0.1:8000`. The sign-in page lists every seeded test account for the selected portal under *Test accounts for this installation*; click a row to sign in. **The password for all of them is `Demo@1234`.** The list endpoint is disabled when `APP_ENV=production`.

| Role | Karnataka tenant (`ka-bengaluru`) | Chennai tenant (`tn-chennai`) |
|---|---|---|
| Citizen | `ka.citizen1`, `ka.citizen2` (or mobile OTP) | `tn.citizen1`, `tn.citizen2` |
| Call-centre agent | `ka.agent1`, `ka.agent2` | `tn.agent1` |
| Department officer | `ka.officer.streetlight`, `ka.officer.water`, `ka.officer.swm`, `ka.officer.roads`, `ka.officer.elec_emg`, ... (one per department) | `tn.officer.*` |
| Ward/zone nodal officer | `ka.nodal` (city), `ka.nodal.south` (South zone) | `tn.nodal` |
| Head of department | `ka.hod` | `tn.hod` |
| Contractor | `ka.vendor` | `tn.vendor` |
| QA / auditor | `ka.auditor` | `tn.auditor` |
| Content / language manager | `ka.content` | `tn.content` |
| Tenant admin | `ka.admin` | `tn.admin` |

For citizen OTP, enter any 10-digit mobile number starting 6 to 9. Because no SMS gateway is configured, the one-time code is shown on screen.

Key URLs: `/api/docs` (Swagger), `/api/health`, `/api/health/ready`, `/api/diagnostics`, `/metrics` (Prometheus), `/api/public/benchmark/dataset`, `/evidence`.

A 10-minute walkthrough is in `docs/DEMO_SCRIPT.md`.

## 4. Tests

```bash
./scripts/test.sh                                   # all tests (unit + API + browser e2e)
python -m pytest tests/unit tests/api -q            # without a browser
python -m playwright install chromium               # once, for tests/e2e
TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest tests/unit tests/api   # against PostgreSQL
```

**Results for this build** (details in `docs/TEST_RESULTS.md`):

- SQLite (run with `TZ=Asia/Kolkata`): **254 passed, 0 failed, 0 skipped**, including 29 Playwright/Chromium end-to-end tests.
- PostgreSQL 16: **225 passed** (unit + API).

## 5. Configuration

All settings are environment variables, documented in `.env.example`. Public links come from `PUBLIC_BASE_URL`, or from the request host, and never from a hardcoded `localhost`. Tenants, departments, categories, wards, SLA and escalation rules, languages, templates, schemes and integrations all live in the database and are editable in `/admin` and `/knowledge`. Demo values come from `backend/app/data/seed_data.py`.

## 6. What still needs external credentials or approvals

See `docs/EXTERNAL_DEPENDENCIES.md`. In short:

- An LLM provider
- Bhashini/AI4Bharat STT and translation
- An OCR provider
- A DLT-registered SMS / WhatsApp Business provider
- Telephony (SIP/WebRTC/CPaaS)
- DigiLocker, Aadhaar e-KYC and state SSO/MFA
- e-Office and DSC/eSign
- CPGRAMS and state-portal sync
- Authorization to monitor Seva Sindhu, Kaveri 2.0 and Kutumba
- Official GIS ward boundaries
- Verified scheme rules, links and translations
- Legal review of the privacy notice

## 7. Known limitations

- Routing uses a transparent keyword/lexicon classifier with safety rules (or an LLM when `LLM_*` is configured); it is not a trained model. The citizen screens show plain *Routing details* instead of model internals, but staff and auditors still see the rules applied. Its accuracy table is measured on a 60-example set the team wrote (currently 100% - a regression check, not evidence of real-world accuracy).
- All complaints, people and officer names in the seed data are synthetic.
- Full interface translation exists for English and Kannada (96% of citizen screens). Hindi and Tamil cover the main citizen flow; anything untranslated falls back to English. The other 21 registry languages show an English interface with a notice. Translations need native-speaker review.
- Ward boundaries are approximate squares around each ward centre, not official GIS boundaries.
- Rate limiting and the token revocation list are kept in process. Use a shared store such as Redis when running several instances.
- Staff use password sign-in. MFA or SSO is a production requirement and is not implemented.
