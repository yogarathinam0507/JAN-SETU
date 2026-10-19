# Architecture

```
Browser (ES-module SPA, strict CSP)  ──HTTPS/JSON──►  FastAPI app (backend/app)
  frontend/js/pages/*.js                                ├─ routers/   (REST, OpenAPI at /api/docs)
  frontend/i18n/{en,kn,hi,ta}.json                      ├─ services/  (domain logic, provider adapters)
                                                        ├─ models.py  (SQLAlchemy, Alembic migrations)
                                                        └─ background loops: SLA escalation, health checks
                                                                 │
                                                  SQLite (demo) / PostgreSQL (deploy)
```

## Modules (backend/app)
| Concern | Files |
|---|---|
| Config, DB, security/RBAC | `config.py`, `db.py`, `security.py` (role→permission matrix, PBKDF2 passwords, JWT, revocation) |
| Tenant scoping | `services/scope.py` - every grievance query goes through `grievance_scope`/`can_view` |
| Triage pipeline (PS1) | `services/triage.py`, `services/language.py`, `services/geo.py`, `data/lexicon.py`, `services/llm.py` |
| Grievance lifecycle | `services/workflow.py` (state machine, SLA, duplicates, escalation, notifications), `routers/grievances.py`, `routers/nodal.py` |
| Call centre (PS2) | `services/callcentre.py` (telephony adapter boundary, QA rubric), `routers/agent.py` |
| e-Office (PS3) | `routers/officer.py`, `services/drafting.py`, `routers/vendor.py` |
| Monitoring (PS4) | `services/monitoring.py`, `routers/monitoring.py`, `routers/health.py` (`/metrics`) |
| Benefits & KB (PS5) | `services/benefits.py`, `services/kb.py`, `routers/assistant.py`, `routers/knowledge.py` |
| Analytics, audit, admin | `routers/analytics.py`, `services/evaluation.py`, `services/audit.py` (hash chain), `routers/audit_routes.py`, `routers/admin.py` |

## Triage pipeline
`text or confirmed transcript → language detection (Unicode script, transliteration hints) → [translation adapter if configured] → classification (LLM adapter or transparent lexicon) → location/ward extraction (GPS-in-boundary or locality name; never a default ward) → deterministic emergency & risk rules → confidence threshold (configurable) → registry validation (department/category/SLA must exist for the tenant) → TriageOutput schema → TriageRecord persisted (provider, version, rules, output, later human override)`.
Ticket creation is a separate call after citizen confirmation. Unclear, low-confidence, unsupported-language, disputed or AI-failed complaints go to the **human triage queue** with no department.

## Data model
Tenants, roles/permissions, languages, jurisdictions (zones/wards with polygons), departments, categories, SLA policies, escalation rules, users, OTP challenges, grievances, ticket events, audit logs (hash-chained), triage records, master incidents, duplicate links, attachments, interactions, knowledge documents/chunks (versioned), schemes, vendors, work orders, officer files, file movements, document templates, drafts, monitored services, health checks, incidents, alerts, AI evaluations, integration configs, data requests, assistant usage events. Public identifiers are random (`GRV-7KQ2-M9XD`); primary keys are UUIDs. Schema: `backend/migrations/versions/0001_initial_schema.py`.

## Design choices
- **No-build frontend:** fewer moving parts for government hosting, no CDN, CSP `script-src 'self'` without `unsafe-inline`. Trade-off: no component library; the UI is a small hand-written helper (`frontend/js/core.js`) that never uses `innerHTML` with data.
- **In-process background jobs** instead of Celery/Redis: the audits suggested queues, but they are not needed at demo scale and would prevent a one-command local run. Jobs are idempotent and can be disabled for an external scheduler.
- **BM25 retrieval** instead of a vector DB by default: deterministic, offline, cited. The `search()` interface is the place to plug in Qdrant/FAISS.
- **Rule-based classifier as the offline mode** - clearly labelled - because a fake "AI" score would repeat the audited credibility problem.

## Scaling notes
Stateless API (except the in-process rate limiter and token revocation list - move both to Redis for multi-instance), PostgreSQL with indexes on tenant/status/department, uploads on a mounted volume or object storage. Background loops should run in one instance only (or via an external scheduler) when scaling horizontally.
