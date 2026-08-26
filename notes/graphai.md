# GraphAI Integration Notes

Date: 2026-06-19

## Overview

GraphAI is the EPFL Graph Data Platform's semantic-analysis service. GraphRegistry consumes GraphAI for text understanding, translation, embeddings, OCR, and video/audio processing. This note documents the service layout, the legacy client, the new hexagonal adapters, and how they are wired into GraphRegistry.

## Sources of truth

- GraphAI service source copy: `resources/graphai_repo/`
- Legacy Python client: `resources/graphai_client/`
- New hexagonal adapters: `graphregistry/adapters/gateways/graphai/`
- Application ports: `graphregistry/application/gateways/gtw_*.py`
- Dependency wiring: `graphregistry/entrypoints/cli/dependencies.py`

## GraphAI service

- FastAPI + Celery (RabbitMQ/Redis). Local copy version `0.14.1`.
- Runs by default on port `28800`.
- Bearer-token auth via `POST /token`.
- Two endpoint styles: synchronous and asynchronous.
- Async pattern:
  1. Submit job: `POST /{domain}/{action}` -> `{"task_id": "..."}`.
  2. Poll status: `GET /{domain}/{action}/status/{task_id}`.
  3. Status values: `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`.
- Task result payload keys to watch:
  - `successful`, `result`, `text_too_large`, `fresh`, `device`
  - `token`, `token_status`, `token_size` (for media jobs)
  - `file_found` (missing source file signal)
  - `failure_reason` (on `/video/retrieve_url`)

### Endpoints consumed by GraphRegistry

| Domain | Endpoint | Purpose |
|--------|----------|---------|
| text | `/text/wiki_search` | Search Wikipedia concept index |
| text | `/text/wikify` | Concept detection from text or keywords |
| translation | `/translation/translate` | Translate text or list of texts |
| translation | `/translation/detect_language` | Detect language of text |
| embedding | `/embedding/embed` | Text embedding |
| image | `/image/extract_text` | OCR on slide/image token |
| image | `/image/calculate_fingerprint` | Image fingerprint |
| video | `/video/retrieve_url` | Download video from URL |
| video | `/video/calculate_fingerprint` | Video fingerprint |
| video | `/video/extract_audio` | Extract audio token |
| video | `/video/detect_slides` | Slide detection |
| video | `/video/get_file` | Download file bytes by token |
| voice | `/voice/transcribe` | Audio transcription |
| voice | `/voice/detect_language` | Detect spoken language |
| voice | `/voice/calculate_fingerprint` | Audio fingerprint |

## Legacy client (`resources/graphai_client/`)

The legacy client is a procedural wrapper around the GraphAI REST API.

- `client.py`: high-level orchestration (`process_video`, `process_slides`, `process_audio`).
- `client_api/text.py`: `extract_concepts_from_text`, `extract_keywords_from_text`, `extract_concepts_from_keywords`.
- `client_api/translation.py`: `translate_text`, `translate_text_str`, `translate_text_list`, `detect_language`.
- `client_api/embedding.py`: `embed_text`, `embed_text_str`, `embed_text_list`.
- `client_api/image.py`: `extract_text_from_slide`, `calculate_fingerprint`.
- `client_api/video.py`: `get_video_token`, `fingerprint_video`, `extract_audio`, `extract_slides`, `download_file`.
- `client_api/voice.py`: `transcribe_audio`, `detect_language`, `calculate_fingerprint`.
- `client_api/utils.py`: `login`, `call_async_endpoint` (polling loop), text-list helpers.
- `utils.py`: subtitle utilities, MySQL helpers, Google API helpers.

Status: being refactored into hexagonal adapters. New code should prefer the adapters; legacy code remains for the `ai` CLI domain and older scripts.

## Hexagonal adapters (`graphregistry/adapters/gateways/graphai/`)

### Base gateway (`agt_base.py`)

`GraphAIBaseGateway` centralizes concerns every adapter needs:

- Resolves config path from `GlobalConfig().settings["graphai"]["client_config_file"]` or an explicit `graph_api_json`.
- Lazy login and token refresh.
- HTTP retry with exponential backoff and jitter.
- A persistent `requests.Session` so that TCP/TLS connections are reused across the submit → status polling pattern (significantly reduces per-call latency after the first request).
- Async submission + polling (`_call_async_endpoint`, `get_async_task_result`).
- Optional `launch_only=True` mode to return a task id instead of blocking.
- `close()` and context-manager support to release the underlying session.

### Concept detection (`agt_conceptdet.py`)

`GraphAIConceptDetectionGateway` implements `ConceptDetectionGateway`.

- `wiki_search(search_term)` -> list of Wikipedia concept dicts.
- `detect_concepts(text)` / `detect_concepts(keywords)` -> `ScoredConceptList`.
- Maps response fields `concept_id`, `concept_name`, `mixed_score`/`score` to `ScoredConcept`.
- `extract_keywords(text, use_nltk=False)` calls `POST /text/keywords` and returns a list of keyword strings.

### Translation (`agt_translation.py`)

`GraphAITextTranslationGateway` implements `TextTranslationGateway`.

- `translate_text(text, source, target) -> str`
- `translate_multilingual(text, source, targets) -> MultilingualText`
- Direct pairs: `fr<->en`, `de<->en`, `it<->en`; everything else routes through English.
- Same-language and empty-text short-circuits.
- Auto-chunks on `text_too_large` and preserves original list shape.

### Embedding (`agt_embedding.py`)

`GraphAIEmbeddingGateway`:

- `embed_text` handles both strings and lists.
- Splits long text on punctuation/spaces, averages chunk embeddings weighted by length.
- Handles `text_too_large` by reducing chunk size.

### Image (`agt_image.py`)

`GraphAIImageGateway`:

- `extract_text_from_slide(slide_token, ocr_model="google", ...)` -> `{"text": ..., "language": ...}`.
- Prefers `ocr_google_1_token` / `ocr_google_1_results` results.
- `calculate_fingerprint(slide_token)` -> fingerprint string.

### Video (`agt_video.py`)

`GraphAIVideoGateway`:

- `get_video(file_url)` -> `Video` domain object.
- `fingerprint(input)` -> video fingerprint.
- `extract_audio(input)` -> `Voice` object.
- `extract_slides(input)` -> `SlideList`.
- `download_file(token, file_path)` -> saves bytes.
- Also exposes launch/result helpers for async orchestration.

### Voice (`agt_voice.py`)

`GraphAIVoiceGateway`:

- `transcribe_audio(input)` -> `Transcript` with segments.
- `detect_language(audio_token)` -> language code.
- `fingerprint(input)` -> audio fingerprint.

## Application ports

- `graphregistry/application/gateways/gtw_conceptdet.py`: `ConceptDetectionGateway`
- `graphregistry/application/gateways/gtw_translation.py`: `TextTranslationGateway`
- `graphregistry/application/gateways/gtw_video.py`, `gtw_voice.py`: lecture processing ports

Domain models:

- `graphregistry/domain/models/entities/mdl_conceptmap.py`: `Concept`, `ScoredConcept`, `ScoredConceptList`
- `graphregistry/domain/models/entities/mdl_text.py`: `MultilingualText`, `LanguageCode`, `LanguageCodeList`
- `graphregistry/domain/models/entities/mdl_lecture.py`: `Video`, `Voice`, `Slide`, `SlideList`, `Transcript`, `TranscriptSegment`
- Task models: `mdl_conceptdet.py` (`ConceptDetectionTask`), `mdl_translation.py` (`TranslationTask`)

## Wiring in GraphRegistry

- `graphregistry/entrypoints/cli/dependencies.py`:
  - `build_lecture_operations(...)` wires `GraphAIVideoGateway` and `GraphAIConceptDetectionGateway` into `LectureOperations`.
  - `build_node_operations_with_concept_detection_from_args(...)` wires `GraphAIConceptDetectionGateway` into `NodeOperations`.
- `graphregistry/entrypoints/api/router.py`:
  - `get_node_factory()` uses `GraphAIConceptDetectionGateway(debug=True)` for concept-aware node creation.
- `graphregistry/entrypoints/cli/main.py`:
  - For the `ai` domain, still imports legacy `graphai_client` and logs in to obtain `graphai_auth_token` stored in `CLIContext`.

## Configuration

- Active config: `config/config_graphai.json` (gitignored).
- Template: `config/config_graphai.template.json` (committed).
- `GlobalConfig().settings["graphai"]["client_config_file"]` points to the active file.

## Common pitfalls

- **Token-based media model**: GraphAI returns opaque tokens for cached files. Adapters must map these to domain entities and handle missing `token_status`/`file_found=False` gracefully.
- **Async polling durations**: video/slide tasks can take up to 6000s. Use `launch_only=True` and orchestrate when processing many videos.
- **Result shape variance**: embeddings may be JSON strings; batch endpoints may return lists of dicts; always validate before mapping.
- **Language fallback**: legacy client forces English/French on detection/transcription failure. New adapters should preserve equivalent graceful degradation.
- **Text chunking**: translation and embedding adapters split long inputs and recombine outputs. Keep split-to-original index mappings correct.
- **Auth is an adapter concern**: `login_info` should not leak into application or domain layers.

## Recent changes

### 2026-06-19 — Token-status recovery for video/audio/slide adapters

- Added `GraphAIBaseGateway._requires_media_retry()` to detect missing/inactive cached files from `token_status`.
- `GraphAIVideoGateway.get_video()` now retries with `force=True` when a cached download is inactive/missing.
- `GraphAIVideoGateway.extract_audio()` and `extract_slides()` now retry with `recalculate_cached=True` when cached derived media is inactive/missing.
- Raises `RuntimeError` if the file is still missing on a fresh or forced result, matching the legacy client.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_token_status_recovery.py`.

### 2026-06-19 — Concept detection parameters and keyword path

- Restored all parameters in `ConceptDetectionTask.get_params_dict()`.
- Added `ConceptDetectionTask.get_url_safe_params_dict()` for lowercase boolean query values.
- `GraphAIConceptDetectionGateway.detect_concepts()` now uses the same parameters for both text and keyword inputs.
- Added `GraphAIConceptDetectionGateway.detect_concepts_with_task()` for fully configured tasks.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_concept_detection.py`.

### 2026-06-19 — Translation list batching and text_too_large handling

- `GraphAITextTranslationGateway._translate_list()` now splits long lists by total character length (`max_text_list_length`).
- Added `translate_text_list()` public method on the concrete adapter.
- Added `max_text_length` parameter to `translate_text()`.
- Both string and list paths retry with reduced `max_text_length` when GraphAI reports `text_too_large`.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_translation_batching.py`.

### 2026-06-19 — Embedding list batching and L2-normalized recombination

- `GraphAIEmbeddingGateway.embed_text_list()` now processes lists in total-length batches (`max_text_list_length`).
- Long items are split into chunks, batched, and recombined into one embedding per original item.
- Recombined embeddings are L2-normalized, matching the legacy client's behavior.
- Per-batch `text_too_large` now retries with a reduced `max_text_length`.
- Added helpers `_embed_batch()` and `_recombine_embeddings()`; updated `_weighted_average_embeddings()` to L2-normalize.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_embedding_batching.py`.

### 2026-06-19 — Audio transcription fallback and subtitle translation

- `GraphAIVoiceGateway.transcribe_audio()` now detects language when `force_lang` is not provided.
- Detected languages outside `{en, fr, de, it}` are discarded, matching the legacy client's filtering.
- Empty transcriptions fall back to English, then French.
- Added `destination_languages` and `translation_gateway` parameters for subtitle translation.
- Added `translations` field to `TranscriptSegment` to store per-language segment text.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_transcription_fallback.py`.

### 2026-06-19 — Slide processing orchestration

- Added `GraphAIVideoGateway.process_slides()` mirroring the legacy `process_slides` flow.
- Extracts slides, fingerprints each slide, runs OCR, detects dominant language, filters unsupported languages, falls back to English, and translates text to destination languages.
- Added optional `image_gateway` injection to `GraphAIVideoGateway` (lazy fallback creates one).
- Extended `Slide` domain model with `text`, `language`, and `translations` fields.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_slide_processing.py`.

### 2026-06-19 — Application ports and explicit gateway wiring

- Completed `VideoProcessingGateway` and `VoiceProcessingGateway` protocols with all methods used by operations.
- Added `ImageProcessingGateway` and `TextEmbeddingGateway` protocols.
- Updated `AIGateways` registry to include all gateway types.
- Replaced the untyped `ai_gateways: dict[str, Any]` parameter in `NodeOperations` and `LectureOperations` with explicit, typed gateway parameters:
  - `NodeOperations(concept_detection_gateway=...)`
  - `LectureOperations(video_processing_gateway=..., concept_detection_gateway=..., lecture_enrichment_gateway=...)`
- Updated CLI dependency builders and the `t_conceptdet_nf.py` script to use the new signatures.
- Added `tests/unit_tests/application/test_ops_lecture.py` to verify explicit gateway wiring.

### 2026-06-19 — Type-check pass

- Added `Literal` overloads to `GraphAIBaseGateway._call_async_endpoint()` so `wait_for_result=True` returns `dict | None` and `False` returns `str | None`.
- Added runtime `assert isinstance(task_result, dict)` guards after `launch_only` branches to narrow types for pyright.
- Fixed list covariance issues with `cast(list[str | None], ...)` at internal call sites.
- Fixed `max(dict, key=dict.get)` overload ambiguity by using lambdas.
- Ran `npx pyright` on all changed modules: 0 errors, 0 warnings.
- All unit tests still pass.

### 2026-06-19 — Adapter examples

- Added `examples/adapters/graphai/` with one example per endpoint, grouped by domain:
  - `video/`, `voice/`, `image/`, `text/`, `translation/`, `embedding/`.
- Each example contains `example.py` and `run.sh`.
- Added `examples/adapters/graphai/README.md` with usage instructions and pipeline notes.
- Verified all examples compile and pass `npx pyright`.

### 2026-06-19 — Embedding list failure handling

- `GraphAIEmbeddingGateway._embed_batch()` now raises `RuntimeError` when GraphAI returns `None`, an invalid result shape, or a `text_too_large` response that cannot be split further.
- This matches the legacy `embed_text_list()` behavior and prevents silent lists of `None` embeddings.
- Added unit tests for failure modes in `tests/unit_tests/adapters/gateways/graphai/test_embedding_batching.py`.

### 2026-06-19 — Fast failure for unreachable GraphAI

- Added `submit_timeout` and `status_timeout` to the async GraphAI helpers so lightweight submit/status requests fail fast when the service is unreachable.
- Defaults were raised from 10s/5s to 30s/15s after observing that production GraphAI enqueue and result-backend lookups can legitimately take several seconds.
- Capped inner HTTP retries for submit/status calls at 2 to avoid multiplying wait times.
- Reduced default `max_tries` for `_call_async_endpoint`, `get_async_task_result`, and the embedding adapter methods from 5 to 2.
- Embedding examples pass `max_tries=1` so an unreachable service surfaces quickly instead of retrying for minutes; production callers can keep the higher defaults.

### 2026-06-19 — Smarter async polling loop

- Replaced fixed 1s sleep in `get_async_task_result()` with exponential backoff starting at 0.1s and capped at 2s.
- Fixed the deadline bug where each outer retry attempt reset the deadline, allowing `max_tries * max_processing_time_s` total wait.
- Outer retries now only happen on transient status-check exceptions, not on task-level SUCCESS/FAILURE.
- Added module-level login cache keyed by config path so multiple gateway instances in the same process reuse the bearer token.
- Added a 30s timeout to `_login()` so a slow/unreachable `/token` endpoint fails fast instead of using the 600s default.

### 2026-06-19 — File-based token cache

- Added `~/.cache/graphregistry/graphai_tokens.json` to persist GraphAI bearer tokens across process runs.
- `_ensure_login_info()` now loads from the file cache before calling `/token`.
- `_request()` updates both the in-memory and file caches after a 401 token refresh.
- Cache file is created with `0600` permissions.
- First example run still pays the slow `/token` cost, but subsequent runs reuse the cached token and are limited only by the embedding/status HTTP calls.

### 2026-06-19 — Persistent HTTP session for lower latency

- Added a lazy `requests.Session` to `GraphAIBaseGateway`, exposed via `_http_session`.
- Changed `_request()` from accepting a `request_func` callable (`get`/`post`) to accepting a `method: str` and dispatching through the shared session.
- Updated all callers in `agt_conceptdet.py`, `agt_video.py`, and `agt_base.py` to use `method="GET"` / `method="POST"`.
- Added `GraphAIBaseGateway.close()` and context-manager (`with`) support so callers can release connections explicitly.
- Fixed `GraphAITextTranslationGateway.__init__()` to call `super().__init__()` so the session is inherited correctly.
- Added unit tests: `tests/unit_tests/adapters/gateways/graphai/test_session_reuse.py`.
- Raised default `submit_timeout` from 10s to 30s and `status_timeout` from 5s to 15s to accommodate production GraphAI latency.
- Observed impact: session reuse removes repeated TLS handshakes; remaining latency is dominated by GraphAI server-side TTFB (see below).

### 2026-06-19 — GraphAI server-side TTFB diagnosis

- curl timing breakdown shows DNS/TCP/TLS are fast (< 0.05s); the delay is TTFB (1–9s).
- Even FastAPI auto-generated endpoints (`/openapi.json`) and the root redirect (`/`) show multi-second TTFB, pointing to a global bottleneck (middleware, instrumentation, or worker saturation) plus per-request rate-limiter overhead.
- `fastapi-user-limiter` creates a new Redis connection on every request; authenticated endpoints run through two limiters (global + per-endpoint), each doing Redis + a MySQL rate-limit override lookup.
- Created developer instructions for the GraphAI team: `docs/graphai_rate_limiter_fix.md`.
- Created a benchmark script to measure progress: `scripts/graphai_speed_test.sh`.

### 2026-06-19 — Batch endpoint result parsing

- Fixed `get_async_task_result()` to return `task_result` when it is a list of per-item dicts (used by `/embedding/embed` and `/translation/translate` for batch inputs). Previously it returned `None` for batch results.
- Updated `GraphAIEmbeddingGateway._embed_batch()` to parse both dict-style and list-style results, including per-item `successful`/`text_too_large` flags.
- Updated `GraphAITextTranslationGateway._translate_string()` and `_translate_list()` to handle list-style results.
- Verified `embed_text_list`, `embed_text_str`, `translate_text`, and `translate_multilingual` examples now return real embeddings/translations from GraphAI.

## Known gaps vs. legacy client

No known functional gaps remain in the GraphAI adapter surface relative to the legacy client. Remaining work is non-GraphAI-specific cleanup (e.g., removing the legacy `ai_gateways` TypedDict once all callers are migrated, broader pyright coverage).

## Related notes

- `.opencode/skills/graphai/SKILL.md`
- `.opencode/agents/graphai-specialist.md`
