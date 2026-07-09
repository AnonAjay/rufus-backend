from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Rufus Backend"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rufus"
    create_db_tables_on_startup: bool = False

    firebase_project_id: Optional[str] = None
    firebase_credentials_path: Optional[str] = None

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None

    litellm_primary_model: str = "gemini/gemini-2.0-flash"
    litellm_fallback_model: str = "ollama/llama3.1"

    home_assistant_mcp_url: Optional[str] = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Rufus Backend"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        environment=os.getenv("ENVIRONMENT", "development"),
        debug=_as_bool(os.getenv("DEBUG"), True),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/rufus",
        ),
        create_db_tables_on_startup=_as_bool(os.getenv("CREATE_DB_TABLES_ON_STARTUP"), False),
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID"),
        firebase_credentials_path=os.getenv("FIREBASE_CREDENTIALS_PATH"),
        mqtt_host=os.getenv("MQTT_HOST", "localhost"),
        mqtt_port=_as_int(os.getenv("MQTT_PORT"), 1883),
        mqtt_username=os.getenv("MQTT_USERNAME"),
        mqtt_password=os.getenv("MQTT_PASSWORD"),
        litellm_primary_model=os.getenv("LITELLM_PRIMARY_MODEL", "gemini/gemini-2.0-flash"),
        litellm_fallback_model=os.getenv("LITELLM_FALLBACK_MODEL", "ollama/llama3.1"),
        home_assistant_mcp_url=os.getenv("HOME_ASSISTANT_MCP_URL"),
    )
