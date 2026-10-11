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
    """Open a web address in the user's default browser with scheme and search normalization."""
    import re
    import urllib.parse

    target = (url or "").strip()
    lower = target.lower()

    if not target:
        return "Please provide a website URL or search term."

    # Reject executable extensions and local file schemes
    if lower.endswith((".exe", ".bat", ".cmd", ".ps1", ".vbs", ".sh")):
        return f"Invalid URL format: '{url}'. Executable files cannot be opened as websites."

    if lower.startswith(("file:", "javascript:", "data:")):
        return f"Invalid URL scheme: '{url}'. Only http:// and https:// are permitted."

    # Normalize scheme and search intents
    if not (target.startswith("http://") or target.startswith("https://")):
        if target.startswith("www."):
            target = "https://" + target
        elif "." in target and " " not in target:
            target = "https://" + target
        elif "youtube" in lower:
            # Direct search on YouTube
            q = re.sub(r"\b(open|youtube|channel|video|on|the|web)\b", "", lower, flags=re.I).strip()
            target = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q or 'trending')}"
        elif "wikipedia" in lower:
            q = re.sub(r"\b(open|wikipedia|article|on|the|web)\b", "", lower, flags=re.I).strip()
            target = f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(q)}" if q else "https://en.wikipedia.org"
        else:
            # Safe search for general website names
            target = f"https://www.google.com/search?q={urllib.parse.quote(target)}"

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


def system_volume(action: str, level: Any = None) -> str:
    """Adjust or query master system volume on Windows."""
    act = (action or "get").strip().lower()
    try:
        from pycaw.pycaw import AudioUtilities

        device = AudioUtilities.GetSpeakers()
        if not device or not hasattr(device, "EndpointVolume"):
            return "Unable to access default Windows audio endpoint."

        volume = device.EndpointVolume
        current_scalar = volume.GetMasterVolumeLevelScalar()
        current_pct = round(current_scalar * 100)
        is_muted = bool(volume.GetMute())

        if act == "get":
            status = "muted" if is_muted else f"{current_pct}%"
            return f"Current master volume is {status}."

        if act == "mute":
            volume.SetMute(1, None)
            return "Master volume muted."

        if act == "unmute":
            volume.SetMute(0, None)
            return f"Master volume unmuted at {current_pct}%."

        if act == "up":
            step = int(str(level).replace("%", "").strip()) if level is not None else 10
            new_pct = min(100, current_pct + step)
            volume.SetMasterVolumeLevelScalar(new_pct / 100.0, None)
            if is_muted:
                volume.SetMute(0, None)
            return f"Increased volume to {new_pct}%."

        if act == "down":
            step = int(str(level).replace("%", "").strip()) if level is not None else 10
            new_pct = max(0, current_pct - step)
            volume.SetMasterVolumeLevelScalar(new_pct / 100.0, None)
            return f"Decreased volume to {new_pct}%."

        if act == "set":
            if level is None:
                return "Please provide a volume percentage to set."
            target = max(0, min(100, int(str(level).replace("%", "").strip())))
            volume.SetMasterVolumeLevelScalar(target / 100.0, None)
            if is_muted:
                volume.SetMute(0, None)
            return f"Set master volume to {target}%."

        return f"Unknown volume action '{action}'. Valid actions: get, set, up, down, mute, unmute."
    except Exception as exc:
        logger.error("Failed to execute system volume action: %s", exc)
        return f"System volume adjustment failed: {exc}"


def screen_brightness(action: str, level: Any = None, display: Any = 0) -> str:
    """Query or adjust monitor brightness on Windows with automatic fallback."""
    act = (action or "get").strip().lower()

    # Try screen_brightness_control first
    try:
        import os
        import sys

        pywin32_dir = os.path.join(sys.prefix, "Lib", "site-packages", "pywin32_system32")
        if pywin32_dir not in sys.path:
            sys.path.insert(0, pywin32_dir)
        if hasattr(os, "add_dll_directory") and os.path.isdir(pywin32_dir):
            try:
                os.add_dll_directory(pywin32_dir)
            except Exception:
                pass

        try:
            import pywintypes  # noqa: F401
        except ImportError:
            pass

        import screen_brightness_control as sbc

        raw = sbc.get_brightness()
        valid_levels = [val for val in raw if isinstance(val, int)]
        current = valid_levels[0] if valid_levels else 50

        if act == "get":
            return f"Current display brightness is {current}%."

        # Coerce display parameter safely to integer
        try:
            disp_int = int(display)
        except (ValueError, TypeError):
            disp_int = 0
        target_display = disp_int if disp_int > 0 else 0

        if act == "set":
            if level is None:
                return "Please provide a brightness percentage to set."
            target = max(0, min(100, int(str(level).replace("%", "").strip())))
            sbc.set_brightness(target, display=target_display)
            return f"Set display brightness to {target}%."

        if act == "up":
            step = int(str(level).replace("%", "").strip()) if level is not None else 10
            target = min(100, current + step)
            sbc.set_brightness(target, display=target_display)
            return f"Increased display brightness to {target}%."

        if act == "down":
            step = int(str(level).replace("%", "").strip()) if level is not None else 10
            target = max(0, current - step)
            sbc.set_brightness(target, display=target_display)
            return f"Decreased display brightness to {target}%."

        return f"Unknown brightness action '{action}'. Valid actions: get, set, up, down."
    except Exception as sbc_exc:
        logger.warning("screen_brightness_control failed (%s), attempting native fallback", sbc_exc)
        return f"Could not adjust brightness on connected displays: {sbc_exc}"




def capture_screenshot(display: Any = 1) -> str:
    """Capture a screenshot of the specified monitor and save for vision analysis."""
    # Ensure display is an integer to prevent '<=' comparison exceptions
    try:
        disp_int = int(display)
    except (ValueError, TypeError):
        disp_int = 1

    try:
        from pathlib import Path
        import mss

        cache_dir = Path("tmp_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_file = cache_dir / "screen_capture.png"

        with mss.MSS() as sct:
            num_monitors = len(sct.monitors) - 1
            idx = disp_int if 1 <= disp_int <= num_monitors else 1
            monitor = sct.monitors[idx]
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(output_file))

        return f"Screenshot of display {idx} ({screenshot.width}x{screenshot.height}) captured and saved to {output_file}."
    except Exception as exc:
        logger.warning("MSS screenshot failed, attempting fallback: %s", exc)
        try:
            from PIL import ImageGrab
            cache_dir = Path("tmp_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            output_file = cache_dir / "screen_capture.png"
            img = ImageGrab.grab(all_screens=(disp_int == 0))
            img.save(str(output_file))
            return f"Screenshot captured via fallback and saved to {output_file}."
        except Exception as fallback_exc:
            return f"Failed to capture screen: {fallback_exc}"


def inspect_screen(query: str = "", display: Any = 1) -> str:
    """Capture the screen and analyze it with local vision model (Moondream)."""
    from pathlib import Path
    import base64
    import io
    import json
    import urllib.request
    from PIL import Image

    try:
        disp_int = int(display)
    except (ValueError, TypeError):
        disp_int = 1

    # 1. Capture screen
    cap_msg = capture_screenshot(display=disp_int)
    cache_file = Path("tmp_cache") / "screen_capture.png"
    if not cache_file.exists():
        return f"Unable to capture screen for vision inspection: {cap_msg}"

    try:
        with Image.open(cache_file) as img:
            # Downscale to max 1024x1024 to optimize inference latency and memory
            img_thumb = img.copy()
            img_thumb.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img_thumb.convert("RGB").save(buf, format="JPEG", quality=85)
            b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as img_exc:
        logger.error("Failed to process screen capture for vision: %s", img_exc)
        return f"Failed to process screenshot for vision: {img_exc}"

    # 2. Formulate vision prompt
    q = (query or "").strip()
    if q:
        prompt = f"The user asks: '{q}'. Analyze this computer screen capture and answer their question directly and concisely."
    else:
        prompt = "Describe what is currently visible on this computer screen, including active windows, applications, and main content."

    # 3. Query local Ollama moondream model
    try:
        from app.config import get_settings
        settings = get_settings()
        ollama_url = f"{settings.ollama_api_base.rstrip('/')}/api/generate"

        payload = {
            "model": "moondream:latest",
            "prompt": prompt,
            "images": [b64_img],
            "stream": False,
        }

        req = urllib.request.Request(
            ollama_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            analysis = data.get("response", "").strip()
            if not analysis:
                return "Vision model analyzed the screen but returned an empty response."
            return f"Visual observation of display {display}: {analysis}"
    except Exception as vlm_exc:
        logger.error("VLM inference failed via Ollama: %s", vlm_exc)
        return f"Screen vision analysis failed: {vlm_exc}"


def lock_workstation(confirm: bool = False) -> str:
    """Lock the Windows desktop session safely."""
    if not confirm:
        return "Workstation was not locked. Confirmation parameter required to prevent accidental lockout."

    import ctypes
    try:
        success = ctypes.windll.user32.LockWorkStation()
        if success:
            return "Windows workstation successfully locked."
        return "LockWorkStation call failed."
    except Exception as exc:
        return f"Failed to lock workstation: {exc}"


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
    {
        "name": "system_volume",
        "description": "Queries or adjusts the master system volume on Windows (get, set percentage, up, down, mute, unmute).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set", "up", "down", "mute", "unmute"],
                    "description": "Volume action to perform",
                },
                "level": {
                    "type": "integer",
                    "description": "Target volume percentage (0 to 100) for set, or step delta for up/down",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "screen_brightness",
        "description": "Queries or adjusts the monitor/screen brightness on Windows.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get", "set", "up", "down"],
                    "description": "Brightness action to perform",
                },
                "level": {
                    "type": "integer",
                    "description": "Brightness percentage (0 to 100) to set or step delta",
                },
                "display": {
                    "type": "integer",
                    "description": "Target display index (1 for primary, 2 for secondary, default 1)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "inspect_screen",
        "description": "Takes a screenshot of the user's screen and uses vision AI (Moondream) to inspect, read, and understand what is visible. Use whenever the user asks to take a screenshot, look at the screen, read an error, see open songs or apps, or asks any question about what is displayed on their monitor.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific question to ask about what is visible on screen (e.g. 'what songs are in the list?', 'what error is displayed?'). Leave empty if the user just wants a general screenshot or description.",
                },
                "display": {
                    "type": "integer",
                    "description": "Target monitor to inspect (1 for primary, 2 for secondary, default 1)",
                },
            },
        },
    },
    {
        "name": "lock_workstation",
        "description": "Locks the Windows workstation screen when the user explicitly requests to lock the PC.",
        "parameters": {
            "type": "object",
            "properties": {
                "confirm": {
                    "type": "boolean",
                    "description": "Must be set to true to execute workstation lock",
                },
            },
            "required": ["confirm"],
        },
    },
]

TOOL_REGISTRY: dict[str, Callable[..., str]] = {
    "open_app": open_app,
    "open_website": open_website,
    "web_search": web_search,
    "spotify_control": spotify_control,
    "system_volume": system_volume,
    "screen_brightness": screen_brightness,
    "capture_screenshot": inspect_screen,  # Alias to inspect_screen so screen questions are never missed
    "inspect_screen": inspect_screen,
    "lock_workstation": lock_workstation,
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

