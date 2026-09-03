---
name: graphai
description: GraphAI service, its legacy client, and queuing-style API patterns.
---

# GraphAI

GraphAI is the EPFL Graph Data Platform's semantic-analysis service. A local copy of the service source lives in `resources/graphai_repo/`, and the legacy client package lives in `resources/graphai_client/`.

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

## Domains and representative endpoints

- `text`: `/text/keywords`, `/text/wiki_search`, `/text/wikify`
- `translation`: `/translation/translate`, `/translation/detect_language`, `/translation/calculate_fingerprint`
- `embedding`: `/embedding/embed`, `/embedding/calculate_fingerprint`
- `image`: `/image/extract_text`, `/image/calculate_fingerprint`, `/image/retrieve_url`, `/image/upload_file`
- `video`: `/video/retrieve_url`, `/video/calculate_fingerprint`, `/video/extract_audio`, `/video/detect_slides`, `/video/get_file`
- `voice`: `/voice/transcribe`, `/voice/detect_language`, `/voice/calculate_fingerprint`

## Task-result semantics

- `task_status`: `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`.
- `successful=False` + `text_too_large=True` means the caller should split the input and retry.
- `file_found=False` means the source media file is missing on GraphAI.
- `/video/retrieve_url` may return a non-empty `failure_reason` for download failures.
- Batch endpoints may return a list of per-item dicts instead of a single dict.

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

The legacy client is procedural and mixes HTTP details with orchestration. It is being incrementally replaced by typed hexagonal adapters inside GraphRegistry.

## Queuing / API conventions

- Provide `launch_only=True` variants for long-running async tasks when callers need to orchestrate many jobs.
- Use persistent HTTP sessions across submit → status polling to reduce TLS overhead.
- Back off exponentially when polling status; cap the sleep interval and respect a total deadline.
- Retry transient HTTP errors (`408/425/429/5xx`) and refresh the bearer token on `401`.
- Defensively parse task results; GraphAI may return dicts, lists, or JSON-stringified values.
- Keep `login_info` (auth payload) inside client/adapter code; do not expose it to caller business logic.
- Preserve legacy graceful-degradation behavior at the client level: language fallback (English/French), text chunking on `text_too_large`, and list-shape reconstruction.
