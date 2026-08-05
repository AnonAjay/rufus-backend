from pathlib import Path
from typing import Optional

from app.config import BASE_DIR


PIPER_VOICE_ROOT = BASE_DIR / "piper_voices"
_voice_preferences: dict[str, str] = {}


def _display_name(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ")


def list_available_voices() -> list[dict[str, str]]:
    if not PIPER_VOICE_ROOT.exists():
        return []

    voices: list[dict[str, str]] = []
    for path in sorted(PIPER_VOICE_ROOT.rglob("*.onnx")):
        voices.append(
            {
                "display_name": _display_name(path),
                "voice_path": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
            }
        )
    return voices


def set_voice_preference(session_id: str, voice_path: str) -> dict[str, str]:
    path = (BASE_DIR / voice_path).resolve()
    root = PIPER_VOICE_ROOT.resolve()
    if path.suffix != ".onnx" or root not in path.parents or not path.exists():
        raise ValueError("voice_path must point to a downloaded Piper .onnx voice under piper_voices/")

    stored_path = str(path.relative_to(BASE_DIR)).replace("\\", "/")
    _voice_preferences[session_id] = stored_path
    return {"session_id": session_id, "voice_path": stored_path}


def get_voice_preference(session_id: Optional[str]) -> Optional[str]:
    if not session_id:
        return None
    return _voice_preferences.get(session_id)


def clear_voice_preferences() -> None:
    _voice_preferences.clear()
