"""Generate docs/API.md and docs/openapi.json from the live FastAPI schema."""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("ENABLE_BACKGROUND_JOBS", "false")
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app  # noqa: E402
spec = app.openapi()
(ROOT / "docs" / "openapi.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
lines = ["# API reference", "", "Interactive docs: `/api/docs` (Swagger UI), `/api/redoc`; machine-readable: `/api/openapi.json` (copy in `docs/openapi.json`).", "",
         "## Conventions", "", "- Auth: `Authorization: Bearer <token>` from `POST /api/auth/login` or `POST /api/auth/otp/verify`. Tokens expire after `TOKEN_TTL_MINUTES`.",
         "- Public endpoints take `?tenant=<code>` (`ka-bengaluru`, `tn-chennai`). Signed-in users are always bound to their own tenant.",
         "- Errors: `{\"error\": {\"code\": \"...\", \"message\": \"...\", \"fields\": [...]}}` with standard HTTP status codes (401, 403, 404, 409, 413, 415, 422, 429, 502).",
         "- Records the caller may not see return **404** (not 403) so existence is not leaked across users/tenants.",
         "- Lists support `page`, `page_size`; grievance lists also `status`, `department_id`, `category_id`, `priority`, `q`, `date_from`, `date_to`, `sla`, `sort`.", ""]
by_tag = {}
for path, ops in spec["paths"].items():
    for method, op in ops.items():
        by_tag.setdefault((op.get("tags") or ["other"])[0], []).append((method.upper(), path, op.get("summary", ""), (op.get("description") or "").split("\n")[0]))
for tag, rows in by_tag.items():
    lines += [f"## {tag}", "", "| Method | Path | Summary |", "|---|---|---|"]
    lines += [f"| {m} | `{p}` | {s}{(' - ' + d) if d else ''} |" for m, p, s, d in rows]
    lines.append("")
(ROOT / "docs" / "API.md").write_text("\n".join(lines), encoding="utf-8")
print(sum(len(v) for v in by_tag.values()), "operations")
