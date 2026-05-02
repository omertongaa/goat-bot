"""Tool-agnostic outreach delivery.

Outreach agent always produces a campaign artifact (sequence + leads) without
being locked to one provider. After approval, the user picks where to send it
from — Instantly, Composio Gmail, manual export, etc. This module dispatches
the actual delivery based on the chosen channel.
"""

import os
from typing import Optional

from core import activity_log


def deliver(company_id: str, ticket: dict, channel: str) -> dict:
    """Route the approved campaign to the chosen delivery channel.

    Returns {ok, info|error}.
    """
    result = ticket.get("result") or {}
    sequence = result.get("sequence") or []
    leads = result.get("leads") or []
    campaign_id = result.get("campaign_id")
    instantly_id = result.get("instantly_draft_id") or campaign_id

    if channel == "instantly":
        return _send_instantly(company_id, ticket, instantly_id)
    if channel == "composio_gmail":
        return _send_via_composio_gmail(company_id, ticket, sequence, leads)
    if channel in ("export_csv", "export_md"):
        # Already handled by the /api/core/tickets/{id}/export endpoint
        activity_log.append(company_id, "campaign_export_ready", actor="user",
                            subject=ticket["id"], details={"format": channel})
        return {"ok": True, "info": "Export hazır — drawer'dan indir"}
    return {"ok": False, "error": f"Bilinmeyen kanal: {channel}"}


def _send_instantly(company_id: str, ticket: dict, campaign_id: Optional[str]) -> dict:
    if not campaign_id:
        return {"ok": False, "error": "Instantly campaign_id yok"}
    from services.email import activate_campaign, get_api_key
    from core import store
    company = store.load_company(company_id) or {}
    api_key = company.get("api_keys", {}).get("instantly_api_key") \
              or os.getenv("INSTANTLY_API_KEY") or get_api_key()
    if not api_key:
        return {"ok": False, "error": "Instantly API key yok"}
    ok = activate_campaign(campaign_id, api_key)
    activity_log.append(
        company_id, "campaign_activated" if ok else "campaign_activation_failed",
        actor="system", subject=ticket["id"],
        details={"campaign_id": campaign_id, "channel": "instantly"},
    )
    return {"ok": ok, "info": "Instantly aktive edildi" if ok else "Instantly hata"}


def _send_via_composio_gmail(company_id: str, ticket: dict, sequence: list, leads: list) -> dict:
    """Send the FIRST email in the sequence via Composio Gmail to all leads.
    Follow-up emails (steps 2-3) are scheduled by the user externally for now."""
    from services import composio_tools as _ct
    if "gmail" not in _ct.list_connected_toolkits(company_id):
        return {"ok": False, "error": "Gmail Composio bağlı değil — /apps üstünden bağla"}
    if not (sequence and leads):
        return {"ok": False, "error": "Email dizisi veya lead yok"}
    first = sequence[0]
    sent = 0
    failed = 0
    for lead in leads:
        if not lead.get("email"):
            continue
        body = (first.get("body") or "")
        body = body.replace("{{first_name}}", lead.get("first_name") or "")
        body = body.replace("{{company_name}}", lead.get("company_name") or "")
        res = _ct.execute_tool("GMAIL_SEND_EMAIL", user_id=company_id, arguments={
            "to": lead["email"],
            "subject": first.get("subject", ""),
            "body_text": body,
        })
        if res.get("ok"):
            sent += 1
        else:
            failed += 1
    activity_log.append(
        company_id, "campaign_sent_composio", actor="system", subject=ticket["id"],
        details={"sent": sent, "failed": failed, "step": 1, "channel": "composio_gmail"},
    )
    return {"ok": sent > 0, "info": f"Gmail: {sent} gönderildi, {failed} başarısız"}
