---
name: grapharchitecture
description: Graph Architecture repo (~/dev/grapharchitecture) — platform map, service graph files, schema/v1.json, validate_graph.py, canvas. Use when editing or validating the architecture graph files.
---

# GraphArchitecture

Collaborative definition and visual representation of the Graph Data Platform architecture. Guiding principle: **"the file is the API"** — the YAML graph files are the single source of truth; the canvas is a view + editor over them. Format spec: *Platform architecture diagram format (v0 draft)* in the Outline **Agents** collection.

## Repo map

- `platform.graph.yaml` — root platform map (C4 levels 1–2): platform systems, external infra, `meta.include` of the service files; declares the shared system-level vocabulary.
- `services/graphregistry.graph.yaml`, `services/graphai.graph.yaml`, `services/graphdb-client.graph.yaml` — per-service component views (C4 level 3); each header names its owning agent.
- `schema/v1.json` — canonical contract for the graph format.
- `validate_graph.py` — the validation gate.
- `canvas/` — React Flow (`@xyflow/react`) + Vite loader/saver app.

## Read deeper (reference files in this folder)

| File | Read when |
|---|---|
| `reference/format.md` | creating or editing nodes/edges/groups, or touching ids, envs, stubs, or redaction rules |
| `reference/validator-canvas.md` | running validation, using `--fix`, or starting/configuring the canvas |

## Invariants

- One node = one architectural component/role, never a single source file.
- No hosts, credentials, tokens, or ports in the graph files — environment NAMES only.
- Commit style: gitmoji.
