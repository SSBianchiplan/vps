#!/usr/bin/env bash
# Sobe o backend FastAPI (cria venv e instala o core na primeira execução).
set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

exec uvicorn app.main:app --reload \
  --host "${VISIONDESK_HOST:-0.0.0.0}" \
  --port "${VISIONDESK_PORT:-8200}"
