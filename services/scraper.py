"""Apify scraper service — sıkı limitlenmiş, çok-katmanlı koruma.

Üç savunma katmanı kullanırız:

1. **Aktör input parametresi** (en katı — actor mantığını durdurur):
   - compass / lukaskrivka → `maxCrawledPlacesPerSearch`
   - code_crafter~leads-finder → `maxResults` + `maxItems` (her iki adı geçer)
2. **Apify run-level URL paramları** (`?maxItems=N&timeout=300&memory=1024`):
   - `maxItems`: pay-per-result aktörlerinde overcharge önler
   - `timeout`: 300s sonra Apify run'ı 408'le keser
   - `memory`: actor memory cap (MB)
3. **Dataset fetch limit** (`?limit=N&clean=true`):
   - Sadece istenen kadar item indirilir, geri kalanı hiç network'e gelmez

Plus 30dk cache, 100 hard cap, kullanıcının `?max=25` isteği end-to-end korunur.
"""

import os
import time
import json
import requests
from typing import Optional

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

# Tüm cap'lerin merkezi — kullanıcı param yoksa default 50, hard cap 50.
# Sebep: actor input cap'leri her zaman tutmuyor (özellikle leads-finder gibi
# schema'sı belirsiz actor'larda). Bu yüzden 50'ye ulaşınca run'ı erken abort
# ediyoruz (_poll_apify_run + _abort_apify_run).
DEFAULT_MAX_LEADS = 50
HARD_CAP = 50
APIFY_MEMORY_MB = 1024              # actor memory cap
APIFY_RUN_TIMEOUT_SEC = 300         # 5dk hard cap (Apify runtime kesi)
APIFY_POLL_INTERVAL = 1             # saniyede bir kontrol — Apify durmaz, biz durdururuz
APIFY_POLL_BUFFER = 60              # poll'u Apify timeout'undan biraz uzun tut
APIFY_FIRST_PROBE_DELAY = 0.5       # ilk count probe — actor warmup için kısa bekle
APIFY_DEFAULT_MAX_CHARGE_USD = 0.30 # 50 lead × ~$0.006 = $0.30 üst sınır
CACHE_TTL_SECONDS = 1800            # 30dk

GMAPS_ACTORS = {
    "compass": "compass~google-maps-extractor",
    "lukaskrivka": "lukaskrivka~google-maps-with-contact-details",
}
LEADS_FINDER_ACTOR = "code_crafter~leads-finder"


# ── Helpers ────────────────────────────────────────────────────────────────

def _selected_actor() -> str:
    choice = os.getenv("SCRAPER_ACTOR", "compass").strip().lower()
    return GMAPS_ACTORS.get(choice, GMAPS_ACTORS["compass"])


def _resolve_token() -> str:
    """Try env first, then active company's api_keys."""
    token = APIFY_TOKEN or os.getenv("APIFY_TOKEN", "").strip()
    if token:
        return token
    try:
        from core import store
        company = store.load_company(store.active_company_id()) or {}
        return (company.get("api_keys") or {}).get("apify_token", "")
    except Exception:
        return ""


def _clamp(n, default=DEFAULT_MAX_LEADS, lo=1, hi=HARD_CAP) -> int:
    """Sertçe sınırla — None / 0 / negatif değerleri default'a, üst sınırı hi'a."""
    try:
        v = int(n)
        if v <= 0:
            return default
        return max(lo, min(v, hi))
    except (TypeError, ValueError):
        return default


def _cache_lookup(query: str, location: str, max_results: int, log=None):
    """30dk içinde aynı (query, location) için scrape varsa cache'den dön."""
    try:
        from core.paths import data_path as _dp
        raw_dir = _dp("leads", "raw")
        if not raw_dir.exists():
            return None
        now = time.time()
        nq = (query or "").strip().lower()
        nl = (location or "").strip().lower()
        for f in sorted(raw_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            age = now - f.stat().st_mtime
            if age > CACHE_TTL_SECONDS:
                break
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if (data.get("query", "").strip().lower() == nq
                    and data.get("location", "").strip().lower() == nl):
                cached = (data.get("leads") or [])[:max_results]
                if cached:
                    if log:
                        log(f"Cache hit ({len(cached)} lead, {int(age)}sn yaş) — Apify çağrılmadı")
                    return cached
    except Exception:
        pass
    return None


def _run_apify_actor(actor_id: str, payload: dict, max_items: int, token: str,
                     log=None, max_charge_usd: Optional[float] = None) -> list:
    """Tek merkezi Apify runner. Üç katmanlı limit:
       1) actor input payload (verilen şekilde — caller doldurur)
       2) URL params: maxItems + timeout + memory
       3) dataset fetch: ?limit=max_items
    Hata durumlarında [] döner ve log'lar."""
    max_items = _clamp(max_items)

    # Build run kickoff URL with all the safety caps Apify supports server-side
    params = {
        "token": token,
        "maxItems": max_items,
        "timeout": APIFY_RUN_TIMEOUT_SEC,
        "memory": APIFY_MEMORY_MB,
    }
    # Default charge cap if caller didn't specify — protects against runaway billing
    charge_cap = max_charge_usd if (max_charge_usd is not None and max_charge_usd > 0) else APIFY_DEFAULT_MAX_CHARGE_USD
    params["maxTotalChargeUsd"] = charge_cap

    if log:
        log(f"Apify '{actor_id}' başlıyor (maxItems={max_items}, timeout={APIFY_RUN_TIMEOUT_SEC}s, memory={APIFY_MEMORY_MB}MB)")

    try:
        resp = requests.post(
            f"https://api.apify.com/v2/acts/{actor_id}/runs",
            params=params,
            json=payload,
            timeout=30,
        )
    except Exception as e:
        if log:
            log(f"Apify istek hatası: {e}")
        return []

    if resp.status_code not in (200, 201):
        if log:
            log(f"Apify start failed {resp.status_code}: {resp.text[:300]}")
        return []

    run_data = resp.json().get("data") or {}
    run_id = run_data.get("id")
    if not run_id:
        if log:
            log(f"Apify run id yok: {resp.text[:200]}")
        return []

    if log:
        log(f"  run id: {run_id} — pollluyorum...")

    # Poll for status — abort early if dataset hits max_items
    dataset_id = _poll_apify_run(run_id, token, log, max_items=max_items)
    if not dataset_id:
        return []

    # Fetch dataset with limit + clean (strip empty fields, single-line items)
    items = _fetch_dataset(dataset_id, token, max_items, log)

    # Cost attribution — actor responses sometimes include charge info
    try:
        from core.cost_tracker import record
        usage = run_data.get("stats") or {}
        kind = (
            "apify.gmaps.lukaskrivka" if "lukaskrivka" in actor_id
            else "apify.gmaps.compass" if "compass" in actor_id
            else "apify.leads_finder" if "leads-finder" in actor_id
            else "apify.run"
        )
        record(kind, units=len(items), meta={
            "actor": actor_id,
            "max_items": max_items,
            "compute_units": usage.get("computeUnits"),
        })
    except Exception:
        pass

    return items


def _poll_apify_run(run_id: str, token: str, log=None,
                    max_items: Optional[int] = None) -> Optional[str]:
    """Poll the run AND its dataset every second. Apify itself does NOT stop
    when input cap is reached on some actors — we are the brake.

    EARLY-ABORT: her tick'te datasetin item count'unu kontrol et. Hedefe
    ulaşıldığında run'ı abort et ve dataset_id'yi dön. RUNNING / READY /
    SUCCEEDED — fark etmez, count >= max_items olduğu an dur.

    İlk tick: çok kısa bir warmup (APIFY_FIRST_PROBE_DELAY) sonra probe et.
    Sonraki tick'ler: APIFY_POLL_INTERVAL aralıklı.
    """
    max_polls = int((APIFY_RUN_TIMEOUT_SEC + APIFY_POLL_BUFFER) / APIFY_POLL_INTERVAL)
    last_dataset_id = None
    elapsed = 0.0
    last_log_at = -1.0

    # Warmup — actor henüz dataset_id atamamış olabilir
    time.sleep(APIFY_FIRST_PROBE_DELAY)
    elapsed += APIFY_FIRST_PROBE_DELAY

    for i in range(max_polls):
        try:
            sr = requests.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                params={"token": token},
                timeout=10,
            )
            if sr.status_code == 200:
                data = (sr.json() or {}).get("data") or {}
                status = data.get("status", "?")
                ds_id = data.get("defaultDatasetId")
                if ds_id:
                    last_dataset_id = ds_id

                # Periodic status log (every ~5sn)
                if log and (elapsed - last_log_at) >= 5:
                    log(f"  durum: {status} ({elapsed:.0f}sn)")
                    last_log_at = elapsed

                # ── EARLY-ABORT: count check on every single tick ──
                if max_items and last_dataset_id:
                    count = _dataset_item_count(last_dataset_id, token)
                    if count >= max_items:
                        if log:
                            log(f"  ✓ {count}/{max_items} hedef ulaşıldı ({elapsed:.1f}sn) — run abort")
                        _abort_apify_run(run_id, token, log)
                        return last_dataset_id

                # Terminal states
                if status == "SUCCEEDED":
                    return last_dataset_id
                if status in ("FAILED", "ABORTED", "TIMED-OUT", "TIMING-OUT"):
                    if log:
                        log(f"  çalışma sonlandı: {status}")
                    return last_dataset_id if (max_items and last_dataset_id) else None
            else:
                if log and (elapsed - last_log_at) >= 5:
                    log(f"  poll http={sr.status_code}")
                    last_log_at = elapsed
        except Exception as e:
            if log and (elapsed - last_log_at) >= 5:
                log(f"  polling hatası: {e}")
                last_log_at = elapsed

        time.sleep(APIFY_POLL_INTERVAL)
        elapsed += APIFY_POLL_INTERVAL

    if log:
        log(f"  poll zaman aşımı ({elapsed:.0f}sn) — abort + partial fetch")
    if last_dataset_id:
        _abort_apify_run(run_id, token, log)
        return last_dataset_id
    return None


def _dataset_item_count(dataset_id: str, token: str) -> int:
    """Lightweight HEAD-style probe for current item count in a dataset."""
    try:
        r = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}",
            params={"token": token},
            timeout=10,
        )
        if r.status_code != 200:
            return 0
        return ((r.json() or {}).get("data") or {}).get("itemCount", 0) or 0
    except Exception:
        return 0


def _abort_apify_run(run_id: str, token: str, log=None) -> None:
    """Politely stop a running actor (POST /actor-runs/{id}/abort).
    Best-effort — failures are logged but not raised."""
    try:
        r = requests.post(
            f"https://api.apify.com/v2/actor-runs/{run_id}/abort",
            params={"token": token, "gracefully": "1"},
            timeout=15,
        )
        if log:
            log(f"  abort http={r.status_code}")
    except Exception as e:
        if log:
            log(f"  abort hatası: {e}")


def _fetch_dataset(dataset_id: str, token: str, limit: int, log=None) -> list:
    """Sadece `limit` item indir — geri kalan hiç network'e gelmez.
    `clean=true` empty/hidden field'ları filtreler, JSON daha kompakt olur."""
    try:
        items_resp = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={
                "token": token,
                "limit": limit,
                "clean": "true",
                "format": "json",
            },
            timeout=60,
        )
        if items_resp.status_code != 200:
            if log:
                log(f"  dataset fetch http={items_resp.status_code}")
            return []
        data = items_resp.json()
        if not isinstance(data, list):
            return []
        if log:
            log(f"  {len(data)} item indirildi (limit={limit})")
        return data[:limit]   # belt and suspenders
    except Exception as e:
        if log:
            log(f"  dataset fetch hatası: {e}")
        return []


# ── Public API ──────────────────────────────────────────────────────────────

def scrape_google_maps(query: str, location: str = "",
                       max_results: int = DEFAULT_MAX_LEADS, log=None) -> list:
    """Google Maps tarama. Yoksa B2B Lead Finder'a düşer."""
    token = _resolve_token()
    if not token:
        if log:
            log("APIFY_TOKEN ayarlı değil — Apify çağrılmadı.")
        return []

    n = _clamp(max_results)
    cached = _cache_lookup(query, location, n, log)
    if cached is not None:
        return cached

    leads = _run_google_maps(query, location, n, token, log)
    if not leads:
        if log:
            log("Google Maps boş — B2B Lead Finder deneniyor...")
        leads = _run_leads_finder(query, location, n, token, log)
    return leads[:n]


def scrape_b2b_leads(query: str, location: str = "",
                     max_results: int = DEFAULT_MAX_LEADS, log=None) -> list:
    """B2B Lead Finder önce, yoksa Google Maps'a düşer."""
    token = _resolve_token()
    if not token:
        if log:
            log("APIFY_TOKEN ayarlı değil.")
        return []

    n = _clamp(max_results)
    cached = _cache_lookup(query, location, n, log)
    if cached is not None:
        return cached

    leads = _run_leads_finder(query, location, n, token, log)
    if not leads:
        if log:
            log("B2B boş — Google Maps deneniyor...")
        leads = _run_google_maps(query, location, n, token, log)
    return leads[:n]


# ── Actor-specific runners ──────────────────────────────────────────────────

def _run_google_maps(query, location, max_results, token, log) -> list:
    """compass | lukaskrivka actor'unu çalıştırır.
    Actor input'una `maxCrawledPlacesPerSearch` koyarız — bu actor mantığını
    da durdurur, sadece run-level cap değil."""
    n = _clamp(max_results)
    actor = _selected_actor()
    search_term = f"{query} {location}".strip() if location else query

    payload = {
        "searchStringsArray": [search_term],
        "locationQuery": location or "",
        "maxCrawledPlacesPerSearch": n,
        "language": "tr",
        "countryCode": "tr",
        "skipClosedPlaces": True,
    }
    if "lukaskrivka" not in actor:
        # compass actor takes scrapeContacts; lukaskrivka does it natively
        payload["scrapeContacts"] = True

    items = _run_apify_actor(actor, payload, n, token, log)
    if not items:
        return []

    leads = []
    for item in items:
        leads.append({
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
        })
    if log:
        log(f"Google Maps: {len(leads)} sonuç")
    return leads[:n]


def _run_leads_finder(query, location, max_results, token, log) -> list:
    """code_crafter~leads-finder actor'u — B2B email/LinkedIn/job title.

    Bu actor'un input schema'sı public değil; bu yüzden HEM `maxResults` HEM
    `maxItems` HEM `limit` adlarını payload'a koyarız (actor hangisini tanırsa
    onu uygular). Ayrıca run-level `maxItems` URL paramı koruma sağlar.
    """
    n = _clamp(max_results)
    search_query = f"{query} {location}".strip() if location else query

    payload = {
        "searchQuery": search_query,
        # Çoklu isim — actor schema'sı belirsiz olduğu için hepsini geç
        "maxResults": n,
        "maxItems": n,
        "limit": n,
        "resultCount": n,
    }

    items = _run_apify_actor(LEADS_FINDER_ACTOR, payload, n, token, log)
    if not items:
        return []

    leads = []
    for item in items[:n]:   # ekstra güvence
        name = (item.get("company_name") or
                f"{item.get('first_name', '')} {item.get('last_name', '')}".strip())
        if not name:
            continue
        leads.append({
            "name": name,
            "address": "",
            "phone": item.get("mobile_number", "") or "",
            "website": item.get("company_website", "") or "",
            "email": item.get("email") or item.get("personal_email") or "",
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
        })
    if log:
        log(f"B2B Lead Finder: {len(leads)} sonuç")
    return leads[:n]


# ── Field extractors ────────────────────────────────────────────────────────

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
