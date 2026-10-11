# Running Evidra

Tested locally on Windows with Python 3.12 and Node 24. Use a recent Python installer if a virtual environment cannot locate the runtime. Keep both services bound to `127.0.0.1`.

## Repeatable setup

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
.venv\Scripts\python -m pip install -e . --no-deps
.venv\Scripts\python -m uvicorn evidra.api:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal, `cd frontend`, `npm ci`, then `npm run dev`. Open `http://127.0.0.1:5173`. Port 5173 is strict so the instructions do not silently point at the wrong app.

Python package versions are recorded in `requirements.lock.txt`; npm uses `package-lock.json`. Heavy optional packages and model artifacts are not included in the base lock.

## Local Ollama

Install Ollama from its official distribution, download `qwen3:8b`, and keep its service running. In the backend terminal set:

```powershell
$env:EVIDRA_PROVIDER = 'ollama'
$env:EVIDRA_MODEL = 'qwen3:8b'
$env:EVIDRA_OLLAMA_URL = 'http://127.0.0.1:11434'
```

Restart the API and reload the workspace. This mode requires actual model resources; base setup does not download model weights. An unavailable model produces a review result, not an invented answer.

## Optional speech

Install `.[voice]` in a compatible Python environment. The adapters now use Whisper small for English and medium for Hindi and Piper for speech. Download a voice with `python -m piper.download_voices --data-dir data/models en_US-ljspeech-medium hi_IN-pratham-medium`. First transcription downloads its recognition model. PyAV is limited to version 16 because version 19 broke the decoder API used by faster-whisper 1.2.1. A synthetic Piper question was successfully transcribed locally after this fix. Use Start voice for microphone turns, the headphones button for audio uploads, and Read aloud for saved answers. See deployment notes for voice behavior and public sessions.

## Current retrieval and parsing

Base local mode uses lexical retrieval without downloading models. To use the same CPU retrieval as hosting, install `pip install -e ".[embeddings]"`, set `EVIDRA_RETRIEVAL=hybrid`, and restart the API. E5 and cross-encoder ONNX weights download on first use into ignored `data/models/retrieval`. Upload builds a persisted embedding index; later questions reuse it. Transformers mode requires the separate chat dependencies and compatible PyTorch environment. The hosted answer model is Qwen3-4B-Instruct-2507; base local mode still returns excerpts.

PDF extraction retains page locators. Passages overlap to preserve boundary facts. Short-document overviews include all extracted passages up to an 8,800-character evidence budget; longer files use evenly spaced passages and report sampling. This is not OCR or exhaustive long-document summarization. Search scores are routing heuristics, not calibrated confidence probabilities.

## Verification

```powershell
.venv\Scripts\python -m pytest -q --basetemp=.pytest_tmp
.venv\Scripts\python -m black --check backend tests
cd frontend
npm run build
npx prettier --check src
```

The fixture suite initially surfaced a singular “dose” question that retrieved participant facts while missing the document's exclusion. That case became a regression test. The fix checks explicit missing-information statements across the selected document rather than only the three retrieved passages. It remains a heuristic, not a general medical policy engine.

## Persistence and access

Local records live in `data/evidra.db`, which is ignored by Git. PostgreSQL can be selected with `EVIDRA_DATABASE_URL` and the `postgres` extra; that deployment path has not been integration-tested. The default local workspace is unauthenticated. Public demo mode uses signed temporary sessions, separate visitor databases, and bounded requests; see deployment notes before exposing an instance.

The interface's fonts are loaded from Google Fonts, with system fallbacks. Document content is not sent with font requests. Original doodles live in the React source as SVG paths.

Hindi document conversations also need `.[chat]` and Transformers mode. The translation models download on first use. Set `EVIDRA_WHISPER_HINDI_MODEL` to a local model directory if needed. The base extractive mode supports English questions without model downloads.
