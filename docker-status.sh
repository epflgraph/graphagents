#!/usr/bin/env bash

printf "\n👻 Graph Agents\n\n"

docker compose --env-file outline.env ps --format '{{.Service}}|{{.Status}}|{{.Ports}}' |
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
printf "   %-12s %s\n" "VoceChat" "http://graphregistry.<your-domain>:3009"
printf "   %-12s %s\n" "Outline"  "http://graphregistry.<your-domain>:3010"

echo
