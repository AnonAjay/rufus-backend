"""
Unit tests verifying all Rufus end-to-end benchmark product fixes.
Tests:
1. Tool argument coercion & validation (string to int, aliases, clamping).
2. App allowlist & rejection of unresolvable apps (no explorer fallback).
3. Confirmation gate for high-impact tools (WhatsApp send, lock).
4. Tier 2 Action-Intent Gating & ModernBERT router calibration.
5. Tier 3 Domain Tool Scoping.
"""
import pytest
from app.agent.graph import (
    coerce_and_validate_tool_args,
    scope_tools_for_query,
    get_system_prompt,
    CONFIRMATION_REQUIRED_TOOLS,
)
from app.agent.laya_router import classify_intent
from app.agent.tools import execute_tool, APP_ALLOWLIST, TOOL_DEFINITIONS


# --- Test 1: Tool Argument Coercion & Clamping ---
def test_system_volume_arg_coercion():
    # String integer "65"
    args, err = coerce_and_validate_tool_args("system_volume", {"action": "set", "level": "65"})
    assert err is None
    assert args["level"] == 65
    assert isinstance(args["level"], int)

    # Alias "value" -> "level"
    args, err = coerce_and_validate_tool_args("system_volume", {"action": "set", "value": "40"})
    assert err is None
    assert args["level"] == 40

    # Percentage string "80%"
    args, err = coerce_and_validate_tool_args("system_volume", {"action": "set", "level": "80%"})
    assert err is None
    assert args["level"] == 80

    # Clamping > 100
    args, err = coerce_and_validate_tool_args("system_volume", {"action": "set", "level": 150})
    assert err is None
    assert args["level"] == 100

    # Clamping < 0
    args, err = coerce_and_validate_tool_args("system_volume", {"action": "set", "level": -20})
    assert err is None
    assert args["level"] == 0

    # Non-numeric garbage returns clarification
    args, err = coerce_and_validate_tool_args("system_volume", {"action": "set", "level": "high"})
    assert args == {}
    assert "number between 0 and 100" in err


# --- Test 2: App Allowlist & Silent Fallback Removal ---
def test_open_app_allowlist_and_rejection():
    assert "calculator" in APP_ALLOWLIST
    assert "calc" in APP_ALLOWLIST
    assert "notepad" in APP_ALLOWLIST

    # Unresolvable app should return error, NOT fallback to explorer
    res = execute_tool("open_app", {"app_name": "non_existent_fake_app_xyz"})
    assert "not recognized" in res.lower() or "not installed" in res.lower() or "blocked" in res.lower()
    assert "successfully opened" not in res.lower()


# --- Test 3: Tier 2 Action-Intent Gating & Chit-chat Protection ---
def test_chitchat_routed_to_speech():
    for text in ["Hi Rufus!", "Good morning", "Tell me a joke", "How was your day?", "I am feeling tired"]:
        res = classify_intent(text)
        assert res["action_type"] == "speech", f"Failed for '{text}': got {res['action_type']}"


def test_near_miss_traps_routed_to_speech():
    traps = [
        "Explain Spotify's recommendation algorithm",
        "How does volume normalization work?",
        "What is WhatsApp's encryption protocol?",
        "How do vision-language models process screenshot patches into image embeddings?",
    ]
    for text in traps:
        res = classify_intent(text)
        assert res["action_type"] == "speech", f"Failed for trap '{text}': got {res['action_type']}"


def test_action_and_hinglish_routed_to_action():
    actions = [
        "set volume to 65",
        "mute the volume",
        "launch calculator",
        "open notepad",
        "Search online for the current weather in Paris today",
        "Gaane ki aawaz thodi kam kar do",
        "Speaker ki aawaz thodi badha do",
        "Mera notepad khol do kuch note karna hai",
    ]
    for text in actions:
        res = classify_intent(text)
        assert res["action_type"] == "action", f"Failed for action '{text}': got {res['action_type']}"


# --- Test 4: Tier 3 Domain Tool Scoping ---
def test_scoped_tools_for_query():
    def _name(t):
        return t.get("name") or t.get("function", {}).get("name")

    # Volume query should only get system controls
    tools = scope_tools_for_query("set volume to 65", TOOL_DEFINITIONS)
    tool_names = {_name(t) for t in tools}
    assert "system_volume" in tool_names
    assert "whatsapp_send_message" not in tool_names
    assert "inspect_screen" not in tool_names

    # App launch query should only get app launcher
    tools = scope_tools_for_query("open calculator", TOOL_DEFINITIONS)
    tool_names = {_name(t) for t in tools}
    assert "open_app" in tool_names
    assert "system_volume" not in tool_names
    assert "whatsapp_send_message" not in tool_names

    # Weather/search should only get observation tools
    tools = scope_tools_for_query("what is the weather in Tokyo", TOOL_DEFINITIONS)
    tool_names = {_name(t) for t in tools}
    assert "web_search" in tool_names
    assert "system_volume" not in tool_names


# --- Test 5: Clean System Prompt in Chat Mode ---
def test_clean_chat_prompt_omits_tools():
    chat_prompt = get_system_prompt("companion", include_tools=False)
    assert "whatsapp" not in chat_prompt.lower()
    assert "inspect_screen" not in chat_prompt.lower()
    assert "tools to open" not in chat_prompt.lower()

    action_prompt = get_system_prompt("companion", include_tools=True)
    assert "whatsapp" in action_prompt.lower()
    assert "inspect_screen" in action_prompt.lower()


# --- Test 6: Confirmation Gate Set ---
def test_confirmation_required_tools():
    assert "whatsapp_send_message" in CONFIRMATION_REQUIRED_TOOLS
    assert "lock_workstation" in CONFIRMATION_REQUIRED_TOOLS
    assert "system_volume" not in CONFIRMATION_REQUIRED_TOOLS
    assert "open_app" not in CONFIRMATION_REQUIRED_TOOLS
