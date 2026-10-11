import base64
import logging

from fastapi import APIRouter, HTTPException
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, Field

from app.agent.graph import run_agent
from app.agent.llm_router import LLMServiceUnavailableError
from app.agent.memory import conversation_memory
from app.agent.stt_client import transcribe_audio
from app.agent.tts_client import get_tts_audio_mime_type, synthesize_speech, use_tts_session
from app.config import get_settings


router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)
CLARIFICATION_REPLY = "Sorry, I didn't catch that. Can you say that again?"


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    reply: str
    model_used: str
    actions: list[str] = Field(default_factory=list)


class VoiceResponse(BaseModel):
    transcript: str
    reply_text: str
    model_used: str
    audio_base64: str
    audio_mime_type: str
    actions: list[str] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await run_agent(request.session_id, request.message)
    except LLMServiceUnavailableError as exc:
        detail = str(exc) if get_settings().debug else "Configured Ollama model unavailable"
        raise HTTPException(status_code=503, detail=detail) from exc

    from app.agent.graph import sanitize_reply
    cleaned_reply = sanitize_reply(result.get("reply", "")) or "I've handled that for you."

    return ChatResponse(
        reply=cleaned_reply,
        model_used=result.get("model_used") or get_settings().ollama_model,
        actions=result.get("actions", []),
    )


@router.post("/voice", response_model=VoiceResponse)
async def voice(
    session_id: str = Form(..., min_length=1),
    audio_file: UploadFile = File(...),
) -> VoiceResponse:
    audio_bytes = await audio_file.read()
    mime_type = audio_file.content_type or "application/octet-stream"
    settings = get_settings()

    try:
        transcript = (await transcribe_audio(audio_bytes, mime_type)).strip()
    except Exception as exc:
        logger.warning("STT failed for voice request: %s", exc)
        transcript = ""

    actions: list[str] = []
    if transcript:
        try:
            result = await run_agent(session_id, transcript)
            reply_text = result["reply"]
            model_used = result.get("model_used") or settings.ollama_model
            actions = result.get("actions", [])
        except LLMServiceUnavailableError as exc:
            detail = str(exc) if settings.debug else "Configured Ollama model unavailable"
            raise HTTPException(status_code=503, detail=detail) from exc
    else:
        reply_text = CLARIFICATION_REPLY
        model_used = settings.ollama_model

    audio_base64 = ""
    audio_mime_type = ""
    try:
        with use_tts_session(session_id):
            speech_bytes = await synthesize_speech(reply_text)
        audio_base64 = base64.b64encode(speech_bytes).decode("ascii")
        audio_mime_type = get_tts_audio_mime_type()
    except Exception as exc:
        logger.warning("TTS failed for voice request: %s", exc)

    return VoiceResponse(
        transcript=transcript,
        reply_text=reply_text,
        model_used=model_used,
        audio_base64=audio_base64,
        audio_mime_type=audio_mime_type,
        actions=actions,
    )


@router.get("/history/{session_id}")
async def history(session_id: str) -> dict[str, list[dict[str, str]]]:
    return {"messages": conversation_memory.get_history(session_id)}
