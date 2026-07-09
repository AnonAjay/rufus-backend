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

## Development Notes

The current implementation includes working FastAPI app creation, environment
configuration, Firebase ID token verification behind a swappable auth interface,
and SQLAlchemy session setup. Agent, MCP, MQTT, WebSocket, hardware mock, and
notification modules are intentionally stubbed with TODOs for focused feature
branches.
