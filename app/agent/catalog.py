"""
Integration and Application Catalog for Rufus.
Defines known applications, detection signatures on Windows, and capabilities.
"""
from typing import TypedDict, Literal

class DetectionRules(TypedDict, total=False):
    uri_schemes: list[str]
    executable_names: list[str]
    app_path_names: list[str]
    start_menu_names: list[str]
    registry_display_names: list[str]

class IntegrationDefinition(TypedDict):
    id: str
    display_name: str
    category: str
    type: Literal["os_action", "mcp_stdio", "web_service"]
    detection: DetectionRules
    capabilities: list[str]
    description: str
    default_uri: str | None
    default_command: str | None

INTEGRATIONS_CATALOG: list[IntegrationDefinition] = [
    {
        "id": "whatsapp",
        "display_name": "WhatsApp",
        "category": "communication",
        "type": "os_action",
        "detection": {
            "uri_schemes": ["whatsapp"],
            "start_menu_names": ["WhatsApp", "WhatsApp Beta"],
            "executable_names": ["WhatsApp.exe"],
        },
        "capabilities": ["open", "send_message", "summarize_chat"],
        "description": "Desktop instant messaging and communication.",
        "default_uri": "whatsapp:",
        "default_command": None,
    },
    {
        "id": "vscode",
        "display_name": "Visual Studio Code",
        "category": "development",
        "type": "os_action",
        "detection": {
            "uri_schemes": ["vscode"],
            "executable_names": ["code.cmd", "code.exe", "code"],
            "start_menu_names": ["Visual Studio Code"],
            "registry_display_names": ["Microsoft Visual Studio Code"],
        },
        "capabilities": ["open", "open_workspace", "read_diagnostics"],
        "description": "Code editor and developer environment.",
        "default_uri": None,
        "default_command": "code",
    },
    {
        "id": "antigravity",
        "display_name": "Antigravity",
        "category": "development",
        "type": "os_action",
        "detection": {
            "uri_schemes": ["antigravity"],
            "start_menu_names": ["Antigravity"],
            "executable_names": ["antigravity.exe", "antigravity"],
        },
        "capabilities": ["open", "pair_program"],
        "description": "Google DeepMind agentic AI coding workspace.",
        "default_uri": "antigravity:",
        "default_command": "antigravity",
    },
    {
        "id": "spotify",
        "display_name": "Spotify",
        "category": "media",
        "type": "os_action",
        "detection": {
            "uri_schemes": ["spotify"],
            "start_menu_names": ["Spotify"],
            "executable_names": ["Spotify.exe"],
        },
        "capabilities": ["open", "play", "pause", "search_music"],
        "description": "Digital music and podcast streaming service.",
        "default_uri": "spotify:",
        "default_command": None,
    },
    {
        "id": "chrome",
        "display_name": "Google Chrome",
        "category": "browser",
        "type": "os_action",
        "detection": {
            "app_path_names": ["chrome.exe"],
            "start_menu_names": ["Google Chrome"],
            "executable_names": ["chrome.exe", "chrome"],
            "registry_display_names": ["Google Chrome"],
        },
        "capabilities": ["open", "browse_url", "web_search"],
        "description": "Fast and secure web browser by Google.",
        "default_uri": None,
        "default_command": "chrome.exe",
    },
    {
        "id": "brave",
        "display_name": "Brave Browser",
        "category": "browser",
        "type": "os_action",
        "detection": {
            "app_path_names": ["brave.exe"],
            "start_menu_names": ["Brave"],
            "executable_names": ["brave.exe"],
        },
        "capabilities": ["open", "browse_url"],
        "description": "Privacy-focused web browser.",
        "default_uri": None,
        "default_command": "brave.exe",
    },
    {
        "id": "discord",
        "display_name": "Discord",
        "category": "communication",
        "type": "os_action",
        "detection": {
            "uri_schemes": ["discord"],
            "start_menu_names": ["Discord"],
            "executable_names": ["Discord.exe"],
        },
        "capabilities": ["open", "voice_chat"],
        "description": "Voice, video, and text communication service.",
        "default_uri": "discord:",
        "default_command": None,
    },
    {
        "id": "telegram",
        "display_name": "Telegram",
        "category": "communication",
        "type": "os_action",
        "detection": {
            "uri_schemes": ["tg"],
            "start_menu_names": ["Telegram Desktop", "Telegram"],
            "executable_names": ["Telegram.exe"],
        },
        "capabilities": ["open", "send_message"],
        "description": "Encrypted cloud-based mobile and desktop messaging.",
        "default_uri": "tg:",
        "default_command": None,
    },
    {
        "id": "arduino",
        "display_name": "Arduino IDE",
        "category": "robotics",
        "type": "os_action",
        "detection": {
            "start_menu_names": ["Arduino IDE"],
            "executable_names": ["arduino.exe"],
        },
        "capabilities": ["open", "firmware_flash"],
        "description": "Integrated development environment for ESP32 and Arduino firmware.",
        "default_uri": None,
        "default_command": "arduino.exe",
    },
    {
        "id": "canva",
        "display_name": "Canva",
        "category": "design",
        "type": "os_action",
        "detection": {
            "start_menu_names": ["Canva"],
            "executable_names": ["Canva.exe"],
        },
        "capabilities": ["open"],
        "description": "Visual design and content creation workspace.",
        "default_uri": None,
        "default_command": "Canva.exe",
    },
    {
        "id": "docker",
        "display_name": "Docker Desktop",
        "category": "development",
        "type": "os_action",
        "detection": {
            "app_path_names": ["Docker Desktop.exe"],
            "start_menu_names": ["Docker Desktop"],
            "executable_names": ["docker.exe", "docker"],
        },
        "capabilities": ["open", "inspect_containers"],
        "description": "Container virtualization and local microservice management.",
        "default_uri": None,
        "default_command": "Docker Desktop.exe",
    },
    {
        "id": "ollama",
        "display_name": "Ollama",
        "category": "ai",
        "type": "os_action",
        "detection": {
            "start_menu_names": ["Ollama"],
            "executable_names": ["ollama.exe", "ollama"],
        },
        "capabilities": ["open", "local_inference"],
        "description": "Local large language model server running Llama and Moondream.",
        "default_uri": None,
        "default_command": "ollama.exe",
    },
    {
        "id": "notepad",
        "display_name": "Notepad",
        "category": "productivity",
        "type": "os_action",
        "detection": {
            "start_menu_names": ["Notepad"],
            "executable_names": ["notepad.exe"],
        },
        "capabilities": ["open", "take_notes"],
        "description": "Lightweight text editor.",
        "default_uri": None,
        "default_command": "notepad.exe",
    },
    {
        "id": "explorer",
        "display_name": "File Explorer",
        "category": "system",
        "type": "os_action",
        "detection": {
            "start_menu_names": ["File Explorer"],
            "executable_names": ["explorer.exe"],
        },
        "capabilities": ["open", "navigate_directory"],
        "description": "Windows native file manager.",
        "default_uri": None,
        "default_command": "explorer.exe",
    },
]
