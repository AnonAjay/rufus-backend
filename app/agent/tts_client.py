import asyncio
import os
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator, Optional

from app.config import BASE_DIR, get_settings
from app.settings.voice_preferences import get_voice_preference


_current_session_id: ContextVar[Optional[str]] = ContextVar("tts_session_id", default=None)


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


async def synthesize_speech(text: str) -> bytes:
    voice_path = _resolve_piper_voice_path()
    if not voice_path.exists():
        raise TextToSpeechError(f"Piper voice model not found: {voice_path}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as output_file:
        output_path = output_file.name

    try:
        process = await asyncio.create_subprocess_exec(
            "piper",
            "--model",
            str(voice_path),
            "--output_file",
            output_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(text.encode("utf-8"))
        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
            raise TextToSpeechError(f"Piper failed: {error.strip()}")

        return Path(output_path).read_bytes()
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def get_tts_audio_mime_type() -> str:
    return "audio/wav"


@contextmanager
def use_tts_session(session_id: str) -> Iterator[None]:
    token = _current_session_id.set(session_id)
    try:
        yield
    finally:
        _current_session_id.reset(token)
