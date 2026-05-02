"""Email Finder — multi-provider enrichment service.

Scout scrapes businesses from Google Maps/B2B, but not every lead has an email.
This service wraps multiple third-party APIs behind a common interface so the
user can swap providers (or waterfall them) without touching Scout.

Providers (all PAYG, no subscription required except EmailAPI):
    - emailapi     → EmailAPI.ai (Leadfwd) — ~$19-40/1000, Bearer auth, per-account domain
    - leadmagic    → LeadMagic.io — ~$7/1000, X-API-Key, 100 free trial credits
    - generect     → Generect.com — ~$30-50/1000, Token auth, real-time scraping
    - apify_web    → Apify website email scraper (vdrmota/contact-info-scraper) — ~$2/1000

Usage:
    from services.email_finder import enrich_leads
    leads = enrich_leads(leads, providers=["leadmagic", "generect"], log=print)

Config:
    EMAIL_FINDER_PROVIDERS  - comma-separated priority list (waterfall)
    EMAILAPI_KEY            - "{authKey}.{authSecret}"
    EMAILAPI_DOMAIN         - per-account API domain (e.g. api.leadfwd.com)
    LEADMAGIC_API_KEY       - LeadMagic API key
    GENERECT_API_KEY        - Generect auth token
    APIFY_TOKEN             - already used by scraper, reused here for apify_web

Design: the system guides but never forces a single provider. Users enable
whichever ones they have keys for, order them by preference, and the waterfall
stops at the first hit per lead.
"""

import os
import re
from typing import Callable, Optional

import requests

REQUEST_TIMEOUT = 20

AVAILABLE_PROVIDERS = ("emailapi", "leadmagic", "generect", "apify_web")


def enrich_leads(
    leads: list,
    providers: Optional[list] = None,
    log: Optional[Callable] = None,
) -> list:
    """Enrich leads missing email via the configured provider waterfall.

    Mutates and returns the input list. Each enriched lead gets:
        email          - found address (or "" if all providers missed)
        email_source   - provider name that found it
        email_verified - boolean if the provider reports verification

    Providers that need person-level input (first/last name) are skipped for
    leads without contact_name. apify_web works on domain alone.
    """
    providers = providers or _providers_from_env()
    if not providers:
        if log:
            log("Email enrichment skipped: no providers configured")
        return leads

    providers = [p for p in providers if p in AVAILABLE_PROVIDERS]
    if not providers:
        if log:
            log(f"Email enrichment skipped: no valid providers in {providers}")
        return leads

    missing = [l for l in leads if not l.get("email")]
    if not missing:
        if log:
            log("Email enrichment skipped: all leads already have email")
        return leads

    if log:
        log(f"Enriching {len(missing)} leads without email via: {', '.join(providers)}")

    found_count = 0
    for lead in missing:
        for provider in providers:
            try:
                result = _dispatch(provider, lead, log)
            except Exception as e:
                if log:
                    log(f"  {provider} error for {lead.get('name', '?')}: {e}")
                continue
            if result and result.get("email"):
                lead["email"] = result["email"]
                lead["email_source"] = provider
                lead["email_verified"] = bool(result.get("verified"))
                found_count += 1
                # Cost attribution per valid email found
                try:
                    from core.cost_tracker import record
                    record(f"{provider}.email", units=1, meta={"domain": result.get("domain", "")})
                except Exception:
                    pass
                break

    if log:
        log(f"Enrichment done: {found_count}/{len(missing)} emails found")
    return leads


def _dispatch(provider: str, lead: dict, log) -> Optional[dict]:
    if provider == "emailapi":
        return _emailapi_find(lead, log)
    if provider == "leadmagic":
        return _leadmagic_find(lead, log)
    if provider == "generect":
        return _generect_find(lead, log)
    if provider == "apify_web":
        return _apify_web_find(lead, log)
    return None


def _providers_from_env() -> list:
    raw = os.getenv("EMAIL_FINDER_PROVIDERS", "").strip()
    if not raw:
        return []
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _emailapi_find(lead: dict, log) -> Optional[dict]:
    """EmailAPI.ai (Leadfwd) — POST {domain}/v2/email-finder.
    Needs first_name + last_name + domain."""
    key = os.getenv("EMAILAPI_KEY", "").strip()
    api_domain = os.getenv("EMAILAPI_DOMAIN", "").strip()
    if not key or not api_domain:
        return None
    fname, lname = _split_name(lead.get("contact_name") or "")
    domain = _domain_from_lead(lead)
    if not (fname and lname and domain):
        return None
    resp = requests.post(
        f"https://{api_domain}/v2/email-finder",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"domain": domain, "fname": fname, "lname": lname},
        timeout=REQUEST_TIMEOUT,
    )
    if not resp.ok:
        return None
    data = resp.json() or {}
    email = data.get("email") or data.get("emailAddress") or ""
    if not email:
        return None
    return {"email": email, "verified": str(data.get("status", "")).lower() == "verified"}


def _leadmagic_find(lead: dict, log) -> Optional[dict]:
    """LeadMagic — POST /v1/people/email-finder. Needs name + domain OR company."""
    key = os.getenv("LEADMAGIC_API_KEY", "").strip()
    if not key:
        return None
    fname, lname = _split_name(lead.get("contact_name") or "")
    domain = _domain_from_lead(lead)
    company = lead.get("name", "")
    if not ((fname and lname) or company):
        return None
    if not (domain or company):
        return None
    body = {}
    if fname:
        body["first_name"] = fname
    if lname:
        body["last_name"] = lname
    if domain:
        body["domain"] = domain
    elif company:
        body["company_name"] = company
    resp = requests.post(
        "https://api.leadmagic.io/v1/people/email-finder",
        headers={"X-API-Key": key, "Content-Type": "application/json"},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    if not resp.ok:
        return None
    data = resp.json() or {}
    email = data.get("email") or ""
    if not email:
        return None
    status = str(data.get("status", "")).lower()
    return {"email": email, "verified": status in ("valid", "verified", "deliverable")}


def _generect_find(lead: dict, log) -> Optional[dict]:
    """Generect — POST /api/linkedin/email_finder/ (accepts array).
    Needs first_name + last_name + domain."""
    key = os.getenv("GENERECT_API_KEY", "").strip()
    if not key:
        return None
    fname, lname = _split_name(lead.get("contact_name") or "")
    domain = _domain_from_lead(lead)
    if not (fname and lname and domain):
        return None
    resp = requests.post(
        "https://api.generect.com/api/linkedin/email_finder/",
        headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
        json=[{"first_name": fname, "last_name": lname, "domain": domain}],
        timeout=REQUEST_TIMEOUT,
    )
    if not resp.ok:
        return None
    data = resp.json()
    item = data[0] if isinstance(data, list) and data else data
    if not isinstance(item, dict):
        return None
    email = item.get("email") or item.get("work_email") or ""
    if not email:
        return None
    return {"email": email, "verified": bool(item.get("mx_valid") or item.get("deliverable"))}


def _apify_web_find(lead: dict, log) -> Optional[dict]:
    """Apify vdrmota/contact-info-scraper — visits the business website and extracts
    email/phone/social from public pages. Works with domain only (no name needed).
    Slower (~30-120s) because it triggers an Apify run; use sparingly for SMB leads."""
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return None
    website = lead.get("website", "") or ""
    if not website:
        return None
    if not website.startswith("http"):
        website = "https://" + website
    try:
        start = requests.post(
            f"https://api.apify.com/v2/acts/vdrmota~contact-info-scraper/run-sync-get-dataset-items?token={token}",
            json={
                "startUrls": [{"url": website}],
                "maxDepth": 2,
                "maxRequestsPerStartUrl": 5,
                "sameDomain": True,
            },
            timeout=180,
        )
    except requests.Timeout:
        return None
    if not start.ok:
        return None
    items = start.json() if start.content else []
    if not isinstance(items, list):
        return None
    for item in items:
        emails = item.get("emails") or []
        if emails:
            return {"email": emails[0], "verified": False}
    return None


def _split_name(full: str) -> tuple:
    """Split 'John Doe' into ('John', 'Doe'). Handles Turkish names, titles.
    Returns ('', '') if not splittable."""
    if not full:
        return "", ""
    cleaned = re.sub(r"\b(Dr|Prof|Doç|Mr|Mrs|Ms|Av)\b\.?", "", full, flags=re.IGNORECASE)
    parts = [p for p in cleaned.split() if p and p != "."]
    if len(parts) < 2:
        return "", ""
    return parts[0], " ".join(parts[1:])


def _domain_from_lead(lead: dict) -> str:
    """Extract bare domain from website URL."""
    website = lead.get("website", "") or ""
    if not website:
        return ""
    domain = re.sub(r"^https?://", "", website.strip(), flags=re.IGNORECASE)
    domain = domain.split("/")[0].split("?")[0]
    domain = re.sub(r"^www\.", "", domain, flags=re.IGNORECASE)
    return domain.strip().lower()
