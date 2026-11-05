---
name: graphauth
description: GraphAuth service reference (~/dev/graphauth) — gk- keys, tuple-pattern grants, PDP, schema, endpoints, compose stack, tests. Use when working in ~/dev/graphauth or on GraphAuth authN/authZ details.
---

# GraphAuth

Centralized authentication and access management for the Graph Data Platform. Services call `POST /v1/verify` with `Bearer gk-…` keys before touching graph data; deny is a normal 200 with `decision: deny` (callers map it to 403). Three authorization levels: L0 identity (Authentik — Phase 1) · L1 app access (Authentik groups — Phase 1) · L2 domain grants (tuple-pattern permissions — Phase 0, live). The IdP owns identity; each service owns its authorization data; node/edge patterns NEVER live in Authentik attributes.

FastAPI + uvicorn + PyMySQL, Python >= 3.10, hexagonal layout.

## Repo map

- `graphauth/domain/models/` — `mdl_patterns.py` (NodePattern/EdgePattern), `mdl_grant.py`, `mdl_principal.py`, `mdl_apikey.py`.
- `graphauth/application/` — `operations/ops_admin.py`, `operations/ops_auth.py`; `policies/pol_access.py` (the single decision point, PDP); `ports/gtw_*.py`.
- `graphauth/adapters/` — `db.py`, `repositories/rpr_*.py`.
- `graphauth/entrypoints/api/` — `machine.py` (`/v1`), `admin.py` (console), `main.py`, `schemas.py`, `templates/`.
- `graphauth/bootstrap.py` — creates the first admin principal, prints its key ONCE.
- `graphauth/common/` — `keys.py`, `config.py`.
- `database/schema.sql` · `docker-compose.yml` · `scripts/security/` · `.githooks/pre-commit`.

## Read deeper (reference files in this folder)

| File | Read when |
|---|---|
| `reference/auth-model.md` | working on keys, grants, the PDP, endpoints, or the DB schema |
| `reference/stack-ops.md` | deploying, configuring, restarting, backing up, or testing the stack |
| `reference/tooling.md` | running or changing the secret-scan tooling, or triaging the hardening candidates |

## Safety invariants

- Only the SHA-256 hash of an API key is ever stored; the full key is shown exactly once at issue.
- Pattern matching happens in Python (application layer), never in SQL.
- The pre-commit secret-scanning hook must never be bypassed or weakened.
- Commit style: gitmoji.
