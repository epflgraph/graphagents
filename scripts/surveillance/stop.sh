#!/usr/bin/env bash
# graphagents/scripts/surveillance/stop.sh
# Stops the surveillance kit (poller + webhook tripwire) via their pid files.
set -uo pipefail

SURV="$(cd "$(dirname "$0")/../.." && pwd)/.surveillance"

for name in poller tripwire; do
    pidfile="$SURV/$name.pid"
    if [ -f "$pidfile" ]; then
        pid="$(cat "$pidfile")"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" && echo "$name stopped (pid $pid)"
        else
            echo "$name not running (stale pid $pid)"
        fi
        rm -f "$pidfile"
    else
        echo "$name: no pid file"
    fi
done
