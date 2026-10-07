---
name: note-taking
description: Take, edit, and search shared wiki notes in the Outline knowledge base. Use when asked to take notes, create or edit wiki pages, record decisions, conventions or findings, consult shared knowledge before exploring, or when the user says "note", "wiki", "write it down", "document it", or "search the wiki".
---

# Note Taking

Shared agent knowledge (wikis, decisions, conventions, pitfalls, API findings) lives in the **Outline knowledge base** — a self-hosted [Outline](https://www.getoutline.com) instance. Each Graph service has its own **collection**; notes are markdown **documents** inside those collections.

The concepts in this top section are technology-agnostic; only the backend section is implementation-specific.

## Collections per service

| Collection      | Covers                          | Primary agent             |
| --------------- | ------------------------------- | ------------------------- |
| `Registry`      | Graph Registry                  | senior-hexa-developer     |
| `AI`            | Graph AI                        | graphai-engineer          |
| `Search`        | Graph Search                    | full-stack-developer      |
| `Ontology`      | Graph Ontology                  | —                         |
| `Agents`        | Graph Agents (the agent repo)   | agentic-coding-manager    |
| `DB Client`     | MySQL/MariaDB CLI client        | —                         |
| `ES Client`     | ElasticSearch CLI client        | —                         |
| `SDK`           | Graph SDK (not developed yet)   | —                         |
| `Dashboard`     | GraphDashboard monitoring stack | systems-monitoring-engineer |

Write into your own service's collection; read freely across all of them.

## Note conventions

- Consult the knowledge base before extensive code exploration, searches, greps, or repository scans.
- Before creating a new page, **search the collection first** — prefer updating an existing note over creating an overlapping one.
- Create new pages when discovering project knowledge likely to help future agents (decisions, conventions, workflows, architecture, endpoints, pitfalls).
- Update existing pages when information becomes outdated, incomplete, or inaccurate; improve other agents' notes when it increases accuracy or clarity.
- Keep notes concise, factual, and implementation-focused. Assume future agents have no context beyond the knowledge base and the current task.
- Avoid storing transient debugging results or task-specific notes unlikely to be reused.
- Give pages descriptive titles (e.g. "GraphAI async task model", "GraphRegistry wiring in entrypoints").
- End each note with a short attribution footer (e.g. "*— recorded by graphai-engineer*"), so other agents know the origin of a page even when agents share one API key.
- Outline's markdown import rewrites list structure (a single `- [ ]` item flips unrelated lists into checkboxes) — see **Markdown import quirks** in the backend section.
- Repo-local `notes/*.md` files remain for infrastructure setup notes; durable service knowledge belongs in Outline.

## Natural Language Intent Parsing

| Component       | How to detect                                     | Examples                             |
| --------------- | ------------------------------------------------- | ------------------------------------ |
| **Intent**      | "note", "wiki", "write down", "document", "record" | "take a note about the timeout fix"  |
| **Target**      | Collection name or a service name                 | "in the AI collection", "for Registry" |
| **Content**     | Everything after "about"/"that"/":" or in quotes  | "the endpoint needs a token refresh" |
| **Search**      | "search the wiki", "look up in Outline"           | "search the wiki for wikify"         |

Default to your own service's collection when no target is given.

---

## Backend: Outline

[Outline](https://www.getoutline.com) is an open-source wiki/knowledge-base app. The instance is self-hosted next to VoceChat at `<server-url>/home`.

- Official API reference: <https://www.getoutline.com/developers>
- OpenAPI spec: <https://github.com/outline/openapi>

### API model

RPC-style: every endpoint is `POST {server}/api/{method}` with a JSON body and `Authorization: Bearer <api-key>`. Responses are `{ok: true, data: ..., pagination?}`; errors return `ok: false` with an `error` message. List endpoints paginate via `limit`/`offset` in the body.

Documents store **Markdown**; the API accepts and returns markdown text directly.

### Server Configuration

| Variable                   | Description                                        |
| -------------------------- | -------------------------------------------------- |
| `OUTLINE_SERVER`           | Base URL of the Outline server (no trailing `/`)   |
| `OUTLINE_<AGENT>_API_KEY`  | Per-agent API key, as named per agent in `agents/identities.json` |
| `OUTLINE_API_KEY`          | Fallback API key when no agent identity is given   |

Store these in `.env`. Never commit API keys. `.env` is gitignored — every server that runs agents needs its own copy.

Each agent speaks as its own Outline user. Agents are call-sign agnostic: pass `--as <your own agent name>` and the central registry `agents/identities.json` maps it to the exact key variable. Agent users are regular Outline members (Outline has no bot accounts); each user creates its own key under **Settings -> API & Apps**.

### Zero-setup onboarding

Agents should not need to research any of this — the client is primed for it:

- The client auto-loads `.env`: the first `.env` found walking up from the current directory, then the agents repo root. Never `source .env` or export key variables by hand.
- Agents are identity-agnostic: pass your own agent name (`--as senior-hexa-developer`) or your call sign (whatever it currently is — see the registry) — both resolve through the central registry `agents/identities.json`, which holds the current call signs and the exact per-service key variable names.
- The project uses per-agent keys only; there is no shared `OUTLINE_API_KEY` fallback that resolves. Always pass `--as <your name or call sign>`.
- If a call fails with a key error, the message lists every agent and its call sign (from the registry) — identify yourself by your own agent name; never grep `.env` or inspect its contents.
- Verify the setup in one command before anything else: `python skills/note-taking/outline_client.py --as <your agent name> auth`.

### Key creation

1. Log in to the Outline web UI.
2. Go to **Settings -> API & Apps -> New API key**.
3. Name it (e.g. "agents-notes"), copy the key — it starts with `ol_api_` followed by 38 characters.
4. Scopes: the default key has full access; scoped alternatives include `read`, `write`, `documents.*`, `collections.*`.

### Core endpoints

| Method                   | Purpose                                     | Key params                                     |
| ------------------------ | ------------------------------------------- | ---------------------------------------------- |
| `auth.info`              | Verify the key, get current user/team       | —                                              |
| `collections.list`       | List collections                            | `limit`, `offset`                              |
| `collections.info`       | Collection metadata                         | `id`                                           |
| `collections.documents`  | Nested document tree of a collection        | `id`                                           |
| `documents.list`         | List documents                              | `collectionId`, `limit`, `offset`              |
| `documents.info`         | One document with full text                 | `id`                                           |
| `documents.create`       | Create a document                           | `collectionId`, `title` (max 100), `text`, `parentDocumentId`, `publish` |
| `documents.update`       | Replace or append text                      | `id` (required), `title`, `text`, `append`, `publish` |
| `documents.search`       | Full-text search                            | `query`, `collectionId`, `limit`               |
| `documents.archive`      | Soft-delete (reversible)                    | `id`                                           |
| `documents.delete`       | Permanent delete                            | `id`                                           |
| `documents.move`         | Move to another collection/parent           | `id`, `collectionId`                           |

### Markdown import quirks

Outline's markdown import rewrites list structure — verified by bisection (2026-10):

- **Checkbox poisoning**: a single `- [ ]` task item anywhere in a document converts unrelated bullet lists across the whole page into checkboxes on import. Write notes without `- [ ]` markers; use plain bullets and let readers convert to checkboxes in the Outline UI.
- **Updates preserve node types**: `documents.update` replaces text but keeps the existing block structure, so checkbox pollution survives in-place edits.
- **Recreate, don't edit**: when a page imports wrong, archive it and `create` a fresh one — fresh `create` imports cleanly. Always `read` the page back after writing to verify what actually landed.

Bisection: a Context+Facts+Open-items doc flips every list to checkboxes; the same doc without the task list imports clean. Archived scratch page "Markdown import test (archive me)" (Registry collection) holds the repro.

## Python Client

A bundled client (`outline_client.py`) provides all operations using only the standard library.

```bash
# Verify the key and show current user/team
python skills/note-taking/outline_client.py auth

# List collections
python skills/note-taking/outline_client.py collections

# Show the document tree of a collection
python skills/note-taking/outline_client.py collection-docs --collection agents

# Create a note from a markdown file
python skills/note-taking/outline_client.py create --collection agents \
    --title "VoceChat integration" --file my-note.md

# Create inline
python skills/note-taking/outline_client.py create --collection ai \
    --title "Endpoint quirks" --text "## Token refresh\n\n401 triggers refresh."

# Create as a child page (nested under another note)
python skills/note-taking/outline_client.py create --collection registry \
    --title "Sub-adapter notes" --parent <parent-document-id> --file sub.md

# Read a document (markdown to stdout)
python skills/note-taking/outline_client.py read --id <document-id>

# Replace a document's text with a file's content
python skills/note-taking/outline_client.py edit --id <document-id> --file new.md

# Append to a document instead of replacing
python skills/note-taking/outline_client.py edit --id <document-id> --append --text "New finding."

# Search (optionally scoped to a collection)
python skills/note-taking/outline_client.py search --query "async task" --collection ai

# Archive (reversible) / delete (permanent)
python skills/note-taking/outline_client.py archive --id <document-id>
python skills/note-taking/outline_client.py delete --id <document-id>
```

## Collection directory

Friendly collection names, aliases and ids live in `skills/note-taking/collections.json`. Resolve targets by name or alias (`agents`, `ai`, `registry`, ...), collection id (UUID), or exact Outline name. When a new collection is created in Outline, add an entry here.

```json
{
  "collections": {
    "agents": { "id": "<uuid>", "aliases": ["graph agents", "agent repo"] }
  }
}
```

## Safety

- Never expose or commit the API key.
- Deleting documents is destructive — always ask the user first; prefer `archive` (reversible).
- Outline is the shared canonical knowledge base: other users and agents read it, and the owner supervises it — write accurate, professional content.
- Respect collection boundaries: write service knowledge into the right collection.
