#!/usr/bin/env bash
# Server loop for machines where the user systemd manager is not kept alive at boot.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -s "$HOME/game-editor/.env" ]]; then
    echo "Missing private server configuration: $HOME/game-editor/.env" >&2
    exit 1
fi
set -a
source "$HOME/game-editor/.env"
set +a
mkdir -p logs
while true; do
    .venv/bin/uvicorn orchestrator.main:app --host 127.0.0.1 --port 8000
    sleep 5
done
