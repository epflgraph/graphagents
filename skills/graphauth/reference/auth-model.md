# GraphAuth — auth model reference

## API key model (`common/keys.py`)

- `gk-` + 43-char urlsafe token (256-bit entropy).
- Only the SHA-256 hex digest is stored (unsalted is intentional for high-entropy keys — lookup by hash).
- Full key shown exactly once at issue (GitHub-PAT style); `key_prefix` (`gk-` + 8 chars) is display-only.
- `expires_at` / `revoked_at` / `last_used_at` (throttled ≤ 1/min).

## Grant model

- One grant = `(principal, action ∈ {read, write}, pattern)`.
- Patterns are wildcarded GraphRegistry key tuples: type slots use the literal `*`; id slots are JSON arrays where `["*"]` = any id; `*` never mixes with concrete ids; id sets are a cross-product — paired ids go in separate rules.
- Semantics: default deny · allow-only (no deny rules) · write never implies read · node grants match only node keys, edge grants only edge keys · disabling a principal or revoking a key takes effect on the next request.
- Pattern MATCHING happens in Python (application layer), not SQL; SQL indexes serve storage and reverse audit queries only.

## Endpoints

- `GET /health` — liveness, no auth.
- `GET /ready` — readiness (MariaDB round-trip).
- `GET /admin` — management console (session cookie via admin-key login).
- `POST /v1/verify` — `Bearer gk-…`; exactly one of `node`/`edge` in the body; GraphRegistry key ordering; ids coerced to strings.
- `GET /v1/whoami` — principal behind the key.

## Database (`database/schema.sql`, MariaDB 11.x / InnoDB / utf8mb4)

- `principals` — UUIDv4, kind `user|service`, `idp_sub` for Authentik humans (Phase 1).
- `api_keys` — unique `key_hash`, FK cascade on principal.
- `grants` — wildcarded edge-key supersets: node grants leave `to_*`/`context` NULL.
