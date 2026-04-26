"""Apps registry — MCP-style integrations via composio.dev (v3 API).

Composio is a managed integration layer that handles OAuth and tool execution
for 250+ SaaS apps. We expose a curated catalog with our own icons/categories
and use Composio's REST API to:

    1. Auto-create a managed auth_config when needed (per toolkit)
    2. Initiate a connected_account (returns OAuth redirect URL)
    3. List connections per company

Stored connections live per-company under data/companies/{id}/apps.json so
each company has its own keychain.

Composio API:
    GET  /api/v3/toolkits                  — list available apps
    POST /api/v3/auth_configs              — create managed auth config
    GET  /api/v3/auth_configs              — list existing
    POST /api/v3/connected_accounts        — initiate OAuth
    GET  /api/v3/connected_accounts        — list connections
    Header: x-api-key: ak_xxx
"""

import json
import os
from pathlib import Path
from typing import Optional

import requests

from core.store import company_dir, active_company_id

COMPOSIO_API = "https://backend.composio.dev/api/v3"
TIMEOUT = 15

# Curated catalog. Composio has hundreds of apps; we surface the most useful
# ones with our own categorization, descriptions, and icons. The Composio
# slug field maps directly to their toolkit identifier.
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
    {"category": "project",       "name": "ClickUp",        "slug": "clickup",        "icon": "📋", "desc": "Task ve docs."},

    # Sales / Marketing
    {"category": "sales",         "name": "HubSpot",        "slug": "hubspot",        "icon": "🧲", "desc": "Lead, deal, kampanya yönet."},
    {"category": "sales",         "name": "Salesforce",     "slug": "salesforce",     "icon": "☁️", "desc": "Account, opportunity, contact."},
    {"category": "sales",         "name": "Stripe",         "slug": "stripe",         "icon": "💳", "desc": "Ödeme linki, fatura, müşteri."},
    {"category": "sales",         "name": "Mailchimp",      "slug": "mailchimp",      "icon": "🐵", "desc": "Email kampanyası, liste ekle."},
    {"category": "sales",         "name": "Intercom",       "slug": "intercom",       "icon": "💭", "desc": "Müşteri konuşmaları."},

    # Social
    {"category": "social",        "name": "Twitter / X",    "slug": "twitter",        "icon": "🐦", "desc": "Tweet at, mention sor."},
    {"category": "social",        "name": "LinkedIn",       "slug": "linkedin",       "icon": "💼", "desc": "Post paylaş, profil sorgu."},
    {"category": "social",        "name": "Reddit",         "slug": "reddit",         "icon": "👽", "desc": "Subreddit izle, post ekle."},
    {"category": "social",        "name": "YouTube",        "slug": "youtube",        "icon": "▶️", "desc": "Video upload, analytics."},

    # Dev / Code
    {"category": "dev",           "name": "GitHub",         "slug": "github",         "icon": "🐙", "desc": "Repo, issue, PR yönet."},
    {"category": "dev",           "name": "GitLab",         "slug": "gitlab",         "icon": "🦊", "desc": "Issue, MR, pipeline."},
    {"category": "dev",           "name": "Vercel",         "slug": "vercel",         "icon": "▲", "desc": "Deploy bilgisi, env yönet."},

    # Files / Storage
    {"category": "files",         "name": "Dropbox",        "slug": "dropbox",        "icon": "📦", "desc": "Dosya yükle, paylaş."},
    {"category": "files",         "name": "OneDrive",       "slug": "one_drive",      "icon": "☁️", "desc": "Microsoft cloud storage."},

    # Analytics
    {"category": "analytics",     "name": "Google Analytics","slug": "google_analytics","icon": "📈", "desc": "Trafik raporu çek."},
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


# ── Composio HTTP helpers ──────────────────────────────────────────

def _headers() -> dict:
    key = os.getenv("COMPOSIO_API_KEY", "").strip()
    return {"x-api-key": key, "Content-Type": "application/json"}


def _has_key() -> bool:
    return bool(os.getenv("COMPOSIO_API_KEY", "").strip())


def _get_or_create_auth_config(slug: str) -> Optional[str]:
    """Return an auth_config_id for the given toolkit slug, creating one with
    Composio-managed auth if none exists."""
    # Look up existing
    try:
        r = requests.get(
            f"{COMPOSIO_API}/auth_configs?limit=100",
            headers=_headers(), timeout=TIMEOUT,
        )
        if r.ok:
            for item in r.json().get("items", []):
                tk = item.get("toolkit") or {}
                if tk.get("slug") == slug:
                    return item.get("id") or (item.get("auth_config") or {}).get("id")
    except Exception:
        pass

    # Create one with managed auth
    try:
        r = requests.post(
            f"{COMPOSIO_API}/auth_configs",
            headers=_headers(),
            json={
                "toolkit": {"slug": slug},
                "name": f"goat-{slug}",
                "auth_config": {"type": "use_composio_managed_auth"},
            },
            timeout=TIMEOUT,
        )
        if r.ok:
            data = r.json()
            ac = data.get("auth_config") or {}
            return ac.get("id") or data.get("id")
    except Exception:
        pass
    return None


# ── Public API ─────────────────────────────────────────────────────

def initiate_connection(slug: str, company_id: Optional[str] = None) -> dict:
    """Start a Composio OAuth flow for the given toolkit slug.
    Returns a dict with redirect_url the user should visit."""
    company_id = company_id or active_company_id()
    if not _has_key():
        return {
            "ok": False,
            "error": "COMPOSIO_API_KEY ayarlanmamış. composio.dev'den ücretsiz key al.",
            "setup_url": "https://app.composio.dev/developers",
        }

    auth_config_id = _get_or_create_auth_config(slug)
    if not auth_config_id:
        return {"ok": False, "error": f"'{slug}' için auth config oluşturulamadı"}

    try:
        r = requests.post(
            f"{COMPOSIO_API}/connected_accounts",
            headers=_headers(),
            json={
                "auth_config": {"id": auth_config_id},
                "connection": {"user_id": company_id},
            },
            timeout=TIMEOUT,
        )
        if not r.ok:
            return {"ok": False, "error": f"Composio HTTP {r.status_code}: {r.text[:200]}"}
        data = r.json()
        url = data.get("redirect_url") or data.get("redirect_uri")
        cid = data.get("id")
        status = data.get("status", "INITIATED")

        # Persist
        conns = list_connections(company_id)
        conns[slug] = {
            "slug": slug,
            "status": status.lower() if status else "pending",
            "connection_id": cid,
            "auth_config_id": auth_config_id,
            "redirect_url": url,
        }
        save_connections(company_id, conns)
        return {"ok": True, "redirect_url": url, "connection_id": cid, "status": status}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def refresh_connection_status(company_id: Optional[str] = None) -> dict:
    """Hit Composio to refresh ACTIVE/INITIATED state of all stored connections.
    Returns updated connections dict."""
    company_id = company_id or active_company_id()
    if not _has_key():
        return list_connections(company_id)
    conns = list_connections(company_id)
    if not conns:
        return conns
    try:
        r = requests.get(
            f"{COMPOSIO_API}/connected_accounts?user_ids={company_id}&limit=100",
            headers=_headers(), timeout=TIMEOUT,
        )
        if not r.ok:
            return conns
        items = r.json().get("items", [])
        # Map by toolkit slug → status
        by_slug = {}
        for it in items:
            tk = it.get("toolkit") or {}
            sl = tk.get("slug")
            if sl:
                by_slug[sl] = (it.get("status") or "").lower()
        changed = False
        for sl, conn in conns.items():
            new_status = by_slug.get(sl)
            if new_status and new_status != conn.get("status"):
                conn["status"] = new_status
                changed = True
        if changed:
            save_connections(company_id, conns)
    except Exception:
        pass
    return conns


def disconnect(slug: str, company_id: Optional[str] = None) -> dict:
    """Forget a connection locally + delete on Composio if connection_id exists."""
    company_id = company_id or active_company_id()
    conns = list_connections(company_id)
    if slug not in conns:
        return {"ok": False, "error": "Connection not found"}

    conn_id = conns[slug].get("connection_id")
    if conn_id and _has_key():
        try:
            requests.delete(
                f"{COMPOSIO_API}/connected_accounts/{conn_id}",
                headers=_headers(), timeout=TIMEOUT,
            )
        except Exception:
            pass

    del conns[slug]
    save_connections(company_id, conns)
    return {"ok": True}
