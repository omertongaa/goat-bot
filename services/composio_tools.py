"""Composio tool discovery + execution.

Bridge between agents and the user's connected SaaS apps. When the user has
connected Gmail/Slack/etc via /apps, this service:
    1. Lists the active connections for a company (user_id)
    2. Fetches tools for those toolkits via Composio v3 REST API
    3. Converts tool schemas to Anthropic tool-use format
    4. Executes tool calls when the model emits a tool_use block

Usage from CEO:
    from services import composio_tools as ct
    tools = ct.tools_for_anthropic(user_id="default", per_toolkit=8)
    # pass tools=... to anthropic.Anthropic().messages.create()
    # on tool_use, call ct.execute_tool(slug, user_id, arguments)
"""

import os
from typing import Optional

import requests

COMPOSIO_API = "https://backend.composio.dev/api/v3"
TIMEOUT = 30
DEFAULT_PER_TOOLKIT = 8     # cap tools per connection so context stays small
MAX_TOTAL_TOOLS = 40        # absolute cap for one chat call


def _headers() -> dict:
    return {"x-api-key": os.getenv("COMPOSIO_API_KEY", "").strip(),
            "Content-Type": "application/json"}


def _has_key() -> bool:
    return bool(os.getenv("COMPOSIO_API_KEY", "").strip())


def list_connected_toolkits(user_id: str) -> list:
    """Return slugs of toolkits with ACTIVE connections for this user."""
    if not _has_key() or not user_id:
        return []
    try:
        r = requests.get(
            f"{COMPOSIO_API}/connected_accounts",
            params={"user_ids": user_id, "limit": 100},
            headers=_headers(), timeout=TIMEOUT,
        )
        if not r.ok:
            return []
        out = []
        for it in r.json().get("items", []):
            status = (it.get("status") or "").upper()
            if status != "ACTIVE":
                continue
            tk = it.get("toolkit") or {}
            slug = tk.get("slug")
            if slug and slug not in out:
                out.append(slug)
        return out
    except Exception:
        return []


def list_tools_for_toolkit(toolkit_slug: str, limit: int = DEFAULT_PER_TOOLKIT) -> list:
    """Fetch tool schemas for a toolkit. Returns list of tool dicts with
    slug + name + description + input_parameters (JSON schema)."""
    if not _has_key():
        return []
    try:
        r = requests.get(
            f"{COMPOSIO_API}/tools",
            params={"toolkit_slug": toolkit_slug, "limit": limit},
            headers=_headers(), timeout=TIMEOUT,
        )
        if not r.ok:
            return []
        return r.json().get("items", [])
    except Exception:
        return []


def tools_for_anthropic(user_id: str, per_toolkit: int = DEFAULT_PER_TOOLKIT) -> list:
    """Build the `tools=` payload for Anthropic API based on user's active connections."""
    toolkits = list_connected_toolkits(user_id)
    if not toolkits:
        return []
    out = []
    for slug in toolkits:
        for t in list_tools_for_toolkit(slug, limit=per_toolkit):
            spec = _to_anthropic_tool(t)
            if spec:
                out.append(spec)
            if len(out) >= MAX_TOTAL_TOOLS:
                return out
    return out


def _to_anthropic_tool(t: dict) -> Optional[dict]:
    """Map a Composio tool descriptor to Anthropic tool-use spec."""
    slug = t.get("slug")
    if not slug:
        return None
    description = (t.get("description") or t.get("name") or slug)[:512]
    input_schema = t.get("input_parameters") or {"type": "object", "properties": {}}
    # Anthropic requires top-level type=object
    if input_schema.get("type") != "object":
        input_schema = {"type": "object", "properties": {}, "additionalProperties": True}
    # Anthropic tool name pattern: ^[a-zA-Z0-9_-]{1,128}$ — Composio slugs match
    return {
        "name": slug,
        "description": description,
        "input_schema": input_schema,
    }


def execute_tool(slug: str, user_id: str, arguments: dict) -> dict:
    """Execute a Composio tool. Returns {ok, data|error}."""
    if not _has_key():
        return {"ok": False, "error": "COMPOSIO_API_KEY not configured"}
    try:
        r = requests.post(
            f"{COMPOSIO_API}/tools/execute/{slug}",
            headers=_headers(),
            json={"user_id": user_id, "arguments": arguments or {}},
            timeout=TIMEOUT,
        )
        if not r.ok:
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
        data = r.json()
        # Composio response shape: {data, successful, error}
        if data.get("successful") is False:
            return {"ok": False, "error": data.get("error") or "Tool execution failed",
                    "data": data.get("data")}
        return {"ok": True, "data": data.get("data") or data}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
