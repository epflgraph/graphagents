---
name: graphai
description: Understanding of the GraphAI service, its legacy client, and the hexagonal adapters in GraphRegistry.
---

# GraphAI

GraphAI is the EPFL Graph Data Platform's semantic-analysis service. GraphRegistry consumes it through a set of hexagonal gateway adapters. A local copy of the GraphAI service source lives in `resources/graphai_repo/`, and the legacy client package lives in `resources/graphai_client/`.

## What GraphAI provides

- Text processing: keyword extraction, Wikipedia concept search, concept detection (`/text/*`).
- Translation: text and list translation, language detection (`/translation/*`).
- Embeddings: text embedding with optional model selection (`/embedding/*`).
- Image/OCR: text extraction from slides/images, image fingerprinting (`/image/*`).
- Video processing: download from URL, video fingerprinting, audio extraction, slide detection (`/video/*`).
- Voice processing: audio fingerprinting, language detection, transcription (`/voice/*`).

## Service architecture

- FastAPI API + Celery workers (RabbitMQ broker, Redis result backend).
- Endpoints can be **synchronous** or **asynchronous**.
- Async pattern:
  1. `POST /{domain}/{action}` returns `{"task_id": "..."}`.
  2. Poll `GET /{domain}/{action}/status/{task_id}` until `task_status` is `SUCCESS` or `FAILURE`.
- Async status response contains `task_result` with metadata such as `successful`, `result`, `text_too_large`, `fresh`, `device`, `token`, `token_status`, `token_size`, `file_found`, `failure_reason`.
- Bearer-token authentication via `POST /token`.
- Configured in GraphRegistry through `config/config_graphai.json` (`graphai.client_config_file` in `GlobalConfig`).

## Legacy client (`resources/graphai_client/`)

- `client.py`: high-level video/audio/slide orchestration.
- `client_api/`: low-level per-domain callers.
  - `text.py`: concept/keyword detection.
  - `translation.py`: translation and text language detection.
  - `embedding.py`: text embedding.
  - `image.py`: OCR and image fingerprinting.
  - `video.py`: video download, fingerprint, audio extraction, slide detection.
  - `voice.py`: audio transcription, language detection, fingerprinting.
  - `utils.py`: login, async polling loop, shared list/text helpers.
- `utils.py`: subtitle helpers, MySQL helpers, Google API helpers.

The legacy client is procedural and mixes HTTP details with orchestration. It is being incrementally replaced by typed hexagonal adapters.

## Hexagonal adapters (`graphregistry/adapters/gateways/graphai/`)

- `agt_base.py`: `GraphAIBaseGateway`
  - Config resolution, lazy login, HTTP retry logic, async task submission/polling.
- `agt_conceptdet.py`: `GraphAIConceptDetectionGateway`
  - Port: `ConceptDetectionGateway`.
  - `wiki_search`, `detect_concepts`.
- `agt_translation.py`: `GraphAITextTranslationGateway`
  - Port: `TextTranslationGateway`.
  - `translate_text`, `translate_multilingual`, direct-pair routing, auto-chunking.
- `agt_embedding.py`: `GraphAIEmbeddingGateway`
  - `embed_text` for strings and lists; auto-chunking and weighted averaging.
- `agt_image.py`: `GraphAIImageGateway`
  - `extract_text_from_slide`, `calculate_fingerprint`.
- `agt_video.py`: `GraphAIVideoGateway`
  - `get_video`, `fingerprint`, `extract_audio`, `extract_slides`, `download_file`, plus async launch/result helpers.
- `agt_voice.py`: `GraphAIVoiceGateway`
  - `transcribe_audio`, `detect_language`, `fingerprint`.
- `types.py`: `GraphAIGateway`, `GraphAIGatewayDict` type aliases.

## Ports and domain models

- Application ports:
  - `graphregistry/application/gateways/gtw_conceptdet.py`: `ConceptDetectionGateway`
  - `graphregistry/application/gateways/gtw_translation.py`: `TextTranslationGateway`
  - `graphregistry/application/gateways/gtw_video.py`, `gtw_voice.py`: video/voice processing ports.
- Domain models:
  - `mdl_conceptmap.py`: `Concept`, `ScoredConcept`, `ScoredConceptList`
  - `mdl_text.py`: `MultilingualText`, `LanguageCode`, `LanguageCodeList`
  - `mdl_lecture.py`: `Video`, `Voice`, `Slide`, `SlideList`, `Transcript`, `TranscriptSegment`

## Wiring in GraphRegistry

- CLI dependency builders in `graphregistry/entrypoints/cli/dependencies.py` inject GraphAI gateways into `NodeOperations` and `LectureOperations`.
- API router `get_node_factory()` uses `GraphAIConceptDetectionGateway` for concept-aware node creation.
- CLI `main.py` still imports the legacy `graphai_client` package only for the `ai` domain.

## Key implementation conventions

- Keep `login_info` (auth payload) inside adapters; do not expose it to application or domain layers.
- Map GraphAI's token-based media model to domain entities (`Video`, `Voice`, `Slide`) in the adapter.
- Defensively parse task results; GraphAI may return dicts, lists, or JSON-stringified values.
- Provide `launch_only=True` variants for long-running async tasks when callers need to orchestrate many jobs.
- Preserve legacy graceful-degradation behavior: language fallback (English/French), text chunking on `text_too_large`, and list-shape reconstruction.
- Gateways are normal instantiable objects; tests can inject `login_info` to bypass real authentication.
