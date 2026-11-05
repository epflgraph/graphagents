# Security Policy

## Supported scope

This repository contains **agent definitions, skills, shared notes, and
configuration** for the Graph Data Platform's agentic coding layer. It contains
no application source code and no credentials (sensitive values live in
untracked local files such as `.env` and `LOCAL-INFRA.md`).

## Reporting a vulnerability

Do **not** open a public issue for security reports.

Contact the maintainer directly through GitHub (fpereira-epfl) or the
project's security channel. Include:

- a description of the issue and its impact;
- reproduction steps or proof-of-concept;
- affected files or components.

You will receive an acknowledgement as soon as possible, followed by status
updates until the issue is resolved.

## Operational notes for deployers

- This repository documents an agent ecosystem whose services (chatroom,
  wiki, dashboard) are reached over the network. When deploying from these
  files, review which ports you expose publicly — default to loopback
  bindings and place authenticated services behind a reverse proxy.
- Agents act on instructions from their chatroom. Treat chatroom access as
  privileged: close public registration, use per-bot API keys, and require
  human approval for destructive operations.
- Never commit heap snapshots (`.heapsnapshot`), `.env` files, or local
  infrastructure notes; the hooks in this repo scan staged changes for
  secrets, but review is still your responsibility.
