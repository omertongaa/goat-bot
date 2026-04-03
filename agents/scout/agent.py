"""Scout — Lead Finder Agent

Scrapes Google Maps via Apify to find potential clients
for the user's automation agency.
"""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR
from services.scraper import scrape_google_maps


class ScoutAgent(BaseAgent):
    agent_id = "scout"
    name = "Scout"
    role = "Finds potential clients via Google Maps / Apify"
    category = "acquisition"

    def run(self, query: str = "", location: str = "", limit: int = 50) -> dict:
        config = self.load_config()

        # Use provided params or fall back to user_profile config
        if not query:
            industries = config.get("target_industries", [])
            query = industries[0] if industries else "restaurants"
        if not location:
            cities = config.get("target_cities", [])
            location = cities[0] if cities else ""

        self.log(f"Searching for '{query}' in '{location}' (limit: {limit})...")

        import os
        used_fallback = False
        has_apify = bool(os.environ.get("APIFY_TOKEN", "").strip())

        if has_apify:
            leads = scrape_google_maps(
                query=query,
                location=location,
                max_results=limit,
                log=self.log,
            )
        else:
            leads = []

        # Fallback: try free DuckDuckGo search if Apify unavailable
        if not leads:
            if not has_apify:
                self.log("⚠ APIFY_TOKEN not set — using free search (limited results)")
            else:
                self.log("Apify returned no results, trying free search fallback...")
            try:
                from services.google_search import search_and_enrich
                leads = search_and_enrich(query, location, min(limit, 20))
                if leads:
                    used_fallback = True
                    self.log(f"Free search found {len(leads)} leads")
            except Exception as e:
                self.log(f"Free search fallback failed: {e}")

        if not leads:
            # Check for cached data
            cached = self._load_latest_raw()
            if cached:
                self.log(f"Using cached data: {len(cached)} leads")
                leads = cached
            else:
                return {
                    "status": "error",
                    "summary": "Lead bulunamadı. APIFY_TOKEN ayarlanmamış ve ücretsiz arama da sonuç döndüremedi.",
                    "metrics": {},
                    "leads": [],
                    "recommendations": [
                        "APIFY_TOKEN'ı .env dosyasına ekle (en iyi sonuçlar için — console.apify.com)",
                        "Farklı bir arama terimi veya şehir dene",
                    ],
                }

        # Save raw results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = query.lower().replace(" ", "_")[:30]
        filename = f"leads/raw/{timestamp}_{slug}.json"
        self.save_data(filename, {
            "query": query,
            "location": location,
            "scraped_at": datetime.now().isoformat(),
            "count": len(leads),
            "leads": leads,
        })

        # Strip raw field for the report
        clean_leads = [{k: v for k, v in l.items() if k != "raw"} for l in leads]

        # Stats
        with_email = sum(1 for l in leads if l.get("email"))
        with_website = sum(1 for l in leads if l.get("website"))
        with_phone = sum(1 for l in leads if l.get("phone"))
        avg_rating = sum(l.get("rating", 0) for l in leads) / len(leads) if leads else 0

        fallback_warning = ""
        if used_fallback:
            fallback_warning = " ⚠ Ücretsiz arama kullanıldı — daha iyi sonuçlar için APIFY_TOKEN ekle."

        results = {
            "status": "ok",
            "summary": f"Found {len(leads)} businesses for '{query}' in {location or 'all locations'}.{fallback_warning}",
            "metrics": {
                "total_found": len(leads),
                "with_email": with_email,
                "with_website": with_website,
                "with_phone": with_phone,
                "avg_rating": round(avg_rating, 1),
                "query": query,
                "location": location,
                "scraped_at": datetime.now().isoformat(),
            },
            "leads": clean_leads[:20],  # Top 20 in report
            "recommendations": [
                f"Found {with_email} leads with email — ready for outreach",
                f"{with_website} have websites — check for automation opportunities",
                "Run Filter agent next to score and rank these leads",
            ] + (["⚠ Ücretsiz arama kullanıldı. Apify ile Google Maps verisi çok daha zengin (rating, yorum, kategori). console.apify.com'dan ücretsiz token al."] if used_fallback else []),
        }

        self.save_output("scout_leads_report.json", results)
        self.log(f"Done: {len(leads)} leads found, {with_email} with email")
        return results

    def _load_latest_raw(self) -> list:
        """Load the most recent raw scrape file."""
        raw_dir = DATA_DIR / "leads" / "raw"
        if not raw_dir.exists():
            return []
        files = sorted(raw_dir.glob("*.json"), reverse=True)
        if files:
            with open(files[0]) as f:
                data = json.load(f)
                return data.get("leads", [])
        return []
