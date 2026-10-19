#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
[ -d ../.venv ] && . ../.venv/bin/activate
python -m app.seed --reset
