"""Instantly.ai stats puller — campaign-level bounce/reply/open rates.

Used by:
    - /api/email/stats endpoint for the cost dashboard
    - CEO heartbeat: if reply_rate < 1% → suggest A/B subject revision
    - Outreach ticket post-run hook: attaches latest stats to ticket
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from services.email import _headers, API_BASE


def fetch_campaign_stats(campaign_id: str, api_key: Optional[str] = None) -> dict:
    """Returns {sent, opens, replies, bounces, open_rate, reply_rate, bounce_rate}."""
    try:
        r = requests.get(
            f"{API_BASE}/campaigns/{campaign_id}/analytics",
            headers=_headers(api_key),
            timeout=10,
        )
        if r.status_code != 200:
            return {"error": f"http {r.status_code}", "campaign_id": campaign_id}
        raw = r.json() or {}
        sent = int(raw.get("sent") or raw.get("emails_sent") or 0)
        opens = int(raw.get("opens") or raw.get("emails_opened") or 0)
        replies = int(raw.get("replies") or raw.get("emails_replied") or 0)
        bounces = int(raw.get("bounces") or raw.get("emails_bounced") or 0)
        return {
            "campaign_id": campaign_id,
            "sent": sent,
            "opens": opens,
            "replies": replies,
            "bounces": bounces,
            "open_rate": round(opens / sent * 100, 2) if sent else 0.0,
            "reply_rate": round(replies / sent * 100, 2) if sent else 0.0,
            "bounce_rate": round(bounces / sent * 100, 2) if sent else 0.0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "campaign_id": campaign_id}


def aggregate(api_key: Optional[str] = None) -> dict:
    """Pull every campaign + sum totals. Slow on big accounts; cache callers."""
    api_key = api_key or os.getenv("INSTANTLY_API_KEY", "")
    if not api_key:
        return {"error": "INSTANTLY_API_KEY missing", "campaigns": [], "totals": {}}
    try:
        r = requests.get(
            f"{API_BASE}/campaigns",
            headers=_headers(api_key),
            params={"limit": 50},
            timeout=15,
        )
        if r.status_code != 200:
            return {"error": f"http {r.status_code}", "campaigns": [], "totals": {}}
        campaigns = r.json() or []
        if isinstance(campaigns, dict):
            campaigns = campaigns.get("items") or campaigns.get("data") or []
    except Exception as e:
        return {"error": str(e), "campaigns": [], "totals": {}}

    rows = []
    totals = {"sent": 0, "opens": 0, "replies": 0, "bounces": 0}
    for c in campaigns[:25]:
        cid = c.get("id") or c.get("campaign_id")
        if not cid:
            continue
        stats = fetch_campaign_stats(cid, api_key)
        stats["name"] = c.get("name", cid)
        stats["status"] = c.get("status", "?")
        rows.append(stats)
        for k in ("sent", "opens", "replies", "bounces"):
            totals[k] += int(stats.get(k) or 0)

    sent = totals["sent"]
    return {
        "campaigns": rows,
        "totals": {
            **totals,
            "open_rate": round(totals["opens"] / sent * 100, 2) if sent else 0.0,
            "reply_rate": round(totals["replies"] / sent * 100, 2) if sent else 0.0,
            "bounce_rate": round(totals["bounces"] / sent * 100, 2) if sent else 0.0,
        },
        "warnings": _warnings(rows),
    }


def _warnings(rows: list) -> list:
    """Surface campaigns that need user attention."""
    out = []
    for r in rows:
        sent = r.get("sent") or 0
        if sent < 30:
            continue
        if r.get("bounce_rate", 0) > 5.0:
            out.append(f"⚠ {r.get('name')}: bounce {r['bounce_rate']}% — domain warmup gerek")
        if sent >= 100 and r.get("reply_rate", 0) < 1.0:
            out.append(f"💤 {r.get('name')}: reply {r['reply_rate']}% — subject A/B test öner")
    return out
