#!/usr/bin/env bash
# graphagents/scripts/surveillance/start.sh
# Starts the surveillance kit (idempotent): the HAL polling listener
# (primary collection) and the webhook tripwire (delivery diagnosis).
# Safe to run repeatedly and at boot (cron @reboot). No root required.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SURV="$REPO/.surveillance"
mkdir -p "$SURV"

KEY_LINE="$(grep -E '^VOCECHAT_HAL_API_KEY=' "$REPO/.env" | head -1 | cut -d= -f2-)"
if [ -z "$KEY_LINE" ]; then
    echo "ERROR: VOCECHAT_HAL_API_KEY not found in $REPO/.env" >&2
    exit 1
fi

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

# --- Polling listener (primary collection) -----------------------------------
# The API key is handed over via the VOCECHAT_API_KEY environment variable,
# NOT a command-line argument: argv is world-readable via ps//proc cmdline.
if alive "$SURV/poller.pid"; then
    echo "poller already running (pid $(cat "$SURV/poller.pid"))"
else
    ( cd "$REPO" && setsid nohup env VOCECHAT_API_KEY="$KEY_LINE" \
        python3 skills/chat/vocechat_listen.py --all --interval 15 \
        >> "$SURV/vocechat.log" 2>> "$SURV/poller.err" & ) 2>/dev/null
    sleep 1
    pgrep -f "vocechat_listen.py" | head -1 > "$SURV/poller.pid"
    echo "poller started (pid $(cat "$SURV/poller.pid")) -> $SURV/vocechat.log"
fi

# --- Webhook tripwire (delivery diagnosis) -----------------------------------
if alive "$SURV/tripwire.pid"; then
    echo "tripwire already running (pid $(cat "$SURV/tripwire.pid"))"
else
    ( cd "$REPO" && setsid nohup python3 scripts/surveillance/webhook_tripwire.py \
        --bind 172.23.0.1 --port 8010 --log "$SURV/webhook-capture.jsonl" \
        >> "$SURV/tripwire.log" 2>&1 & ) 2>/dev/null
    sleep 1
    pgrep -f "webhook_tripwire.py" | head -1 > "$SURV/tripwire.pid"
    echo "tripwire started (pid $(cat "$SURV/tripwire.pid")) -> $SURV/webhook-capture.jsonl"
fi
