#!/usr/bin/env bash

printf "\n👻 Graph Agents\n\n"

docker compose ps --format '{{.Service}}|{{.Status}}|{{.Ports}}' |
while IFS='|' read -r service status ports; do
    case "$status" in
        *healthy*)
            icon="🟢"
            ;;
        *starting*)
            icon="🟡"
            ;;
        *Restarting*|*unhealthy*)
            icon="🔴"
            ;;
        *Exited*|*Dead*)
            icon="🔴"
            ;;
        Up*)
            icon="🟢"
            ;;
        *)
            icon="🟡"
            ;;
    esac

    printf "%-3s %-16s %-32s %s\n" "$icon" "$service" "$status" "$ports"
done

printf "\n🔗 Services\n\n"
# Service URLs come from .env (untracked) so real hosts aren't hardcoded here.
ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if [ -f "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; fi
printf "   %-12s %s\n" "VoceChat" "${VOCECHAT_SERVER:-<not configured — see LOCAL-INFRA.md>}"
printf "   %-12s %s\n" "Outline"  "${OUTLINE_SERVER:-<not configured — see LOCAL-INFRA.md>}"

echo
