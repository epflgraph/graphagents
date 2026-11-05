# GraphDB Client — config contract, rules, tests

## Configuration

- `config.yaml` at repo root (template: `config.example.yaml`), path overridable via `GRAPHDB_CONFIG`/`.env`.
- Contains client/dump binaries (often docker-wrapped `mysql:8.0`), `export_path`, named environments (host, port, username, password), optional per-environment `ssl` block (`ca`, `cert`, `key`, `cipher`, `mode`, `verify_server_cert` — forwarded both as CLI flags and SQLAlchemy/PyMySQL SSL args; `mode` defaults to `REQUIRED`), and `default_env`.
- Preserve the multi-environment YAML config contract; avoid breaking changes to the config structure.

## Architecture rules (repo-specific)

- Shell-based operations (`mysqldump`, streamed SQL files) are intentional for performance on multi-GB tables; keep them.
- Chunked operations rely on `row_id` columns or dense boundary discovery; changing them affects large-table consistency.
- SSL handling has two paths (SQLAlchemy connect args vs. CLI flags); keep them aligned but separate.
- The client is currently a thick client with singleton tendencies — when advising refactoring, prefer injecting it into adapters over importing it from domain/application code.

## Tests

- `pytest` under `tests/` — application services, CLI commands, config, domain config, SSL paths (client and infrastructure), port conformance, SQLQuery.
- `tests/fakes.py` provides in-memory fakes so tests run without databases.

## Docker, legacy, misc

- `Dockerfile` + `docker_push.sh` publish `epflgraph/graphdb-client`; users mount their own `config.yaml` read-only.
- Legacy monoliths `graphdb-legacy.py` and `graphdb_patched.py` are reference-only; do not extend them.
- `scripts/sqlquery_showcase.py` demonstrates the SQLQuery value object.
- Logs (`copydb.log`, `graphdb-import.log`) are runtime artifacts; do not edit or commit them.
