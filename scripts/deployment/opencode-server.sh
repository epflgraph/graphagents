#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# opencode-server.sh — control the shared OpenCode server (one for all repos)
#
# The server runs headless (`opencode serve`) inside a tmux session, so it
# survives closing VS Code / terminals. Attach clients from any repo with:
#
#   opencode attach http://127.0.0.1:4596 --dir /path/to/repo
#
# or use opencode-client.sh (next to this file), copied/symlinked into the
# root of each repo you want to work in.
#
# Usage:
#   opencode-server.sh [start|stop|restart|status|logs]   (default: status)
#
# Configuration (environment):
#   OPENCODE_SERVER_PORT   TCP port to listen on       (default: 4596)
#   OPENCODE_SERVER_LOG    stdout/stderr capture file  (default: ~/.local/share/opencode/serve.log)
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"                 # graphagents repo root
SCRIPT_PATH="$SCRIPT_DIR/$(basename "$0")"

SESSION_NAME="opencode-server"
BIND_HOST="127.0.0.1"
PORT="${OPENCODE_SERVER_PORT:-4596}"
LOG_FILE="${OPENCODE_SERVER_LOG:-$HOME/.local/share/opencode/serve.log}"
PID_FILE="$HOME/.local/share/opencode/serve.pid"
OPENCODE_BIN="$HOME/.bun/bin/opencode"
MODEL_CACHE="$HOME/.cache/opencode/models-minimal.json"

log()  { printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }
die()  { warn "Error: $*"; exit 1; }

tcp_ok() { timeout 1 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null; }

server_pid() {
  pgrep -f "$OPENCODE_BIN serve --hostname $BIND_HOST --port $PORT" 2>/dev/null | tail -1 || true
}

human_rss() {
  local pid="$1"
  ps -o rss= -p "$pid" 2>/dev/null | awk '{printf "%.1f MiB", $1/1024}' || true
}

load_env() {
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$HOME/.local/bin:$PATH"
  if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
  fi
  if [[ -f "$MODEL_CACHE" ]]; then
    export OPENCODE_MODELS_PATH="$MODEL_CACHE"
  fi
}

require_key() {
  if [[ -z "${EPFL_RCP_API_KEY:-}" ]]; then
    die "EPFL_RCP_API_KEY is not set. Add it to $ROOT_DIR/.env or export it first."
  fi
}

usage() {
  cat <<EOF
opencode-server.sh — control the shared OpenCode server

Usage:
  opencode-server.sh [start|stop|restart|status|logs]

Commands:
  start     launch the headless server (tmux if available, nohup otherwise)
  stop      stop the server (tmux session, pid file and matching process)
  restart   stop + start
  status    show whether the server is running (default when no command given)
  logs      tail the server log (Ctrl+C to stop following)

Environment:
  OPENCODE_SERVER_PORT   TCP port (default 4596)
  OPENCODE_SERVER_LOG    log file (default ~/.local/share/opencode/serve.log)

Attach a client from any repo:
  opencode attach http://$BIND_HOST:$PORT --dir /path/to/repo
EOF
}

# --- internal: the actual server process (runs inside tmux / under nohup) ---
cmd___run-server() {
  load_env
  require_key
  mkdir -p "$(dirname "$LOG_FILE")"
  cd "$ROOT_DIR"
  exec "$OPENCODE_BIN" serve --hostname "$BIND_HOST" --port "$PORT" >>"$LOG_FILE" 2>&1
}

cmd_start() {
  local pid
  pid="$(server_pid)"
  if [[ -n "$pid" ]] || tcp_ok "$BIND_HOST" "$PORT"; then
    log "OpenCode server already running (port $PORT). Nothing to do."
    cmd_status
    return 0
  fi

  # Fail fast on a missing key before spawning anything.
  load_env
  require_key

  if command -v tmux >/dev/null 2>&1; then
    tmux new-session -d -s "$SESSION_NAME" "bash '$SCRIPT_PATH' __run-server"
    log "Launched server in tmux session '$SESSION_NAME'."
  else
    nohup bash "$SCRIPT_PATH" __run-server >/dev/null 2>&1 &
    local nohup_pid=$!
    printf '%s\n' "$nohup_pid" > "$PID_FILE"
    log "Launched server with nohup (pid $nohup_pid, no tmux available)."
  fi

  local ready=0
  for _ in $(seq 1 30); do
    if tcp_ok "$BIND_HOST" "$PORT"; then
      ready=1
      break
    fi
    sleep 1
  done

  if [[ "$ready" -eq 1 ]]; then
    pid="$(server_pid)"
    log "Ready: http://$BIND_HOST:$PORT  (pid ${pid:-?}, RSS $(human_rss "$pid"))"
    log "Attach a client:  opencode attach http://$BIND_HOST:$PORT --dir /path/to/repo"
  else
    warn "Server did not become ready within 30s. Last log lines:"
    tail -n 10 "$LOG_FILE" >&2 || true
    exit 1
  fi
}

cmd_stop() {
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    tmux kill-session -t "$SESSION_NAME"
    log "Killed tmux session '$SESSION_NAME'."
  fi
  if [[ -f "$PID_FILE" ]]; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  # Catch any stray server process started outside tmux/nohup bookkeeping.
  pkill -f "$OPENCODE_BIN serve --hostname $BIND_HOST --port $PORT" 2>/dev/null || true
  if tcp_ok "$BIND_HOST" "$PORT"; then
    warn "Warning: something is still listening on port $PORT."
  else
    log "OpenCode server stopped."
  fi
}

cmd_status() {
  local pid rss etime endpoint
  pid="$(server_pid)"
  if tcp_ok "$BIND_HOST" "$PORT"; then endpoint="reachable"; else endpoint="not reachable"; fi
  if [[ -n "$pid" ]]; then
    rss="$(human_rss "$pid")"
    etime="$(ps -o etime= -p "$pid" 2>/dev/null | xargs || true)"
    log "OpenCode server: RUNNING (pid $pid, RSS ${rss:-unknown}, up ${etime:-?}) — endpoint $endpoint: http://$BIND_HOST:$PORT"
  else
    log "OpenCode server: NOT RUNNING (endpoint $endpoint: http://$BIND_HOST:$PORT)"
  fi
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log "tmux session '$SESSION_NAME' present — 'tmux attach -t $SESSION_NAME' to watch it live."
  fi
  log "Attach:  opencode attach http://$BIND_HOST:$PORT --dir /path/to/repo"
}

cmd_logs() {
  if [[ ! -f "$LOG_FILE" ]]; then
    die "No log file yet at $LOG_FILE."
  fi
  tail -n 50 -f "$LOG_FILE"
}

case "${1:-status}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop; cmd_start ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  __run-server) cmd___run-server ;;
  -h|--help|help) usage ;;
  *) warn "Unknown command: $1"; usage; exit 1 ;;
esac
