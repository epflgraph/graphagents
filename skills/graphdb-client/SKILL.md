---
name: graphdb-client
description: Graph DB Client repo reference (~/dev/graphdb-client) — hexagonal layout, graphdb CLI commands, YAML config/SSL contract, export/import/copy/compare, tests. Use when working in ~/dev/graphdb-client.
---

# GraphDB Client

Python >= 3.10, packaged as `graphdb-client` (`pyproject.toml`); virtualenv at `.venv.graphdb`; console script `graphdb` -> `graphdb.entrypoints.cli.cli_main:main`; type-checked with `pyright` (`pyrightconfig.json`). Moves and manages the platform's MySQL/MariaDB data between named environments (export, import, copy, compare).

## Repo map (hexagonal, dependencies point inward)

- `graphdb/domain/models/` — `GraphDBConfig`, `SQLQuery`, `Table`, `Connection`; `domain/sql.py`, `domain/exceptions.py`.
- `graphdb/application/operations/` — `ops_connectivity`, `ops_config`, `ops_export`, `ops_import`, `ops_copy` (composes export+import), `ops_compare`.
- `graphdb/application/ports/` — `prt_*` interfaces in `engine/`, `gateways/`, `data/`, `persistence/`, `rendering/`, `schema/`.
- `graphdb/application/policies/` — `pol_ddl`, `pol_table`, `pol_config`.
- `graphdb/adapters/` — `eng_*` (SQLAlchemy), `gtw_*` (dbclient, mysqldump, filesystem, yaml, environment), `dta_*` (copy, import, integrity), `prs_*` (cell persistence), `rdr_*` (Rich rendering), `sch_*` (schema); `adapters/environments.py` builds per-environment handles.
- `graphdb/entrypoints/cli/` — Typer app `cli_main.py`, one `cmd_*.py` per command, `container.py` is the composition root.

## Read deeper (reference files in this folder)

| File | Read when |
|---|---|
| `reference/cli.md` | invoking, writing, or changing `graphdb` commands |
| `reference/config-and-rules.md` | touching the YAML config/SSL contract, chunking/SSL behavior, tests, or docker publishing |

## Invariants

- Ports live in `application/ports/`, implemented in `adapters/`; infrastructure details stay inside adapters.
- CLI entrypoints stay thin; `container.py` is the composition root.
- Do not expose SQLAlchemy rows, SQL strings, or subprocess payloads to domain/application logic.
- Commit style: gitmoji (`✨ feat:`, `🐛 fix:`, `♻️ refactor:`, `🗑️ ...`).
