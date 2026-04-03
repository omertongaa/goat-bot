"""Free Lead Discovery — DuckDuckGo + page scraping.

Uses duckduckgo-search as a free fallback when APIFY_TOKEN is not set.
Results are decent but less structured than Apify/Google Maps.
"""

import re
import requests
from duckduckgo_search import DDGS

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def search_businesses(query: str, location: str = "", num_results: int = 20):
    """Search DuckDuckGo for businesses and extract basic info."""
    search_query = f"{query} {location}".strip() if location else query

    leads = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, region="wt-wt", max_results=num_results * 2))

        for r in results:
            url = r.get("href", "")

            # Skip social media, directories
            skip_domains = [
                "facebook.com", "instagram.com", "twitter.com", "youtube.com",
                "linkedin.com", "tripadvisor.com", "yelp.com", "wikipedia.org",
                "google.com", "yemeksepeti.com", "getir.com", "foursquare.com",
                "klinikbewertungen.de", "sahibinden.com", "sikayetvar.com",
                "reddit.com", "pinterest.com", "tiktok.com",
            ]
            if any(d in url for d in skip_domains):
                continue

            lead = _extract_info_from_url(url)
            if lead:
                # Use DDG snippet as fallback description
                if not lead.get("description") and r.get("body"):
                    lead["description"] = r["body"][:300]
                # Use DDG title as fallback name
                if not lead.get("name") or lead["name"] == url:
                    lead["name"] = r.get("title", url).split(" - ")[0].split(" | ")[0].strip()
                lead["source"] = "duckduckgo_search"
                lead["search_query"] = search_query
                leads.append(lead)

    except Exception as e:
        print(f"DuckDuckGo search error: {e}")

    return leads


def _extract_info_from_url(url: str) -> dict:
    """Try to extract business info from a URL by fetching the page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if resp.status_code != 200:
            return None

        html = resp.text

        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        name = title_match.group(1).strip() if title_match else url
        name = re.split(r'\s*[-|–—]\s*', name)[0].strip()

        # Extract description
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if not desc_match:
            desc_match = re.search(
                r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
                html, re.IGNORECASE,
            )
        description = desc_match.group(1).strip() if desc_match else ""

        # Extract email
        email_match = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
        emails = [e for e in email_match if not any(x in e.lower() for x in
                  ["example.com", "domain.com", "email.com", "wixpress", "sentry"])]
        email = emails[0] if emails else ""

        # Extract phone (Turkish format)
        phone_match = re.findall(
            r'(?:\+90|0)[\s-]?\(?[0-9]{3}\)?[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2}', html
        )
        phone = phone_match[0].strip() if phone_match else ""

        # Extract address hints
        address = ""
        addr_match = re.search(
            r'<[^>]*(?:class|itemprop)=["\'][^"\']*address[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            html, re.IGNORECASE | re.DOTALL,
        )
        if addr_match:
            address = re.sub(r'<[^>]+>', '', addr_match.group(1)).strip()

        return {
            "name": name[:100],
            "website": url,
            "email": email,
            "phone": phone,
            "address": address[:200],
            "description": description[:300],
            "rating": 0,
            "review_count": 0,
            "category": "",
            "location": "",
            "google_maps_url": "",
        }

    except Exception:
        return None


def search_and_enrich(query: str, location: str = "", num_results: int = 15):
    """Search and return enriched leads ready for the Filter agent."""
    leads = search_businesses(query, location, num_results)

    for lead in leads:
        if lead.get("email"):
            lead["_has_contact"] = True
        if lead.get("phone"):
            lead["_has_contact"] = True

    return leads
