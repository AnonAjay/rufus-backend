"""Dynamic App and Skill Permission Engine for Rufus.

Maintains persistent allowlists/denylists for desktop applications and LangGraph tools.
Enforces dual-layer defense:
1. Schema pruning before LLM inference (pre-generation).
2. Deterministic execution gatekeeper in tools_node (post-generation).
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
PERMISSIONS_FILE = DATA_DIR / "tool_permissions.json"

# Mapping between skill/integration IDs and backend tool names
INTEGRATION_TOOL_MAP: dict[str, list[str]] = {
    "research": ["web_search"],
    "vision": ["inspect_screen", "capture_screenshot"],
    "volume": ["system_volume"],
    "display": ["screen_brightness"],
    "spotify": ["spotify_control"],
    "stunts": ["robot_stunt"],
    "memory": ["save_user_memory"],
    "workstation": ["lock_workstation"],
}

# Granular action keys mapped to specific tool names
ACTION_TOOL_MAP: dict[str, str] = {
    "whatsapp.send": "whatsapp_send_message",
    "whatsapp.read": "whatsapp_get_last_interaction",
    "whatsapp.contacts": "whatsapp_search_contacts",
    "spotify.control": "spotify_control",
    "system.volume": "system_volume",
    "system.display": "screen_brightness",
    "system.vision": "inspect_screen",
    "research.web": "web_search",
    "robot.stunt": "robot_stunt",
}

DEFAULT_PERMISSIONS: dict[str, Any] = {
    "apps": {
        "whatsapp": True,
        "vscode": True,
        "antigravity": True,
        "spotify": True,
        "chrome": True,
        "browser": True,
        "explorer": True,
        "brave": True,
        "discord": True,
    },
    "skills": {
        "web_search": True,
        "system_volume": True,
        "screen_brightness": True,
        "inspect_screen": True,
        "capture_screenshot": True,
        "spotify_control": True,
        "whatsapp_send_message": True,
        "whatsapp_get_last_interaction": True,
        "whatsapp_search_contacts": True,
        "whatsapp_list_messages": True,
        "whatsapp_save_contact": True,
        "robot_stunt": True,
        "save_user_memory": True,
        "lock_workstation": True,
        "open_website": True,
    },
}


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_permissions() -> dict[str, Any]:
    """Load tool and app permissions from disk with default fallbacks."""
    _ensure_data_dir()
    if not PERMISSIONS_FILE.exists():
        save_permissions(DEFAULT_PERMISSIONS)
        return DEFAULT_PERMISSIONS.copy()

    try:
        with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure required top-level keys exist
            apps = {**DEFAULT_PERMISSIONS["apps"], **data.get("apps", {})}
            skills = {**DEFAULT_PERMISSIONS["skills"], **data.get("skills", {})}
            return {"apps": apps, "skills": skills}
    except Exception as exc:
        logger.error("Failed to read %s: %s; using defaults", PERMISSIONS_FILE, exc)
        return DEFAULT_PERMISSIONS.copy()


def save_permissions(permissions: dict[str, Any]) -> None:
    """Save permissions dictionary to disk."""
    _ensure_data_dir()
    try:
        with open(PERMISSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(permissions, f, indent=2)
    except Exception as exc:
        logger.error("Failed to write %s: %s", PERMISSIONS_FILE, exc)


# In-memory cached copy for sub-millisecond lookup
_CACHED_PERMISSIONS: dict[str, Any] = load_permissions()


def get_permissions() -> dict[str, Any]:
    """Return live active permissions."""
    global _CACHED_PERMISSIONS
    return _CACHED_PERMISSIONS


def update_permissions(updates: dict[str, Any]) -> dict[str, Any]:
    """Update permissions from client request and persist to disk."""
    global _CACHED_PERMISSIONS
    current = load_permissions()

    if "apps" in updates and isinstance(updates["apps"], dict):
        for k, v in updates["apps"].items():
            current["apps"][k.lower()] = bool(v)

    if "skills" in updates and isinstance(updates["skills"], dict):
        for k, v in updates["skills"].items():
            current["skills"][k] = bool(v)

    # Allow syncing from frontend integration items
    if "integrations" in updates and isinstance(updates["integrations"], list):
        for item in updates["integrations"]:
            item_id = str(item.get("id", "")).lower()
            enabled = bool(item.get("enabled", True))
            item_type = item.get("type", "app")

            if item_type == "app":
                current["apps"][item_id] = enabled
                # If Spotify app is disabled, also disable spotify_control
                if item_id == "spotify" and not enabled:
                    current["skills"]["spotify_control"] = False
                elif item_id == "spotify" and enabled:
                    current["skills"]["spotify_control"] = True
            elif item_type == "skill":
                # Map skill to tool names
                tools = INTEGRATION_TOOL_MAP.get(item_id, [item_id])
                for t in tools:
                    current["skills"][t] = enabled

            # Parse granular sub-tool permissions if present
            tools_list = item.get("tools", [])
            if isinstance(tools_list, list):
                for sub in tools_list:
                    action_key = sub.get("actionKey")
                    sub_enabled = bool(sub.get("enabled", True))
                    if action_key and action_key in ACTION_TOOL_MAP:
                        target_tool = ACTION_TOOL_MAP[action_key]
                        current["skills"][target_tool] = enabled and sub_enabled

    save_permissions(current)
    _CACHED_PERMISSIONS = current
    return _CACHED_PERMISSIONS


def is_app_allowed(app_name: str) -> bool:
    """Check if an application is allowed to be launched."""
    key = app_name.strip().lower()
    # Normalize aliases
    if key in {"vs code", "code"}:
        key = "vscode"
    elif key in {"chrome", "google chrome"}:
        key = "chrome"
    elif key in {"browser", "web browser"}:
        key = "browser"
    elif key in {"file explorer", "explorer.exe"}:
        key = "explorer"

    perms = get_permissions()
    return perms.get("apps", {}).get(key, True)


def is_tool_allowed(tool_name: str) -> bool:
    """Check if a LangGraph tool is permitted to execute."""
    perms = get_permissions()
    return perms.get("skills", {}).get(tool_name, True)


def filter_tool_definitions(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prune disabled tool schemas so the LLM context never sees them."""
    perms = get_permissions()
    skills_map = perms.get("skills", {})
    allowed: list[dict[str, Any]] = []

    for tool in tool_definitions:
        tname = tool.get("name", "")
        # Check if the tool itself is disabled
        if not skills_map.get(tname, True):
            continue

        # If it is open_app, verify at least one app is allowed
        if tname == "open_app":
            apps_map = perms.get("apps", {})
            any_app_allowed = any(apps_map.values())
            if not any_app_allowed:
                continue

        allowed.append(tool)

    return allowed
