#!/usr/bin/env bash
#
# skills/note-taking/outline-magic-link.sh
#
# Trigger an Outline "Magic Sign-in Link" email for an agent address, fish
# the returned link out of the local MailPit sink, and strip the
# desktop-app handoff suffix so it signs straight into the web UI.
#
# Outline magic links embed the IP address of whoever REQUESTED the sign-in,
# and Outline rejects the callback when the clicking IP differs - so always
# request the email from the agent's own browser window first (Sign in with
# email), then run this script to extract a clean, desktop-free link.
#
# Usage:
#   skills/note-taking/outline-magic-link.sh --buzz
#   skills/note-taking/outline-magic-link.sh --hubert
#   skills/note-taking/outline-magic-link.sh --victoria
#   skills/note-taking/outline-magic-link.sh --admin
#   skills/note-taking/outline-magic-link.sh --email <addr> --wait 30
#
# Options:
#   --buzz | --hubert | --victoria | --admin
#                     shorthand for the agent/owner addresses
#   --email <addr>    explicit address (overrides the shorthands)
#   --request         send the sign-in request from THIS HOST instead -
#                     WARNING: the produced link is bound to the host's IP
#                     and fails when clicked from any other IP
#   --wait <seconds>  how long to poll MailPit for a fresh link (default 1)
#
# Requires: curl, python3.
# Exit codes: 0 = link printed, 1 = failure.

set -u

# ---------------------------------------------------------------------------
# Resolve the repo root (script lives in skills/note-taking/) and load .env
# so OUTLINE_SERVER is available for the request step.
# ---------------------------------------------------------------------------

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1090
set -a
source "$ROOT/.env"
set +a

OUTLINE_SERVER="${OUTLINE_SERVER:?OUTLINE_SERVER is not set in .env}"
MAILPIT="${OUTLINE_MAILPIT:-http://localhost:8025}"

EMAIL=""
REQUEST=0
WAIT=1

# ---------------------------------------------------------------------------
# Agent and owner addresses live in the shared contact directory
# (skills/chat/contacts.json) - one place to add or change them.
# ---------------------------------------------------------------------------

resolve_email_for_flag() {
    python3 - "$1" "$ROOT/skills/chat/contacts.json" <<'PYEOF'
import json
import sys

flag, path = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(0)
flag = flag.lower()

for name, entry in (data.get('humans') or {}).items():
    aliases = {str(a).lower() for a in entry.get('aliases', [])}
    if flag == name.lower() or flag in aliases:
        if entry.get('email'):
            print(entry['email'])
        sys.exit(0)

for key, entry in (data.get('agents') or {}).items():
    aliases = {str(a).lower() for a in entry.get('aliases', [])}
    aliases.add(str(entry.get('bot', '')).lower())
    if flag == key.lower() or flag in aliases:
        if entry.get('email'):
            print(entry['email'])
        sys.exit(0)
PYEOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --email) EMAIL="$2"; shift 2 ;;
        --buzz|--hubert|--victoria|--admin)
            EMAIL="$(resolve_email_for_flag "${1#--}")"
            if [[ -z "$EMAIL" ]]; then
                echo "Error: no address for $1 in skills/chat/contacts.json -" \
                    "add an 'email' field to its entry, or use --email" >&2
                exit 1
            fi
            shift ;;
        --request) REQUEST=1; shift ;;
        --wait) WAIT="$2"; shift 2 ;;
        --no-request)
            echo "  note: --no-request is now the default; links are IP-bound to the requester"
            shift ;;
        *) echo "Error: unknown option $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$EMAIL" ]]; then
    echo "Error: --email is required" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Ask Outline to send the magic sign-in email. The public endpoint answers
# {"success":true}; if Outline ever ignores it, request the email from the
# web sign-in page instead and re-run with --no-request.
# ---------------------------------------------------------------------------

if (( REQUEST == 1 )); then
    echo "WARNING: --request sends the sign-in from this host - the link gets"
    echo "         bound to the host's IP and fails when clicked elsewhere."
    echo "Requesting sign-in email for $EMAIL ..."
    RESP="$(curl -s --max-time 10 -X POST -H "Content-Type: application/json" \
        -d "{\"email\": \"$EMAIL\"}" "$OUTLINE_SERVER/auth/email" || true)"
    echo "  outline says: $RESP"
fi

# ---------------------------------------------------------------------------
# Snapshot the sign-in email IDs already in MailPit, so the script only ever
# prints a link that is genuinely fresh.
# ---------------------------------------------------------------------------

SEEN_IDS="$(curl -s --max-time 10 "$MAILPIT/api/v1/messages" | EMAIL="$EMAIL" python3 -c "
import json, os, sys
try:
    d = json.load(sys.stdin)
    email = os.environ['EMAIL'].lower()
    ids = [m['ID'] for m in d.get('messages', [])
           if m['To'][0]['Address'].lower() == email
           and 'Magic Sign-in Link' in m.get('Subject', '')]
    print(' '.join(ids))
except Exception:
    pass")"

# ---------------------------------------------------------------------------
# Poll MailPit for a fresh Magic Sign-in Link for the address.
# ---------------------------------------------------------------------------

NEW_ID=""
ELAPSED=0
while (( ELAPSED <= WAIT )); do
    NEW_ID="$(curl -s --max-time 10 "$MAILPIT/api/v1/messages" | \
        EMAIL="$EMAIL" SEEN="$SEEN_IDS" python3 -c "
import json, os, sys
try:
    d = json.load(sys.stdin)
    email = os.environ['EMAIL'].lower()
    seen = set(os.environ.get('SEEN', '').split())
    for m in d.get('messages', []):
        if (m['To'][0]['Address'].lower() == email
                and 'Magic Sign-in Link' in m.get('Subject', '')
                and m['ID'] not in seen):
            print(m['ID'])
            break
except Exception:
    pass")"
    if [[ -n "$NEW_ID" ]]; then
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

# ---------------------------------------------------------------------------
# Fall back to the newest existing link, with a warning, when nothing fresh
# arrived during the polling window.
# ---------------------------------------------------------------------------

FALLBACK_NOTE=""
if [[ -z "$NEW_ID" ]]; then
    NEW_ID="$(curl -s --max-time 10 "$MAILPIT/api/v1/messages" | \
        EMAIL="$EMAIL" python3 -c "
import json, os, sys
try:
    d = json.load(sys.stdin)
    email = os.environ['EMAIL'].lower()
    candidates = [m['ID'] for m in d.get('messages', [])
                  if m['To'][0]['Address'].lower() == email
                  and 'Magic Sign-in Link' in m.get('Subject', '')]
    if candidates:
        print(candidates[0])
except Exception:
    pass")"
    FALLBACK_NOTE="(note: no fresh link arrived; printing the newest existing one - if it was already consumed, request a new sign-in email first)"
fi

if [[ -z "$NEW_ID" ]]; then
    echo "Error: no Magic Sign-in Link email found in MailPit for $EMAIL" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Extract the /auth/email.callback link and strip the desktop handoff.
# ---------------------------------------------------------------------------

LINK="$(curl -s --max-time 10 "$MAILPIT/api/v1/message/$NEW_ID" | python3 -c "
import json, re, sys
d = json.load(sys.stdin)
html = d.get('HTML', '') or ''
text = d.get('Text', '') or ''
urls = re.findall(r'https?://[^\s\"<>]+', html + ' ' + text)
for u in urls:
    if '/auth/email.callback?token=' in u:
        print(u)
        break
")"

if [[ -z "$LINK" ]]; then
    echo "Error: callback link not found in the caught email" >&2
    exit 1
fi

LINK="${LINK%%\&client=desktop*}"

echo
if [[ -n "$FALLBACK_NOTE" ]]; then
    echo "$FALLBACK_NOTE"
fi
echo "Web sign-in link for $EMAIL - paste it into the agent's own browser window:"
echo "$LINK"
exit 0
