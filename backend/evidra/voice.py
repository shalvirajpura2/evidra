import io
import os
import tempfile
import wave
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def transcription_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        os.getenv("EVIDRA_WHISPER_MODEL", "base.en"),
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        download_root="data/models/whisper",
    )


def transcribe(content):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as file:
        file.write(content)
        name = file.name
    try:
        segments, info = transcription_model().transcribe(
            name, beam_size=1, language="en"
        )
        if info.duration > 30:
            raise ValueError("Keep voice turns shorter than 30 seconds")
        return " ".join(segment.text.strip() for segment in segments)
    finally:
        Path(name).unlink(missing_ok=True)


@lru_cache(maxsize=1)
def speech_model():
    from piper import PiperVoice

    return PiperVoice.load(
        os.getenv("EVIDRA_PIPER_MODEL", "data/models/en_US-ljspeech-medium.onnx")
    )


def speak(text):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        speech_model().synthesize_wav(text, wav_file)
    return buffer.getvalue()
