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

## High-level architecture

- Hexagonal-ish layout:
  - `graphregistry/domain/models/` — business entities and value objects.
  - `graphregistry/application/operations/` — use cases / application services.
  - `graphregistry/application/gateways/` — ports for external capabilities (persistence, AI, search, etc.).
  - `graphregistry/adapters/` — concrete implementations of ports (MySQL repositories, GraphAI gateways, Elasticsearch clients, etc.).
  - `graphregistry/entrypoints/` — FastAPI routers and CLI commands; kept thin.
- Dependencies point inward: entrypoints and adapters depend on application and domain layers, not the reverse.
- `GlobalConfig` loads at startup from `config/config_global.yaml`.

## Entrypoints

- API factory: `graphregistry.entrypoints.api.main:create_app`
- CLI entrypoint: `graphregistry.entrypoints.cli.main:main` (script name: `graphregistry`)
- Key CLI domains: `data`, `es`, `airflow`, `cache`, `index`, `run`, `ai`, `setup`, `config`

## Ports

- `graphregistry/application/gateways/gtw_conceptdet.py`: `ConceptDetectionGateway`
- `graphregistry/application/gateways/gtw_translation.py`: `TextTranslationGateway`
- `graphregistry/application/gateways/gtw_video.py`, `gtw_voice.py`: video/voice processing ports used by lecture factories/operations.

## GraphAI adapters (`graphregistry/adapters/gateways/graphai/`)

GraphRegistry consumes GraphAI through hexagonal gateway adapters.

- `agt_base.py`: `GraphAIBaseGateway`
  - Loads config from `GlobalConfig().settings["graphai"]["client_config_file"]` or an explicit `graph_api_json` path.
  - Lazy login via `_ensure_login_info()`; stores `login_info` dict with bearer token.
  - `_request(...)`: low-level HTTP helper with exponential backoff, retry on `408/425/429/5xx`, automatic token refresh on `401`.
  - `_call_async_endpoint(...)`: submit + poll until completion; returns `task_result` dict or task id string when `launch_only=True`.
  - `get_async_task_result(...)`: poll an existing task id; supports one-shot (`wait_for_result=False`) or blocking mode.
- `agt_conceptdet.py`: `GraphAIConceptDetectionGateway(GraphAIBaseGateway, ConceptDetectionGateway)`
  - `wiki_search(search_term: str) -> list[dict]` calls `POST /text/wiki_search`.
  - `detect_concepts(text: str | list[str]) -> ScoredConceptList` calls `POST /text/wikify`.
  - Maps response items to `ScoredConcept(concept=Concept(id, name), score=...)` using `mixed_score` or `score`.
- `agt_translation.py`: `GraphAITextTranslationGateway(GraphAIBaseGateway, TextTranslationGateway)`
  - Implements `TextTranslationGateway` port (`translate_text`, `translate_multilingual`).
  - Direct translation pairs: `(fr,en)`, `(en,fr)`, `(de,en)`, `(en,de)`, `(it,en)`, `(en,it)`; routes everything else through English.
  - Same-language and empty-text short-circuits.
  - Auto-splits text that GraphAI rejects as `text_too_large`.
  - Cleans `None`/empty items from lists and reconstructs original list shape after translation.
- `agt_embedding.py`: `GraphAIEmbeddingGateway(GraphAIBaseGateway)`
  - `embed_text` dispatches to `embed_text_str` or `embed_text_list`.
  - Splits long strings on `\n`, `.`, `;`, `,`, ` `, `$`; averages chunk embeddings weighted by length.
  - Handles `text_too_large` by reducing `max_text_length`.
  - Parses embedding payloads that are raw lists or JSON strings.
- `agt_image.py`: `GraphAIImageGateway(GraphAIBaseGateway)`
  - `extract_text_from_slide(slide_token, ...)` calls `/image/extract_text`.
  - Prefers `ocr_google_1_token` / `ocr_google_1_results` method results.
  - `calculate_fingerprint(slide_token, ...)` calls `/image/calculate_fingerprint`.
- `agt_video.py`: `GraphAIVideoGateway(GraphAIBaseGateway)`
  - `get_video(file_url)` -> `Video` domain object with token, stream metadata, fingerprint.
  - `fingerprint(input)` -> video fingerprint string.
  - `extract_audio(input)` -> `Voice` object.
  - `extract_slides(input)` -> `SlideList`.
  - `download_file(token, file_path)` -> downloads bytes via `POST /video/get_file`.
  - Also exposes launch/get-result pairs for async orchestration.
- `agt_voice.py`: `GraphAIVoiceGateway(GraphAIBaseGateway)`
  - `transcribe_audio(input)` -> `Transcript` with `TranscriptSegment`s.
  - `detect_language(audio_token)` -> language code string.
  - `fingerprint(input)` -> audio fingerprint string.
- `types.py`: type aliases `GraphAIGateway` and `GraphAIGatewayDict`.

## Domain models used by adapters

- `graphregistry/domain/models/entities/mdl_conceptmap.py`: `Concept`, `ScoredConcept`, `ScoredConceptList`
- `graphregistry/domain/models/entities/mdl_text.py`: `MultilingualText`, `LanguageCode`, `LanguageCodeList`
- `graphregistry/domain/models/entities/mdl_lecture.py`: `Video`, `Voice`, `Slide`, `SlideList`, `Transcript`, `TranscriptSegment`
- `graphregistry/domain/models/tasks/mdl_conceptdet.py`: `ConceptDetectionTask`
- `graphregistry/domain/models/tasks/mdl_translation.py`: `TranslationTask`

## Wiring

- CLI dependency builders in `graphregistry/entrypoints/cli/dependencies.py`:
  - `build_node_operations(..., concept_detection_gateway=None)`
  - `build_lecture_operations(include_video_gateway=True, include_concept_gateway=True, ...)` wires `GraphAIVideoGateway` and `GraphAIConceptDetectionGateway`.
  - `build_node_operations_with_concept_detection_from_args` uses `GraphAIConceptDetectionGateway()`.
- API router (`graphregistry/entrypoints/api/router.py`):
  - `get_node_factory()` instantiates `GraphAIConceptDetectionGateway(debug=True)` for the `NodeFactory`.
- CLI main (`graphregistry/entrypoints/cli/main.py`):
  - For the `ai` domain, imports the legacy `graphai_client` package and calls `GraphAIClient.login(...)` to obtain an auth token; stores it in `CLIContext.graphai_auth_token`.
  - This legacy path still exists for the `ai` CLI commands; the hexagonal adapters manage their own login.

## Adapter conventions

- Do not leak `login_info` dicts into domain/application logic. Auth is an adapter-internal concern managed by `GraphAIBaseGateway`.
- Map GraphAI's token-based media model to domain entities (`Video`, `Voice`, `Slide`) inside the adapter.
- Preserve legacy graceful-degradation behavior in adapters: language fallback (English/French), text chunking on `text_too_large`, and list-shape reconstruction.
- Gateways are normal instantiable objects; tests can inject `login_info` to skip real auth.
- Provide `launch_only=True` variants for long-running async tasks when callers need to orchestrate many jobs.
