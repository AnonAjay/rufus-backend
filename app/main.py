from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.llm_router import get_completion
from app.agent.router import router as agent_router
from app.agent.stt_client import load_whisper_model
from app.config import get_settings
from app.db.session import dispose_engine, initialize_database
from app.devices.router import router as devices_router
from app.realtime.mqtt_client import connect_mqtt, disconnect_mqtt
from app.reminders.router import router as reminders_router
from app.settings.router import router as settings_router
from app.stunts.router import router as stunts_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.create_db_tables_on_startup:
        try:
            initialize_database()
        except Exception as exc:
            logger.warning("Database initialization failed during startup: %s", exc)
    try:
        connect_mqtt()
    except Exception as exc:
        logger.warning("MQTT backend connection failed during startup: %s", exc)
    try:
        await get_completion([{"role": "user", "content": "hi"}])
    except Exception as exc:
        logger.warning("Ollama pre-warm failed during startup: %s", exc)
    try:
        load_whisper_model()
    except Exception as exc:
        logger.warning("Whisper pre-warm failed during startup: %s", exc)
    yield
    disconnect_mqtt()
    dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agent_router)
    app.include_router(devices_router)
    app.include_router(reminders_router)
    app.include_router(settings_router)
    app.include_router(stunts_router)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
