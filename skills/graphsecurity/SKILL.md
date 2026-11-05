---
name: graphsecurity
description: GraphSecurity repo reference (~/dev/graphsecurity) — greenfield security-tooling conventions, scanner seed patterns from graphauth, tool golden rules. Use when working in ~/dev/graphsecurity.
---

# GraphSecurity

Platform security tooling and automation: **secret detection, code scanning, vulnerability assessment, and intrusion testing** across Graph services.

## Status

Greenfield — one "Initial commit" on `main` (published to origin) containing only a README and a Python-oriented `.gitignore`. The structure (package layout, `pyproject.toml`, tests, docs, hook/CI wiring) is designed as the work unfolds.

## Conventions

- Python >= 3.10; follow the platform's code conventions (see the `code-validation` skill); gitmoji commit style.
- Prefer a light hexagonal separation (scanner/assessment logic in domain/application layers, CLI entrypoints thin) but do not over-engineer a tooling repo.
- The graphauth repo's `scripts/security/` scanners are the seed patterns — promote and generalize them here as the first tools:
  - `scan-staged.sh` (staged-content secret scan, fail-closed pre-commit hook in `.githooks/pre-commit`)
  - `scan-leaks.sh` (published-history audit: isolated bare clone of origin branches → TruffleHog with live verification + gitleaks against `.gitleaks.toml`)
  - Exit-code convention worth keeping: 0 clean, 1 findings, 2 scan failed/unreliable.

## Golden rules for every tool in this repo

- Findings are reported as **locations and severities only** — never echo secret values, key material, or credentials into logs, reports, exit messages, or chat.
- Tools act only on explicitly given targets (repo paths, hosts); never build in ambient or background scanning of the platform.
- Scanners must fail closed: if the scan cannot run reliably, report failure rather than "clean".
