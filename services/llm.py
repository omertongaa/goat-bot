"""Unified LLM completion interface with provider waterfall.

Agents call `complete(messages, task='cheap')`. The router picks the
best available provider in this order:

    cheap/fast → Ollama (if configured) → Anthropic Haiku → Claude CLI
    smart      → Anthropic Sonnet → Claude CLI → Ollama (if no API key)
    local      → Ollama only (force)

Each agent can override per-call. Cost is auto-recorded into the active
ticket via cost_tracker.

Why this exists:
    - Ücretsiz path: kullanıcının Anthropic key'i yoksa Ollama'ya
      düşülsün, sistem yine de çalışsın.
    - Progresif upgrade: aynı prompt aynı sonucu döndürebilsin.
"""

import json
import os
import subprocess
from typing import Optional

from core import cost_tracker


# Task → preferred providers (first that's available wins)
TASK_PREFERENCES = {
    "cheap": ["anthropic.haiku", "ollama", "claude_cli"],
    "smart": ["anthropic.sonnet", "claude_cli", "ollama"],
    "local": ["ollama"],
    "fast": ["ollama", "anthropic.haiku", "claude_cli"],
    "default": ["anthropic.haiku", "ollama", "claude_cli"],
}


def complete(
    messages: list,
    task: str = "default",
    system: str = "",
    max_tokens: int = 1500,
    force_provider: Optional[str] = None,
) -> dict:
    """Returns {text, provider, error?}."""
    chain = [force_provider] if force_provider else TASK_PREFERENCES.get(task, TASK_PREFERENCES["default"])
    last_error = ""
    for prov in chain:
        if not prov:
            continue
        try:
            handler = _PROVIDERS.get(prov)
            if not handler:
                continue
            result = handler(messages, system, max_tokens)
            if result.get("text"):
                return {**result, "provider": prov}
            last_error = result.get("error", "")
        except Exception as e:
            last_error = f"{prov}: {type(e).__name__}: {e}"
            continue
    return {"text": "", "provider": "none", "error": last_error or "no provider available"}


def _via_anthropic(messages: list, system: str, max_tokens: int, model: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY missing"}
    try:
        import anthropic
    except Exception:
        return {"error": "anthropic SDK missing"}
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or "Sen yardımcı bir asistansın.",
        messages=messages,
    )
    usage = getattr(msg, "usage", None)
    if usage:
        cost_tracker.record("claude.token_in", units=getattr(usage, "input_tokens", 0))
        cost_tracker.record("claude.token_out", units=getattr(usage, "output_tokens", 0))
    text = msg.content[0].text if msg.content else ""
    return {"text": text, "model": model}


def _via_haiku(messages, system, max_tokens):
    return _via_anthropic(messages, system, max_tokens, "claude-haiku-4-5-20251001")


def _via_sonnet(messages, system, max_tokens):
    return _via_anthropic(messages, system, max_tokens, "claude-sonnet-4-6")


def _via_claude_cli(messages: list, system: str, max_tokens: int) -> dict:
    """Subprocess to local `claude` CLI (free if user has Claude.ai sub)."""
    try:
        prompt = ((system + "\n\n") if system else "") + _flatten(messages)
        proc = subprocess.run(
            ["claude", "--print", "--output-format", "text"],
            input=prompt.encode(),
            capture_output=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return {"error": f"claude cli rc={proc.returncode}: {proc.stderr.decode()[:200]}"}
        return {"text": proc.stdout.decode().strip()}
    except FileNotFoundError:
        return {"error": "claude CLI not installed"}
    except subprocess.TimeoutExpired:
        return {"error": "claude CLI timeout"}


def _via_ollama(messages: list, system: str, max_tokens: int) -> dict:
    from services import ollama as _o
    if not _o.is_available():
        return {"error": "ollama not running (default localhost:11434)"}
    model = os.getenv("OLLAMA_MODEL") or _o.default_model()
    text = _o.chat(model=model, messages=messages, system=system, max_tokens=max_tokens)
    if not text:
        return {"error": "ollama returned empty"}
    cost_tracker.record("ollama.run", units=1.0)
    return {"text": text, "model": model}


def _flatten(messages: list) -> str:
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
        out.append(f"{role.upper()}: {content}")
    return "\n\n".join(out)


_PROVIDERS = {
    "anthropic.haiku": _via_haiku,
    "anthropic.sonnet": _via_sonnet,
    "claude_cli": _via_claude_cli,
    "ollama": _via_ollama,
}


def available_providers() -> dict:
    """Quick health check — what can we actually call right now?"""
    out = {}
    out["anthropic"] = bool(os.getenv("ANTHROPIC_API_KEY"))
    try:
        proc = subprocess.run(["claude", "--version"], capture_output=True, timeout=3)
        out["claude_cli"] = proc.returncode == 0
    except Exception:
        out["claude_cli"] = False
    try:
        from services import ollama as _o
        out["ollama"] = _o.is_available()
    except Exception:
        out["ollama"] = False
    return out
