---
name: graphdashboard
description: Deep reference for the GraphDashboard monitoring service at ~/dev/graphdashboard. Use when asked about Dashy, Grafana, Prometheus, Loki, Infisical, nginx, Docker Compose, or service-status monitoring for the Graph Data Platform.
---

# GraphDashboard

Deep reference for the **GraphDashboard** service located at `~/dev/graphdashboard`.

GraphDashboard provides dashboards, metrics, logs, and secrets management for the EPFL Graph Data Platform. It is a Docker Compose stack exposed behind an nginx reverse proxy with SSL termination.

## What GraphDashboard provides

- A **Dashy** landing page aggregating links to all platform services with live status checks.
- **Grafana** dashboards for visualizing Prometheus metrics.
- **Prometheus** scraping of platform exporters and endpoints.
- **Loki** log aggregation for the stack.
- **Infisical** as the central secrets manager for the platform.
- An **nginx** reverse proxy routing HTTPS traffic to each component.

## Tech stack

| Component | Technology |
| --- | --- |
| Orchestration | Docker Compose |
| Dashboard | Dashy (`lissy93/dashy`) |
| Metrics / visualization | Grafana + Prometheus |
| Logs | Grafana Loki 3.3.2 |
| Secrets manager | Infisical |
| Secrets backend | PostgreSQL 16 + Redis 7 |
| Reverse proxy | nginx 1.27 with Let's Encrypt SSL |
| Helper scripts | Python 3 (PyYAML), Bash |

## Directory layout

```
~/dev/graphdashboard
├── docker-compose.yml              # Stack definition
├── .env                            # Compose environment variables
├── .infisical.env                  # Infisical CLI credentials
├── infisical.yml                   # Required secrets per environment
├── prometheus.yml                  # Prometheus scrape configuration
├── loki-config.yaml                # Loki server/storage configuration
├── nginx.graphdash-https.conf      # nginx upstream + SSL configuration
├── config/
│   ├── dashy/
│   │   ├── config.yml              # Dashy sections, items, auth users, icons
│   │   └── icons/                  # Custom item icons
│   └── grafana/
│       ├── dashboards/             # JSON dashboard definitions
│       └── provisioning/
│           ├── dashboards/         # Dashboard provider YAML
│           └── datasources/        # Data-source provider YAML
├── scripts/
│   ├── dashy/
│   │   └── create_user.sh          # Helper to create Dashy users
│   └── infisical/
│       ├── backup.sh
│       ├── NS_backup_env.sh
│       ├── login.sh
│       ├── list_secrets.sh
│       ├── NS_list_secrets_https.sh
│       ├── list_required_vars.py
│       ├── NS_list_tags.sh
│       └── NS_manage_tags.sh
├── .data/                          # Runtime data (gitignored)
│   ├── grafana/
│   ├── loki/
│   ├── prometheus/
│   └── infisical/
│       ├── postgres/
│       └── redis/
└── assets/                         # Static assets (e.g. icon.png)
```

## Compose services

| Service | Image | Purpose |
| --- | --- | --- |
| `loki` | `grafana/loki:3.3.2` | Log aggregation |
| `prometheus` | `prom/prometheus:latest` | Metrics scraper and TSDB |
| `grafana` | `grafana/grafana:latest` | Metrics visualization |
| `postgres` | `postgres:16` | Infisical database |
| `redis` | `redis:7` | Infisical cache/backend |
| `infisical` | `infisical/infisical:latest` | Secrets manager UI/API |
| `dashy` | `lissy93/dashy:latest` | Service dashboard |
| `reverse-proxy` | `nginx:1.27` | SSL terminator and router |

## Public endpoints

All HTTPS endpoints are served from the dashboard host — real hostname in `LOCAL-INFRA.md` (untracked):

| Port | Service | Upstream |
| --- | --- | --- |
| `8444` | Dashy | `http://dashy:8080/` |
| `9444` | Grafana | `http://grafana:3000` |
| `9445` | Prometheus | `http://prometheus:9090` |
| `9446` | Infisical | `http://infisical:8080` (with websocket upgrade) |
| `80` | Loki | `http://loki:3100/loki/` under `/loki/` |

## Dashy configuration

File: `config/dashy/config.yml`

Key concepts:

- `pageInfo`: title, description, footer, nav links, logo.
- `appConfig`: theme (`one-dark`), layout, icon size, and authentication users.
- `sections`: groups of service links (e.g. Graph Dashboard, Graph Search, Graph AI @ RCP).
- `items`: individual tiles with `title`, `description`, `url`, `icon`, `color`, and optional `statusCheck`.

Status checks:

- `statusCheck: true` enables polling of `statusCheckUrl`.
- `statusCheckAllowInsecure: true` allows self-signed or untrusted certificates.
- Dashy runs in-browser, so URLs must be reachable from the client.

Authentication:

- Users live under `appConfig.auth.users` with SHA-256 hashes and roles (`admin`, `normal`).
- `enableGuestAccess: false` requires login.
- Custom icons are served from `config/dashy/icons/`.

## Prometheus configuration

File: `prometheus.yml`

- `global.scrape_interval: 15s`
- `global.evaluation_interval: 15s`
- External labels: `environment: rcp-remote`, `role: monitor-client`

Targets (all on the monitoring host — real address in LOCAL-INFRA.md, untracked):

| Job | Target | Purpose |
| --- | --- | --- |
| `celery` | `:9808` | Celery metrics exporter |
| `rabbitmq` | `:15672` | RabbitMQ management / exporter |
| `docker` | `:9417` | Docker Compose/container stats exporter |
| `gpu` | `:9400` | NVIDIA GPU metrics exporter |

## Loki configuration

File: `loki-config.yaml`

- `auth_enabled: false`
- HTTP on `3100`, gRPC on `9095`
- In-memory ring (single-instance deployment)
- `boltdb-shipper` index + filesystem object store
- Pattern ingester enabled; volume and log-level discovery enabled
- Ruler configured with local storage and Alertmanager target `http://localhost:9093`

Important Loki 3.x removals:

- `max_transfer_retries` and `shared_store` were removed.
- `chunk_store_config.max_look_back_period` is no longer valid.

## Infisical

- Runs on port `9446` behind nginx.
- Backed by PostgreSQL (`infisical_db`) and Redis.
- Memory limit: 768 MB; CPU limit: `1.0`.
- Helper scripts live in `scripts/infisical/`.
- `infisical.yml` declares `required_vars` per environment.
- `list_required_vars.py` reads `infisical.yml`, authenticates via the Infisical CLI, and emits prefixed environment variables.

## nginx reverse proxy

File: `nginx.graphdash-https.conf`

- Listens on `8444`, `9444`, `9445`, `9446` with SSL + HTTP/2.
- Uses certificates from the host's Let's Encrypt live directory (cert name in LOCAL-INFRA.md).
- Also listens on port `80` for the Loki `/loki/` path.
- Sets standard forwarded headers (`X-Forwarded-Proto`, `X-Forwarded-For`, `X-Real-IP`).
- Infisical location includes websocket upgrade headers.

## Common operations

Start the stack:

```bash
cd ~/dev/graphdashboard
docker compose up -d
```

Restart a service:

```bash
docker compose restart <service>
```

View logs:

```bash
docker compose logs -f <service>
```

Reload nginx after config changes:

```bash
docker compose exec reverse-proxy nginx -s reload
```

Validate Prometheus config:

```bash
docker compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

Validate Dashy config: check Dashy container logs on startup or use the in-app config validator.

## Troubleshooting checklist

1. Check container health: `docker compose ps`
2. Check logs for the failing service: `docker compose logs --tail 100 <service>`
3. Verify `.env` variables are exported before running Compose.
4. Verify bind-mount permissions (services run as `${HOST_UID}:${HOST_GID}` except Loki which runs as root).
5. Verify nginx config syntax before reloading.
6. Verify Prometheus targets are reachable from the Prometheus container.
7. Verify Dashy status-check URLs are reachable from the browser.
8. For Infisical issues, verify PostgreSQL and Redis are healthy first.

## Safety rules

- Do not edit `.env`, `.infisical.env`, or secrets files unless explicitly requested.
- Do not restart, scale, or modify the production stack unless explicitly requested.
- Do not access production databases, Infisical vaults, or Grafana/Prometheus data unless explicitly requested.
- Prefer rolling restarts and config validation before applying changes.
