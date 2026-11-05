<img src="assets/icon.png" alt="Project logo" height="64">

[![License](https://img.shields.io/github/license/epflgraph/graphagents?logo=apache&color=743EE6&logoColor=white&label=License)](https://github.com/epflgraph/graphagents/blob/master/LICENSE)
[![Latest Release on Github](https://img.shields.io/github/v/release/epflgraph/graphagents?sort=semver&logo=git&color=743EE6&logoColor=white&label=Release)](https://github.com/epflgraph/graphagents/releases/latest)
[![Contributors](https://img.shields.io/github/contributors/epflgraph/graphagents?sort=semver&logo=githubsponsors&color=743EE6&logoColor=white&label=Contributors)](https://github.com/epflgraph/graphagents/graphs/contributors)
[![GitHub Stars](https://img.shields.io/github/stars/epflgraph/graphagents?style=social)](https://github.com/epflgraph/graphagents/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/epflgraph/graphagents?logo=github&color=743EE6&logoColor=white&label=Last%20Commit)](https://github.com/epflgraph/graphagents/commits/master)
[![Open Issues](https://img.shields.io/github/issues/epflgraph/graphagents?logo=github&color=743EE6&logoColor=white&label=Issues)](https://github.com/epflgraph/graphagents/issues)
[![Open PRs](https://img.shields.io/github/issues-pr/epflgraph/graphagents?logo=github&color=743EE6&logoColor=white&label=Pull%20Requests)](https://github.com/epflgraph/graphagents/pulls)

🏠 [Project Home](https://github.com/epflgraph/graphproject) > Agents

**List of core services:**<br/>
[Registry](https://github.com/epflgraph/graphregistry) |
[AI](https://github.com/epflgraph/graphai/tree/rcp_deployment) |
[Ontology](https://github.com/epflgraph/graphontology) |
[Search](https://github.com/epflgraph/graphsearch_ui) |
[Chat](https://github.com/epflgraph/graphchatbot)

**List of utilities:**<br/>
[Dash](https://github.com/epflgraph/graphdashboard) |
[DB client](https://github.com/epflgraph/graphdb-client) |
[ES client](https://github.com/epflgraph/graphes-client) |
[SDK](https://github.com/epflgraph/graph-sdk) |
Agents

<br />

Overview
========
**Graph Agents** is the agentic coding layer of the Graph Data Platform. It hosts an [opencode](https://opencode.ai/) agent ecosystem that assists the team with architecture, implementation, debugging, and operations across the Graph services. This repository contains agent definitions, reusable skills, shared notes, and configuration, rather than application source code.

Agents
------
Specialist agents live in `agents/<name>.md` and are wired through `opencode.jsonc`. Each agent is scoped to a specific domain and loaded with the skills it needs.

| Agent | Focus |
|-------|-------|
| `senior-hexa-developer` | Hexagonal architecture and the GraphRegistry service. |
| `graphai-engineer` | GraphAI service contract, async task API, and legacy client. |
| `systems-monitoring-engineer` | GraphDashboard monitoring stack (Dashy, Grafana, Prometheus, Loki, Infisical). |
| `full-stack-developer` | GraphSearch UI Next.js project (search, chatbot, auth, CMS). |
| `agentic-coding-manager` | Orchestration, skill design, task delegation, and VoceChat surveillance. |

Skills
------
Reusable knowledge and tooling live in `skills/<name>/SKILL.md`. Skills cover both cross-cutting concerns and service-specific expertise.

- **Agentic coding**: `agentic-coding`, `delegation`.
- **Architecture & project**: `software-architecture`, `hexagonal-architecture`, `graph-project`, `project-safety`.
- **Service deep-dives**: `graph-registry`, `graphai`, `graphdashboard`, `graphsearch-ui`.
- **Collaboration**: `chat`, `note-taking`.
- **Validation**: `code-validation` for project Python conventions.

Configuration
-------------
`opencode.jsonc` defines the default agent, skill discovery, model provider, and tool permissions. Agents are primary agents (`mode: primary`) that can delegate sub-tasks to specialist subagents when a request spans multiple domains.

Chatroom & Surveillance
-----------------------
Agents coordinate in real time through a [VoceChat](https://voce.chat/) channel. The `chat` skill bundles `vocechat_client.py`, a CLI and Python module for the VoceChat Bot API. The `agentic-coding-manager` can run a webhook receiver to monitor conversations, detect blockers or conflicts, and post guidance when agents need course correction.

Shared Memory
-------------
Durable agent knowledge (wikis, decisions, conventions, pitfalls) lives in the [Outline](https://www.getoutline.com) knowledge base, one collection per Graph service. The `note-taking` skill bundles `outline_client.py`, a CLI for listing collections and creating, editing, and searching notes. Repo-local `notes/<name>.md` files remain for infrastructure setup instructions.
