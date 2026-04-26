"""Apps registry — MCP-style integrations via composio.dev.

Composio (composio.dev) is a managed integration layer that handles OAuth and
API access for 100+ SaaS tools. We expose a curated catalog here, and the
"Connect" flow goes through composio's hosted OAuth.

Without a COMPOSIO_API_KEY the catalog is still browsable but Connect buttons
return a "configure key first" prompt. When the key is set, we initiate a real
connection request via Composio's REST API.

Stored connections live per-company under data/companies/{id}/apps.json.
"""

import json
import os
from pathlib import Path
from typing import Optional

import requests

from core.store import company_dir, active_company_id

COMPOSIO_API = "https://backend.composio.dev/api/v1"

# Curated catalog. category, name, slug (Composio app slug), description, icon.
APPS_CATALOG = [
    # Communication
    {"category": "communication", "name": "Gmail",          "slug": "gmail",          "icon": "📧", "desc": "Email gönder, oku, etiketle. Outreach takipleri için ideal."},
    {"category": "communication", "name": "Slack",          "slug": "slack",          "icon": "💬", "desc": "Kanallara mesaj gönder, kullanıcıyı uyandır."},
    {"category": "communication", "name": "Discord",        "slug": "discord",        "icon": "🎮", "desc": "Topluluk kanallarına bot mesajı."},
    {"category": "communication", "name": "Telegram",       "slug": "telegram",       "icon": "✈️", "desc": "Bildirim ve onay mesajları."},
    {"category": "communication", "name": "Microsoft Teams","slug": "microsoft_teams","icon": "👥", "desc": "Kurumsal mesajlaşma."},
    {"category": "communication", "name": "Zoom",           "slug": "zoom",           "icon": "🎥", "desc": "Toplantı oluştur, link paylaş."},

    # Productivity
    {"category": "productivity",  "name": "Google Calendar","slug": "googlecalendar", "icon": "📅", "desc": "Toplantı kur, müsait saatleri sor."},
    {"category": "productivity",  "name": "Google Drive",   "slug": "googledrive",    "icon": "📁", "desc": "Dosya yükle, klasör paylaş."},
    {"category": "productivity",  "name": "Google Docs",    "slug": "googledocs",     "icon": "📝", "desc": "Doküman oluştur, içerik yapıştır."},
    {"category": "productivity",  "name": "Google Sheets",  "slug": "googlesheets",   "icon": "📊", "desc": "Lead listelerini çek, satır ekle."},
    {"category": "productivity",  "name": "Notion",         "slug": "notion",         "icon": "📓", "desc": "Sayfa oluştur, database satırı ekle."},
    {"category": "productivity",  "name": "Airtable",       "slug": "airtable",       "icon": "🗂️", "desc": "Base'e kayıt ekle / oku."},
    {"category": "productivity",  "name": "Calendly",       "slug": "calendly",       "icon": "🗓️", "desc": "Randevu linkini paylaş, slot sor."},

    # Project / CRM
    {"category": "project",       "name": "Linear",         "slug": "linear",         "icon": "📐", "desc": "Issue oluştur, takip et."},
    {"category": "project",       "name": "Asana",          "slug": "asana",          "icon": "✅", "desc": "Task oluştur, atla."},
    {"category": "project",       "name": "Trello",         "slug": "trello",         "icon": "📌", "desc": "Kart ekle, board takip."},
    {"category": "project",       "name": "Jira",           "slug": "jira",           "icon": "🔧", "desc": "Issue tracker."},
    {"category": "project",       "name": "Monday.com",     "slug": "monday",         "icon": "📋", "desc": "Item ekle, status güncelle."},

    # Sales / Marketing
    {"category": "sales",         "name": "HubSpot",        "slug": "hubspot",        "icon": "🧲", "desc": "Lead, deal, kampanya yönet."},
    {"category": "sales",         "name": "Salesforce",     "slug": "salesforce",     "icon": "☁️", "desc": "Account, opportunity, contact."},
    {"category": "sales",         "name": "Stripe",         "slug": "stripe",         "icon": "💳", "desc": "Ödeme linki, fatura, müşteri."},
    {"category": "sales",         "name": "Mailchimp",      "slug": "mailchimp",      "icon": "🐵", "desc": "Email kampanyası, liste ekle."},
    {"category": "sales",         "name": "Intercom",       "slug": "intercom",       "icon": "💭", "desc": "Müşteri konuşmaları."},

    # Social
    {"category": "social",        "name": "Twitter / X",    "slug": "twitter",        "icon": "🐦", "desc": "Tweet at, mention sor."},
    {"category": "social",        "name": "LinkedIn",       "slug": "linkedin",       "icon": "💼", "desc": "Post paylaş, profil sorgu."},
    {"category": "social",        "name": "Instagram",      "slug": "instagram",      "icon": "📸", "desc": "Post planla, DM oku."},
    {"category": "social",        "name": "Reddit",         "slug": "reddit",         "icon": "👽", "desc": "Subreddit izle, post ekle."},
    {"category": "social",        "name": "YouTube",        "slug": "youtube",        "icon": "▶️", "desc": "Video upload, analytics."},

    # Dev / Code
    {"category": "dev",           "name": "GitHub",         "slug": "github",         "icon": "🐙", "desc": "Repo, issue, PR yönet."},
    {"category": "dev",           "name": "GitLab",         "slug": "gitlab",         "icon": "🦊", "desc": "Issue, MR, pipeline."},
    {"category": "dev",           "name": "Vercel",         "slug": "vercel",         "icon": "▲", "desc": "Deploy bilgisi, env yönet."},
    {"category": "dev",           "name": "Cloudflare",     "slug": "cloudflare",     "icon": "🌩️", "desc": "DNS, worker, R2."},

    # Files / Storage
    {"category": "files",         "name": "Dropbox",        "slug": "dropbox",        "icon": "📦", "desc": "Dosya yükle, paylaş."},
    {"category": "files",         "name": "OneDrive",       "slug": "onedrive",       "icon": "☁️", "desc": "Microsoft cloud storage."},

    # Analytics
    {"category": "analytics",     "name": "Google Analytics","slug": "googleanalytics","icon": "📈", "desc": "Trafik raporu çek."},
    {"category": "analytics",     "name": "Mixpanel",       "slug": "mixpanel",       "icon": "📊", "desc": "Event analytics."},
]


# ── Storage ────────────────────────────────────────────────────────

def _connections_path(company_id: str) -> Path:
    return company_dir(company_id) / "apps.json"


def list_connections(company_id: str) -> dict:
    p = _connections_path(company_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_connections(company_id: str, data: dict) -> None:
    p = _connections_path(company_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Composio integration ───────────────────────────────────────────

def initiate_connection(slug: str, company_id: Optional[str] = None) -> dict:
    """Start a Composio OAuth flow for the given app slug. Returns a dict
    containing the redirect URL the user should visit, or an error."""
    company_id = company_id or active_company_id()
    api_key = os.getenv("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        return {
            "ok": False,
            "error": "COMPOSIO_API_KEY ayarlanmamış. composio.dev'den ücretsiz key al ve .env'e ekle.",
            "setup_url": "https://app.composio.dev/developers",
        }

    try:
        # Composio v1: /connections/initiate with appName
        resp = requests.post(
            f"{COMPOSIO_API}/connectedAccounts",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "integrationId": slug,
                "entityId": company_id,
                "redirectUri": os.getenv("APPS_REDIRECT_URI", "http://localhost:7778/apps?connected=" + slug),
            },
            timeout=15,
        )
        if resp.status_code >= 400:
            return {"ok": False, "error": f"Composio HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        url = data.get("redirectUrl") or data.get("authUrl") or data.get("url")
        connection_id = data.get("id") or data.get("connectionId")

        # Persist pending connection so we can show it as "connecting" in the UI
        conns = list_connections(company_id)
        conns[slug] = {
            "slug": slug,
            "status": "pending",
            "connection_id": connection_id,
            "redirect_url": url,
        }
        save_connections(company_id, conns)
        return {"ok": True, "redirect_url": url, "connection_id": connection_id}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def disconnect(slug: str, company_id: Optional[str] = None) -> dict:
    """Forget a connection locally. Doesn't revoke OAuth on the provider."""
    company_id = company_id or active_company_id()
    conns = list_connections(company_id)
    if slug in conns:
        del conns[slug]
        save_connections(company_id, conns)
        return {"ok": True}
    return {"ok": False, "error": "Connection not found"}
