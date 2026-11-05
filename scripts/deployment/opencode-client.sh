#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# opencode-client.sh — attach this repo to the shared OpenCode server
#
# Copy or symlink this file into the ROOT of each repo you want to work in,
# e.g.:
#   ln -s ~/dev/graphagents/scripts/deployment/opencode-client.sh \
#         ~/dev/graphauth/opencode.sh
#
# The "repo" is always the directory the script lives in (works both copied
# and symlinked). All model inference happens on the shared server, so this
# client is just a viewport and does not need EPFL_RCP_API_KEY itself.
#
# Usage:
#   ./opencode.sh                 attach to the shared server
#   ./opencode.sh -c              attach and continue this repo's last session
#   ./opencode.sh --mini          attach with the minimal TUI (lighter)
#   ./opencode.sh --direct        bypass the server, run a standalone instance
#                                 (the old 1-instance-per-repo behaviour)
#
# Configuration (environment):
#   OPENCODE_SERVER_URL   server to attach to (default: http://127.0.0.1:4596)
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"
REPO_ROOT="$(pwd)"

export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$HOME/.local/bin:$PATH"
OPENCODE_BIN="$HOME/.bun/bin/opencode"

SERVER_URL="${OPENCODE_SERVER_URL:-http://127.0.0.1:${OPENCODE_SERVER_PORT:-4596}}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Standalone escape hatch: skip the shared server entirely.
if [[ "${1:-}" == "--direct" ]]; then
  shift
  exec "$OPENCODE_BIN" "$@"
fi

# Pre-flight: is the shared server reachable?
HOST="${SERVER_URL#http*://}"
HOST="${HOST%%/*}"
HOSTONLY="${HOST%%:*}"
PORT="${HOST##*:}"
if [[ "$PORT" == "$HOSTONLY" ]]; then
  PORT=4596
fi
if ! timeout 2 bash -c "exec 3<>/dev/tcp/$HOSTONLY/$PORT" 2>/dev/null; then
  {
    echo "Error: shared OpenCode server not reachable at $SERVER_URL."
    echo "Start it with:   ~/dev/graphagents/scripts/deployment/opencode-server.sh start"
    echo "Or run standalone in this repo:  $0 --direct"
  } >&2
  exit 1
fi

if [[ -z "${EPFL_RCP_API_KEY:-}" ]]; then
  echo "Note: no EPFL_RCP_API_KEY in this repo — model calls are handled by the shared server." >&2
fi

exec "$OPENCODE_BIN" attach "$SERVER_URL" --dir "$REPO_ROOT" "$@"
