---
name: project-safety
description: Guidelines for ensuring safety and minimizing risk in project operations.
---

# Project Safety

- Default to read-only investigation unless the user explicitly requests modifications.
- Make the smallest change that solves the stated problem.
- Never perform large-scale refactors without explicit authorization.
- Never rewrite, move, rename, or delete large portions of the codebase without explicit authorization.
- Never delete files unless the user explicitly requests the deletion.
- Never modify generated, exported, cached, or third-party files unless explicitly requested.
- Never modify multiple subsystems when the task concerns only one subsystem.

## Secrets and Credentials

- Never read `.env`, `.env.*`, secrets, credentials, tokens, certificates, private keys, or password files unless explicitly required for the task.
- Never expose secrets in responses, notes, logs, commits, or AI Wiki entries.
- Never copy credentials between files.
- Treat all configuration files as potentially sensitive.

## Git Safety

- Stay in the current repo; don't venture into others deployed on the same server.
- Do not execute Git commands unless explicitly requested by the user.
- Do not commit, push, pull, merge, rebase, stash, reset, checkout, cherry-pick, tag, or modify Git history.
- Do not assume Git operations are safe simply because they appear read-only.
- If Git information is required, ask for permission or use information already provided by the user.

## Database Safety

- Do not connect to databases unless explicitly requested.
- Do not execute INSERT, UPDATE, DELETE, ALTER, DROP, TRUNCATE, CREATE, or migration commands unless explicitly authorized.
- Treat all production databases as critical systems.
- Prefer proposing SQL changes rather than executing them.
- Clearly distinguish between read-only analysis and database modifications.

## Infrastructure Safety

- Do not start, stop, restart, deploy, or reconfigure services without explicit authorization.
- Do not modify cloud resources, containers, servers, CI/CD pipelines, or infrastructure settings unless explicitly requested.
- Do not install packages, dependencies, or system software without authorization.

## Investigation Strategy

- Consult AI Wiki notes before performing extensive repository exploration.
- Read only the files necessary to complete the task.
- Prefer targeted inspection over broad repository scans.
- Avoid expensive, disruptive, or unnecessary operations.

## Change Management

- Explain significant changes before making them.
- Prefer incremental changes over broad changes.
- Preserve existing architecture, conventions, and behavior unless the task requires otherwise.
- When uncertain whether an action is safe, stop and ask for clarification.
- Favor caution over initiative when data loss, service interruption, security exposure, or architectural drift is possible.
