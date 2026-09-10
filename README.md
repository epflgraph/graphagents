<img src="assets/icon.png" alt="Project logo" height="64">

[![License](https://img.shields.io/github/license/epflgraph/graphagents)](https://github.com/epflgraph/graphagents/blob/master/LICENSE)
[![Latest Release on Github](https://img.shields.io/github/v/release/epflgraph/graphagents?sort=semver)](https://github.com/epflgraph/graphagents/releases/latest)
[![GitHub Stars](https://img.shields.io/github/stars/epflgraph/graphagents?style=social)](https://github.com/epflgraph/graphagents/stargazers)
[![Contributors](https://img.shields.io/github/contributors/epflgraph/graphagents)](https://github.com/epflgraph/graphagents/graphs/contributors)
[![Last Commit](https://img.shields.io/github/last-commit/epflgraph/graphagents)](https://github.com/epflgraph/graphagents/commits/master)
[![Open Issues](https://img.shields.io/github/issues/epflgraph/graphagents)](https://github.com/epflgraph/graphagents/issues)
[![Open PRs](https://img.shields.io/github/issues-pr/epflgraph/graphagents)](https://github.com/epflgraph/graphagents/pulls)

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
- **Collaboration**: `chat`, `chat-post`, `chat-read`, `note-taking`.
- **Validation**: `code-validation` for project Python conventions.

Configuration
-------------
`opencode.jsonc` defines the default agent, skill discovery, model provider, and tool permissions. Agents are primary agents (`mode: primary`) that can delegate sub-tasks to specialist subagents when a request spans multiple domains.

Chatroom & Surveillance
-----------------------
Agents coordinate in real time through a [VoceChat](https://voce.chat/) channel. The `chat` skill bundles `vocechat_client.py`, a CLI and Python module for the VoceChat Bot API. The `agentic-coding-manager` can run a webhook receiver to monitor conversations, detect blockers or conflicts, and post guidance when agents need course correction.

Shared Memory
-------------
Notes in `notes/<name>.md` act as shared AI Wiki memory across agents. They record conventions, decisions, pitfalls, and setup instructions so that knowledge persists between sessions.
