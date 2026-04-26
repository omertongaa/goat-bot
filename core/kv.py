"""Upstash Redis REST client (no SDK).

Activates when UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN are set.
Used by core.store as the durable backend on Vercel where /tmp is ephemeral.

Free tier on upstash.com: 10K commands/day, 256MB. More than enough for goat.

Get yours: https://console.upstash.com/redis → Create database → REST API tab
Set in .env or Vercel env:
    UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
    UPSTASH_REDIS_REST_TOKEN=AY...
"""

import json
import os
from typing import Any, Optional

import requests

REQUEST_TIMEOUT = 10
KEY_PREFIX = "goat:"


def _url() -> str:
    return os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.getenv('UPSTASH_REDIS_REST_TOKEN', '')}"}


def is_enabled() -> bool:
    return bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))


def _post(commands: list) -> Any:
    """Execute one or many Redis commands via Upstash pipeline endpoint.
    Returns the first command's result for a single command, or list for batch."""
    if not is_enabled():
        return None
    if not commands:
        return None
    is_batch = isinstance(commands[0], list)
    body = commands if is_batch else [commands]
    try:
        r = requests.post(
            f"{_url()}/pipeline",
            headers={**_headers(), "Content-Type": "application/json"},
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        if not r.ok:
            return None if not is_batch else [None] * len(body)
        results = [item.get("result") for item in r.json()]
        return results if is_batch else results[0]
    except Exception:
        return None if not is_batch else [None] * len(body)


# ── String set / get ───────────────────────────────────────────────

def set_json(key: str, value: Any) -> bool:
    payload = json.dumps(value, ensure_ascii=False)
    res = _post(["SET", KEY_PREFIX + key, payload])
    return res == "OK"


def get_json(key: str, default: Any = None) -> Any:
    res = _post(["GET", KEY_PREFIX + key])
    if res is None:
        return default
    try:
        return json.loads(res)
    except Exception:
        return default


def delete(key: str) -> bool:
    res = _post(["DEL", KEY_PREFIX + key])
    return bool(res)


# ── Set operations (for tracking IDs) ──────────────────────────────

def sadd(key: str, *members: str) -> int:
    if not members:
        return 0
    res = _post(["SADD", KEY_PREFIX + key, *members])
    return int(res or 0)


def smembers(key: str) -> list:
    res = _post(["SMEMBERS", KEY_PREFIX + key])
    return list(res or [])


def srem(key: str, *members: str) -> int:
    if not members:
        return 0
    res = _post(["SREM", KEY_PREFIX + key, *members])
    return int(res or 0)


# ── List operations (for activity log) ─────────────────────────────

def rpush_json(key: str, value: Any) -> int:
    res = _post(["RPUSH", KEY_PREFIX + key, json.dumps(value, ensure_ascii=False)])
    return int(res or 0)


def lrange_json(key: str, start: int = 0, stop: int = -1) -> list:
    res = _post(["LRANGE", KEY_PREFIX + key, str(start), str(stop)])
    if not res:
        return []
    out = []
    for item in res:
        try:
            out.append(json.loads(item))
        except Exception:
            continue
    return out


def ltrim(key: str, start: int, stop: int) -> bool:
    res = _post(["LTRIM", KEY_PREFIX + key, str(start), str(stop)])
    return res == "OK"


def llen(key: str) -> int:
    res = _post(["LLEN", KEY_PREFIX + key])
    return int(res or 0)


# ── Bulk fetch helper ──────────────────────────────────────────────

def mget_json(keys: list) -> list:
    """Fetch many JSON values in one request. Returns list parallel to keys
    with None for missing/invalid entries."""
    if not keys:
        return []
    cmds = [["GET", KEY_PREFIX + k] for k in keys]
    res = _post(cmds)
    if not res:
        return [None] * len(keys)
    out = []
    for item in res:
        if item is None:
            out.append(None)
            continue
        try:
            out.append(json.loads(item))
        except Exception:
            out.append(None)
    return out
