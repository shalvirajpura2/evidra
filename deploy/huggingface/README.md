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
  - Systran/faster-whisper-small
  - Systran/faster-whisper-medium
  - Helsinki-NLP/opus-mt-hi-en
  - facebook/nllb-200-distilled-600M
---

# Evidra

**Turn your documents into a voice assistant.**

Choose **Try the sample**, click **Start talking**, and ask: “How many days of paid leave do I get?” Hear the reply and inspect the source beside it. You can upload a searchable PDF, text file, or Markdown document up to 5 MB.

Choose **हिन्दी · Hindi** to ask and hear replies in Hindi. The demo uses English documents; Hindi questions are translated for document search. Hindi is an early demo and needs human verification. Voice is turn-taking, with interruptible playback.

## Built with open models

Qwen2.5-1.5B-Instruct answers on ZeroGPU. Whisper small transcribes English and medium transcribes Hindi. Marian translates questions; NLLB translates cited replies and Piper generates English and Hindi audio on CPU. No paid inference API is used.

Each browser gets a separate temporary workspace. Use non-sensitive files; records can disappear on restart. Raw recordings are deleted after transcription. The Northstar handbook and Aster evaluation reference are fictional.

Free hosting has daily quotas and shared queues. Open this canonical Space page and sign in for your account's quota. The target is ten independent visitors with queued inference, not ten simultaneous real-time calls.

## Licenses

React, FastAPI and faster-whisper are MIT; Qwen weights are Apache-2.0; Piper's engine is GPL-3.0. Voices have separate notices. The Hindi Pratham voice's dataset is CC-BY-NC-SA-4.0, restricting commercial use. This is a noncommercial portfolio demonstration, not a commercially licensed voice service. Model weights are downloaded from their publishers and are excluded from the source bundle.
