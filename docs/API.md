# API reference

Interactive docs: `/api/docs` (Swagger UI), `/api/redoc`; machine-readable: `/api/openapi.json` (copy in `docs/openapi.json`).

## Conventions

- Auth: `Authorization: Bearer <token>` from `POST /api/auth/login` or `POST /api/auth/otp/verify`. Tokens expire after `TOKEN_TTL_MINUTES`.
- Public endpoints take `?tenant=<code>` (`ka-bengaluru`, `tn-chennai`). Signed-in users are always bound to their own tenant.
- Errors: `{"error": {"code": "...", "message": "...", "fields": [...]}}` with standard HTTP status codes (401, 403, 404, 409, 413, 415, 422, 429, 502).
- Records the caller may not see return **404** (not 403) so existence is not leaked across users/tenants.
- Lists support `page`, `page_size`; grievance lists also `status`, `department_id`, `category_id`, `priority`, `q`, `date_from`, `date_to`, `sla`, `sort`.

## health

| Method | Path | Summary |
|---|---|---|
| GET | `/api/health` | Health |
| GET | `/api/health/ready` | Ready |
| GET | `/api/diagnostics` | Diagnostics |
| GET | `/metrics` | Metrics - Prometheus exposition format (scrape target for an external Prometheus, if configured). |

## auth

| Method | Path | Summary |
|---|---|---|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/otp/request` | Otp Request |
| POST | `/api/auth/otp/verify` | Otp Verify |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/demo-accounts` | Demo Accounts |
| GET | `/api/me` | Me |
| PATCH | `/api/me/language` | Set Language |
| GET | `/api/me/export` | Export My Data - Data-access request: returns the signed-in user's own records. |
| POST | `/api/me/deletion-request` | Deletion Request |

## public

| Method | Path | Summary |
|---|---|---|
| GET | `/api/public/tenants` | Tenants |
| GET | `/api/public/config` | Tenant Config |
| GET | `/api/public/languages` | Languages |
| GET | `/api/public/privacy` | Privacy |
| GET | `/api/public/integrations` | Integrations |
| GET | `/api/public/evidence` | Evidence |
| GET | `/api/public/benchmark/dataset` | Benchmark Dataset - Public labelled triage evaluation dataset (demo). Link is built from PUBLIC_BASE_URL / request host. |

## grievances

| Method | Path | Summary |
|---|---|---|
| POST | `/api/triage/preview` | Triage Preview - Runs the full triage pipeline and returns a structured, explainable result. Creates no ticket. |
| POST | `/api/grievances` | Create |
| GET | `/api/grievances` | List Grievances |
| GET | `/api/grievances/{ref}` | Get Grievance |
| GET | `/api/track/{public_id}` | Track - Public tracking by ticket ID: status and public updates only - no personal data or complaint text. |
| POST | `/api/grievances/{ref}/actions` | Act |
| POST | `/api/grievances/{ref}/feedback` | Feedback |
| POST | `/api/grievances/{ref}/reveal-contact` | Reveal Contact |
| POST | `/api/grievances/{ref}/attachments` | Upload Attachment |
| GET | `/api/attachments/{att_id}` | Download Attachment |
| GET | `/api/grievances/{ref}/duplicates` | Duplicates |

## officer / e-office

| Method | Path | Summary |
|---|---|---|
| GET | `/api/officer/summary` | Summary |
| GET | `/api/officer/colleagues` | Colleagues |
| POST | `/api/grievances/{ref}/assign` | Assign |
| POST | `/api/grievances/{ref}/transfer` | Transfer |
| POST | `/api/grievances/{ref}/joint` | Add Joint |
| POST | `/api/grievances/{ref}/escalate` | Escalate |
| POST | `/api/grievances/{ref}/public-update` | Public Update |
| GET | `/api/templates` | Templates |
| POST | `/api/drafts/generate` | Generate Draft |
| GET | `/api/drafts` | List Drafts |
| PUT | `/api/drafts/{draft_id}` | Update Draft |
| GET | `/api/efiles` | List Efiles |
| POST | `/api/efiles` | Create Efile |
| GET | `/api/efiles/{file_id}` | Get Efile |
| POST | `/api/efiles/{file_id}/move` | Move Efile |
| POST | `/api/documents` | Upload Document |
| GET | `/api/documents` | Search Documents |
| GET | `/api/vendors` | Vendors |
| POST | `/api/grievances/{ref}/work-orders` | Create Work Order |
| GET | `/api/grievances/{ref}/work-orders` | Grievance Work Orders |
| POST | `/api/work-orders/{wo_id}/verify` | Verify Work Order |

## nodal

| Method | Path | Summary |
|---|---|---|
| GET | `/api/nodal/triage-queue` | Triage Queue |
| POST | `/api/nodal/triage-queue/{ref}/route` | Route |
| GET | `/api/nodal/master-incidents` | Masters |
| POST | `/api/nodal/grievances/{ref}/unlink` | Unlink |
| GET | `/api/nodal/escalations` | Escalations |
| GET | `/api/nodal/cross-department` | Cross Department |
| POST | `/api/nodal/run-escalations` | Run Escalations Now |

## call centre

| Method | Path | Summary |
|---|---|---|
| GET | `/api/agent/queue` | Queue |
| POST | `/api/agent/simulate-call` | Simulate Call - Creates a clearly-labelled SIMULATED inbound call with a scripted transcript (no telephony involved). |
| POST | `/api/agent/interactions` | Create Interaction - Manual record of an interaction (e.g. a call on a desk phone). Channels without a configured provider are |
| GET | `/api/agent/interactions/{iid}` | Get Interaction |
| POST | `/api/agent/interactions/{iid}/accept` | Accept |
| POST | `/api/agent/interactions/{iid}/transcript` | Add Line |
| GET | `/api/agent/interactions/{iid}/assist` | Assist |
| POST | `/api/agent/interactions/{iid}/create-ticket` | Create Ticket |
| POST | `/api/agent/interactions/{iid}/wrap` | Wrap |
| POST | `/api/agent/interactions/{iid}/handoff` | Handoff |
| POST | `/api/agent/interactions/{iid}/reveal` | Reveal |
| GET | `/api/agent/agents` | Agents |
| GET | `/api/agent/supervisor` | Supervisor |
| POST | `/api/agent/interactions/{iid}/qa` | Qa Review |

## benefits & assistant

| Method | Path | Summary |
|---|---|---|
| GET | `/api/benefits/categories` | Categories |
| GET | `/api/benefits/schemes` | Schemes |
| GET | `/api/benefits/schemes/{code}` | Scheme Detail |
| POST | `/api/benefits/schemes/{code}/check` | Check |
| POST | `/api/assistant/chat` | Chat |
| POST | `/api/assistant/callback-request` | Callback Request - Assisted-service mode: a person asks a human to call back. Lands in the agent queue (a real record). |

## knowledge base

| Method | Path | Summary |
|---|---|---|
| GET | `/api/knowledge/documents` | List Docs |
| POST | `/api/knowledge/documents` | Create Doc |
| GET | `/api/knowledge/documents/{doc_id}` | Get Doc |
| POST | `/api/knowledge/documents/upload` | Upload Doc |
| POST | `/api/knowledge/documents/{doc_id}/status` | Set Status |
| POST | `/api/knowledge/reindex` | Reindex |
| GET | `/api/knowledge/search` | Search |
| PUT | `/api/knowledge/schemes/{code}` | Update Scheme |
| PUT | `/api/knowledge/translations` | Set Translation |

## service monitoring

| Method | Path | Summary |
|---|---|---|
| GET | `/api/monitoring/services` | Services |
| POST | `/api/monitoring/services` | Add Service |
| GET | `/api/monitoring/services/{sid}` | Service Detail |
| PATCH | `/api/monitoring/services/{sid}` | Toggle |
| POST | `/api/monitoring/services/{sid}/check-now` | Check Now |
| GET | `/api/monitoring/incidents` | Incidents |
| POST | `/api/monitoring/incidents/{iid}` | Incident Action |
| GET | `/api/monitoring/alerts` | Alerts |
| GET | `/api/monitoring/traffic` | Traffic - Platform load trend from real persisted records (tickets + interactions per day) and a capacity-risk rule. |

## analytics

| Method | Path | Summary |
|---|---|---|
| GET | `/api/analytics/overview` | Overview |
| GET | `/api/analytics/export` | Export |
| GET | `/api/analytics/ai-eval` | Ai Eval |
| POST | `/api/analytics/ai-eval/run` | Ai Eval Run |

## audit & QA

| Method | Path | Summary |
|---|---|---|
| GET | `/api/audit/logs` | Logs |
| GET | `/api/audit/verify-chain` | Verify |
| GET | `/api/audit/closure-sample` | Closure Sample |

## admin

| Method | Path | Summary |
|---|---|---|
| GET | `/api/admin/overview` | Overview |
| POST | `/api/admin/users` | Create User |
| PATCH | `/api/admin/users/{uid}` | Set Active |
| PUT | `/api/admin/sla/{sid}` | Update Sla |
| PUT | `/api/admin/escalation/{eid}` | Update Escalation |
| PATCH | `/api/admin/categories/{cid}` | Update Category |
| PATCH | `/api/admin/integrations/{code}` | Update Integration |

## vendor

| Method | Path | Summary |
|---|---|---|
| GET | `/api/vendor/work-orders` | My Work Orders |
| POST | `/api/vendor/work-orders/{wo_id}/progress` | Progress |
| POST | `/api/vendor/work-orders/{wo_id}/photo` | Completion Photo |
| GET | `/api/vendor/scorecard` | Scorecard |

## maps & live tracking

| Method | Path | Summary |
|---|---|---|
| GET | `/api/map/config` | Map Config |
| GET | `/api/map/live` | Live Map - Complaint markers in the caller's scope + live field-team positions. Poll every few seconds. |
| PUT | `/api/field/location` | Share Location |
| DELETE | `/api/field/location` | Stop Sharing |
| GET | `/api/map/mine` | My Map - Citizen view: own complaints with pins, plus approximate distance of the assigned officer when shared. |
| GET | `/api/grievances/{ref}/tracking` | Ticket Tracking - Location + live progress for one ticket (citizen owner or staff in scope). |

## dashboard

| Method | Path | Summary |
|---|---|---|
| GET | `/api/dashboard` | Dashboard |
| GET | `/api/notifications` | Notifications |
