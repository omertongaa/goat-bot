"""Telegram approval bot.

When a ticket goes to needs_review, push a message with [✅ Approve] /
[❌ Reject] inline buttons. User taps from phone, webhook hits us back,
we call core_runtime.approve()/reject().

Setup:
    1. @BotFather → /newbot → grab TELEGRAM_BOT_TOKEN
    2. Onboarding stores TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID per company
    3. Set webhook once: POST /api/telegram/setup
    4. needs_review tickets auto-push (called by agent_runtime hook)

No SDK — pure HTTPS via requests.
"""

import os
from typing import Optional

import requests

from core import store

API = "https://api.telegram.org/bot{token}/{method}"


def _company_keys(company_id: str) -> tuple[Optional[str], Optional[str]]:
    company = store.load_company(company_id) or {}
    keys = company.get("api_keys") or {}
    settings = company.get("settings") or {}
    token = keys.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = settings.get("telegram_chat_id") or keys.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
    return token, chat_id


def is_configured(company_id: str) -> bool:
    token, chat_id = _company_keys(company_id)
    return bool(token and chat_id)


def _post(token: str, method: str, payload: dict) -> dict:
    url = API.format(token=token, method=method)
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def push_ticket_for_approval(company_id: str, ticket: dict, base_url: str = "") -> dict:
    """Send a ticket card to Telegram with approve/reject inline buttons."""
    token, chat_id = _company_keys(company_id)
    if not (token and chat_id):
        return {"ok": False, "error": "telegram not configured"}

    title = ticket.get("title") or ticket.get("agent_id", "ticket")
    cost = ticket.get("cost_usd") or 0.0
    summary = (ticket.get("result", {}) or {}).get("summary", "")[:300]
    text = (
        f"*🔔 Onay bekliyor*\n"
        f"*{title}*\n"
        f"💰 ${cost:.4f}\n"
        f"\n{summary or 'Detaylar için board:.html'}\n"
        f"\n`{ticket.get('id')}`"
    )
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Onayla", "callback_data": f"approve:{ticket.get('id')}"},
            {"text": "❌ Reddet", "callback_data": f"reject:{ticket.get('id')}"},
        ]]
    }
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
    }
    return _post(token, "sendMessage", payload)


def push_text(company_id: str, text: str) -> dict:
    """Generic notification (heartbeat done, budget alert, etc.)."""
    token, chat_id = _company_keys(company_id)
    if not (token and chat_id):
        return {"ok": False, "error": "telegram not configured"}
    return _post(token, "sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})


def setup_webhook(company_id: str, base_url: str) -> dict:
    """Register webhook with Telegram. base_url should be public HTTPS root.
    Webhook will hit base_url + /api/webhooks/telegram."""
    token, _ = _company_keys(company_id)
    if not token:
        return {"ok": False, "error": "no token"}
    return _post(token, "setWebhook", {
        "url": f"{base_url.rstrip('/')}/api/webhooks/telegram",
        "allowed_updates": ["callback_query", "message"],
    })


def handle_callback(update: dict) -> dict:
    """Process inline button taps from Telegram. Returns action dict for
    caller (app.py route) to execute via core_runtime."""
    cq = update.get("callback_query") or {}
    data = cq.get("data") or ""
    cq_id = cq.get("id")
    if not data or ":" not in data:
        return {"action": "noop"}
    action, ticket_id = data.split(":", 1)
    answer_token, _ = _company_keys(_active_company())
    if answer_token and cq_id:
        _post(answer_token, "answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": f"{action} → {ticket_id}",
        })
    return {"action": action, "ticket_id": ticket_id}


def _active_company() -> str:
    try:
        return store.active_company_id()
    except Exception:
        return "default"
