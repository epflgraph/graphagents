---
name: graph-registry
description: GraphRegistry service structure, hexagonal architecture, ports, adapters, and wiring.
---

# Graph Registry

GraphRegistry is the ingestion/ETL layer of the Graph Data Platform. It exposes a FastAPI REST API and a `graphregistry` CLI for building the knowledge graph.

## Role in the platform

- First layer of the Graph Data Platform.
- Ingests structured data and constructs the semantic knowledge graph.
- Feeds GraphSearch and GraphChat.
- System of record for graph entities and relationships.

## High-level architecture (hexagonal-ish, dependencies point inward)

- `graphregistry/domain/models/` — business entities and value objects.
- `graphregistry/application/operations/` — use cases / application services.
- `graphregistry/application/gateways/` — ports for external capabilities (persistence, AI, search, etc.).
- `graphregistry/adapters/` — concrete implementations of ports (MySQL repositories, GraphAI gateways, Elasticsearch clients, etc.).
- `graphregistry/entrypoints/` — FastAPI routers and CLI commands; kept thin.
- `GlobalConfig` loads at startup from `config/config_global.yaml`.

## Entrypoints

- API factory: `graphregistry.entrypoints.api.main:create_app`
- CLI entrypoint: `graphregistry.entrypoints.cli.main:main` (script name: `graphregistry`)
- Key CLI domains: `data`, `es`, `airflow`, `cache`, `index`, `run`, `ai`, `setup`, `config`

## Ports

- `graphregistry/application/gateways/gtw_conceptdet.py`: `ConceptDetectionGateway`
- `graphregistry/application/gateways/gtw_translation.py`: `TextTranslationGateway`
- `graphregistry/application/gateways/gtw_video.py`, `gtw_voice.py`: video/voice processing ports used by lecture factories/operations.

## Read deeper (reference files in this folder)

| File | Read when |
|---|---|
| `reference/graphai-adapters.md` | working on the GraphAI gateway adapters in `graphregistry/adapters/gateways/graphai/` |
| `reference/models-wiring.md` | touching domain models used by adapters, dependency wiring, or adapter conventions |
