"""Apify scraper service — abstracts the Apify API for lead generation.

Three modes:
1. Google Maps — local businesses with address, phone, email, rating.
   Two actor options controlled by SCRAPER_ACTOR env:
     - "compass"     → compass~google-maps-extractor (default, broad data)
     - "lukaskrivka" → lukaskrivka~google-maps-with-contact-details
       ($2.10/1000 place, richer email+phone+social extraction, recommended
       for Turkish SMB use case per benchmark research)
2. B2B Leads (code_crafter~leads-finder) — business contacts with email, LinkedIn, job title

Falls back from one to the other if no results found.
Default and hard-cap of 100 leads per run.
"""

import os
import time
import requests
from pathlib import Path

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
DEFAULT_MAX_LEADS = 100
HARD_CAP = 100

GMAPS_ACTORS = {
    "compass": "compass~google-maps-extractor",
    "lukaskrivka": "lukaskrivka~google-maps-with-contact-details",
}


def _selected_actor() -> str:
    choice = os.getenv("SCRAPER_ACTOR", "compass").strip().lower()
    return GMAPS_ACTORS.get(choice, GMAPS_ACTORS["compass"])


def scrape_google_maps(query: str, location: str = "", max_results: int = DEFAULT_MAX_LEADS, log=None) -> list:
    """Scrape Google Maps for businesses. Falls back to B2B leads if no results."""
    token = APIFY_TOKEN or os.getenv("APIFY_TOKEN", "")
    if not token:
        if log:
            log("No APIFY_TOKEN set — cannot scrape. Add it to .env")
        return []

    if log:
        log(f"Google Maps'te arıyorum: {query} {location}")
    leads = _run_google_maps(query, location, max_results, token, log)

    if not leads:
        if log:
            log("Google Maps sonuç vermedi, B2B lead finder deneniyor...")
        leads = _run_leads_finder(query, location, max_results, token, log)

    return leads


def scrape_b2b_leads(query: str, location: str = "", max_results: int = DEFAULT_MAX_LEADS, log=None) -> list:
    """B2B lead finder first, falls back to Google Maps."""
    token = APIFY_TOKEN or os.getenv("APIFY_TOKEN", "")
    if not token:
        if log:
            log("No APIFY_TOKEN set")
        return []

    if log:
        log(f"B2B lead finder'da arıyorum: {query} {location}")
    leads = _run_leads_finder(query, location, max_results, token, log)

    if not leads:
        if log:
            log("B2B sonuç vermedi, Google Maps deneniyor...")
        leads = _run_google_maps(query, location, max_results, token, log)

    return leads


def _run_google_maps(query, location, max_results, token, log):
    """Google Maps scraper. Actor selected by SCRAPER_ACTOR env (compass|lukaskrivka)."""
    max_results = min(max_results or DEFAULT_MAX_LEADS, HARD_CAP)
    search_term = f"{query} {location}".strip() if location else query
    actor = _selected_actor()

    if actor == GMAPS_ACTORS["lukaskrivka"]:
        payload = {
            "searchStringsArray": [search_term],
            "locationQuery": location or "",
            "maxCrawledPlacesPerSearch": max_results,
            "language": "tr",
            "countryCode": "tr",
            "skipClosedPlaces": True,
        }
    else:
        payload = {
            "searchStringsArray": [search_term],
            "locationQuery": location or "",
            "maxCrawledPlacesPerSearch": max_results,
            "language": "tr",
            "countryCode": "tr",
            "skipClosedPlaces": True,
            "scrapeContacts": True,
        }

    try:
        if log:
            log(f"Actor: {actor}")
        resp = requests.post(
            f"https://api.apify.com/v2/acts/{actor}/runs?token={token}",
            json=payload,
            timeout=30,
        )
        run_data = resp.json().get("data", {})
        run_id = run_data.get("id")

        if not run_id:
            if log:
                log(f"Google Maps başlatılamadı: {resp.text[:200]}")
            return []

        if log:
            log(f"Google Maps taraması başladı ({run_id})")

        results = _poll_apify_run(run_id, token, log)
        if not results:
            return []

        # Cost attribution against the active ticket
        try:
            from core.cost_tracker import record
            kind = "apify.gmaps.lukaskrivka" if "lukaskrivka" in actor else "apify.gmaps.place"
            record(kind, units=len(results), meta={"actor": actor, "query": search_term})
        except Exception:
            pass

        leads = []
        for item in results:
            lead = {
                "name": item.get("title", ""),
                "address": item.get("address", ""),
                "phone": item.get("phone", ""),
                "website": item.get("website", ""),
                "email": _extract_email(item),
                "instagram": _first(item.get("instagrams")),
                "facebook": _first(item.get("facebooks")),
                "rating": item.get("totalScore", 0),
                "review_count": item.get("reviewsCount", 0),
                "category": item.get("categoryName", ""),
                "google_maps_url": item.get("url", ""),
                "location": item.get("city", location),
                "source": "google_maps",
                "raw": item,
            }
            leads.append(lead)

        if log:
            log(f"Google Maps: {len(leads)} sonuç bulundu")
        return leads

    except Exception as e:
        if log:
            log(f"Google Maps hatası: {e}")
        return []


def _run_leads_finder(query, location, max_results, token, log):
    """B2B lead finder via code_crafter~leads-finder."""
    max_results = min(max_results or DEFAULT_MAX_LEADS, HARD_CAP)
    search_query = f"{query} {location}".strip() if location else query

    try:
        resp = requests.post(
            f"https://api.apify.com/v2/acts/code_crafter~leads-finder/runs?token={token}",
            json={
                "searchQuery": search_query,
                "maxResults": max_results,
            },
            timeout=30,
        )
        run_data = resp.json().get("data", {})
        run_id = run_data.get("id")

        if not run_id:
            if log:
                log(f"B2B finder başlatılamadı: {resp.text[:200]}")
            return []

        if log:
            log(f"B2B lead finder başladı ({run_id})")

        results = _poll_apify_run(run_id, token, log)
        if not results:
            return []

        try:
            from core.cost_tracker import record
            record("apify.run", units=max(1, len(results) // 10),
                   meta={"actor": "code_crafter~leads-finder", "query": search_query})
        except Exception:
            pass

        leads = []
        for item in results:
            name = item.get("company_name", "") or f"{item.get('first_name', '')} {item.get('last_name', '')}".strip()
            if not name:
                continue
            lead = {
                "name": name,
                "address": "",
                "phone": item.get("mobile_number", "") or "",
                "website": item.get("company_website", "") or "",
                "email": item.get("email", "") or item.get("personal_email", "") or "",
                "rating": 0,
                "review_count": 0,
                "category": item.get("industry", ""),
                "google_maps_url": "",
                "location": location,
                "source": "b2b_leads",
                "contact_name": item.get("full_name", ""),
                "job_title": item.get("job_title", ""),
                "linkedin": item.get("linkedin", ""),
                "company_size": item.get("company_size", 0),
                "raw": item,
            }
            leads.append(lead)

        if log:
            log(f"B2B finder: {len(leads)} sonuç bulundu")
        return leads

    except Exception as e:
        if log:
            log(f"B2B finder hatası: {e}")
        return []


def _poll_apify_run(run_id, token, log, max_polls=120, interval=5):
    """Poll an Apify run until completion. 5s interval x 120 polls = 10min cap."""
    for i in range(max_polls):
        time.sleep(interval)
        try:
            sr = requests.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}",
                timeout=15,
            )
            status = sr.json().get("data", {}).get("status")

            if log and i % 6 == 0:
                log(f"  durum: {status} ({(i+1)*interval}sn)")

            if status == "SUCCEEDED":
                dataset_id = sr.json().get("data", {}).get("defaultDatasetId")
                items_resp = requests.get(
                    f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}",
                    timeout=30,
                )
                return items_resp.json()

            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                if log:
                    log(f"  çalışma başarısız: {status}")
                return []
        except Exception as e:
            if log:
                log(f"  polling hatası: {e}")

    if log:
        log("  zaman aşımı (10dk)")
    return []


def _extract_email(item: dict) -> str:
    if item.get("email"):
        return item["email"]
    for field in ("emails", "contactEmail", "contactEmails"):
        val = item.get(field)
        if val:
            if isinstance(val, list) and val:
                return val[0]
            if isinstance(val, str):
                return val
    return ""


def _first(val):
    if isinstance(val, list) and val:
        return val[0]
    if isinstance(val, str):
        return val
    return ""
