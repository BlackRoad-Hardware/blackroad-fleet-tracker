"""Tests for ollama_router — alias detection and Ollama routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ollama_router import (
    ALIAS_TRIGGERS,
    OllamaClient,
    detect_alias,
    route_query,
    strip_alias,
)


# ── detect_alias ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "@ollama what is the weather?",
    "@copilot write me a function",
    "@lucidia summarise the fleet report",
    "@blackboxprogramming fix this bug",
    "Hey @ollama, help me out",
    "Use @COPILOT please",          # case-insensitive
    "ping @Lucidia",
    "@BlackboxProgramming do this",
])
def test_detect_alias_true(text):
    assert detect_alias(text) is True


@pytest.mark.parametrize("text", [
    "what is the weather?",
    "write me a function",
    "fleet status check",
    "@unknown_bot query",
    "",
])
def test_detect_alias_false(text):
    assert detect_alias(text) is False


def test_alias_triggers_contains_all():
    expected = {"@ollama", "@copilot", "@lucidia", "@blackboxprogramming"}
    assert expected == set(ALIAS_TRIGGERS)


# ── strip_alias ──────────────────────────────────────────────────────

def test_strip_alias_removes_prefix():
    assert strip_alias("@ollama tell me about geofencing") == "tell me about geofencing"


def test_strip_alias_removes_inline():
    assert strip_alias("ping @copilot please") == "ping please"


def test_strip_alias_no_alias_unchanged():
    assert strip_alias("plain text") == "plain text"


# ── OllamaClient.generate ────────────────────────────────────────────

def test_ollama_client_generate_calls_correct_endpoint():
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "hello from ollama"}
    mock_response.raise_for_status = MagicMock()

    with patch("ollama_router.requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient(base_url="http://localhost:11434")
        result = client.generate("tell me something", model="llama3")

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "http://localhost:11434/api/generate"
    assert call_args[1]["json"]["prompt"] == "tell me something"
    assert call_args[1]["json"]["model"] == "llama3"
    assert result == "hello from ollama"


def test_ollama_client_generate_with_system_prompt():
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "fleet answer"}
    mock_response.raise_for_status = MagicMock()

    with patch("ollama_router.requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient()
        client.generate("query", model="llama3", system="You are a fleet assistant.")

    payload = mock_post.call_args[1]["json"]
    assert payload["system"] == "You are a fleet assistant."


# ── OllamaClient.chat ────────────────────────────────────────────────

def test_ollama_client_chat_calls_correct_endpoint():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "chat reply"}
    }
    mock_response.raise_for_status = MagicMock()

    messages = [{"role": "user", "content": "hello"}]

    with patch("ollama_router.requests.post", return_value=mock_response) as mock_post:
        client = OllamaClient(base_url="http://localhost:11434")
        result = client.chat(messages=messages, model="llama3")

    call_args = mock_post.call_args
    assert call_args[0][0] == "http://localhost:11434/api/chat"
    assert call_args[1]["json"]["messages"] == messages
    assert result == "chat reply"


def test_ollama_client_chat_missing_content_returns_empty():
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()

    with patch("ollama_router.requests.post", return_value=mock_response):
        client = OllamaClient()
        result = client.chat(messages=[], model="llama3")

    assert result == ""


# ── OllamaClient.list_models ─────────────────────────────────────────

def test_ollama_client_list_models():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [{"name": "llama3"}, {"name": "mistral"}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("ollama_router.requests.get", return_value=mock_response):
        client = OllamaClient()
        models = client.list_models()

    assert models == ["llama3", "mistral"]


# ── route_query ──────────────────────────────────────────────────────

def _make_mock_client(reply: str = "ollama says hi") -> OllamaClient:
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.chat.return_value = reply
    return mock_client


@pytest.mark.parametrize("alias", [
    "@ollama", "@copilot", "@lucidia", "@blackboxprogramming",
])
def test_route_query_all_aliases_route_to_ollama(alias):
    mock_client = _make_mock_client("fleet data response")
    result = route_query(f"{alias} show fleet status", client=mock_client)

    assert result["routed"] is True
    assert result["alias"] == alias.lower()
    assert result["response"] == "fleet data response"
    assert result["model"] is not None
    mock_client.chat.assert_called_once()


def test_route_query_no_alias_not_routed():
    mock_client = _make_mock_client()
    result = route_query("show fleet status", client=mock_client)

    assert result["routed"] is False
    assert result["alias"] is None
    assert result["response"] is None
    mock_client.chat.assert_not_called()


def test_route_query_strips_alias_before_sending():
    mock_client = _make_mock_client("response")
    route_query("@ollama tell me about idle trucks", client=mock_client)

    call_messages = mock_client.chat.call_args[1]["messages"]
    user_content = next(m["content"] for m in call_messages if m["role"] == "user")
    assert "@ollama" not in user_content
    assert "tell me about idle trucks" in user_content


def test_route_query_includes_history():
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    mock_client = _make_mock_client("here is the fleet data")
    route_query("@copilot list assets", history=history, client=mock_client)

    call_messages = mock_client.chat.call_args[1]["messages"]
    assert call_messages[0] == history[0]
    assert call_messages[1] == history[1]
    assert call_messages[2]["role"] == "user"


def test_route_query_passes_model():
    mock_client = _make_mock_client()
    result = route_query("@ollama query", model="mistral", client=mock_client)

    assert result["model"] == "mistral"
    mock_client.chat.assert_called_once_with(
        messages=mock_client.chat.call_args[1]["messages"],
        model="mistral",
        system=None,
    )


def test_route_query_passes_system_prompt():
    mock_client = _make_mock_client()
    route_query("@lucidia query", system="You manage a fleet.", client=mock_client)

    mock_client.chat.assert_called_once_with(
        messages=mock_client.chat.call_args[1]["messages"],
        model=mock_client.chat.call_args[1]["model"],
        system="You manage a fleet.",
    )


def test_route_query_case_insensitive_alias():
    mock_client = _make_mock_client()
    result = route_query("@COPILOT do something", client=mock_client)

    assert result["routed"] is True
    assert result["alias"] == "@copilot"


def test_route_query_no_external_http_without_client():
    """route_query must not make any real HTTP calls when alias is absent."""
    with patch("ollama_router.requests.post") as mock_post:
        route_query("plain query with no alias")
    mock_post.assert_not_called()
