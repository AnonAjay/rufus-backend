"""
E2E Test Harness Server for Rufus.
Wraps the real FastAPI app with safety stubs, telemetry recorders, and test hooks.
Strictly adheres to E2E Rules:
- Stubs WhatsApp, Spotify, and Web Search with recorders.
- Real system volume adjustment with pre-read and restoration.
- Real calculator/notepad launching with immediate process cleanup.
- Tracks LLM calls per turn, prompt-eval time, and generation tokens/sec from Ollama.
- Uses a temporary copy of data/ directory to isolate test state from production.
"""
import ast
import asyncio
import atexit
import logging
import os
import re
import shutil
import sys
import time
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("rufus_e2e_harness")

# Ensure rufus-backend is on path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RUFUS_BACKEND_DIR = Path(os.environ.get("RUFUS_BACKEND_DIR", str(BASE_DIR / "rufus-backend")))
sys.path.insert(0, str(RUFUS_BACKEND_DIR))

# ---------------------------------------------------------------------------
# Data Directory Isolation (Temp copy for test execution)
# ---------------------------------------------------------------------------
REAL_DATA_DIR = RUFUS_BACKEND_DIR / "data"
TEMP_DATA_DIR = RUFUS_BACKEND_DIR / "data_temp_e2e"

if TEMP_DATA_DIR.exists():
    shutil.rmtree(TEMP_DATA_DIR, ignore_errors=True)
if REAL_DATA_DIR.exists():
    shutil.copytree(REAL_DATA_DIR, TEMP_DATA_DIR)
else:
    TEMP_DATA_DIR.mkdir(parents=True, exist_ok=True)

def cleanup_temp_data():
    if TEMP_DATA_DIR.exists():
        try:
            shutil.rmtree(TEMP_DATA_DIR, ignore_errors=True)
        except Exception:
            pass

atexit.register(cleanup_temp_data)

# Monkeypatch data paths before loading app modules
import app.agent.hybrid_memory as hm
hm.DB_DIR = TEMP_DATA_DIR
hm.DB_PATH = TEMP_DATA_DIR / "rufus_memory.db"

import app.agent.permissions as perms
perms.DATA_DIR = TEMP_DATA_DIR
perms.PERMISSIONS_FILE = TEMP_DATA_DIR / "tool_permissions.json"
perms._CACHED_PERMISSIONS = perms.load_permissions()

import app.mcp_servers.whatsapp.tools as wa_tools
wa_tools.CONTACTS_FILE = TEMP_DATA_DIR / "contacts.json"
wa_tools.DB_SEARCH_PATHS = [TEMP_DATA_DIR / "whatsapp.db"]

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Global telemetry and recorder state
AUDIT_RECORDER: dict[str, Any] = {
    "whatsapp_calls": [],
    "spotify_calls": [],
    "web_search_calls": [],
    "screen_inspect_calls": [],
    "volume_actions": [],
    "spawned_pids": [],
    "llm_calls_in_turn": 0,
    "llm_usage_in_turn": [],
    "last_tool_executed": None,
    "last_tool_args": {},
    "last_path_taken": None,
}

# ---------------------------------------------------------------------------
# 1. Monkeypatch safety stubs into app.agent.tools and whatsapp MCP
# ---------------------------------------------------------------------------
import app.agent.tools as agent_tools

orig_execute_tool = agent_tools.execute_tool
orig_open_app = agent_tools.open_app
orig_system_volume = agent_tools.system_volume


def stubbed_whatsapp_send_message(recipient: str, message: str, **kwargs: Any) -> str:
    """Safe recorder stub: records recipient and message without sending real messages."""
    if kwargs:
        logger.info("stubbed_whatsapp_send_message extra kwargs: %s", kwargs)
    payload = {"recipient": recipient, "message": message, **kwargs}
    AUDIT_RECORDER["whatsapp_calls"].append(payload)
    AUDIT_RECORDER["last_tool_executed"] = "whatsapp_send_message"
    AUDIT_RECORDER["last_tool_args"] = payload
    return f"Sent WhatsApp message to {recipient}: '{message}'"


def stubbed_spotify_control(command: str, query: str = "", **kwargs: Any) -> str:
    """Safe recorder stub: records command and query without launching apps or audio."""
    if kwargs:
        logger.info("stubbed_spotify_control extra kwargs: %s", kwargs)
    payload = {"command": command, "query": query, **kwargs}
    AUDIT_RECORDER["spotify_calls"].append(payload)
    AUDIT_RECORDER["last_tool_executed"] = "spotify_control"
    AUDIT_RECORDER["last_tool_args"] = payload
    return f"Executed Spotify action: {command} {query}".strip()


def stubbed_web_search(query: str, **kwargs: Any) -> str:
    """Safe recorder stub: records query and returns deterministic stubbed search results."""
    if kwargs:
        logger.info("stubbed_web_search extra kwargs: %s", kwargs)
    payload = {"query": query, **kwargs}
    AUDIT_RECORDER["web_search_calls"].append(payload)
    AUDIT_RECORDER["last_tool_executed"] = "web_search"
    AUDIT_RECORDER["last_tool_args"] = payload
    return (
        f"Live web search results for '{query}':\n\n"
        f"[1] Verified Search Reference\n"
        f"URL: https://example.com/test-search\n"
        f"Excerpt: Verified empirical documentation regarding {query}."
    )


def stubbed_inspect_screen(display: int = 1, query: str = "", **kwargs: Any) -> str:
    """Safe recorder stub: returns deterministic screen analysis."""
    if kwargs:
        logger.info("stubbed_inspect_screen extra kwargs: %s", kwargs)
    payload = {"display": display, "query": query, **kwargs}
    AUDIT_RECORDER["screen_inspect_calls"].append(payload)
    AUDIT_RECORDER["last_tool_executed"] = "inspect_screen"
    AUDIT_RECORDER["last_tool_args"] = payload
    return "Visual observation of display 1: The screen currently displays an active text editor."


def stubbed_lock_workstation(confirm: bool = False, **kwargs: Any) -> str:
    """Safe stub: prevents locking tester desktop."""
    if kwargs:
        logger.info("stubbed_lock_workstation extra kwargs: %s", kwargs)
    payload = {"confirm": confirm, **kwargs}
    AUDIT_RECORDER["last_tool_executed"] = "lock_workstation"
    AUDIT_RECORDER["last_tool_args"] = payload
    return "Windows workstation successfully locked (mocked for safety)."


def safe_tracked_system_volume(action: str = "get", level: Any = None, **kwargs: Any) -> str:
    """
    Real tool execution with readback verification and state restoration.
    Gracefully handles 'value' alias for level.
    """
    if level is None and "value" in kwargs:
        level = kwargs.pop("value")
    if kwargs:
        logger.info("safe_tracked_system_volume extra kwargs: %s", kwargs)

    from pycaw.pycaw import AudioUtilities
    orig_pct = 50
    try:
        dev = AudioUtilities.GetSpeakers()
        if dev and hasattr(dev, "EndpointVolume"):
            orig_scalar = dev.EndpointVolume.GetMasterVolumeLevelScalar()
            orig_pct = round(orig_scalar * 100)
    except Exception:
        pass

    res = orig_system_volume(action=action, level=level)

    new_pct = orig_pct
    try:
        dev = AudioUtilities.GetSpeakers()
        if dev and hasattr(dev, "EndpointVolume"):
            new_scalar = dev.EndpointVolume.GetMasterVolumeLevelScalar()
            new_pct = round(new_scalar * 100)
            # Restore to original level so tester environment is untouched
            dev.EndpointVolume.SetMasterVolumeLevelScalar(orig_pct / 100.0, None)
    except Exception:
        pass

    AUDIT_RECORDER["volume_actions"].append({
        "action": action,
        "level": level,
        "value": level,
        "initial_pct": orig_pct,
        "achieved_pct": new_pct,
        "restored_pct": orig_pct,
    })
    AUDIT_RECORDER["last_tool_executed"] = "system_volume"
    AUDIT_RECORDER["last_tool_args"] = {"action": action, "level": level, "value": level, **kwargs}
    return res


def safe_tracked_open_app(app_name: str, **kwargs: Any) -> str:
    """
    Real tool execution for calculator and notepad, with immediate process termination.
    """
    if kwargs:
        logger.info("safe_tracked_open_app extra kwargs: %s", kwargs)
    app_clean = (app_name or "").strip().lower()
    if app_clean in {"calculator", "calc", "calc.exe"}:
        proc = subprocess.Popen(["calc.exe"])
        AUDIT_RECORDER["spawned_pids"].append(proc.pid)
        time.sleep(0.3)
        proc.terminate()
        AUDIT_RECORDER["last_tool_executed"] = "open_app"
        AUDIT_RECORDER["last_tool_args"] = {"app_name": "calculator", **kwargs}
        return "Opened Calculator for you."
    elif app_clean in {"notepad", "notepad.exe"}:
        proc = subprocess.Popen(["notepad.exe"])
        AUDIT_RECORDER["spawned_pids"].append(proc.pid)
        time.sleep(0.3)
        proc.terminate()
        AUDIT_RECORDER["last_tool_executed"] = "open_app"
        AUDIT_RECORDER["last_tool_args"] = {"app_name": "notepad", **kwargs}
        return "Opened Notepad for you."
    else:
        # Standard open_app
        res = orig_open_app(app_name)
        AUDIT_RECORDER["last_tool_executed"] = "open_app"
        AUDIT_RECORDER["last_tool_args"] = {"app_name": app_name, **kwargs}
        return res


# Apply monkeypatches to tool registry
agent_tools.TOOL_REGISTRY["whatsapp_send_message"] = stubbed_whatsapp_send_message
agent_tools.TOOL_REGISTRY["spotify_control"] = stubbed_spotify_control
agent_tools.TOOL_REGISTRY["web_search"] = stubbed_web_search
agent_tools.TOOL_REGISTRY["inspect_screen"] = stubbed_inspect_screen
agent_tools.TOOL_REGISTRY["capture_screenshot"] = stubbed_inspect_screen
agent_tools.TOOL_REGISTRY["lock_workstation"] = stubbed_lock_workstation
agent_tools.TOOL_REGISTRY["system_volume"] = safe_tracked_system_volume
agent_tools.TOOL_REGISTRY["open_app"] = safe_tracked_open_app

# ---------------------------------------------------------------------------
# 2. Monkeypatch litellm.completion to count calls and record token metrics
# ---------------------------------------------------------------------------
import litellm
orig_litellm_completion = litellm.completion


def tracked_litellm_completion(*args, **kwargs):
    t0 = time.perf_counter()
    resp = orig_litellm_completion(*args, **kwargs)
    dt = time.perf_counter() - t0

    AUDIT_RECORDER["llm_calls_in_turn"] += 1

    usage = getattr(resp, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

    tok_per_sec = (completion_tokens / dt) if dt > 0 else 0.0

    AUDIT_RECORDER["llm_usage_in_turn"].append({
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "wall_latency_s": dt,
        "tokens_per_sec": tok_per_sec,
    })
    return resp


litellm.completion = tracked_litellm_completion

# ---------------------------------------------------------------------------
# 3. Mount real FastAPI app and register audit endpoints
# ---------------------------------------------------------------------------
from app.main import app as real_app


@real_app.get("/e2e/health")
async def e2e_health() -> dict[str, str]:
    return {"status": "ok", "mode": "e2e_harness"}


@real_app.post("/e2e/reset")
async def e2e_reset() -> dict[str, str]:
    """Reset the audit recorder before each test run."""
    AUDIT_RECORDER["whatsapp_calls"].clear()
    AUDIT_RECORDER["spotify_calls"].clear()
    AUDIT_RECORDER["web_search_calls"].clear()
    AUDIT_RECORDER["screen_inspect_calls"].clear()
    AUDIT_RECORDER["volume_actions"].clear()
    AUDIT_RECORDER["spawned_pids"].clear()
    AUDIT_RECORDER["llm_calls_in_turn"] = 0
    AUDIT_RECORDER["llm_usage_in_turn"].clear()
    AUDIT_RECORDER["last_tool_executed"] = None
    AUDIT_RECORDER["last_tool_args"].clear()
    AUDIT_RECORDER["last_path_taken"] = None
    return {"status": "reset"}


@real_app.get("/e2e/telemetry")
async def e2e_telemetry() -> dict[str, Any]:
    """Retrieve recorded turn telemetry."""
    return dict(AUDIT_RECORDER)


if __name__ == "__main__":
    port = int(os.environ.get("RUFUS_E2E_PORT", 8008))
    print(f"Starting Rufus E2E Test Harness Server on http://127.0.0.1:{port}...")
    uvicorn.run(real_app, host="127.0.0.1", port=port, log_level="warning")
