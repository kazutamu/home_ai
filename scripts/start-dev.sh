#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${HOME_AI_WEB_PORT:-8080}"
FRONTEND_PORT="${VITE_PORT:-5173}"
TEMPORAL_LOG="${HOME_AI_TEMPORAL_LOG:-/tmp/home-ai-temporal.log}"
TEMPORAL_PORT="${HOME_AI_TEMPORAL_PORT:-7233}"
API_TARGET="${VITE_API_TARGET:-http://localhost:${BACKEND_PORT}}"

is_port_in_use() {
  local port="$1"
  lsof -ti "tcp:${port}" >/dev/null 2>&1
}

is_home_ai_backend() {
  local port="$1"
  local body
  body="$(curl -sS --max-time 2 "http://127.0.0.1:${port}/" || true)"
  [[ "$body" == *"Home AI"* ]]
}

cleanup() {
  local pids
  pids=$(jobs -p) || true
  if [[ -n "${pids:-}" ]]; then
    kill $pids 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if command -v temporal >/dev/null 2>&1; then
  if is_port_in_use "$TEMPORAL_PORT"; then
    echo "Temporal already running on port ${TEMPORAL_PORT}; skipping start."
  else
    temporal server start-dev >"$TEMPORAL_LOG" 2>&1 &
    echo "Started Temporal dev server (logs: $TEMPORAL_LOG)"
  fi
else
  echo "temporal CLI not found; assuming Temporal is already running at localhost:7233"
fi

if is_port_in_use "$BACKEND_PORT"; then
  if is_home_ai_backend "$BACKEND_PORT"; then
    echo "Backend already running at http://localhost:${BACKEND_PORT}; reusing it."
  else
    echo "Port ${BACKEND_PORT} is in use by a different service."
    echo "Stop that process or run with HOME_AI_WEB_PORT=<free-port> and matching VITE_API_TARGET."
    exit 1
  fi
else
  uv run python -m home_ai.web.server &
  echo "Backend started at http://localhost:${BACKEND_PORT}"
fi

if is_port_in_use "$FRONTEND_PORT"; then
  echo "Frontend port ${FRONTEND_PORT} is already in use. Stop the existing process or set VITE_PORT."
  exit 1
fi

(
  cd web_client
  export VITE_API_TARGET="${API_TARGET}"
  npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
) &
echo "Frontend dev server starting at http://localhost:${FRONTEND_PORT}"
echo "Frontend proxy target: ${API_TARGET}"

echo "Press Ctrl+C to stop all services."
wait
