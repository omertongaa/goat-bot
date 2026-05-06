"""Ollama local model integration.

Free path for users without an Anthropic API key. Talks to local
Ollama daemon (default localhost:11434) over HTTP, supports chat &
generate endpoints.

Recommended models for goat-bot tasks:
    - llama3.1:8b     — general planning + Turkish OK
    - qwen2.5:7b      — strong reasoning, multi-language
    - phi3:mini       — ultra-fast, low memory (lead scoring, classification)
    - mistral:latest  — alternative general

Pull a model once:  ollama pull llama3.1:8b
"""

import os
from typing import Optional

import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))


def is_available() -> bool:
    """Quick TCP-level health check."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list:
    """Return [{name, size_gb, modified}] for installed models."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code != 200:
            return []
        models = (r.json() or {}).get("models", [])
        return [{
            "name": m.get("name"),
            "size_gb": round((m.get("size") or 0) / 1e9, 2),
            "family": (m.get("details") or {}).get("family"),
            "params": (m.get("details") or {}).get("parameter_size"),
            "modified": m.get("modified_at"),
        } for m in models]
    except Exception:
        return []


def default_model() -> str:
    """Pick a sensible default — env override or first installed model."""
    if DEFAULT_MODEL:
        names = [m["name"] for m in list_models()]
        if DEFAULT_MODEL in names:
            return DEFAULT_MODEL
    models = list_models()
    return models[0]["name"] if models else DEFAULT_MODEL


def pull(model: str) -> dict:
    """Trigger model download (long-running)."""
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/pull",
            json={"name": model, "stream": False},
            timeout=600,
        )
        return {"ok": r.status_code == 200, "model": model, "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": model}


def chat(
    model: Optional[str] = None,
    messages: Optional[list] = None,
    system: str = "",
    max_tokens: int = 1500,
) -> str:
    """Chat completion. Returns response text only."""
    model = model or default_model()
    msgs = list(messages or [])
    if system:
        msgs = [{"role": "system", "content": system}] + msgs
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": msgs,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.7},
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return ""
        return ((r.json() or {}).get("message") or {}).get("content", "").strip()
    except Exception:
        return ""


def generate(model: Optional[str], prompt: str, system: str = "", max_tokens: int = 1500) -> str:
    """Single-shot completion (no chat history)."""
    model = model or default_model()
    try:
        r = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.7},
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return ""
        return (r.json() or {}).get("response", "").strip()
    except Exception:
        return ""


def status() -> dict:
    """Health summary for /api/ollama/status panel."""
    return {
        "host": OLLAMA_HOST,
        "available": is_available(),
        "default_model": DEFAULT_MODEL,
        "installed": list_models() if is_available() else [],
    }
