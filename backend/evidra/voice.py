import io
import tempfile
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def transcription_model():
    from faster_whisper import WhisperModel

    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe(content):
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as file:
        file.write(content)
        name = file.name
    try:
        segments, _ = transcription_model().transcribe(name)
        return " ".join(segment.text.strip() for segment in segments)
    finally:
        Path(name).unlink(missing_ok=True)


@lru_cache(maxsize=1)
def speech_model():
    from kokoro import KPipeline

    return KPipeline(lang_code="a")


def speak(text):
    import numpy as np
    import soundfile as sf

    audio = [item[2] for item in speech_model()(text, voice="af_heart")]
    buffer = io.BytesIO()
    sf.write(buffer, np.concatenate(audio), 24000, format="WAV")
    return buffer.getvalue()
