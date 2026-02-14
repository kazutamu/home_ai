#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${HOME_AI_WEB_PORT:-8080}"
FRONTEND_PORT="${VITE_PORT:-5173}"
TEMPORAL_LOG="${HOME_AI_TEMPORAL_LOG:-/tmp/home-ai-temporal.log}"

cleanup() {
  local pids
  pids=$(jobs -p) || true
  if [[ -n "${pids:-}" ]]; then
    kill $pids 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if command -v temporal >/dev/null 2>&1; then
  temporal server start-dev >"$TEMPORAL_LOG" 2>&1 &
  echo "Started Temporal dev server (logs: $TEMPORAL_LOG)"
else
  echo "temporal CLI not found; assuming Temporal is already running at localhost:7233"
fi

uv run python -m home_ai.web.server &
echo "Backend started at http://localhost:${BACKEND_PORT}"

(
  cd web_client
  npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
) &
echo "Frontend dev server starting at http://localhost:${FRONTEND_PORT}"

echo "Press Ctrl+C to stop all services."
wait
