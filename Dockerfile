FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libsndfile1 espeak-ng tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 app
WORKDIR /app
COPY requirements.lock.txt pyproject.toml ./
COPY backend/ backend/
RUN pip install --no-cache-dir -r requirements.lock.txt && pip install --no-cache-dir -e . --no-deps
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir faster-whisper==1.2.1 av==16.1.0 piper-tts==1.8.0 transformers==4.57.6 huggingface-hub==0.36.2 sentencepiece==0.2.1
COPY --from=frontend /build/dist frontend/dist
RUN mkdir -p data/models data/hf-cache && chown -R app:app /app
USER app
ENV HF_HOME=/app/data/hf-cache EVIDRA_PUBLIC=1 EVIDRA_PROVIDER=transformers EVIDRA_MODEL=Qwen/Qwen2.5-1.5B-Instruct EVIDRA_STATIC_DIR=/app/frontend/dist EVIDRA_CPU_THREADS=2
RUN python -m piper.download_voices --data-dir data/models en_US-ljspeech-medium hi_IN-pratham-medium
RUN python -c "from evidra.models import model_pair; from evidra.voice import transcription_model; from evidra.languages import translation_pair; model_pair(); transcription_model(); transcription_model('hi'); translation_pair()"
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "evidra.api:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
