#!/usr/bin/env bash
# Sobe o frontend Vite (instala dependências na primeira execução).
set -euo pipefail
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules ]; then
  npm install
fi
exec npm run dev
