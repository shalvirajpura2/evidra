---
title: Evidra
emoji: 🌱
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: '6.30.0'
python_version: '3.12'
app_file: app.py
pinned: false
preload_from_hub:
  - Qwen/Qwen2.5-1.5B-Instruct
  - Systran/faster-whisper-base.en
---

# Evidra

An answer should come with something you can check.

Independent evidence-backed conversations, document versions, reviews, and reproducible evaluations. The original React interface is served with the Python API on one origin. Voice uses faster-whisper and Piper; conversational answers use Qwen2.5-1.5B-Instruct. No paid inference API is used.

Each browser has a separate temporary session. Do not upload sensitive documents. Raw recordings are removed after transcription; recognized text stays in that visitor's temporary conversation. The Aster sample is fictional. This is a portfolio engineering demo, not a medical product.

Start voice, allow the microphone, speak, and pause. You can end voice at any time or interrupt playback to speak again. English recognition and CPU turn-taking have noticeable latency. Free hosting may sleep or clear records.

Upstream components retain their licenses: React/FastAPI/faster-whisper (MIT), Qwen2.5 weights (Apache-2.0), and Piper engine (GPL-3.0). The ljspeech voice has its own model card and dataset notice. Model assets are downloaded from their public publishers and are not included in the source archive.
