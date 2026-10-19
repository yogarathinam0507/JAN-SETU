#!/usr/bin/env bash
# One-time local setup: virtualenv, dependencies, .env, migrations, demo seed.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
[ -f .env ] || { cp .env.example .env; python3 - <<'PY'
import re, secrets, pathlib
p = pathlib.Path(".env"); s = p.read_text()
p.write_text(re.sub(r"^SECRET_KEY=.*$", "SECRET_KEY=" + secrets.token_hex(32), s, flags=re.M))
PY
}
cd backend
alembic upgrade head
python -m app.seed
echo "Setup complete. Run: scripts/run.sh"
