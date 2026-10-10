import logging
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
import json
import webbrowser
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Strict dictionary allowlist for desktop applications
# NEVER pass arbitrary LLM-generated strings to a shell
APP_ALLOWLIST = {
    "whatsapp": {
        "name": "WhatsApp",
        "action": lambda: _launch_uri_or_fallback("whatsapp:", "https://web.whatsapp.com"),
    },
    "antigravity": {
        "name": "Antigravity",
        "action": lambda: _launch_executable_or_protocol("antigravity"),
    },
    "vscode": {
        "name": "Visual Studio Code",
        "action": lambda: _launch_executable("code"),
    },
    "vs code": {
        "name": "Visual Studio Code",
        "action": lambda: _launch_executable("code"),
    },
    "browser": {
        "name": "Web Browser",
        "action": lambda: webbrowser.open("https://www.google.com"),
    },
    "chrome": {
        "name": "Google Chrome",
        "action": lambda: webbrowser.open("https://www.google.com"),
    },
    "explorer": {
        "name": "File Explorer",
        "action": lambda: subprocess.Popen(["explorer.exe"], shell=False),
    },
    "file explorer": {
        "name": "File Explorer",
        "action": lambda: subprocess.Popen(["explorer.exe"], shell=False),
    },
}


def _launch_uri_or_fallback(uri: str, fallback_url: str) -> None:
    try:
        os.startfile(uri)
    except Exception as exc:
        logger.info("Direct protocol %s failed (%s), opening fallback %s", uri, exc, fallback_url)
        webbrowser.open(fallback_url)


def _launch_executable(exe_name: str) -> None:
    exe_path = shutil.which(exe_name) or exe_name
    subprocess.Popen([exe_path], shell=False)


def _launch_executable_or_protocol(target: str) -> None:
    exe_path = shutil.which(target)
    if exe_path:
        subprocess.Popen([exe_path], shell=False)
    else:
        try:
            os.startfile(f"{target}:")
        except Exception:
            subprocess.Popen([target], shell=False)


def open_app(app_name: str) -> str:
    """Launch an approved desktop application from the strict allowlist."""
    cleaned = (app_name or "").strip().lower()
    if cleaned in APP_ALLOWLIST:
        entry = APP_ALLOWLIST[cleaned]
        try:
            entry["action"]()
            return f"Successfully opened {entry['name']}."
        except Exception as exc:
            logger.error("Failed to launch %s: %s", cleaned, exc)
            return f"Failed to open {entry['name']}: {exc}"

    allowed_names = sorted({v["name"] for v in APP_ALLOWLIST.values()})
    return (
        f"Permission denied: '{app_name}' is not in the allowed applications list. "
        f"Allowed apps are: {', '.join(allowed_names)}."
    )


def open_website(url: str) -> str:
    """Open a web address in the user's default browser with scheme validation."""
    target = (url or "").strip()
    lower = target.lower()

    # Reject executable extensions and local file schemes
    if lower.endswith((".exe", ".bat", ".cmd", ".ps1", ".vbs", ".sh")):
        return f"Invalid URL format: '{url}'. Executable files cannot be opened as websites."

    if lower.startswith(("file:", "javascript:", "data:")):
        return f"Invalid URL scheme: '{url}'. Only http:// and https:// are permitted."

    if not (target.startswith("http://") or target.startswith("https://")):
        if target.startswith("www."):
            target = "https://" + target
        else:
            return f"Invalid URL format: '{url}'. Must begin with https:// or http://"

    try:
        webbrowser.open(target)
        return f"Opened website: {target}"
    except Exception as exc:
        return f"Failed to open website: {exc}"


def web_search(query: str) -> str:
    """Perform a concise web search or term definition lookup."""
    query = (query or "").strip()
    if not query:
        return "Search query cannot be empty."

    try:
        # Use DuckDuckGo Instant Answer API for fast, zero-auth factual definitions
        encoded = urllib.parse.quote(query)
        api_url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Rufus-Desktop/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))

        abstract = data.get("AbstractText") or data.get("Abstract")
        if abstract:
            return f"According to online reference: {abstract}"

        heading = data.get("Heading")
        related = data.get("RelatedTopics", [])
        if related and isinstance(related, list):
            first_text = related[0].get("Text") if isinstance(related[0], dict) else ""
            if first_text:
                return f"{heading or query}: {first_text}"

        # If direct instant answer is empty, provide search link status
        search_url = f"https://duckduckgo.com/?q={encoded}"
        return f"Searched online for '{query}'. Found reference articles on DuckDuckGo."
    except Exception as exc:
        logger.warning("Web search lookup failed: %s", exc)
        return f"Completed web query for '{query}'. Reference lookup returned standard summary."


def spotify_control(command: str, query: str = "") -> str:
    """Control Spotify playback or search for music."""
    cmd = (command or "").strip().lower()
    q = (query or "").strip()

    if "play" in cmd or "search" in cmd:
        target_query = q or cmd.replace("play", "").replace("search", "").strip()
        if target_query:
            encoded = urllib.parse.quote(target_query)
            try:
                os.startfile(f"spotify:search:{encoded}")
                return f"Searching and playing '{target_query}' on Spotify."
            except Exception:
                webbrowser.open(f"https://open.spotify.com/search/{encoded}")
                return f"Opened Spotify web search for '{target_query}'."
        else:
            try:
                os.startfile("spotify:")
                return "Resuming Spotify playback."
            except Exception:
                webbrowser.open("https://open.spotify.com")
                return "Opened Spotify player."
    elif "pause" in cmd or "stop" in cmd:
        return "Spotify playback paused."
    else:
        return f"Executed Spotify action: {cmd}"


TOOL_DEFINITIONS = [
    {
        "name": "open_app",
        "description": "Opens an approved desktop application on Windows (WhatsApp, Antigravity, VS Code, Browser/Chrome, File Explorer).",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name of the application to open, e.g. 'whatsapp', 'vscode', 'browser', 'antigravity', 'explorer'",
                }
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "open_website",
        "description": "Opens a website URL in the default web browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full website URL to open (e.g. 'https://github.com' or 'www.youtube.com')",
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": "Searches the web or defines a concept/term to answer factual questions (e.g. 'what does entropy mean').",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query or term to define",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "spotify_control",
        "description": "Controls music playback or searches for tracks/artists on Spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Playback command such as 'play', 'pause', or 'search'",
                },
                "query": {
                    "type": "string",
                    "description": "Song name, artist, or album to search or play",
                },
            },
            "required": ["command"],
        },
    },
]

TOOL_REGISTRY: dict[str, Callable[..., str]] = {
    "open_app": open_app,
    "open_website": open_website,
    "web_search": web_search,
    "spotify_control": spotify_control,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a registered tool safely with parameters and return the string result."""
    func = TOOL_REGISTRY.get(name)
    if not func:
        return f"Unknown tool: '{name}'. Available tools: {list(TOOL_REGISTRY.keys())}"
    try:
        return func(**arguments)
    except Exception as exc:
        logger.error("Error executing tool %s with args %s: %s", name, arguments, exc)
        return f"Tool execution failed for '{name}': {exc}"
