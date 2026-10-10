from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent import tools
from app.agent.llm_router import CompletionResult
from app.agent.memory import conversation_memory
from app.main import create_app


def test_open_app_allowed_whatsapp(monkeypatch):
    called = []
    monkeypatch.setattr(tools, "_launch_uri_or_fallback", lambda uri, fallback: called.append(uri))

    result = tools.open_app("whatsapp")
    assert "Successfully opened WhatsApp" in result
    assert called == ["whatsapp:"]


def test_open_app_allowed_vscode(monkeypatch):
    called = []
    monkeypatch.setattr(tools, "_launch_executable", lambda exe: called.append(exe))

    result = tools.open_app("vscode")
    assert "Successfully opened Visual Studio Code" in result
    assert called == ["code"]


def test_open_app_denies_unapproved_app():
    result = tools.open_app("powershell.exe")
    assert "Permission denied" in result
    assert "allowed applications list" in result


def test_open_website_valid_url(monkeypatch):
    opened = []
    monkeypatch.setattr(tools.webbrowser, "open", lambda url: opened.append(url))

    result = tools.open_website("https://example.com")
    assert "Opened website: https://example.com" in result
    assert opened == ["https://example.com"]


def test_open_website_rejects_invalid_scheme():
    result = tools.open_website("cmd.exe")
    assert "Invalid URL format" in result


def test_spotify_control_search(monkeypatch):
    called = []
    monkeypatch.setattr(tools.os, "startfile", lambda uri: called.append(uri))

    result = tools.spotify_control("play", query="daft punk")
    assert "daft punk" in result
    assert any("spotify:search:daft%20punk" in c for c in called)


def test_agent_chat_executes_tool_and_returns_action(monkeypatch):
    conversation_memory.clear()

    # Step 1: First LLM call emits a tool call
    # Step 2: Second LLM call after tool execution outputs natural language reply
    call_count = 0

    async def fake_get_completion(messages, tools=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Emits tool call
            return CompletionResult(
                value="",
                model_used="ollama/llama3.2:latest",
                tool_calls=[{"name": "open_app", "arguments": {"app_name": "whatsapp"}}],
            )
        else:
            # Final conversational confirmation
            return CompletionResult(
                value="I have opened WhatsApp for you.",
                model_used="ollama/llama3.2:latest",
            )

    monkeypatch.setattr("app.agent.graph.get_completion", fake_get_completion)
    monkeypatch.setattr(tools, "_launch_uri_or_fallback", lambda u, f: None)

    client = TestClient(create_app())
    response = client.post(
        "/agent/chat",
        json={"session_id": "test-tools-session", "message": "open whatsapp"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "I have opened WhatsApp for you."
    assert "Opened Whatsapp" in data["actions"]
