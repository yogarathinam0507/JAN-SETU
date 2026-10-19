# Security and privacy

> This document and the in-app privacy notice are **drafts for review by the organisation's legal, security and data-protection team**. No compliance (e.g. DPDP Act 2023) or certification is claimed.

## Controls implemented
- **Server-side RBAC** for nine roles (`app/security.py`); every endpoint declares required permissions. Admin and content roles cannot read grievance content; HOD sees aggregates only.
- **Tenant isolation**: users are bound to their tenant in the token; every query filters by tenant; cross-tenant and cross-user reads return 404.
- **PII minimisation**: phone numbers and names masked for staff by default; reveal requires a reason (≥10 chars), is written to the audit log and the ticket's internal timeline. Phone/Aadhaar-like numbers are redacted from free text shown to staff.
- **Audit log**: actor, role, time, action, entity, before/after, reason; SHA-256 hash chain verifiable at `/api/audit/verify-chain`.
- **Authentication**: PBKDF2-SHA256 (240k iterations) passwords, short-lived JWT (default 60 min), logout revocation, OTP codes hashed with a keyed HMAC, 5-minute expiry, 5 attempts.
- **Rate limiting** per IP (stricter on `/api/auth/*`), structured 429.
- **Uploads**: 5 MB cap, allow-list (JPEG, PNG, PDF, UTF-8 text), magic-byte check, random storage names, path-traversal guard, download only after the same visibility check as the ticket.
- **Headers**: strict CSP (no inline script/style), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`; API responses `Cache-Control: no-store`.
- **Input validation**: Pydantic schemas on every body; structured validation errors; ORM-parameterised SQL; frontend renders data with `textContent` only (no `innerHTML`).
- **Secrets** only from environment; `.env` git-ignored; demo accounts and on-screen OTP disabled in `APP_ENV=production`; seed refuses to run in production.
- **Logs** contain method, path, status and latency - never complaint text or phone numbers.
- **AI**: no training on citizen data; provider keys server-side; hidden reasoning is never shown, only matched terms/rules.

## Retention & data subject requests
- Call transcripts carry an expiry (`TRANSCRIPT_RETENTION_DAYS`, default 90) shown to agents. *An automated purge job is not yet implemented - schedule one before production.*
- Citizens can export their data (`/api/me/export`) and file deletion requests (`/api/me/deletion-request`) that are queued for DPO review.
- Raw audio is not stored by the platform (browser speech recognition may be processed by the browser vendor - disclosed in the notice).

## Before production
MFA/SSO for staff, Redis-backed rate limiting and revocation, TLS termination and HSTS at the proxy, malware scanning for uploads, transcript purge job, penetration test, DPIA, legal review of notices and retention schedule, DLT-registered SMS templates.
