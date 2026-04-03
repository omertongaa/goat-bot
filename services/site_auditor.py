"""Site Auditor Service — Free website analysis for leads.

Provides three audit types:
1. Broken link checker
2. SEO meta tag checker
3. Tech stack detector

All pure Python, no API keys needed.
"""

import re
import requests
from urllib.parse import urljoin, urlparse


TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Tech stack detection patterns: (name, check_type, pattern)
TECH_PATTERNS = [
    # CMS
    ("WordPress", "meta", "generator", "wordpress"),
    ("WordPress", "html", r'wp-content|wp-includes'),
    ("Joomla", "meta", "generator", "joomla"),
    ("Drupal", "html", r'Drupal\.settings|drupal\.js'),
    ("Wix", "html", r'wix\.com|_wix'),
    ("Squarespace", "html", r'squarespace\.com|static\.squarespace'),
    ("Webflow", "html", r'webflow\.com|w-webflow'),
    ("Shopify", "html", r'cdn\.shopify\.com|shopify\.'),
    ("PrestaShop", "html", r'prestashop|/modules/ps_'),
    # Frameworks
    ("React", "html", r'react\.production\.min\.js|__react|_react'),
    ("Next.js", "html", r'_next/static|__next'),
    ("Vue.js", "html", r'vue\.min\.js|vue\.runtime|v-cloak'),
    ("Angular", "html", r'ng-version|angular\.min\.js'),
    ("Bootstrap", "html", r'bootstrap\.min\.(css|js)'),
    ("Tailwind CSS", "html", r'tailwindcss|tailwind\.min'),
    ("jQuery", "html", r'jquery\.min\.js|jquery-\d'),
    # Analytics / Marketing
    ("Google Analytics", "html", r'google-analytics\.com|gtag|googletagmanager'),
    ("Google Tag Manager", "html", r'googletagmanager\.com/gtm'),
    ("Facebook Pixel", "html", r'connect\.facebook\.net|fbevents\.js|fbq\('),
    ("Hotjar", "html", r'hotjar\.com|_hjSettings'),
    ("HubSpot", "html", r'hubspot\.com|hs-scripts'),
    # E-commerce
    ("WooCommerce", "html", r'woocommerce|wc-blocks'),
    ("Magento", "html", r'mage/|Magento_'),
    # Hosting / CDN
    ("Cloudflare", "header", "server", "cloudflare"),
    ("Cloudflare", "header", "cf-ray", ""),
    ("Vercel", "header", "x-vercel-id", ""),
    ("Netlify", "header", "x-nf-request-id", ""),
    ("AWS", "header", "x-amz-", ""),
    ("nginx", "header", "server", "nginx"),
    ("Apache", "header", "server", "apache"),
    # Other
    ("Google Fonts", "html", r'fonts\.googleapis\.com'),
    ("Font Awesome", "html", r'font-awesome|fontawesome'),
    ("reCAPTCHA", "html", r'recaptcha|grecaptcha'),
    ("Crisp Chat", "html", r'crisp\.chat|client\.crisp'),
    ("Intercom", "html", r'intercom\.com|intercomSettings'),
    ("Tawk.to", "html", r'tawk\.to|embed\.tawk'),
    ("WhatsApp Widget", "html", r'wa\.me|whatsapp\.com/send|whatsapp-widget'),
]


def fetch_page(url: str) -> dict:
    """Fetch a page and return {html, headers, status, url}."""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return {
            "html": resp.text,
            "headers": dict(resp.headers),
            "status": resp.status_code,
            "url": resp.url,
        }
    except Exception:
        # Try http if https fails
        if url.startswith("https://"):
            try:
                http_url = url.replace("https://", "http://", 1)
                resp = requests.get(http_url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
                return {
                    "html": resp.text,
                    "headers": dict(resp.headers),
                    "status": resp.status_code,
                    "url": resp.url,
                }
            except Exception:
                pass
        return None


def check_broken_links(url: str, max_links: int = 30) -> dict:
    """Check for broken links on a page. Returns summary + broken list."""
    page = fetch_page(url)
    if not page:
        return {"error": "Site erişilemedi", "url": url, "broken": [], "total_checked": 0}

    # Extract all links
    link_pattern = re.compile(r'href=["\']([^"\'#]+)["\']', re.IGNORECASE)
    raw_links = link_pattern.findall(page["html"])

    # Normalize and deduplicate
    base_url = page["url"]
    links = set()
    for link in raw_links:
        if link.startswith("mailto:") or link.startswith("tel:") or link.startswith("javascript:"):
            continue
        full = urljoin(base_url, link)
        if urlparse(full).scheme in ("http", "https"):
            links.add(full)

    # Check each link (limited)
    links = list(links)[:max_links]
    broken = []
    for link in links:
        try:
            r = requests.head(link, headers=HEADERS, timeout=5, allow_redirects=True)
            if r.status_code >= 400:
                broken.append({"url": link, "status": r.status_code})
        except Exception:
            broken.append({"url": link, "status": "timeout"})

    return {
        "url": url,
        "total_checked": len(links),
        "broken_count": len(broken),
        "broken": broken,
        "score": max(0, 100 - (len(broken) * 20)),  # Rough health score
    }


def check_seo(url: str) -> dict:
    """Check SEO meta tags on a page."""
    page = fetch_page(url)
    if not page:
        return {"error": "Site erişilemedi", "url": url, "issues": [], "score": 0}

    html = page["html"]
    issues = []
    score = 100

    # Title
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    if not title:
        issues.append({"type": "critical", "issue": "Title tag eksik"})
        score -= 25
    elif len(title) < 10:
        issues.append({"type": "warning", "issue": f"Title çok kısa ({len(title)} karakter)", "value": title})
        score -= 10
    elif len(title) > 60:
        issues.append({"type": "warning", "issue": f"Title çok uzun ({len(title)} karakter)", "value": title})
        score -= 5

    # Meta description
    desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
    desc = desc_match.group(1).strip() if desc_match else ""
    if not desc:
        issues.append({"type": "critical", "issue": "Meta description eksik"})
        score -= 20
    elif len(desc) < 50:
        issues.append({"type": "warning", "issue": f"Meta description çok kısa ({len(desc)} karakter)"})
        score -= 10

    # Open Graph
    og_title = re.search(r'<meta[^>]*property=["\']og:title["\']', html, re.IGNORECASE)
    og_desc = re.search(r'<meta[^>]*property=["\']og:description["\']', html, re.IGNORECASE)
    og_image = re.search(r'<meta[^>]*property=["\']og:image["\']', html, re.IGNORECASE)
    if not og_title:
        issues.append({"type": "warning", "issue": "Open Graph title eksik (sosyal medya paylaşımlarında kötü görünür)"})
        score -= 5
    if not og_desc:
        issues.append({"type": "warning", "issue": "Open Graph description eksik"})
        score -= 5
    if not og_image:
        issues.append({"type": "warning", "issue": "Open Graph image eksik (sosyal medyada görsel çıkmaz)"})
        score -= 5

    # H1
    h1_match = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if not h1_match:
        issues.append({"type": "warning", "issue": "H1 tag eksik"})
        score -= 10
    elif len(h1_match) > 1:
        issues.append({"type": "info", "issue": f"Birden fazla H1 tag ({len(h1_match)} adet)"})
        score -= 3

    # Viewport (mobile)
    viewport = re.search(r'<meta[^>]*name=["\']viewport["\']', html, re.IGNORECASE)
    if not viewport:
        issues.append({"type": "critical", "issue": "Viewport meta eksik — mobil uyumsuz"})
        score -= 15

    # Canonical
    canonical = re.search(r'<link[^>]*rel=["\']canonical["\']', html, re.IGNORECASE)
    if not canonical:
        issues.append({"type": "info", "issue": "Canonical URL belirtilmemiş"})
        score -= 3

    # HTTPS
    if not page["url"].startswith("https"):
        issues.append({"type": "critical", "issue": "HTTPS kullanılmıyor — güvensiz site"})
        score -= 15

    # robots.txt check
    robots_url = urljoin(page["url"], "/robots.txt")
    try:
        r = requests.get(robots_url, headers=HEADERS, timeout=5)
        has_robots = r.status_code == 200 and len(r.text) > 10
    except Exception:
        has_robots = False
    if not has_robots:
        issues.append({"type": "info", "issue": "robots.txt bulunamadı"})

    # sitemap check
    sitemap_url = urljoin(page["url"], "/sitemap.xml")
    try:
        r = requests.get(sitemap_url, headers=HEADERS, timeout=5)
        has_sitemap = r.status_code == 200 and "urlset" in r.text.lower()
    except Exception:
        has_sitemap = False
    if not has_sitemap:
        issues.append({"type": "info", "issue": "sitemap.xml bulunamadı"})

    return {
        "url": url,
        "title": title,
        "description": desc,
        "score": max(0, score),
        "issues": issues,
        "has_robots": has_robots,
        "has_sitemap": has_sitemap,
    }


def detect_tech_stack(url: str) -> dict:
    """Detect the technology stack of a website."""
    page = fetch_page(url)
    if not page:
        return {"error": "Site erişilemedi", "url": url, "technologies": []}

    html = page["html"]
    headers = page["headers"]
    detected = set()

    for pattern in TECH_PATTERNS:
        name = pattern[0]
        check_type = pattern[1]

        if check_type == "html":
            regex = pattern[2]
            if re.search(regex, html, re.IGNORECASE):
                detected.add(name)

        elif check_type == "meta":
            meta_name = pattern[2]
            keyword = pattern[3]
            meta_match = re.search(
                rf'<meta[^>]*name=["\']{ re.escape(meta_name) }["\'][^>]*content=["\']([^"\']*)["\']',
                html, re.IGNORECASE,
            )
            if meta_match and keyword.lower() in meta_match.group(1).lower():
                detected.add(name)

        elif check_type == "header":
            header_name = pattern[2]
            keyword = pattern[3]
            for hname, hval in headers.items():
                if header_name.lower() in hname.lower():
                    if not keyword or keyword.lower() in hval.lower():
                        detected.add(name)

    # Categorize
    categories = {
        "CMS": ["WordPress", "Joomla", "Drupal", "Wix", "Squarespace", "Webflow", "Shopify", "PrestaShop"],
        "Framework": ["React", "Next.js", "Vue.js", "Angular", "Bootstrap", "Tailwind CSS", "jQuery"],
        "Analytics": ["Google Analytics", "Google Tag Manager", "Facebook Pixel", "Hotjar", "HubSpot"],
        "E-commerce": ["WooCommerce", "Magento", "Shopify"],
        "Hosting": ["Cloudflare", "Vercel", "Netlify", "AWS", "nginx", "Apache"],
        "Tools": ["Google Fonts", "Font Awesome", "reCAPTCHA", "Crisp Chat", "Intercom", "Tawk.to", "WhatsApp Widget"],
    }

    categorized = {}
    for cat, techs in categories.items():
        found = [t for t in techs if t in detected]
        if found:
            categorized[cat] = found

    return {
        "url": url,
        "technologies": sorted(detected),
        "categorized": categorized,
        "total_detected": len(detected),
    }


def full_audit(url: str) -> dict:
    """Run all three audits on a URL. Returns combined report."""
    seo = check_seo(url)
    broken = check_broken_links(url)
    tech = detect_tech_stack(url)

    # Overall score
    overall_score = 0
    count = 0
    if "score" in seo:
        overall_score += seo["score"]
        count += 1
    if "score" in broken:
        overall_score += broken["score"]
        count += 1
    overall_score = round(overall_score / count) if count else 0

    return {
        "url": url,
        "overall_score": overall_score,
        "seo": seo,
        "broken_links": broken,
        "tech_stack": tech,
    }
