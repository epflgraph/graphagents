# GraphArchitecture — format conventions (schema v1)

- `arch` enum: `hexagonal`, `queuing`, `etl`, `storage`, `pipeline`, `external`.
- `interaction` enum: `sync-http`, `async-task`, `sql`, `shell`.
- Edge types: `depends-on`, `adapter-implements`, `data-flow`.
- Component and group ids inside a service file are prefixed with the full `meta.service` (e.g. `graphdb-client-*`); external/infra system ids stay unprefixed — they are the shared vocabulary the stub resolution joins on.
- External systems are stubs (`arch: external`) owned by their own service file; the assembled-graph validator reconciles stub ↔ owner.
- Environment vocabulary is owned by topology owners (graphdb-client declares test/staging/prod); consumers reference the names via `envs`/`env_ref` and never re-declare them.
- Redaction rule: no hosts, credentials, tokens, or ports — environment NAMES only; secrets stay in the service repos' config.
- Only outbound integrations are declared in a service file; consumers own the edges pointing at a service.
- Node `position` is the only persisted layout; group boxes are derived at load.
- Header comments (before `version:`) are preserved on save; comment lines inside the body are dropped (known v0 limitation).
