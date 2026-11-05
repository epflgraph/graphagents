# GraphArchitecture — validator & canvas reference

## Validation gate

From repo root: `python3 validate_graph.py platform.graph.yaml services/*.graph.yaml`

- Per-file: JSON Schema validation, semantic lint (unique ids, edge endpoints, group members, env vocabulary, redaction ban, duplicate from/to/type triples), canonical-dump idempotence, render smoke (React Flow JSON + Mermaid consistency).
- Assembled graph: stub resolution (`stub_owner` → `meta.service` → same-id non-external → `alias_of`), per-env edge joins, cross-file duplicates.
- Exit codes: 0 ok, 1 error(s), 2 warnings only.
- Flags: `--json` (machine-readable report), `--fix` (canonicalize in place; refuses comment-carrying files), `--schema PATH`.

## Canvas

Run modes (from repo root; all bind all interfaces for LAN use):

- `npm run canvas-dev` — Vite dev server, instant HMR.
- `npm run canvas-watch` — `vite build --watch` + static prod server on :5199 (recommended).
- `npm run canvas-start` — one-shot build + serve.
- Headless checks: `npm run smoke` (parse → flow mapping assertions + dump → reparse identity), `npm run build`.

Editing semantics: manual save only (no autosave); the server reads/writes the repo's `*.graph.yaml` via `GET/POST /graphs/<relative-path>` middlewares in `vite.config.js` / `serve.mjs`; dragging records positions, written on **save now**; edges connect as `depends-on`; double-click renames a label.

The canvas is a trusted-LAN dev tool: anyone who can reach the port can edit the YAML through it; git history is the safety net. Never expose it beyond the LAN.

## Known v0 limits

- Single-file view only (no assembled-graph rendering yet; `meta.include` assembly in the browser is future work).
- Deterministic grid auto-layout (elkjs later); group boxes derived, not persisted.
- Comment round-trip limited to the header.

## Ownership

- Each graph file header names its owner (graphdb-client → database-engineer/Ecco). The platform map header still names `senior-hexa-developer` (Buzz) — the senior-software-architect now owns the repo; on first touch of the platform file, update its owner header (confirm with Buzz first, note the handover in the knowledge base).
