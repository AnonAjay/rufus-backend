from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.settings.voice_preferences import list_available_voices, set_voice_preference


router = APIRouter(tags=["settings"])


class VoicePreferenceRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    voice_path: str = Field(..., min_length=1)


@router.get("/voices")
async def get_voices() -> dict[str, list[dict[str, str]]]:
    return {"voices": list_available_voices()}


@router.post("/settings/voice")
async def set_voice(request: VoicePreferenceRequest) -> dict[str, str]:
    try:
        return set_voice_preference(request.session_id, request.voice_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
