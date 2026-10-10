import io
import os
import tempfile
import wave
from functools import lru_cache
from pathlib import Path
from threading import BoundedSemaphore

SPEECH_SLOTS = BoundedSemaphore(2)


class VoiceBusy(Exception):
    pass


@lru_cache(maxsize=1)
def transcription_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        os.getenv("EVIDRA_WHISPER_MODEL", "small"),
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        download_root="data/models/whisper",
    )


def transcribe(content, language="en"):
    if not SPEECH_SLOTS.acquire(timeout=30):
        raise VoiceBusy("Voice is busy. Please try again in a moment.")
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as file:
        file.write(content)
        name = file.name
    try:
        segments, info = transcription_model().transcribe(
            name, beam_size=1, language=language, vad_filter=True
        )
        if info.duration > 30:
            raise ValueError("Keep voice turns shorter than 30 seconds")
        return " ".join(segment.text.strip() for segment in segments)
    finally:
        Path(name).unlink(missing_ok=True)
        SPEECH_SLOTS.release()


@lru_cache(maxsize=2)
def speech_model(language="en"):
    from piper import PiperVoice

    return PiperVoice.load(
        os.getenv("EVIDRA_PIPER_HINDI_MODEL", "data/models/hi_IN-pratham-medium.onnx")
        if language == "hi"
        else os.getenv("EVIDRA_PIPER_MODEL", "data/models/en_US-ljspeech-medium.onnx")
    )


def speak(text, language="en"):
    if not SPEECH_SLOTS.acquire(timeout=30):
        raise VoiceBusy("Voice is busy. Please try again in a moment.")
    try:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            speech_model(language).synthesize_wav(text, wav_file)
        return buffer.getvalue()
    finally:
        SPEECH_SLOTS.release()
