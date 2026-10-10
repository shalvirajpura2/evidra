# Public demo deployment

The Docker image serves React and FastAPI from the same origin on port 7860. It includes CPU-only Qwen2.5-1.5B-Instruct, faster-whisper base.en, and Piper ljspeech-medium. Model downloads happen during image building; no paid inference API key is used.

## Visitor boundaries

`EVIDRA_PUBLIC=1` enables signed, 24-hour visitor tokens. Each browser receives a separate SQLite database. All document, conversation, review, evaluation, and speech routes require the token. Tokens are held in browser local storage; they are never embedded in URLs. A separate token cannot read another visitor's records, even with a known turn or document ID. A server-generated secret changes on restart unless `EVIDRA_SESSION_SECRET` is configured as a host secret.

The demo bounds storage to 128 visitor databases, ten imported reference versions, 100 questions, and three evaluation runs per session. Mutations are limited to 20 per minute per session; session creation is limited per peer address. These are demo controls, not a complete defense against distributed abuse. Model generation is serialized. Evaluation requests may encounter a busy model, which remains visible as a review result rather than a fabricated answer.

Records are temporary. Space disk is ephemeral, and expired uncached visitor databases are removed after 24 hours. Never upload sensitive documents to this demonstration. The included Aster reference is fictional. Raw recordings are temporary files removed after transcription; recognized text is saved in the visitor's conversation.

## Voice behavior

Start voice requests browser microphone permission. Each recording stops after speech followed by 1.4 seconds of quiet, or at 25 seconds. It is transcribed, passed through the existing evidence pipeline, and spoken. The microphone reopens after playback. Send now bypasses silence waiting; End voice releases the microphone and stops playback. Interrupt & speak stops the current reply and listens for a new turn. Listening pauses while generating and speaking to prevent recording the app's own output.

This is a turn-taking voice conversation, not simultaneous full-duplex audio or token/audio streaming. CPU generation can take several seconds. Use headphones in a quiet room. Current speech recognition is English.

## Hugging Face Spaces

The account's creation screen currently marks Docker as paid and offers Gradio/ZeroGPU as its free tier. The staging package uses that Python SDK, serves the existing React interface and API on port 7860, and runs its small models on CPU without requesting GPU time. `deploy/huggingface/` contains the entry point, metadata and dependencies. After building the frontend, `python scripts/package_space.py` produces an allowlisted archive for upload alongside those files. The Dockerfile is an alternative for a host supporting Docker; it is not the free account's chosen deployment.

A public Space exposes uploaded source; keep it private until that disclosure is approved. The GitHub repository can remain private. Free Spaces can sleep and may cold-start; availability and model performance are not guaranteed.

Before public launch verify two independent visitor tokens, upload isolation, audio upload/transcription, model answers, speech bytes, and the browser controls. Free hosting is suitable for a small portfolio demo. For persistent accounts and higher traffic, add durable storage, identity, a job queue, operational monitoring, and dedicated compute.
