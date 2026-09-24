#!/usr/bin/env bash
#
# scripts/test-keys.sh
#
# Validate VoceChat bot API keys from the project .env.
#
# For every VOCECHAT_*_API_KEY variable found in .env, this script:
#   1. Validates the key format locally. A VoceChat API key is a hex string
#      of ~168 characters: hex(HMAC-SHA256 signature + JSON{uid, nonce}).
#      A short or non-hex value means the key was copied incompletely
#      (e.g. from the masked key list in the web UI, which shows only
#      "abcd ... ... wxyz", or by manually selecting the wrapped text in
#      the creation dialog instead of using its "Copy and Close" button).
#   2. Tests the key live against GET /api/bot (200 = valid, 401 = rejected).
#   3. On success, lists the channels the bot is a member of and probes the
#      read endpoint (GET /api/bot/group/{gid}/messages) for each channel.
#
# Key values are never printed or logged - only their lengths.
#
# Usage:
#   bash scripts/test-keys.sh        (or: ./scripts/test-keys.sh)
#
# Requires: curl, python3.
# Exit codes: 0 = all keys valid, 1 = at least one failure.

set -u

# ---------------------------------------------------------------------------
# Locate the repo root (this script lives in scripts/) and load .env.
# ---------------------------------------------------------------------------

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: $ENV_FILE not found." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

if [[ -z "${VOCECHAT_SERVER:-}" ]]; then
    echo "Error: VOCECHAT_SERVER is not set in .env" >&2
    exit 1
fi

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

# ---------------------------------------------------------------------------
# Discover all VOCECHAT_*_API_KEY variables (also matches a plain
# VOCECHAT_API_KEY for the single-bot layout).
# ---------------------------------------------------------------------------

KEY_VARS="$(compgen -A variable VOCECHAT | grep -E '^VOCECHAT([_A-Z0-9]*)?_API_KEY$' | sort)"

if [[ -z "$KEY_VARS" ]]; then
    echo "Error: no VOCECHAT_*_API_KEY variables found in .env" >&2
    exit 1
fi

TESTED=0
FAILURES=0

printf "VoceChat key test - server: %s\n\n" "$VOCECHAT_SERVER"

for VAR in $KEY_VARS; do
    BOT="${VAR#VOCECHAT_}"
    BOT="${BOT%_API_KEY}"
    [[ -z "$BOT" ]] && BOT="default"
    KEY="${!VAR}"
    TESTED=$((TESTED + 1))

    printf -- "--- %s (variable: %s)\n" "$BOT" "$VAR"

    # -----------------------------------------------------------------------
    # Local format checks - fail fast with actionable hints.
    # -----------------------------------------------------------------------

    if [[ -z "$KEY" ]]; then
        echo "    FAIL: empty value"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # Tolerate Windows CRLF line endings, but say so.
    if [[ "$KEY" == *$'\r'* ]]; then
        echo "    note: stripped a carriage return (CRLF line ending) from the value"
        KEY="${KEY//$'\r'/}"
    fi

    printf "    key length: %d chars\n" "${#KEY}"

    if [[ ! "$KEY" =~ ^[0-9a-fA-F]+$ ]]; then
        echo "    FAIL: not a hex string - this is not a VoceChat API key."
        echo "          Re-copy the full key: in the web UI re-create the key and"
        echo "          use the 'Copy and Close' button, or read the full value from"
        echo "          the DevTools Network response of the bot-api-key request."
        FAILURES=$((FAILURES + 1))
        continue
    fi

    if (( ${#KEY} < 100 )); then
        echo "    FAIL: too short (expected ~168 hex chars) - truncated copy."
        echo "          The key list in the web UI masks keys as 'abcd ... ... wxyz';"
        echo "          use the creation dialog's 'Copy and Close' button instead of"
        echo "          selecting the wrapped text manually."
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # -----------------------------------------------------------------------
    # Live auth test: GET /api/bot with the x-api-key header.
    # -----------------------------------------------------------------------

    CODE="$(curl -s -o "$TMP_JSON" -w "%{http_code}" --max-time 10 \
        -H "x-api-key: $KEY" "$VOCECHAT_SERVER/api/bot")"

    if [[ "$CODE" != "200" ]]; then
        if [[ "$CODE" == "000" ]]; then
            echo "    FAIL: cannot reach $VOCECHAT_SERVER (network error)"
        else
            echo "    FAIL: server rejected the key (HTTP $CODE)"
        fi
        FAILURES=$((FAILURES + 1))
        continue
    fi

    echo "    OK: key valid (HTTP 200)"

    # -----------------------------------------------------------------------
    # List the channels the bot is a member of.
    # -----------------------------------------------------------------------

    python3 - "$TMP_JSON" <<'PYEOF'
import json
import sys

try:
    groups = json.load(open(sys.argv[1]))
except Exception as exc:
    print(f"    warn: could not parse groups response: {exc}")
    sys.exit(0)

if not groups:
    print("    (bot is not a member of any channel)")

for g in groups:
    members = g.get("members")
    if isinstance(members, list):
        mstr = f"{len(members)} members {members}"
    else:
        mstr = str(members)
    print(f"    channel: gid={g.get('gid')}  name={g.get('name')!r}  {mstr}")
PYEOF

    # -----------------------------------------------------------------------
    # Read-path probe per channel (this is the "new message for you"
    # endpoint, so it must return 200 for every channel the bot is in).
    # -----------------------------------------------------------------------

    GIDS="$(python3 -c "import json,sys
try:
    print(' '.join(str(g.get('gid')) for g in json.load(open(sys.argv[1]))))
except Exception:
    pass" "$TMP_JSON" 2>/dev/null || true)"

    for GID in $GIDS; do
        MCODE="$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
            -H "x-api-key: $KEY" "$VOCECHAT_SERVER/api/bot/group/$GID/messages?context=5")"
        echo "    read-path gid=$GID: HTTP $MCODE"
    done
done

# ---------------------------------------------------------------------------
# Summary.
# ---------------------------------------------------------------------------

echo
if (( FAILURES == 0 )); then
    echo "RESULT: all $TESTED key(s) valid"
    exit 0
else
    echo "RESULT: $FAILURES of $TESTED key(s) failed"
    exit 1
fi
