# GraphAuth — stack & operations reference

## Docker stack

- Phase 0: `graphauth-app` (host :3011 → container 28801, sibling of GraphRegistry's internal 28800) + `graphauth-mariadb` (127.0.0.1:13306, loopback-only).
- Phase 1 profile `idp`: Authentik (HTTPS :9447, loopback-only, first-time setup via SSH tunnel).
- Healthcheck: dependency-free python-stdlib probe; `mem_limit` 512M; runtime config mounted read-only from `./config` (never baked into the image).
- Public TLS is planned at the edge reverse proxy (`auth.<your-domain>`); everything is loopback-protected until then.

## Operations

- `./restart.sh` — rebuild + recreate the app (`--quick` bounce only, does NOT pick up code changes; `--all` whole Phase-0 stack).
- `docker compose --profile idp up -d` — add Authentik (Phase 1).
- Data: bind-mounted under `/home/dockerhost/docker-volumes/graphauth/` — `mariadb/` and `authentik/postgres/` are tier-0 (include in backups).

## Configuration

- `.env` (gitignored, holds REAL secrets — never read or commit it); `.env.example` is the documented shape with generation one-liners.
- Key variables: `GRAPHAUTH_MARIADB_*`, `GRAPHAUTH_ADMIN_PRINCIPALS`, `GRAPHAUTH_SESSION_SECRET` (admin cookie signing; empty = derived from DB password), `GRAPHAUTH_ADMIN_API_KEY` (tier-0 break-glass key — rotate via issue-new + revoke-old if it ever leaks), `AUTHENTIK_*` (Phase 1).
- Longer term secrets move to Infisical (see the graphdashboard stack for that pattern).

## Tests

- `pytest` under `tests/` — `test_access_policy`, `test_patterns`, `test_keys`, `test_machine_api`, `test_admin_ui`, `test_mysql_adapter` (unit + real-DB integration).
- Run inside the stack: `docker compose run --rm graphauth bash -c "pip install -q pytest httpx && python -m pytest tests -q"`.
