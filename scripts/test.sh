#!/usr/bin/env bash
# Runs unit + API tests, then browser e2e tests (needs: python -m playwright install chromium).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && . .venv/bin/activate
python -m pytest tests -q -rs "$@"
