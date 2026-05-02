"""External webhook handlers — Stripe, Calendly, Instantly.

Each handler converts an inbound event into a goat-bot ticket so the
control plane sees the world like any other agent run.
    Stripe checkout.session.completed → CEO follow-up + onboarding ticket
    Calendly invitee.created → Outreach reschedule + Pitch prep ticket
    Instantly reply received → Outreach hand-off ticket (high prio)

Validation: signature checks where the platform supports them; otherwise
we trust the shape (caller can put a secret in the URL).
"""

import hashlib
import hmac
import json
import os
from typing import Optional

from core import activity_log, agent_runtime, store


def _ceo_ticket(company_id: str, title: str, description: str, params: dict) -> dict:
    return agent_runtime.create_ticket(
        company_id=company_id,
        agent_id="ceo",
        title=title,
        description=description,
        params=params,
    )


def _outreach_ticket(company_id: str, title: str, description: str, params: dict) -> dict:
    return agent_runtime.create_ticket(
        company_id=company_id,
        agent_id="outreach",
        title=title,
        description=description,
        params=params,
    )


def stripe_event(company_id: str, payload: dict, signature: Optional[str] = None) -> dict:
    """Handle a Stripe webhook. Verify signature if STRIPE_WEBHOOK_SECRET set."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if secret and signature:
        if not _verify_stripe_sig(secret, payload, signature):
            return {"error": "bad signature"}

    event_type = payload.get("type", "")
    obj = (payload.get("data") or {}).get("object", {}) or {}
    if event_type == "checkout.session.completed":
        amount = (obj.get("amount_total") or 0) / 100
        email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email", "")
        ticket = _ceo_ticket(
            company_id,
            title=f"💸 Yeni satış: {email or 'müşteri'} (${amount:.2f})",
            description="Stripe checkout tamamlandı. Onboarding mail + welcome paketi gönder.",
            params={"source": "stripe", "amount_usd": amount, "email": email},
        )
        activity_log.append(
            company_id, "stripe_payment_received", actor="webhook",
            subject=ticket["id"], details={"email": email, "amount": amount},
        )
        return {"ok": True, "ticket_id": ticket["id"]}

    if event_type == "invoice.payment_failed":
        ticket = _ceo_ticket(
            company_id,
            title="⚠ Stripe ödeme başarısız",
            description="Müşteri kartı reddedildi. Dunning sequence tetikle.",
            params={"source": "stripe", "type": event_type, "object_id": obj.get("id", "")},
        )
        return {"ok": True, "ticket_id": ticket["id"]}

    return {"ok": True, "ignored": event_type}


def calendly_event(company_id: str, payload: dict) -> dict:
    """Handle a Calendly v2 webhook (invitee.created/canceled)."""
    event_type = payload.get("event", "")
    p = payload.get("payload", {}) or {}
    if event_type == "invitee.created":
        name = p.get("name") or p.get("invitee_name") or "Davetli"
        email = p.get("email") or "?"
        when = (p.get("scheduled_event") or {}).get("start_time", "")
        ticket = _ceo_ticket(
            company_id,
            title=f"📅 Yeni meeting: {name} — {when[:16]}",
            description=f"{email} ile {when} toplantı. Pitch agent ile prep yap.",
            params={"source": "calendly", "email": email, "scheduled_at": when},
        )
        activity_log.append(
            company_id, "calendly_meeting_booked", actor="webhook",
            subject=ticket["id"], details={"email": email, "when": when},
        )
        return {"ok": True, "ticket_id": ticket["id"]}
    return {"ok": True, "ignored": event_type}


def instantly_event(company_id: str, payload: dict) -> dict:
    """Instantly.ai webhook — incoming reply / bounce / unsubscribe."""
    event_type = payload.get("event_type") or payload.get("event") or ""
    lead_email = payload.get("lead_email") or payload.get("email") or "?"
    campaign = payload.get("campaign_name") or payload.get("campaign_id") or ""
    if event_type in ("reply_received", "lead_replied"):
        ticket = _outreach_ticket(
            company_id,
            title=f"💬 Cevap geldi: {lead_email}",
            description=f"Kampanya {campaign} üzerinden yanıt. CEO'ya hand-off, hızlı dön.",
            params={"source": "instantly", "lead_email": lead_email, "campaign": campaign},
        )
        return {"ok": True, "ticket_id": ticket["id"]}
    if event_type in ("email_bounced", "lead_bounced"):
        activity_log.append(
            company_id, "email_bounced", actor="webhook",
            subject=lead_email, details={"campaign": campaign},
        )
        return {"ok": True}
    return {"ok": True, "ignored": event_type}


def _verify_stripe_sig(secret: str, payload: dict, sig_header: str) -> bool:
    """Stripe sends 'Stripe-Signature' header `t=...,v1=...`."""
    try:
        parts = dict(p.split("=", 1) for p in sig_header.split(","))
        ts = parts.get("t", "")
        v1 = parts.get("v1", "")
        signed = f"{ts}.{json.dumps(payload, separators=(',', ':'), sort_keys=True)}"
        expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)
    except Exception:
        return False
