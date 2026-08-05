import asyncio
import os
import tempfile
from typing import Any, Optional

from app.config import get_settings


_whisper_model: Optional[Any] = None
_whisper_model_size: Optional[str] = None


class SpeechToTextError(RuntimeError):
    """Raised when local faster-whisper cannot transcribe audio."""


def _suffix_for_mime_type(mime_type: str) -> str:
    if "webm" in mime_type:
        return ".webm"
    if "mpeg" in mime_type or "mp3" in mime_type:
        return ".mp3"
    if "wav" in mime_type:
        return ".wav"
    return ".audio"


def load_whisper_model() -> Any:
    global _whisper_model, _whisper_model_size

    settings = get_settings()
    if _whisper_model is not None and _whisper_model_size == settings.whisper_model_size:
        return _whisper_model

    from faster_whisper import WhisperModel

    _whisper_model = WhisperModel(
        settings.whisper_model_size,
        device="cpu",
        compute_type="int8",
    )
    _whisper_model_size = settings.whisper_model_size
    return _whisper_model


def _transcribe_local_sync(audio_bytes: bytes, mime_type: str) -> str:
    suffix = _suffix_for_mime_type(mime_type)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as audio_file:
        audio_file.write(audio_bytes)
        audio_path = audio_file.name

    try:
        segments, _info = load_whisper_model().transcribe(audio_path)
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    except Exception as exc:
        raise SpeechToTextError(f"Local faster-whisper transcription failed: {exc}") from exc
    finally:
        os.unlink(audio_path)


async def transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    return await asyncio.to_thread(_transcribe_local_sync, audio_bytes, mime_type)
