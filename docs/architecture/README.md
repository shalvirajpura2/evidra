# Evidra — code-backed architecture walkthrough

A document-grounded, turn-taking voice assistant. Upload a document, ask in English or Hindi, hear a reply and inspect its original source passages.

## Read the single flow diagram
Read the top row left to right: upload → extract text or OCR → split and index → visitor SQLite. Read the lower row left to right: speak/type → Whisper → document retrieval → Qwen and source checks → Piper → playback with sources. Blue dotted arrows connect retrieval and saved turns to the same visitor database. Hindi translation and current queue/streaming limits are described below the flow.

The canvas contains one SVG presentation board. Regenerate it with scripts/draw_architecture.py; the vector source is docs/architecture/evidra-flow.svg.

## Deployment represented
Current code: GitHub main at 0d1888f. Public HF Space: rshalvi/evidra. One Uvicorn app worker, Gradio compute queue, Transformers provider and hybrid retrieval. These boxes are modules/runtime scopes inside one deployment, not independently deployed microservices. The queue worker reopens the selected visitor database rather than inheriting SQLite pooled connections across GPU forks.

## Code map
- Host and queue: deploy/huggingface/app.py; backend/evidra/queued.py.
- Frontend orchestration: frontend/src/api.ts; Guided.tsx; VoiceConversation.tsx.
- Sessions and isolation: backend/evidra/public.py (HMAC token, 24h expiry, ContextVar DB scope, bounded sessions and mutation rate limits).
- Import and OCR: backend/evidra/api.py, documents.py, ocr.py.
- Search: backend/evidra/retrieval.py (multilingual E5 ONNX, cosine + BM25, RRF, MiniLM reranking).
- Overview and policy routing: backend/evidra/overview.py, pipeline.py.
- Generation and source validation: backend/evidra/models.py.
- Translation and audio: backend/evidra/languages.py, voice.py.
- Persistence and evaluation: backend/evidra/db.py, evaluations.py.

## Data model
Document has many Passage records. PassageEmbedding uses (passage_id, model) as its composite key; vectors are JSON in SQLite, not an external vector database. ExtractionReport is one-to-one with Document. Turn references Document and stores conversation_id plus result JSON. Review references one Turn; Run references Document for evaluation results. Each visitor uses data/visitors/{visitor}.db. Storage is temporary, not a durable production data layer.

## Latency and capacity — be precise
The frontend waits for a complete recording, transcript, answer and WAV before playback. There is no token/audio streaming. The GPU queue allows one model job and up to 16 queued jobs. Speech has two shared slots; translation, retrieval, OCR and PDF rendering have separate single-slot locks. The 45s English and 90s Hindi GPU durations are allowances, not observed latency. The displayed elapsed_ms starts after document/index preparation and excludes browser recording, ASR, GPU queue and TTS. Ten isolated visitor tests are not proof of ten simultaneous low-latency voice calls.

## Language behavior
Whisper small (EN) and medium (HI), CPU INT8; explicit language selection. Hindi questions are translated to English with NLLB-200-distilled-600M; Qwen generates a cited English answer, which is translated back to Hindi. Seamless Hinglish/code-switching has not been validated. Piper uses en_US-ljspeech-medium and hi_IN-pratham-medium voices.

## Model and safety boundaries
Qwen/Qwen3-4B-Instruct-2507 runs in FP16 on ZeroGPU. It selects numbered evidence snippets; the backend attaches original text and checks IDs, quote membership and numbers. Empty evidence or failed checks can abstain or withhold a draft for review. These checks do not prove semantic entailment. Scanned documents use Tesseract eng+hin, but perfect OCR, handwriting and complex tables are not guaranteed.

## Next engineering steps — proposed, not deployed
Instrument end-to-end stage timings and time-to-first-audio; evaluate Hinglish; benchmark unfamiliar-document answers. Test a paid API inference adapter behind the existing retrieval/validation contract to remove visitor HF GPU quotas. Then evaluate streaming and independent speech capacity. HF Inference Providers API, dedicated GPUs, Redis queues and external vector databases are not part of the deployed architecture.

Source repository: https://github.com/shalvirajpura2/evidra (private)
Demo: https://huggingface.co/spaces/rshalvi/evidra
