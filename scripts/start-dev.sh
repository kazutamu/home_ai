#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${HOME_AI_WEB_PORT:-8080}"
FRONTEND_PORT="${VITE_PORT:-5173}"
TEMPORAL_LOG="${HOME_AI_TEMPORAL_LOG:-/tmp/home-ai-temporal.log}"
TEMPORAL_PORT="${HOME_AI_TEMPORAL_PORT:-7233}"
API_TARGET="${VITE_API_TARGET:-http://localhost:${BACKEND_PORT}}"
STARTED_PIDS=()

is_port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

is_temporal_ready() {
  temporal operator cluster health --address "127.0.0.1:${TEMPORAL_PORT}" >/dev/null 2>&1
}

is_home_ai_backend() {
  local port="$1"
  local body
  body="$(curl -sS --max-time 2 "http://127.0.0.1:${port}/" || true)"
  [[ "$body" == *"Home AI"* ]]
}

wait_for_temporal() {
  local retries=30
  local delay=1
  for ((i = 1; i <= retries; i++)); do
    if is_temporal_ready; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

ensure_frontend_deps() {
  if [[ -x "web_client/node_modules/.bin/vite" ]]; then
    return
  fi
  echo "Installing frontend dependencies (missing vite)..."
  (
    cd web_client
    npm install
  )
}

cleanup() {
  trap - EXIT INT TERM
  if [[ "${#STARTED_PIDS[@]}" -eq 0 ]]; then
    return
  fi

  for pid in "${STARTED_PIDS[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
    pkill -TERM -P "$pid" 2>/dev/null || true
  done

  sleep 1

  for pid in "${STARTED_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
    pkill -KILL -P "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

if command -v temporal >/dev/null 2>&1; then
  if is_temporal_ready; then
    echo "Temporal already running on port ${TEMPORAL_PORT}; skipping start."
  elif is_port_in_use "$TEMPORAL_PORT"; then
    echo "Port ${TEMPORAL_PORT} is in use but Temporal is not reachable."
    echo "Free the port or stop the conflicting process, then retry."
    exit 1
  else
    temporal server start-dev >"$TEMPORAL_LOG" 2>&1 &
    STARTED_PIDS+=("$!")
    echo "Started Temporal dev server (logs: $TEMPORAL_LOG)"
    if ! wait_for_temporal; then
      echo "Temporal failed to become ready on port ${TEMPORAL_PORT}."
      echo "Last log lines:"
      tail -n 30 "$TEMPORAL_LOG" || true
      exit 1
    fi
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
  (
    unset VIRTUAL_ENV
    uv run python -m home_ai.web.server
  ) &
  STARTED_PIDS+=("$!")
  echo "Backend started at http://localhost:${BACKEND_PORT}"
fi

ensure_frontend_deps

if is_port_in_use "$FRONTEND_PORT"; then
  echo "Frontend port ${FRONTEND_PORT} is already in use. Stop the existing process or set VITE_PORT."
  exit 1
fi

(
  cd web_client
  export VITE_API_TARGET="${API_TARGET}"
  npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
) &
STARTED_PIDS+=("$!")
echo "Frontend dev server starting at http://localhost:${FRONTEND_PORT}"
echo "Frontend proxy target: ${API_TARGET}"

echo "Press Ctrl+C to stop all services."
wait || true
