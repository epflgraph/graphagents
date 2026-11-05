# GraphRegistry — domain models, wiring & adapter conventions

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
