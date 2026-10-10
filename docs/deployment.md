# Public demo deployment

Live demo: [Evidra on Hugging Face](https://huggingface.co/spaces/rshalvi/evidra). Published on October 10, 2026 after approval to expose the demo and uploaded source. The GitHub repository remains private. An unauthenticated launch check confirmed public visibility, RUNNING status, and healthy, ready models on ZeroGPU. Use the canonical Space page for the visitor's Hugging Face quota.

The Docker image serves React and FastAPI from the same origin on port 7860. It includes CPU-only Qwen2.5-1.5B-Instruct, faster-whisper small for English and medium for Hindi, and Piper English and Hindi voices. Model downloads happen during image building; no paid inference API key is used.

## Visitor boundaries

`EVIDRA_PUBLIC=1` enables signed, 24-hour visitor tokens. Each browser receives a separate SQLite database. All document, conversation, review, evaluation, and speech routes require the token. Tokens are held in browser local storage; they are never embedded in URLs. A separate token cannot read another visitor's records, even with a known turn or document ID. A server-generated secret changes on restart unless `EVIDRA_SESSION_SECRET` is configured as a host secret.

The demo bounds storage to 128 visitor databases, ten imported reference versions, 100 questions, and three evaluation runs per session. Mutations are limited to 20 per minute per session; session creation is limited per peer address. These are demo controls, not a complete defense against distributed abuse. Model generation is serialized. Evaluation requests may encounter a busy model, which remains visible as a review result rather than a fabricated answer.

Records are temporary. Space disk is ephemeral, and expired uncached visitor databases are removed after 24 hours. Never upload sensitive documents to this demonstration. The included Aster reference is fictional. Raw recordings are temporary files removed after transcription; recognized text is saved in the visitor's conversation.

## Voice behavior

Start voice requests browser microphone permission. Each recording stops after speech followed by 1.4 seconds of quiet, or at 25 seconds. It is transcribed, passed through the existing evidence pipeline, and spoken. The microphone reopens after playback. Send now bypasses silence waiting; End voice releases the microphone and stops playback. Interrupt & speak stops the current reply and listens for a new turn. Listening pauses while generating and speaking to prevent recording the app's own output.

This is a turn-taking voice conversation, not simultaneous full-duplex audio or token/audio streaming. CPU generation can take several seconds. Use headphones in a quiet room. Speech recognition supports English and Hindi. Hindi questions are translated into English inside the GPU job before retrieval; the original question and translated search text are retained. Hindi answers are requested in Devanagari and Piper selects the language stored with the turn. This version targets English documents.

## Hugging Face Spaces

The account's creation screen currently marks Docker as paid and offers Gradio/ZeroGPU as its free tier. The first private staging package stopped with `No @spaces.GPU function detected during startup`. The adapter now registers real question and evaluation GPU handlers in Gradio, mounted at `/compute` before React's static route. The official Gradio JavaScript client submits those operations from the existing interface. Other document, review, and speech endpoints remain in FastAPI. Direct HTTP question and evaluation endpoints are disabled in ZeroGPU mode.

Hugging Face's current documentation requires a paid plan to create ordinary compute Spaces, while eligible free accounts can create two Gradio ZeroGPU Spaces. The question handler requests up to 45 seconds for English or 90 seconds for Hindi translation plus answering; evaluation requests up to 90 seconds. Both share one model concurrency slot and a 16-job queue. Visitors are subject to Hugging Face's GPU quotas and queue availability; quota failures must be reported, never silently replaced with another provider. No paid plan or compute purchase has been authorized.

The queued handler verifies the signed visitor token again, validates the payload, and reopens only that visitor's already-created SQLite database with a fresh engine. It never inherits a pooled database connection into a GPU worker. It resets database and GPU contexts after each call. Tokens travel as queue inputs, never in URLs. Session isolation and direct-endpoint rejection have regression tests. Model weights are loaded onto emulated CUDA at module startup as required by ZeroGPU, then used on the allocated GPU inside the decorated handlers. CPU mode remains available locally.

`deploy/huggingface/` contains the entry point, metadata and dependencies. After building the frontend, `python scripts/package_space.py` produces an allowlisted archive for upload alongside those files. The Dockerfile is prepared for a host supporting Docker. Hosted dependency resolution and model inference succeeded with PyTorch 2.13.0, Transformers 5.19.0 and Hub 2.2.0. The standard Gradio launch reports registered GPU handlers before the same queue is mounted under FastAPI; its separate listener remains on loopback. Model weights are preloaded during the Space build.

Share the canonical `https://huggingface.co/spaces/rshalvi/evidra` page. The official JavaScript client uses Hugging Face's browser handshake inside that page to apply the signed-in visitor's quota. A direct `hf.space` tab uses anonymous API quota and reached its run limit during staging. The canonical signed-in view successfully ran further questions and the full evaluation without a copied user token or shared creator token. The application displays a link back to that page. Free quota remains finite; this is not unlimited public inference.

A public Space exposes uploaded source; that disclosure was approved for this demo. The GitHub repository remains private. Free Spaces can sleep and may cold-start; availability and model performance are not guaranteed.

Before public launch verify two independent visitor tokens, upload isolation, audio upload/transcription, model answers, speech bytes, and the browser controls. Free hosting is suitable for a small portfolio demo. For persistent accounts and higher traffic, add durable storage, identity, a job queue, operational monitoring, and dedicated compute.
