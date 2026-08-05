import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import llm_router
from app.agent import stt_client
from app.agent import tts_client
from app.agent.memory import ConversationMemory, conversation_memory
from app.db.base import Base
from app.db.session import get_db
from app.devices.models import Device
from app.main import create_app
from app.realtime import mqtt_client, topics
from app.settings import voice_preferences


def _response(content: str, model: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        _hidden_params={"model_id": model},
        model=model,
    )


@pytest.mark.asyncio
async def test_get_completion_calls_ollama_directly(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response("ollama reply", "ollama/llama3.2:latest")

    monkeypatch.setattr(llm_router, "completion", fake_completion)

    result = await llm_router.get_completion([{"role": "user", "content": "hello"}])

    assert str(result) == "ollama reply"
    assert result.model_used == "ollama/llama3.2:latest"
    assert calls[0]["model"] == "ollama/llama3.2:latest"
    assert calls[0]["api_base"] == "http://127.0.0.1:11434"
    assert calls[0]["max_tokens"] == 180


@pytest.mark.asyncio
async def test_get_completion_raises_diagnostic_error_on_ollama_failure(monkeypatch):
    def fake_completion(**kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(llm_router, "completion", fake_completion)

    with pytest.raises(llm_router.LLMServiceUnavailableError) as exc_info:
        await llm_router.get_completion([{"role": "user", "content": "hello"}])

    message = str(exc_info.value)
    assert "Ollama request failed" in message
    assert "ollama serve" in message
    assert "ollama pull llama3.2:latest" in message
    assert "OLLAMA_API_BASE" in message


def test_agent_chat_returns_reply(monkeypatch):
    async def fake_get_completion(messages):
        return llm_router.CompletionResult("hello from Rufus", "ollama/llama3.2:latest")

    conversation_memory.clear()
    monkeypatch.setattr("app.agent.graph.get_completion", fake_get_completion)
    client = TestClient(create_app())

    response = client.post(
        "/agent/chat",
        json={"session_id": "test-session", "message": "hello"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "hello from Rufus"
    assert body["model_used"] == "ollama/llama3.2:latest"


def test_agent_voice_returns_transcript_reply_and_audio(monkeypatch):
    async def fake_transcribe(audio_bytes, mime_type):
        assert audio_bytes == b"fake-audio"
        assert mime_type == "audio/wav"
        return "hello rufus"

    async def fake_run_agent(session_id, message):
        assert session_id == "voice-session"
        assert message == "hello rufus"
        return {
            "session_id": session_id,
            "message": message,
            "reply": "hello from Rufus",
            "model_used": "ollama/llama3.2:latest",
        }

    async def fake_synthesize(text):
        assert text == "hello from Rufus"
        return b"fake-speech"

    monkeypatch.setattr("app.agent.router.transcribe_audio", fake_transcribe)
    monkeypatch.setattr("app.agent.router.run_agent", fake_run_agent)
    monkeypatch.setattr("app.agent.router.synthesize_speech", fake_synthesize)
    monkeypatch.setattr("app.agent.router.get_tts_audio_mime_type", lambda: "audio/wav")

    client = TestClient(create_app())
    response = client.post(
        "/agent/voice",
        data={"session_id": "voice-session"},
        files={"audio_file": ("voice.wav", b"fake-audio", "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "hello rufus"
    assert body["reply_text"] == "hello from Rufus"
    assert body["model_used"] == "ollama/llama3.2:latest"
    assert body["audio_base64"] == base64.b64encode(b"fake-speech").decode("ascii")
    assert body["audio_mime_type"] == "audio/wav"


def test_agent_voice_empty_transcript_skips_agent(monkeypatch):
    async def fake_transcribe(audio_bytes, mime_type):
        return "   "

    async def fail_run_agent(session_id, message):
        raise AssertionError("agent should not be called for empty transcripts")

    async def fake_synthesize(text):
        return b"clarification-audio"

    monkeypatch.setattr("app.agent.router.transcribe_audio", fake_transcribe)
    monkeypatch.setattr("app.agent.router.run_agent", fail_run_agent)
    monkeypatch.setattr("app.agent.router.synthesize_speech", fake_synthesize)
    monkeypatch.setattr("app.agent.router.get_tts_audio_mime_type", lambda: "audio/wav")

    client = TestClient(create_app())
    response = client.post(
        "/agent/voice",
        data={"session_id": "voice-session"},
        files={"audio_file": ("voice.webm", b"fake-audio", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == ""
    assert body["reply_text"] == "Sorry, I didn't catch that. Can you say that again?"
    assert body["audio_base64"] == base64.b64encode(b"clarification-audio").decode("ascii")


@pytest.mark.asyncio
async def test_transcribe_audio_uses_faster_whisper(monkeypatch):
    calls = []

    class FakeWhisperModel:
        def transcribe(self, audio_path):
            calls.append(audio_path)
            return [SimpleNamespace(text=" hello"), SimpleNamespace(text=" rufus ")], None

    monkeypatch.setattr(stt_client, "load_whisper_model", lambda: FakeWhisperModel())

    transcript = await stt_client.transcribe_audio(b"fake-audio", "audio/wav")

    assert transcript == "hello rufus"
    assert calls

@pytest.mark.asyncio
async def test_synthesize_speech_calls_piper_subprocess(monkeypatch, tmp_path):
    voice_path = tmp_path / "piper_voices" / "en" / "en_US" / "amy" / "medium" / "en_US-amy-medium.onnx"
    voice_path.parent.mkdir(parents=True)
    voice_path.write_bytes(b"fake-model")

    class FakeProcess:
        returncode = 0

        def __init__(self, output_path):
            self.output_path = output_path

        async def communicate(self, stdin):
            assert stdin == b"hello"
            self.output_path.write_bytes(b"fake-wav")
            return b"", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        output_path = Path(args[args.index("--output_file") + 1])
        return FakeProcess(output_path)

    monkeypatch.setattr(
        tts_client,
        "get_settings",
        lambda: SimpleNamespace(piper_voice_path=str(voice_path)),
    )
    monkeypatch.setattr(tts_client.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    audio = await tts_client.synthesize_speech("hello")

    assert audio == b"fake-wav"


def test_voice_settings_list_and_store_piper_voice(monkeypatch, tmp_path):
    root = tmp_path / "piper_voices"
    voice_path = root / "en" / "en_US" / "amy" / "medium" / "en_US-amy-medium.onnx"
    voice_path.parent.mkdir(parents=True)
    voice_path.write_bytes(b"fake-model")

    voice_preferences.clear_voice_preferences()
    monkeypatch.setattr(voice_preferences, "BASE_DIR", tmp_path)
    monkeypatch.setattr(voice_preferences, "PIPER_VOICE_ROOT", root)

    client = TestClient(create_app())

    voices_response = client.get("/voices")
    assert voices_response.status_code == 200
    voices = voices_response.json()["voices"]
    assert voices == [
        {
            "display_name": "en US amy medium",
            "voice_path": "piper_voices/en/en_US/amy/medium/en_US-amy-medium.onnx",
        }
    ]

    settings_response = client.post(
        "/settings/voice",
        json={
            "session_id": "voice-session",
            "voice_path": "piper_voices/en/en_US/amy/medium/en_US-amy-medium.onnx",
        },
    )
    assert settings_response.status_code == 200
    assert voice_preferences.get_voice_preference("voice-session") == (
        "piper_voices/en/en_US/amy/medium/en_US-amy-medium.onnx"
    )


def test_memory_caps_history_at_20_messages():
    memory = ConversationMemory()

    for index in range(25):
        memory.add_message("session", "user", f"message {index}")

    history = memory.get_history("session")
    assert len(history) == 20
    assert history[0]["content"] == "message 5"
    assert history[-1]["content"] == "message 24"


def test_topic_constants_format_expected_topics():
    device_id = "rufus-123"

    assert topics.format_topic(topics.TOUCH_SENSOR_TOPIC, device_id) == "rufus/rufus-123/sensors/touch"
    assert topics.format_topic(topics.MOTION_SENSOR_TOPIC, device_id) == "rufus/rufus-123/sensors/motion"
    assert topics.format_topic(topics.LIGHT_SENSOR_TOPIC, device_id) == "rufus/rufus-123/sensors/light"
    assert topics.format_topic(topics.MASK_STATE_SENSOR_TOPIC, device_id) == "rufus/rufus-123/sensors/mask_state"
    assert topics.format_topic(topics.STUNT_COMMAND_TOPIC, device_id) == "rufus/rufus-123/commands/stunt"
    assert topics.format_topic(topics.DISPLAY_COMMAND_TOPIC, device_id) == "rufus/rufus-123/commands/display"
    assert topics.format_topic(topics.ACK_STATUS_TOPIC, device_id) == "rufus/rufus-123/status/ack"
    assert topics.format_topic(topics.BATTERY_STATUS_TOPIC, device_id) == "rufus/rufus-123/status/battery"


@pytest.mark.asyncio
async def test_mqtt_on_message_queues_touch_event(monkeypatch):
    while not mqtt_client.event_queue.empty():
        mqtt_client.event_queue.get_nowait()

    monkeypatch.setattr(mqtt_client, "_mark_device_seen", lambda device_id, topic, payload: None)
    message = SimpleNamespace(
        topic="rufus/mock-1/sensors/touch",
        payload=b'{"pressed": true, "timestamp": "2026-08-01T00:00:00Z"}',
    )

    mqtt_client.on_message(None, None, message)

    event = await mqtt_client.event_queue.get()
    assert event.device_id == "mock-1"
    assert event.event_type == "sensors/touch"
    assert event.payload["pressed"] is True


def test_device_register_and_status_online_logic():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.post("/devices/register", json={"device_id": "mock-1", "name": "Mock Rufus"})
    assert response.status_code == 200
    assert response.json()["id"] == "mock-1"

    offline_response = client.get("/devices/mock-1/status")
    assert offline_response.status_code == 200
    assert offline_response.json()["online"] is False

    with TestingSessionLocal() as db:
        device = db.get(Device, "mock-1")
        device.last_seen = datetime.now(timezone.utc)
        device.battery_percent = 87.5
        db.commit()

    online_response = client.get("/devices/mock-1/status")
    assert online_response.status_code == 200
    online_body = online_response.json()
    assert online_body["online"] is True
    assert online_body["battery_percent"] == 87.5

    with TestingSessionLocal() as db:
        device = db.get(Device, "mock-1")
        device.last_seen = datetime.now(timezone.utc) - timedelta(seconds=61)
        db.commit()

    stale_response = client.get("/devices/mock-1/status")
    assert stale_response.status_code == 200
    assert stale_response.json()["online"] is False
