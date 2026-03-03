"""
ollama_router — Route @-aliased AI queries to a local Ollama instance.

Supported aliases (case-insensitive):
    @ollama, @copilot, @lucidia, @blackboxprogramming

All requests are sent directly to the local Ollama HTTP API.
No external providers (OpenAI, Anthropic, GitHub Copilot, etc.) are used.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

OLLAMA_BASE_URL: str = "http://localhost:11434"
DEFAULT_MODEL: str = "llama3"

# Every alias that should be intercepted and sent to Ollama
ALIAS_TRIGGERS: frozenset[str] = frozenset(
    {"@ollama", "@copilot", "@lucidia", "@blackboxprogramming"}
)

_ALIAS_RE = re.compile(
    r"(?i)(" + "|".join(re.escape(a) for a in ALIAS_TRIGGERS) + r")\b"
)


# ── Helpers ──────────────────────────────────────────────────────────

def detect_alias(text: str) -> bool:
    """Return True if *text* contains any of the routing aliases."""
    return bool(_ALIAS_RE.search(text))


def strip_alias(text: str) -> str:
    """Remove alias token(s) and normalise whitespace in the remaining text."""
    cleaned = _ALIAS_RE.sub("", text)
    return " ".join(cleaned.split())


# ── Ollama client ────────────────────────────────────────────────────

class OllamaClient:
    """Thin wrapper around the Ollama REST API (http://localhost:11434)."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- low-level -------------------------------------------------------

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    # -- generate (single-turn) ------------------------------------------

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> str:
        """Send a generation request and return the response text."""
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        logger.debug("ollama generate → model=%s prompt=%r", model, prompt[:120])
        data = self._post("/api/generate", payload)
        return data.get("response", "")

    # -- chat (multi-turn) -----------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> str:
        """Send a chat request and return the assistant reply text."""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        logger.debug(
            "ollama chat → model=%s messages=%d", model, len(messages)
        )
        data = self._post("/api/chat", payload)
        return data.get("message", {}).get("content", "")

    # -- list available models -------------------------------------------

    def list_models(self) -> List[str]:
        """Return model names available on the local Ollama server."""
        url = f"{self.base_url}/api/tags"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return [m["name"] for m in response.json().get("models", [])]


# ── Public routing entry-point ───────────────────────────────────────

def route_query(
    text: str,
    model: str = DEFAULT_MODEL,
    system: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    client: Optional[OllamaClient] = None,
) -> Dict[str, Any]:
    """
    Route *text* to Ollama if it contains a recognised alias.

    Parameters
    ----------
    text    : The raw user message (may include @alias prefix).
    model   : Ollama model name to use.
    system  : Optional system prompt injected before the conversation.
    history : Prior conversation turns [{"role": ..., "content": ...}, ...].
    client  : Optional pre-constructed OllamaClient (useful for testing).

    Returns
    -------
    dict with keys:
        routed   – bool, True when the message was forwarded to Ollama
        alias    – the matched alias token (or None)
        response – Ollama reply text (or None if not routed)
        model    – model used (or None if not routed)
    """
    match = _ALIAS_RE.search(text)
    if not match:
        return {"routed": False, "alias": None, "response": None, "model": None}

    alias = match.group(1).lower()
    clean_text = strip_alias(text)

    _client = client or OllamaClient()

    messages: List[Dict[str, str]] = list(history or [])
    messages.append({"role": "user", "content": clean_text})

    logger.info(
        "Routing alias=%r to Ollama model=%s  query=%r", alias, model, clean_text[:80]
    )

    reply = _client.chat(messages=messages, model=model, system=system)

    return {
        "routed": True,
        "alias": alias,
        "response": reply,
        "model": model,
    }
