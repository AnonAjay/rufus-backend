import asyncio
import io
import logging
import wave
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator, Optional

from app.config import BASE_DIR, get_settings
from app.settings.voice_preferences import get_voice_preference

logger = logging.getLogger(__name__)

_current_session_id: ContextVar[Optional[str]] = ContextVar("tts_session_id", default=None)
_voice_cache: dict[str, object] = {}


class TextToSpeechError(RuntimeError):
    """Raised when local Piper cannot synthesize speech."""


def _resolve_piper_voice_path() -> Path:
    settings = get_settings()
    preferred_path = get_voice_preference(_current_session_id.get())
    configured_path = preferred_path or settings.piper_voice_path
    path = Path(configured_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def _get_or_load_voice(voice_path: Path):
    path_str = str(voice_path)
    if path_str in _voice_cache:
        return _voice_cache[path_str]

    try:
        from piper.voice import PiperVoice

        voice = PiperVoice.load(path_str)
        _voice_cache[path_str] = voice
        logger.info("Loaded PiperVoice model from %s", path_str)
        return voice
    except Exception as exc:
        raise TextToSpeechError(f"Failed to load PiperVoice model from {path_str}: {exc}") from exc


def _synthesize_in_memory_sync(voice_path: Path, text: str) -> bytes:
    clean_text = (text or "").strip()
    if not clean_text:
        return b""

    voice = _get_or_load_voice(voice_path)
    buf = io.BytesIO()

    try:
        wav_file = wave.open(buf, "wb")
        voice.synthesize_wav(clean_text, wav_file)
        wav_file.close()
        return buf.getvalue()
    except Exception as exc:
        raise TextToSpeechError(f"Piper in-memory synthesis failed: {exc}") from exc


async def synthesize_speech(text: str) -> bytes:
    voice_path = _resolve_piper_voice_path()
    if not voice_path.exists():
        raise TextToSpeechError(f"Piper voice model not found: {voice_path}")

    return await asyncio.to_thread(_synthesize_in_memory_sync, voice_path, text)


def get_tts_audio_mime_type() -> str:
    return "audio/wav"


@contextmanager
def use_tts_session(session_id: str) -> Iterator[None]:
    token = _current_session_id.set(session_id)
    try:
        yield
    finally:
        _current_session_id.reset(token)
