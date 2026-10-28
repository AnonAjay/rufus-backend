# Rufus Backend

Standalone FastAPI backend for Rufus, an ESP32-based companion robot dog.

Rufus is designed as an agent-first system. A single LangGraph agent consumes
events from voice, vision, sensors, app realtime messages, and third-party
integrations, then chooses which MCP tool to invoke. Application code should not
hardcode intent routing such as "if this is a reminder, call reminders." Safety
and trust gates, such as approval before sending WhatsApp messages or placing
calls, are enforced inside the relevant MCP tool implementation.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
ollama pull llama3.2:latest
ollama serve
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Configuration

Set `DATABASE_URL` to your Supabase/Postgres SQLAlchemy URL. For Firebase Auth,
set `FIREBASE_PROJECT_ID` and optionally `FIREBASE_CREDENTIALS_PATH` to a service
account JSON file. If no credentials path is provided, Firebase Admin uses
application default credentials.

Rufus currently uses local Ollama only for LLM calls. Configure the model with
`OLLAMA_MODEL`, the service URL with `OLLAMA_API_BASE`, and local inference
timeout with `OLLAMA_TIMEOUT`. The default API base is `http://127.0.0.1:11434`
to avoid Windows IPv6 `localhost` resolution issues.

Voice input/output is exposed through `POST /agent/voice` as multipart form
data with `session_id` and `audio_file`. STT runs locally with faster-whisper,
which auto-downloads the configured `WHISPER_MODEL_SIZE` on first use. TTS runs
locally with Piper; configure `PIPER_VOICE_PATH` to a downloaded `.onnx` voice
file. Downloaded Piper voice files under `piper_voices/` are listed by
`GET /voices`, and `POST /settings/voice` stores a per-session voice selection
in memory.

## Development Notes

The current implementation includes working FastAPI app creation, environment
configuration, Firebase ID token verification behind a swappable auth interface,
and SQLAlchemy session setup. Agent, MCP, MQTT, WebSocket, hardware mock, and
notification modules are modularized under `app/`.

## MCP Servers & Open-Source Credits

Rufus integrates modular Model Context Protocol (MCP) servers located in `app/mcp_servers/`:

- **WhatsApp MCP (`app/mcp_servers/whatsapp/`)**:
  - Adapted from and inspired by the open-source **[whatsapp-mcp](https://github.com/lharries/whatsapp-mcp)** by **Luke Harries** (MIT License).
  - Provides tools for contact searching, message querying, and WhatsApp message dispatching with dual-mode support (SQLite bridge + Windows protocol handler fallback).

## Mock Device

For local hardware-free development, run a Mosquitto broker on
`127.0.0.1:1883`, start the backend, then run:

```bash
python -m app.devices.mock_device --device-id mock-rufus-001
```

The mock device publishes touch, motion, light, mask-state, and battery MQTT
events using the same `rufus/{device_id}/...` topic contract planned for the
ESP32 firmware. It also listens for stunt/display commands and publishes
`status/ack` responses with the same `command_id`.
