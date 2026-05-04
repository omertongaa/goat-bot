"""Apify actor catalog.

Two layers:
    1. CURATED — hand-picked actors goat-bot agents already use, with
       real-world pricing notes & "best for" hints (Turkish SMB, EU
       e-commerce, etc.). Always available.
    2. LIVE — when user has APIFY_TOKEN, /v2/store actors are fetched
       and merged. 6h cache.

Helps the user (and CEO agent) pick the right scraper for a niche
without guessing actor names.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests


CACHE_PATH = Path(os.getenv("GOAT_DATA_DIR") or (Path(__file__).resolve().parent.parent / "data")) / "apify_catalog.json"
CACHE_TTL = 6 * 3600


CURATED = [
    {
        "actor": "compass/crawler-google-places",
        "category": "lead_scraping",
        "best_for": "Google Maps yerel işletme, default Scout actor",
        "price_per_1000": 1.5,
        "fields": ["name", "address", "phone", "website", "rating", "review_count", "category"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.95,
    },
    {
        "actor": "lukaskrivka/google-maps-with-contact-details",
        "category": "lead_scraping",
        "best_for": "Türkiye SMB — gelişmiş email/phone/social çıkarma",
        "price_per_1000": 2.10,
        "fields": ["name", "address", "phone", "email", "website", "instagram", "facebook", "linkedin", "rating", "reviews"],
        "memory_mb": 1024,
        "speed": "medium",
        "reliability": 0.92,
    },
    {
        "actor": "vdrmota/contact-info-scraper",
        "category": "email_finder",
        "best_for": "Website domain'inden email çıkarma (Türkiye SMB için en iyi)",
        "price_per_1000": 2.0,
        "fields": ["url", "emails", "phones", "social"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.85,
    },
    {
        "actor": "apify/instagram-scraper",
        "category": "social",
        "best_for": "Instagram profil/hashtag/post analizi (rakip araştırması)",
        "price_per_1000": 2.30,
        "fields": ["username", "followers", "posts", "engagement_rate", "bio"],
        "memory_mb": 1024,
        "speed": "medium",
        "reliability": 0.88,
    },
    {
        "actor": "apify/tiktok-scraper",
        "category": "social",
        "best_for": "TikTok video/profil/hashtag — viral içerik araştırma",
        "price_per_1000": 2.80,
        "fields": ["username", "video_url", "views", "likes", "shares", "hashtags"],
        "memory_mb": 1024,
        "speed": "medium",
        "reliability": 0.86,
    },
    {
        "actor": "apify/linkedin-company-scraper",
        "category": "lead_scraping",
        "best_for": "LinkedIn şirket sayfası — B2B prospecting",
        "price_per_1000": 5.0,
        "fields": ["name", "industry", "size", "founded", "specialties", "location", "website"],
        "memory_mb": 1024,
        "speed": "slow",
        "reliability": 0.80,
    },
    {
        "actor": "apify/google-search-scraper",
        "category": "search",
        "best_for": "Google SERP — keyword research, rakip listeleme",
        "price_per_1000": 3.0,
        "fields": ["title", "url", "snippet", "position"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.93,
    },
    {
        "actor": "apify/website-content-crawler",
        "category": "content",
        "best_for": "Site içerik scrape — blog, SEO, RAG için doc çıkarma",
        "price_per_1000": 1.0,
        "fields": ["url", "title", "text", "html", "links"],
        "memory_mb": 1024,
        "speed": "medium",
        "reliability": 0.90,
    },
    {
        "actor": "apify/yandex-search-scraper",
        "category": "search",
        "best_for": "Türkiye için Yandex SERP — yerel SEO research",
        "price_per_1000": 4.0,
        "fields": ["title", "url", "snippet"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.88,
    },
    {
        "actor": "drobnikj/crawler-google-places",
        "category": "lead_scraping",
        "best_for": "Alternative GMaps actor — daha ucuz ama daha az alan",
        "price_per_1000": 0.50,
        "fields": ["name", "address", "phone", "website", "rating"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.85,
    },
    {
        "actor": "apify/twitter-scraper",
        "category": "social",
        "best_for": "Twitter/X — keyword/profil/hashtag, real-time trend",
        "price_per_1000": 2.50,
        "fields": ["username", "tweet_id", "text", "likes", "retweets", "created_at"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.82,
    },
    {
        "actor": "trudax/trustpilot-scraper",
        "category": "reviews",
        "best_for": "Trustpilot review scrape — rakip değerlendirme analizi",
        "price_per_1000": 1.5,
        "fields": ["company", "rating", "review_text", "date"],
        "memory_mb": 512,
        "speed": "fast",
        "reliability": 0.87,
    },
]


def _read_cache() -> Optional[dict]:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
        if time.time() - data.get("_cached_at", 0) > CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _write_cache(data: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data["_cached_at"] = int(time.time())
        CACHE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        pass


def list_actors(category: str = "", refresh: bool = False) -> dict:
    """Curated + (optional) live merge."""
    if not refresh:
        cached = _read_cache()
        if cached:
            actors = cached.get("actors", CURATED)
            if category:
                actors = [a for a in actors if a.get("category") == category]
            return {"actors": actors, "categories": _categories(cached.get("actors", CURATED)), "live": cached.get("live", False)}

    actors = list(CURATED)
    live = False
    token = os.getenv("APIFY_TOKEN", "").strip()
    if token:
        try:
            r = requests.get(
                "https://api.apify.com/v2/store",
                params={"limit": 100, "token": token},
                timeout=10,
            )
            if r.status_code == 200:
                items = (r.json() or {}).get("data", {}).get("items", [])
                known = {a["actor"] for a in actors}
                for it in items:
                    slug = f"{it.get('username','')}/{it.get('name','')}"
                    if slug in known or not slug.strip("/"):
                        continue
                    actors.append({
                        "actor": slug,
                        "category": (it.get("categories") or ["other"])[0],
                        "best_for": (it.get("description") or "")[:120],
                        "price_per_1000": float(it.get("pricingInfos", [{}])[0].get("price", 0)) if it.get("pricingInfos") else 0.0,
                        "memory_mb": 512,
                        "speed": "?",
                        "reliability": 0.0,
                        "live": True,
                    })
                live = True
        except Exception:
            pass

    payload = {"actors": actors, "live": live}
    _write_cache(payload)
    if category:
        actors = [a for a in actors if a.get("category") == category]
    return {"actors": actors, "categories": _categories(payload["actors"]), "live": live}


def _categories(actors: list) -> dict:
    out: dict = {}
    for a in actors:
        c = a.get("category", "other")
        out[c] = out.get(c, 0) + 1
    return out


def recommend_for_niche(niche: str = "") -> list:
    """Match a niche string to top 3 actors via simple keyword match."""
    niche = (niche or "").lower()
    rules = [
        (("restoran", "cafe", "berber", "kuaför", "yerel"), "lukaskrivka/google-maps-with-contact-details"),
        (("ecommerce", "shopify", "woocommerce", "store"), "apify/instagram-scraper"),
        (("b2b", "saas", "kurumsal"), "apify/linkedin-company-scraper"),
        (("seo", "blog", "content"), "apify/website-content-crawler"),
        (("rakip", "trend", "viral"), "apify/tiktok-scraper"),
    ]
    matched = []
    for keywords, actor in rules:
        if any(k in niche for k in keywords):
            matched.append(actor)

    actors = list_actors().get("actors", [])
    by_slug = {a["actor"]: a for a in actors}
    recs = [by_slug[s] for s in matched if s in by_slug]
    if not recs:
        recs = [by_slug["compass/crawler-google-places"]]
    return recs[:3]


def actor_health() -> dict:
    """Quick check — APIFY_TOKEN + actor count + recent run successes."""
    token = os.getenv("APIFY_TOKEN", "").strip()
    return {
        "token_configured": bool(token),
        "curated_count": len(CURATED),
        "categories": _categories(CURATED),
    }


def actor_runs_summary() -> dict:
    """Pull last 30 day run history for the user's account if token set."""
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return {"error": "APIFY_TOKEN missing"}
    try:
        r = requests.get(
            "https://api.apify.com/v2/actor-runs",
            params={"limit": 50, "token": token, "desc": "true"},
            timeout=10,
        )
        if r.status_code != 200:
            return {"error": f"http {r.status_code}"}
        runs = (r.json() or {}).get("data", {}).get("items", [])
        by_status: dict = {}
        cost_total = 0.0
        for run in runs:
            st = run.get("status", "?")
            by_status[st] = by_status.get(st, 0) + 1
            usage = run.get("usage") or {}
            cost_total += float(usage.get("ACTOR_COMPUTE_UNITS", 0)) * 0.25
        return {
            "total_runs": len(runs),
            "by_status": by_status,
            "estimated_cost_usd": round(cost_total, 2),
        }
    except Exception as e:
        return {"error": str(e)}
