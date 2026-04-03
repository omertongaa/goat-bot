"""Site Builder Service — Generates professional landing pages.

Two modes:
1. Agency site — builds the user's own agency website
2. Client site — builds a landing page for a client/lead as a deliverable

All generated HTML is self-contained with inline CSS. No external dependencies
except optional Google Fonts. Output goes to outputs/sites/.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "sites"


def _slugify(text):
    # type: (str) -> str
    s = text.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    return s


def _get_category_theme(category):
    # type: (str) -> Dict[str, str]
    """Return color theme based on business category."""
    cat = (category or "").lower()
    themes = {
        "restoran": {"primary": "#e85d26", "secondary": "#ff7a45", "accent": "#fbbf24", "bg": "#1a1008"},
        "restaurant": {"primary": "#e85d26", "secondary": "#ff7a45", "accent": "#fbbf24", "bg": "#1a1008"},
        "cafe": {"primary": "#8B6914", "secondary": "#D4A843", "accent": "#f5e6c8", "bg": "#1a1508"},
        "klinik": {"primary": "#2563eb", "secondary": "#3b82f6", "accent": "#93c5fd", "bg": "#081a2a"},
        "clinic": {"primary": "#2563eb", "secondary": "#3b82f6", "accent": "#93c5fd", "bg": "#081a2a"},
        "otel": {"primary": "#7c3aed", "secondary": "#8b5cf6", "accent": "#c4b5fd", "bg": "#1a0830"},
        "hotel": {"primary": "#7c3aed", "secondary": "#8b5cf6", "accent": "#c4b5fd", "bg": "#1a0830"},
        "emlak": {"primary": "#059669", "secondary": "#10b981", "accent": "#6ee7b7", "bg": "#081a14"},
        "kuafor": {"primary": "#db2777", "secondary": "#ec4899", "accent": "#f9a8d4", "bg": "#2a0818"},
        "spor": {"primary": "#ea580c", "secondary": "#f97316", "accent": "#fdba74", "bg": "#1a1008"},
        "gym": {"primary": "#ea580c", "secondary": "#f97316", "accent": "#fdba74", "bg": "#1a1008"},
        "oto": {"primary": "#64748b", "secondary": "#94a3b8", "accent": "#e2e8f0", "bg": "#0f1218"},
        "auto": {"primary": "#64748b", "secondary": "#94a3b8", "accent": "#e2e8f0", "bg": "#0f1218"},
    }
    for key, theme in themes.items():
        if key in cat:
            return theme
    return {"primary": "#e85d26", "secondary": "#ff7a45", "accent": "#fbbf24", "bg": "#0a0a0c"}


def _get_category_services(category):
    # type: (str) -> List[Dict[str, str]]
    """Generate service items based on business category."""
    cat = (category or "").lower()
    defaults = [
        {"icon": "&#9733;", "title": "Kaliteli Hizmet", "desc": "Alaninda uzman ekibimizle en iyi hizmeti sunuyoruz."},
        {"icon": "&#9889;", "title": "Hizli Sonuc", "desc": "Zamaniniz degerli. Hizli ve etkili cozumler uretiyoruz."},
        {"icon": "&#9829;", "title": "Musteri Memnuniyeti", "desc": "Musterilerimizin memnuniyeti en buyuk oncelimizdir."},
        {"icon": "&#128640;", "title": "Modern Yaklasim", "desc": "En guncel yontem ve teknolojileri kullaniyoruz."},
    ]
    if "restoran" in cat or "restaurant" in cat or "cafe" in cat:
        return [
            {"icon": "&#127860;", "title": "Lezzetli Menu", "desc": "Ozenle hazirlanan yemeklerimizle damak zevkinize hitap ediyoruz."},
            {"icon": "&#127861;", "title": "Ozel Icecekler", "desc": "Baristalanmizin hazirladigi ozel icecekler sizi bekliyor."},
            {"icon": "&#127881;", "title": "Ozel Etkinlikler", "desc": "Dogum gunu, is yemegi ve ozel gunleriniz icin ideal mekan."},
            {"icon": "&#128666;", "title": "Paket Servis", "desc": "Lezzetlerimizi kapisiniza kadar getiriyoruz."},
        ]
    if "klinik" in cat or "clinic" in cat or "dis" in cat or "doktor" in cat:
        return [
            {"icon": "&#129657;", "title": "Uzman Kadro", "desc": "Alaninda uzman doktorlarimizla guvenilir saglik hizmeti."},
            {"icon": "&#128171;", "title": "Modern Teknoloji", "desc": "Son teknoloji cihazlarla tani ve tedavi."},
            {"icon": "&#128336;", "title": "Randevu Sistemi", "desc": "Online randevu ile bekleme suresi minimum."},
            {"icon": "&#10084;", "title": "Hasta Takibi", "desc": "Tedavi sonrasi duzenli kontrol ve takip."},
        ]
    if "otel" in cat or "hotel" in cat:
        return [
            {"icon": "&#127968;", "title": "Konforlu Odalar", "desc": "Her butceye uygun, konforlu ve temiz odalar."},
            {"icon": "&#127796;", "title": "Havuz & Spa", "desc": "Havuz, spa ve wellness hizmetleriyle kendinizi simartm."},
            {"icon": "&#127860;", "title": "Restoranlar", "desc": "Acik bufe kahvalti ve a la carte restoran secenekleri."},
            {"icon": "&#128205;", "title": "Merkezi Konum", "desc": "Sehrin kalbinde, ulasimi kolay bir konum."},
        ]
    return defaults


def _stars_html(rating):
    # type: (float) -> str
    """Generate CSS star rating HTML."""
    if not rating:
        return ""
    full = int(rating)
    has_half = (rating - full) >= 0.3
    empty = 5 - full - (1 if has_half else 0)
    stars = "&#9733;" * full
    if has_half:
        stars += "&#9734;"
    stars += "&#9734;" * empty
    return '<span class="stars">{stars}</span> <span class="rating-num">{rating}</span>'.format(
        stars=stars, rating=rating
    )


def generate_agency_site(config):
    # type: (Dict[str, Any]) -> Optional[str]
    """Generate agency landing page from user config. Returns path to HTML file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    agency_name = config.get("agency_name", "My Agency")
    owner_name = config.get("owner_name", "")
    niche = config.get("niche", "dijital pazarlama")
    cities = config.get("target_cities", [])
    services = config.get("services", None)

    if not services:
        services = [
            {"title": "Dijital Pazarlama", "desc": "Google ve sosyal medya reklamlari ile musterilerinize ulasin.", "icon": "&#128200;"},
            {"title": "Web Tasarim", "desc": "Modern, mobil uyumlu ve SEO dostu web siteleri tasarliyoruz.", "icon": "&#128187;"},
            {"title": "Sosyal Medya Yonetimi", "desc": "Instagram, Facebook ve TikTok hesaplarinizi profesyonelce yonetiyoruz.", "icon": "&#128241;"},
            {"title": "AI Otomasyon", "desc": "Yapay zeka ile is sureclerinizi otomatiklestirin, zamandan tasarruf edin.", "icon": "&#129302;"},
        ]

    cities_text = ", ".join(cities) if cities else "Turkiye"
    tagline = "{niche} sektorunde dijital donusum ortaginiz".format(niche=niche)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(agency_name)
    filename = "agency_{slug}_{ts}.html".format(slug=slug, ts=timestamp)
    filepath = OUTPUT_DIR / filename

    html = _AGENCY_TEMPLATE.format(
        agency_name=agency_name,
        owner_name=owner_name,
        niche=niche,
        cities_text=cities_text,
        tagline=tagline,
        services_html=_build_services_html(services),
        num_cities=len(cities) if cities else 1,
        year=datetime.now().year,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return str(filepath)


def generate_client_site(lead_data, agency_config=None, audit_data=None):
    # type: (Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]) -> Optional[str]
    """Generate a landing page for a client/lead. Returns path to HTML file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    name = lead_data.get("name", lead_data.get("title", "Business"))
    category = lead_data.get("category", lead_data.get("categoryName", ""))
    phone = lead_data.get("phone", "")
    email = lead_data.get("email", "")
    address = lead_data.get("address", lead_data.get("street", ""))
    website = lead_data.get("website", lead_data.get("url", ""))
    rating = lead_data.get("totalScore", lead_data.get("rating", 0))
    review_count = lead_data.get("reviewsCount", lead_data.get("review_count", 0))

    theme = _get_category_theme(category)
    cat_services = _get_category_services(category)

    # Build stars
    stars = _stars_html(rating) if rating else ""
    review_text = ""
    if rating and review_count:
        review_text = "{rating} puan &middot; {count} degerlendirme".format(rating=rating, count=review_count)

    # WhatsApp link
    whatsapp_html = ""
    if phone:
        clean_phone = re.sub(r'[^0-9+]', '', phone)
        whatsapp_html = '<a href="https://wa.me/{phone}" class="btn btn-whatsapp" target="_blank">&#128172; WhatsApp</a>'.format(
            phone=clean_phone.lstrip('+')
        )

    # Phone button
    phone_html = ""
    if phone:
        phone_html = '<a href="tel:{phone}" class="btn btn-phone">&#128222; {phone}</a>'.format(phone=phone)

    # Email button
    email_html = ""
    if email:
        email_html = '<a href="mailto:{email}" class="btn btn-email">&#9993; E-posta</a>'.format(email=email)

    # Audit insights
    audit_html = ""
    if audit_data:
        score = audit_data.get("overall_score", audit_data.get("seo", {}).get("score", ""))
        if score:
            audit_html = "<!-- Site audit skoru: {score}/100 - Bu site o skordan daha iyi olmali -->".format(score=score)

    # Services HTML
    services_html = ""
    for svc in cat_services:
        services_html += """
        <div class="feature-card">
          <div class="feature-icon">{icon}</div>
          <h3>{title}</h3>
          <p>{desc}</p>
        </div>""".format(**svc)

    # Agency credit
    agency_credit = ""
    if agency_config and agency_config.get("agency_name"):
        agency_credit = agency_config["agency_name"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(name)
    filename = "client_{slug}_{ts}.html".format(slug=slug, ts=timestamp)
    filepath = OUTPUT_DIR / filename

    html = _CLIENT_TEMPLATE.format(
        business_name=name,
        category=category or "Isletme",
        phone=phone,
        email=email,
        address=address,
        stars_html=stars,
        review_text=review_text,
        services_html=services_html,
        whatsapp_html=whatsapp_html,
        phone_html=phone_html,
        email_html=email_html,
        audit_html=audit_html,
        agency_credit=agency_credit,
        primary=theme["primary"],
        secondary=theme["secondary"],
        accent=theme["accent"],
        bg=theme["bg"],
        year=datetime.now().year,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return str(filepath)


def generate_site(site_type, data):
    # type: (str, Dict[str, Any]) -> Optional[str]
    """Universal entry point. site_type is 'agency' or 'client'."""
    if site_type == "agency":
        return generate_agency_site(data)
    elif site_type == "client":
        lead = data.get("lead", data)
        config = data.get("config", {})
        audit = data.get("audit", None)
        return generate_client_site(lead, config, audit)
    return None


def _build_services_html(services):
    # type: (List[Dict[str, str]]) -> str
    html = ""
    for i, svc in enumerate(services):
        span_class = " span-2" if i == 0 else ""
        html += """
        <div class="service-card{span_class}">
          <div class="service-icon">{icon}</div>
          <h3>{title}</h3>
          <p>{desc}</p>
        </div>""".format(
            span_class=span_class,
            icon=svc.get("icon", "&#9733;"),
            title=svc.get("title", ""),
            desc=svc.get("desc", ""),
        )
    return html


# ══════════════════════════════════════════════
# AGENCY SITE TEMPLATE
# ══════════════════════════════════════════════

_AGENCY_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{agency_name} — {tagline}</title>
<meta name="description" content="{agency_name} — {tagline}. {cities_text} bolgesinde hizmet veriyoruz.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

:root {{
  --primary: #e85d26;
  --primary-light: #ff7a45;
  --primary-dark: #c94d1e;
  --bg: #0a0a0c;
  --surface: rgba(17,17,20,0.6);
  --surface-solid: #111114;
  --surface2: #1a1a1e;
  --text: #ededf0;
  --dim: #8a8a9c;
  --border: rgba(255,255,255,0.06);
  --glow: rgba(232,93,38,0.15);
}}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}}

/* ── NOISE & DOT OVERLAY ── */
body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  background-size: 256px 256px;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.5;
}}

body::after {{
  content: '';
  position: fixed;
  inset: 0;
  background-image: radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  pointer-events: none;
  z-index: 0;
}}

/* ── FLOATING NAV ── */
.nav {{
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(-80px);
  z-index: 1000;
  background: rgba(17,17,20,0.7);
  backdrop-filter: blur(20px) saturate(1.8);
  -webkit-backdrop-filter: blur(20px) saturate(1.8);
  border: 1px solid var(--border);
  border-radius: 100px;
  padding: 10px 12px 10px 24px;
  display: flex;
  align-items: center;
  gap: 24px;
  transition: transform 0.5s cubic-bezier(0.16,1,0.3,1);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}}

.nav.visible {{
  transform: translateX(-50%) translateY(0);
}}

.nav-logo {{
  font-weight: 800;
  font-size: 0.9rem;
  letter-spacing: -0.02em;
  white-space: nowrap;
  color: var(--text);
}}

.nav-links {{
  display: flex;
  align-items: center;
  gap: 6px;
}}

.nav-links a {{
  color: var(--dim);
  text-decoration: none;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 100px;
  transition: all 0.2s;
}}

.nav-links a:hover {{
  color: var(--text);
  background: rgba(255,255,255,0.05);
}}

.nav-cta {{
  background: var(--primary) !important;
  color: #fff !important;
  font-weight: 600 !important;
  padding: 8px 20px !important;
}}

.nav-cta:hover {{
  background: var(--primary-light) !important;
  box-shadow: 0 0 20px var(--glow);
}}

/* ── HERO ── */
.hero {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 2rem;
  position: relative;
  overflow: hidden;
  z-index: 1;
}}

.hero::before {{
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 30% 20%, rgba(232,93,38,0.15) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 70%, rgba(255,122,69,0.08) 0%, transparent 50%),
    radial-gradient(ellipse 40% 40% at 50% 50%, rgba(232,93,38,0.04) 0%, transparent 70%);
  pointer-events: none;
  animation: heroGlow 8s ease-in-out infinite alternate;
}}

@keyframes heroGlow {{
  0% {{ opacity: 1; transform: scale(1); }}
  100% {{ opacity: 0.7; transform: scale(1.05); }}
}}

.hero::after {{
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: linear-gradient(to top, var(--bg), transparent);
  z-index: 1;
}}

.hero-badge {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  background: rgba(232,93,38,0.08);
  border: 1px solid rgba(232,93,38,0.15);
  border-radius: 100px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--primary-light);
  margin-bottom: 2.5rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  position: relative;
  z-index: 2;
  animation: fadeUp 0.8s ease both;
}}

.hero h1 {{
  font-size: clamp(3rem, 8vw, 6.5rem);
  font-weight: 900;
  letter-spacing: -0.04em;
  line-height: 1.05;
  margin-bottom: 1.5rem;
  position: relative;
  z-index: 2;
}}

.hero-title-wrap {{
  overflow: hidden;
  display: block;
}}

.hero-title-inner {{
  display: block;
  animation: textReveal 1s cubic-bezier(0.16,1,0.3,1) 0.2s both;
}}

@keyframes textReveal {{
  from {{ transform: translateY(100%); opacity: 0; }}
  to {{ transform: translateY(0); opacity: 1; }}
}}

.hero h1 span {{
  background: linear-gradient(135deg, var(--primary), var(--primary-light), #fbbf24, var(--primary));
  background-size: 300% 300%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: gradientMove 6s ease infinite;
}}

@keyframes gradientMove {{
  0% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }}
}}

.hero p {{
  font-size: clamp(1.05rem, 2.5vw, 1.3rem);
  color: var(--dim);
  max-width: 600px;
  margin-bottom: 3rem;
  position: relative;
  z-index: 2;
  animation: fadeUp 0.8s ease 0.4s both;
}}

@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(24px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.btn-primary {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 18px 40px;
  background: var(--primary);
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  border: none;
  border-radius: 14px;
  text-decoration: none;
  cursor: pointer;
  position: relative;
  z-index: 2;
  transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
  animation: fadeUp 0.8s ease 0.6s both, pulse 3s ease-in-out 2s infinite;
  box-shadow: 0 0 0 0 rgba(232,93,38,0.4);
}}

@keyframes pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(232,93,38,0.4); }}
  50% {{ box-shadow: 0 0 0 12px rgba(232,93,38,0); }}
}}

.btn-primary:hover {{
  background: var(--primary-light);
  transform: scale(1.02);
  box-shadow: 0 8px 40px rgba(232,93,38,0.35);
}}

/* ── MARQUEE / SOCIAL PROOF ── */
.marquee-wrap {{
  overflow: hidden;
  padding: 2.5rem 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  position: relative;
  z-index: 1;
}}

.marquee-track {{
  display: flex;
  gap: 3rem;
  animation: marquee 25s linear infinite;
  width: max-content;
}}

@keyframes marquee {{
  0% {{ transform: translateX(0); }}
  100% {{ transform: translateX(-50%); }}
}}

.marquee-item {{
  white-space: nowrap;
  color: var(--dim);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  opacity: 0.7;
}}

.marquee-item span {{
  color: var(--primary);
}}

/* ── CLIENT LOGOS ── */
.logos-section {{
  padding: 5rem 2rem;
  position: relative;
  z-index: 1;
}}

.logos-section .section-label {{
  text-align: center;
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--dim);
  margin-bottom: 2.5rem;
}}

.logos-grid {{
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
  max-width: 900px;
  margin: 0 auto;
}}

.logo-placeholder {{
  width: 120px;
  height: 50px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.05em;
  opacity: 0.5;
}}

/* ── STATS BAR ── */
.stats-bar {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  max-width: 1000px;
  margin: 0 auto;
  padding: 5rem 2rem;
  gap: 2rem;
  position: relative;
  z-index: 1;
}}

.stat-item {{
  text-align: center;
  padding: 2.5rem 1.5rem;
  background: var(--surface);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 20px;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}}

.stat-item::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(232,93,38,0.2), transparent, rgba(232,93,38,0.1));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}}

.stat-item:hover {{
  transform: scale(1.02);
  box-shadow: 0 0 40px rgba(232,93,38,0.08);
}}

.stat-num {{
  font-size: 2.5rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.stat-label {{
  font-size: 0.85rem;
  color: var(--dim);
  margin-top: 6px;
  font-weight: 500;
}}

/* ── SECTIONS ── */
.section {{
  padding: 8rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}}

.section-title {{
  font-size: clamp(2rem, 5vw, 3.2rem);
  font-weight: 900;
  text-align: center;
  margin-bottom: 1rem;
  letter-spacing: -0.03em;
}}

.section-sub {{
  text-align: center;
  color: var(--dim);
  max-width: 550px;
  margin: 0 auto 4rem;
  font-size: 1.1rem;
  line-height: 1.7;
}}

/* ── SERVICES BENTO GRID ── */
.services-grid {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
}}

.service-card {{
  background: var(--surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 2.5rem;
  transition: all 0.4s cubic-bezier(0.16,1,0.3,1);
  position: relative;
  overflow: hidden;
}}

.service-card::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 24px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(232,93,38,0.15), transparent 50%, rgba(232,93,38,0.05));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.4s ease;
}}

.service-card:hover::before {{
  opacity: 1;
}}

.service-card:hover {{
  transform: scale(1.02);
  box-shadow: 0 20px 60px rgba(0,0,0,0.3), 0 0 40px rgba(232,93,38,0.06);
}}

.service-card.span-2 {{
  grid-column: span 2;
}}

.service-icon {{
  font-size: 2rem;
  margin-bottom: 1.25rem;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(232,93,38,0.08);
  border-radius: 16px;
  border: 1px solid rgba(232,93,38,0.1);
}}

.service-card h3 {{
  font-size: 1.2rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
  letter-spacing: -0.01em;
}}

.service-card p {{
  color: var(--dim);
  font-size: 0.95rem;
  line-height: 1.7;
}}

/* ── NEDEN BIZ (WHY US) ── */
.why-section {{
  background: var(--surface-solid);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  position: relative;
  z-index: 1;
}}

.why-grid {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 3rem;
  max-width: 900px;
  margin: 0 auto;
}}

.why-item {{
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
}}

.why-icon {{
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  background: rgba(232,93,38,0.1);
  border: 1px solid rgba(232,93,38,0.15);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
}}

.why-item h4 {{
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 4px;
}}

.why-item p {{
  color: var(--dim);
  font-size: 0.9rem;
  line-height: 1.6;
}}

/* ── PROCESS / WORKFLOW ── */
.process-section {{
  position: relative;
  z-index: 1;
}}

.process-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2rem;
  position: relative;
  max-width: 1000px;
  margin: 0 auto;
}}

.process-grid::before {{
  content: '';
  position: absolute;
  top: 40px;
  left: 10%;
  right: 10%;
  height: 2px;
  background: linear-gradient(to right, transparent, var(--primary), var(--primary-light), transparent);
  opacity: 0.3;
}}

.process-step {{
  text-align: center;
  position: relative;
}}

.step-num {{
  width: 56px;
  height: 56px;
  margin: 0 auto 1.5rem;
  background: var(--surface-solid);
  border: 2px solid var(--primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--primary);
  position: relative;
  z-index: 2;
  box-shadow: 0 0 20px rgba(232,93,38,0.15);
}}

.process-step h4 {{
  font-size: 0.95rem;
  font-weight: 700;
  margin-bottom: 6px;
}}

.process-step p {{
  color: var(--dim);
  font-size: 0.85rem;
  line-height: 1.5;
}}

/* ── ABOUT ── */
.about-section {{
  background: var(--surface-solid);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  position: relative;
  z-index: 1;
}}

.about-inner {{
  max-width: 700px;
  margin: 0 auto;
  text-align: center;
}}

.about-inner h2 {{
  font-size: clamp(1.5rem, 3vw, 2.2rem);
  margin-bottom: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}}

.about-inner p {{
  color: var(--dim);
  font-size: 1.1rem;
  line-height: 1.9;
}}

.about-name {{
  color: var(--primary);
  font-weight: 700;
}}

/* ── FAQ ACCORDION ── */
.faq-section {{
  position: relative;
  z-index: 1;
}}

.faq-list {{
  max-width: 750px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.faq-list details {{
  background: var(--surface);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
}}

.faq-list details[open] {{
  border-color: rgba(232,93,38,0.2);
  box-shadow: 0 0 30px rgba(232,93,38,0.05);
}}

.faq-list summary {{
  padding: 1.5rem 2rem;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: color 0.2s;
}}

.faq-list summary::-webkit-details-marker {{ display: none; }}

.faq-list summary::after {{
  content: '+';
  font-size: 1.3rem;
  color: var(--primary);
  font-weight: 300;
  transition: transform 0.3s ease;
}}

.faq-list details[open] summary::after {{
  transform: rotate(45deg);
}}

.faq-list summary:hover {{
  color: var(--primary-light);
}}

.faq-answer {{
  padding: 0 2rem 1.5rem;
  color: var(--dim);
  font-size: 0.95rem;
  line-height: 1.7;
}}

/* ── CONTACT ── */
.contact-section {{
  text-align: center;
  position: relative;
  z-index: 1;
}}

.contact-cta {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 20px 48px;
  background: var(--primary);
  color: #fff;
  font-size: 1.1rem;
  font-weight: 700;
  border-radius: 16px;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
  margin-top: 2rem;
  animation: pulse 3s ease-in-out 1s infinite;
  box-shadow: 0 0 0 0 rgba(232,93,38,0.4);
}}

.contact-cta:hover {{
  background: var(--primary-light);
  transform: scale(1.02);
  box-shadow: 0 12px 40px rgba(232,93,38,0.3);
}}

.contact-info {{
  display: flex;
  justify-content: center;
  gap: 2.5rem;
  margin-top: 3rem;
  flex-wrap: wrap;
}}

.contact-item {{
  color: var(--dim);
  font-size: 0.95rem;
  font-weight: 500;
}}

/* ── FOOTER ── */
footer {{
  border-top: 1px solid var(--border);
  padding: 5rem 2rem 3rem;
  position: relative;
  z-index: 1;
}}

.footer-grid {{
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 3rem;
  max-width: 1100px;
  margin: 0 auto 3rem;
}}

.footer-brand h3 {{
  font-size: 1.1rem;
  font-weight: 800;
  margin-bottom: 0.75rem;
  letter-spacing: -0.02em;
}}

.footer-brand p {{
  color: var(--dim);
  font-size: 0.85rem;
  line-height: 1.7;
  max-width: 280px;
}}

.footer-col h4 {{
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--dim);
  margin-bottom: 1rem;
}}

.footer-col a {{
  display: block;
  color: var(--dim);
  text-decoration: none;
  font-size: 0.85rem;
  padding: 4px 0;
  transition: color 0.2s;
}}

.footer-col a:hover {{
  color: var(--primary-light);
}}

.footer-social {{
  display: flex;
  gap: 10px;
  margin-top: 1rem;
}}

.footer-social a {{
  width: 36px;
  height: 36px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 0.9rem;
  transition: all 0.2s;
}}

.footer-social a:hover {{
  background: rgba(232,93,38,0.1);
  border-color: rgba(232,93,38,0.2);
  color: var(--primary-light);
}}

.footer-bottom {{
  text-align: center;
  padding-top: 2rem;
  border-top: 1px solid var(--border);
  color: var(--dim);
  font-size: 0.8rem;
}}

/* ── ANIMATIONS ── */
.fade-in {{
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1);
}}

.fade-in.visible {{
  opacity: 1;
  transform: none;
}}

/* stagger via nth-child */
.services-grid .service-card:nth-child(1) {{ transition-delay: 0s; }}
.services-grid .service-card:nth-child(2) {{ transition-delay: 0.1s; }}
.services-grid .service-card:nth-child(3) {{ transition-delay: 0.2s; }}
.services-grid .service-card:nth-child(4) {{ transition-delay: 0.3s; }}

.why-grid .why-item:nth-child(1) {{ transition-delay: 0s; }}
.why-grid .why-item:nth-child(2) {{ transition-delay: 0.1s; }}
.why-grid .why-item:nth-child(3) {{ transition-delay: 0.15s; }}
.why-grid .why-item:nth-child(4) {{ transition-delay: 0.2s; }}

.process-grid .process-step:nth-child(1) {{ transition-delay: 0s; }}
.process-grid .process-step:nth-child(2) {{ transition-delay: 0.15s; }}
.process-grid .process-step:nth-child(3) {{ transition-delay: 0.3s; }}
.process-grid .process-step:nth-child(4) {{ transition-delay: 0.45s; }}

.stats-bar .stat-item:nth-child(1) {{ transition-delay: 0s; }}
.stats-bar .stat-item:nth-child(2) {{ transition-delay: 0.1s; }}
.stats-bar .stat-item:nth-child(3) {{ transition-delay: 0.2s; }}
.stats-bar .stat-item:nth-child(4) {{ transition-delay: 0.3s; }}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {{
  .stats-bar {{
    grid-template-columns: repeat(2, 1fr);
    padding: 3rem 1.5rem;
  }}
  .services-grid {{
    grid-template-columns: 1fr;
  }}
  .service-card.span-2 {{
    grid-column: span 1;
  }}
  .why-grid {{
    grid-template-columns: 1fr;
    gap: 2rem;
  }}
  .process-grid {{
    grid-template-columns: repeat(2, 1fr);
    gap: 1.5rem;
  }}
  .process-grid::before {{
    display: none;
  }}
  .hero {{
    padding: 2rem 1.5rem;
  }}
  .hero h1 {{
    font-size: clamp(2.2rem, 10vw, 3.5rem);
  }}
  .section {{
    padding: 5rem 1.5rem;
  }}
  .footer-grid {{
    grid-template-columns: 1fr;
    gap: 2rem;
  }}
  .contact-info {{
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }}
  .nav {{
    left: 16px;
    right: 16px;
    transform: translateX(0) translateY(-80px);
    border-radius: 20px;
    padding: 8px 16px;
  }}
  .nav.visible {{
    transform: translateX(0) translateY(0);
  }}
  .nav-links a:not(.nav-cta) {{
    display: none;
  }}
}}
</style>
</head>
<body>

<!-- FLOATING NAV -->
<nav class="nav" id="mainNav">
  <div class="nav-logo">{agency_name}</div>
  <div class="nav-links">
    <a href="#services">Hizmetler</a>
    <a href="#process">Surecimiz</a>
    <a href="#about">Hakkimizda</a>
    <a href="#contact" class="nav-cta">Iletisim</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-badge">&#9889; {niche} Uzmani</div>
  <h1>
    <span class="hero-title-wrap"><span class="hero-title-inner"><span>{agency_name}</span></span></span>
  </h1>
  <p>{tagline}. {cities_text} bolgesinde isletmenizi buyutuyoruz.</p>
  <a href="#contact" class="btn-primary">&#128172; Iletisime Gecin</a>
</section>

<!-- MARQUEE SOCIAL PROOF -->
<div class="marquee-wrap">
  <div class="marquee-track">
    <div class="marquee-item"><span>&#9733;</span> 50+ Mutlu Musteri</div>
    <div class="marquee-item"><span>&#9889;</span> 7/24 Destek</div>
    <div class="marquee-item"><span>&#128640;</span> AI Destekli Cozumler</div>
    <div class="marquee-item"><span>&#128200;</span> Olculebilir Sonuclar</div>
    <div class="marquee-item"><span>&#10003;</span> {cities_text} Bolgesinde Aktif</div>
    <div class="marquee-item"><span>&#9733;</span> Sektorde Guvenilir Ortak</div>
    <div class="marquee-item"><span>&#9733;</span> 50+ Mutlu Musteri</div>
    <div class="marquee-item"><span>&#9889;</span> 7/24 Destek</div>
    <div class="marquee-item"><span>&#128640;</span> AI Destekli Cozumler</div>
    <div class="marquee-item"><span>&#128200;</span> Olculebilir Sonuclar</div>
    <div class="marquee-item"><span>&#10003;</span> {cities_text} Bolgesinde Aktif</div>
    <div class="marquee-item"><span>&#9733;</span> Sektorde Guvenilir Ortak</div>
  </div>
</div>

<!-- CLIENT LOGOS -->
<section class="logos-section">
  <div class="section-label fade-in">Bize Guvenenlerin Arasina Katilin</div>
  <div class="logos-grid fade-in">
    <div class="logo-placeholder">Logo</div>
    <div class="logo-placeholder">Logo</div>
    <div class="logo-placeholder">Logo</div>
    <div class="logo-placeholder">Logo</div>
    <div class="logo-placeholder">Logo</div>
    <div class="logo-placeholder">Logo</div>
  </div>
</section>

<!-- STATS -->
<div class="stats-bar">
  <div class="stat-item fade-in">
    <div class="stat-num">50+</div>
    <div class="stat-label">Mutlu Musteri</div>
  </div>
  <div class="stat-item fade-in">
    <div class="stat-num">{num_cities}</div>
    <div class="stat-label">Sehir</div>
  </div>
  <div class="stat-item fade-in">
    <div class="stat-num">{niche}</div>
    <div class="stat-label">Uzmanlik Alani</div>
  </div>
  <div class="stat-item fade-in">
    <div class="stat-num">7/24</div>
    <div class="stat-label">Destek</div>
  </div>
</div>

<!-- SERVICES -->
<section class="section" id="services">
  <h2 class="section-title fade-in">Hizmetlerimiz</h2>
  <p class="section-sub fade-in">{niche} sektorunde isletmenizi bir ust seviyeye tasiyan cozumler.</p>
  <div class="services-grid">
    {services_html}
  </div>
</section>

<!-- NEDEN BIZ -->
<section class="why-section">
  <div class="section" style="padding-top:6rem;padding-bottom:6rem;">
    <h2 class="section-title fade-in">Neden Biz?</h2>
    <p class="section-sub fade-in">Diger ajanslardaki fark burada baslar.</p>
    <div class="why-grid">
      <div class="why-item fade-in">
        <div class="why-icon">&#129302;</div>
        <div>
          <h4>AI Oncelikli Yaklasim</h4>
          <p>Yapay zeka destekli araclarla rakiplerinizin onune gecin.</p>
        </div>
      </div>
      <div class="why-item fade-in">
        <div class="why-icon">&#128200;</div>
        <div>
          <h4>Veri Odakli Strateji</h4>
          <p>Her karari veriye dayali aliyor, olculebilir sonuclar uretiyoruz.</p>
        </div>
      </div>
      <div class="why-item fade-in">
        <div class="why-icon">&#9889;</div>
        <div>
          <h4>Hizli Teslimat</h4>
          <p>Haftalar degil, gunler icinde somut sonuclar gormeye baslayin.</p>
        </div>
      </div>
      <div class="why-item fade-in">
        <div class="why-icon">&#128588;</div>
        <div>
          <h4>Seffaf Iletisim</h4>
          <p>Her asamada bilgilendirilir, seffaf raporlar alirsiniz.</p>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- PROCESS -->
<section class="section process-section" id="process">
  <h2 class="section-title fade-in">Nasil Calisiyoruz?</h2>
  <p class="section-sub fade-in">4 adimda isletmenizi dijitale tasiyoruz.</p>
  <div class="process-grid">
    <div class="process-step fade-in">
      <div class="step-num">1</div>
      <h4>Analiz</h4>
      <p>Isletmenizi ve sektorunuzu detayli analiz ediyoruz.</p>
    </div>
    <div class="process-step fade-in">
      <div class="step-num">2</div>
      <h4>Strateji</h4>
      <p>Size ozel dijital pazarlama stratejisi olusturuyoruz.</p>
    </div>
    <div class="process-step fade-in">
      <div class="step-num">3</div>
      <h4>Uygulama</h4>
      <p>Plani hayata geciriyor, kampanyalari baslatiyoruz.</p>
    </div>
    <div class="process-step fade-in">
      <div class="step-num">4</div>
      <h4>Optimizasyon</h4>
      <p>Surekli olcum ve iyilestirme ile sonuclari artiriyoruz.</p>
    </div>
  </div>
</section>

<!-- ABOUT -->
<section class="about-section">
  <div class="section" style="padding-top:6rem;padding-bottom:6rem;">
    <div class="about-inner fade-in" id="about">
      <h2>Hakkimizda</h2>
      <p>
        <span class="about-name">{agency_name}</span>, {niche} sektorundeki isletmelerin dijital dunyada buyumesine yardimci olan bir ajanstir.
        Modern AI araclari ve otomasyonlar ile musterilerimizin zamandan tasarruf etmesini ve gelirlerini artirmasini sagliyoruz.
      </p>
      <p style="margin-top:1.5rem;">
        Kurucumuz <span class="about-name">{owner_name}</span>, sektorde uzun yillardir aktif olarak calismaktadir.
      </p>
    </div>
  </div>
</section>

<!-- FAQ -->
<section class="section faq-section">
  <h2 class="section-title fade-in">Sik Sorulan Sorular</h2>
  <p class="section-sub fade-in">Merak ettiklerinizin cevaplari burada.</p>
  <div class="faq-list fade-in">
    <details>
      <summary>Hizmetleriniz ne kadar surede sonuc verir?</summary>
      <div class="faq-answer">Cogu musterimiz ilk 30 gun icinde olculebilir sonuclar gormeye baslar. Dijital pazarlama stratejimiz hizli sonuclar icin optimize edilmistir.</div>
    </details>
    <details>
      <summary>Hangi sehirlerde hizmet veriyorsunuz?</summary>
      <div class="faq-answer">{cities_text} bolgesinde aktif olarak hizmet veriyoruz. Uzaktan calisma modelimiz sayesinde Turkiye genelinde destek saglayabiliyoruz.</div>
    </details>
    <details>
      <summary>Fiyatlandirmaniz nasil calisiyor?</summary>
      <div class="faq-answer">Her isletmenin ihtiyaci farklidir. Ucretsiz danismanlik gorusmemizde isletmenizi analiz edip, size ozel bir teklif hazirliyoruz.</div>
    </details>
    <details>
      <summary>Sozlesme suresi var mi?</summary>
      <div class="faq-answer">Minimum sozlesme suremiz 3 aydir. Ancak cogu musterimiz sonuclardan memnun kaldigi icin uzun vadeli calismayi tercih eder.</div>
    </details>
  </div>
</section>

<!-- CONTACT -->
<section class="section contact-section" id="contact">
  <h2 class="section-title fade-in">Iletisim</h2>
  <p class="section-sub fade-in">Isletmenizi buyutmeye hazir misiniz? Hemen iletisime gecin.</p>
  <div class="fade-in">
    <a href="mailto:info@example.com" class="contact-cta">&#128231; Bize Ulasin</a>
  </div>
  <div class="contact-info fade-in">
    <div class="contact-item">&#128205; {cities_text}</div>
    <div class="contact-item">&#128231; info@example.com</div>
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="footer-grid">
    <div class="footer-brand">
      <h3>{agency_name}</h3>
      <p>{tagline}. {cities_text} bolgesinde isletmelere dijital cozumler sunuyoruz.</p>
      <div class="footer-social">
        <a href="#" title="Instagram">&#9679;</a>
        <a href="#" title="LinkedIn">&#9679;</a>
        <a href="#" title="Twitter">&#9679;</a>
      </div>
    </div>
    <div class="footer-col">
      <h4>Hizmetler</h4>
      <a href="#services">Dijital Pazarlama</a>
      <a href="#services">Web Tasarim</a>
      <a href="#services">Sosyal Medya</a>
      <a href="#services">AI Otomasyon</a>
    </div>
    <div class="footer-col">
      <h4>Sirket</h4>
      <a href="#about">Hakkimizda</a>
      <a href="#process">Surecimiz</a>
      <a href="#contact">Iletisim</a>
    </div>
    <div class="footer-col">
      <h4>Destek</h4>
      <a href="#contact">Bize Ulasin</a>
      <a href="#">SSS</a>
      <a href="#">Gizlilik Politikasi</a>
    </div>
  </div>
  <div class="footer-bottom">
    <p>&copy; {year} {agency_name}. Tum haklari saklidir.</p>
  </div>
</footer>

<!-- SCROLL ANIMATIONS + NAV -->
<script>
(function() {{
  var els = document.querySelectorAll('.fade-in');
  var nav = document.getElementById('mainNav');
  var lastScroll = 0;

  if ('IntersectionObserver' in window) {{
    var obs = new IntersectionObserver(function(entries) {{
      entries.forEach(function(e, i) {{
        if (e.isIntersecting) {{
          e.target.style.transitionDelay = (i * 0.05) + 's';
          e.target.classList.add('visible');
          obs.unobserve(e.target);
        }}
      }});
    }}, {{ threshold: 0.08 }});
    els.forEach(function(el) {{ obs.observe(el); }});
  }} else {{
    els.forEach(function(el) {{ el.classList.add('visible'); }});
  }}

  window.addEventListener('scroll', function() {{
    var st = window.pageYOffset || document.documentElement.scrollTop;
    if (st > 400) {{
      nav.classList.add('visible');
    }} else {{
      nav.classList.remove('visible');
    }}
    lastScroll = st;
  }});
}})();
</script>
</body>
</html>'''


# ══════════════════════════════════════════════
# CLIENT SITE TEMPLATE
# ══════════════════════════════════════════════

_CLIENT_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{business_name} — {category}</title>
<meta name="description" content="{business_name} — {category}. {address}">
{audit_html}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}

:root {{
  --primary: {primary};
  --secondary: {secondary};
  --accent: {accent};
  --bg: {bg};
  --surface: rgba(17,17,20,0.6);
  --surface-solid: #111114;
  --surface2: #1a1a1e;
  --text: #ededf0;
  --dim: #8a8a9c;
  --border: rgba(255,255,255,0.06);
  --whatsapp: #25d366;
}}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
  padding-bottom: 100px;
}}

/* ── NOISE & DOT OVERLAY ── */
body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
  background-size: 256px 256px;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.5;
}}

body::after {{
  content: '';
  position: fixed;
  inset: 0;
  background-image: radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  pointer-events: none;
  z-index: 0;
}}

/* ── FLOATING NAV ── */
.nav {{
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(-80px);
  z-index: 1000;
  background: rgba(17,17,20,0.7);
  backdrop-filter: blur(20px) saturate(1.8);
  -webkit-backdrop-filter: blur(20px) saturate(1.8);
  border: 1px solid var(--border);
  border-radius: 100px;
  padding: 10px 12px 10px 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  transition: transform 0.5s cubic-bezier(0.16,1,0.3,1);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}}

.nav.visible {{
  transform: translateX(-50%) translateY(0);
}}

.nav-logo {{
  font-weight: 800;
  font-size: 0.9rem;
  letter-spacing: -0.02em;
  white-space: nowrap;
  color: var(--text);
}}

.nav-links {{
  display: flex;
  align-items: center;
  gap: 6px;
}}

.nav-links a {{
  color: var(--dim);
  text-decoration: none;
  font-size: 0.8rem;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 100px;
  transition: all 0.2s;
}}

.nav-links a:hover {{
  color: var(--text);
  background: rgba(255,255,255,0.05);
}}

.nav-cta {{
  background: var(--primary) !important;
  color: #fff !important;
  font-weight: 600 !important;
  padding: 8px 20px !important;
}}

.nav-cta:hover {{
  background: var(--secondary) !important;
}}

/* ── HERO ── */
.hero {{
  min-height: 90vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 3rem 2rem;
  position: relative;
  overflow: hidden;
  z-index: 1;
}}

.hero::before {{
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 60% at 50% 30%, color-mix(in srgb, var(--primary) 18%, transparent) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 20% 80%, color-mix(in srgb, var(--secondary) 10%, transparent) 0%, transparent 50%),
    radial-gradient(ellipse 40% 40% at 80% 60%, color-mix(in srgb, var(--accent) 5%, transparent) 0%, transparent 50%);
  pointer-events: none;
  animation: heroGlow 8s ease-in-out infinite alternate;
}}

@keyframes heroGlow {{
  0% {{ opacity: 1; transform: scale(1); }}
  100% {{ opacity: 0.7; transform: scale(1.05); }}
}}

.hero::after {{
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: linear-gradient(to top, var(--bg), transparent);
  z-index: 1;
}}

.hero-category {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  background: color-mix(in srgb, var(--primary) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--primary) 15%, transparent);
  border-radius: 100px;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--accent);
  margin-bottom: 2rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  position: relative;
  z-index: 2;
  animation: fadeUp 0.8s ease both;
}}

@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(24px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.hero h1 {{
  font-size: clamp(2.5rem, 7vw, 5.5rem);
  font-weight: 900;
  letter-spacing: -0.04em;
  line-height: 1.05;
  margin-bottom: 1.25rem;
  position: relative;
  z-index: 2;
}}

.hero-title-wrap {{
  overflow: hidden;
  display: block;
}}

.hero-title-inner {{
  display: block;
  animation: textReveal 1s cubic-bezier(0.16,1,0.3,1) 0.2s both;
}}

@keyframes textReveal {{
  from {{ transform: translateY(100%); opacity: 0; }}
  to {{ transform: translateY(0); opacity: 1; }}
}}

.hero h1 span.gradient-text {{
  background: linear-gradient(135deg, var(--primary), var(--secondary), var(--accent), var(--primary));
  background-size: 300% 300%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: gradientMove 6s ease infinite;
}}

@keyframes gradientMove {{
  0% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }}
}}

.hero-rating {{
  font-size: 1.4rem;
  margin-bottom: 1rem;
  position: relative;
  z-index: 2;
  animation: fadeUp 0.8s ease 0.3s both;
}}

.stars {{
  color: #fbbf24;
  letter-spacing: 3px;
}}

.rating-num {{
  color: var(--dim);
  font-size: 1rem;
  margin-left: 8px;
}}

.hero-review {{
  color: var(--dim);
  font-size: 0.95rem;
  margin-bottom: 2.5rem;
  position: relative;
  z-index: 2;
  animation: fadeUp 0.8s ease 0.4s both;
}}

.btn-cta {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 18px 42px;
  background: var(--primary);
  color: #fff;
  font-size: 1.05rem;
  font-weight: 700;
  border: none;
  border-radius: 14px;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
  position: relative;
  z-index: 2;
  animation: fadeUp 0.8s ease 0.5s both, pulse 3s ease-in-out 2s infinite;
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--primary) 40%, transparent);
}}

@keyframes pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 color-mix(in srgb, var(--primary) 40%, transparent); }}
  50% {{ box-shadow: 0 0 0 12px color-mix(in srgb, var(--primary) 0%, transparent); }}
}}

.btn-cta:hover {{
  background: var(--secondary);
  transform: scale(1.02);
  box-shadow: 0 8px 40px color-mix(in srgb, var(--primary) 35%, transparent);
}}

/* ── SECTIONS ── */
.section {{
  padding: 8rem 2rem;
  max-width: 1100px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}}

.section-title {{
  font-size: clamp(1.8rem, 5vw, 2.8rem);
  font-weight: 900;
  text-align: center;
  margin-bottom: 0.75rem;
  letter-spacing: -0.03em;
}}

.section-sub {{
  text-align: center;
  color: var(--dim);
  max-width: 550px;
  margin: 0 auto 4rem;
  font-size: 1.05rem;
  line-height: 1.7;
}}

/* ── FEATURES BENTO ── */
.features-grid {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
}}

.feature-card {{
  background: var(--surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 2.5rem;
  transition: all 0.4s cubic-bezier(0.16,1,0.3,1);
  position: relative;
  overflow: hidden;
}}

.feature-card::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 24px;
  padding: 1px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 20%, transparent), transparent 50%, color-mix(in srgb, var(--primary) 8%, transparent));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.4s ease;
}}

.feature-card:hover::before {{
  opacity: 1;
}}

.feature-card:hover {{
  transform: scale(1.02);
  box-shadow: 0 20px 60px rgba(0,0,0,0.3), 0 0 40px color-mix(in srgb, var(--primary) 6%, transparent);
}}

.feature-card:first-child {{
  grid-column: span 2;
}}

.feature-icon {{
  font-size: 1.8rem;
  margin-bottom: 1rem;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--primary) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--primary) 12%, transparent);
  border-radius: 14px;
}}

.feature-card h3 {{
  font-size: 1.1rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  letter-spacing: -0.01em;
}}

.feature-card p {{
  color: var(--dim);
  font-size: 0.92rem;
  line-height: 1.7;
}}

.features-grid .feature-card:nth-child(1) {{ transition-delay: 0s; }}
.features-grid .feature-card:nth-child(2) {{ transition-delay: 0.1s; }}
.features-grid .feature-card:nth-child(3) {{ transition-delay: 0.2s; }}
.features-grid .feature-card:nth-child(4) {{ transition-delay: 0.3s; }}

/* ── REVIEW HIGHLIGHT ── */
.review-section {{
  background: var(--surface-solid);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  text-align: center;
  position: relative;
  z-index: 1;
}}

.review-big {{
  font-size: 4.5rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.review-stars {{
  font-size: 2.2rem;
  color: #fbbf24;
  letter-spacing: 6px;
  margin: 0.75rem 0;
}}

.review-count {{
  color: var(--dim);
  font-size: 1rem;
}}

/* ── TESTIMONIALS MARQUEE ── */
.testimonials-wrap {{
  overflow: hidden;
  padding: 3rem 0;
  position: relative;
  z-index: 1;
}}

.testimonials-track {{
  display: flex;
  gap: 1.5rem;
  animation: marquee 30s linear infinite;
  width: max-content;
}}

@keyframes marquee {{
  0% {{ transform: translateX(0); }}
  100% {{ transform: translateX(-50%); }}
}}

.testimonial-card {{
  flex-shrink: 0;
  width: 320px;
  background: var(--surface);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2rem;
}}

.testimonial-stars {{
  color: #fbbf24;
  letter-spacing: 2px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}}

.testimonial-text {{
  color: var(--dim);
  font-size: 0.9rem;
  line-height: 1.7;
  margin-bottom: 1.25rem;
  font-style: italic;
}}

.testimonial-author {{
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text);
}}

.testimonial-role {{
  font-size: 0.75rem;
  color: var(--dim);
  margin-top: 2px;
}}

/* ── GALLERY ── */
.gallery-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}}

.gallery-item {{
  aspect-ratio: 4/3;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--border);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.3s ease;
}}

.gallery-item:hover {{
  border-color: color-mix(in srgb, var(--primary) 30%, transparent);
  background: color-mix(in srgb, var(--primary) 3%, transparent);
}}

.gallery-item:first-child {{
  grid-column: span 2;
  grid-row: span 2;
}}

/* ── WORKING HOURS ── */
.hours-section {{
  position: relative;
  z-index: 1;
}}

.hours-card {{
  max-width: 500px;
  margin: 0 auto;
  background: var(--surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 2.5rem;
  position: relative;
  overflow: hidden;
}}

.hours-card::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 24px;
  padding: 1px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 15%, transparent), transparent 60%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}}

.hours-row {{
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.95rem;
}}

.hours-row:last-child {{
  border-bottom: none;
}}

.hours-day {{
  font-weight: 600;
}}

.hours-time {{
  color: var(--dim);
}}

.hours-closed {{
  color: color-mix(in srgb, var(--primary) 70%, #ff4444);
}}

/* ── MAP PLACEHOLDER ── */
.map-placeholder {{
  max-width: 800px;
  margin: 2rem auto 0;
  height: 280px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  gap: 10px;
}}

.map-placeholder .map-icon {{
  font-size: 2.5rem;
  opacity: 0.5;
}}

/* ── LOCATION ── */
.location-section {{
  text-align: center;
  position: relative;
  z-index: 1;
}}

.location-box {{
  display: inline-block;
  background: var(--surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5rem 3.5rem;
  margin-top: 1.5rem;
  position: relative;
  overflow: hidden;
}}

.location-box::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  padding: 1px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 15%, transparent), transparent 60%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}}

.location-box .address {{
  font-size: 1.1rem;
  color: var(--text);
  margin-bottom: 0.75rem;
  font-weight: 500;
}}

.location-box .directions {{
  color: var(--primary);
  text-decoration: none;
  font-size: 0.95rem;
  font-weight: 500;
  transition: color 0.2s;
}}

.location-box .directions:hover {{
  color: var(--secondary);
}}

/* ── FAQ ACCORDION ── */
.faq-section {{
  position: relative;
  z-index: 1;
}}

.faq-list {{
  max-width: 700px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.faq-list details {{
  background: var(--surface);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
}}

.faq-list details[open] {{
  border-color: color-mix(in srgb, var(--primary) 25%, transparent);
  box-shadow: 0 0 30px color-mix(in srgb, var(--primary) 5%, transparent);
}}

.faq-list summary {{
  padding: 1.5rem 2rem;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: color 0.2s;
}}

.faq-list summary::-webkit-details-marker {{ display: none; }}

.faq-list summary::after {{
  content: '+';
  font-size: 1.3rem;
  color: var(--primary);
  font-weight: 300;
  transition: transform 0.3s ease;
}}

.faq-list details[open] summary::after {{
  transform: rotate(45deg);
}}

.faq-list summary:hover {{
  color: var(--accent);
}}

.faq-answer {{
  padding: 0 2rem 1.5rem;
  color: var(--dim);
  font-size: 0.95rem;
  line-height: 1.7;
}}

/* ── CONTACT BAR (sticky bottom) ── */
.contact-bar {{
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(17,17,20,0.8);
  backdrop-filter: blur(20px) saturate(1.5);
  -webkit-backdrop-filter: blur(20px) saturate(1.5);
  border-top: 1px solid var(--border);
  padding: 14px 20px;
  display: flex;
  justify-content: center;
  gap: 10px;
  z-index: 100;
}}

.btn {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 12px 22px;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: 12px;
  text-decoration: none;
  transition: all 0.3s cubic-bezier(0.16,1,0.3,1);
  white-space: nowrap;
}}

.btn-phone {{
  background: var(--primary);
  color: #fff;
}}

.btn-phone:hover {{
  background: var(--secondary);
  transform: scale(1.02);
}}

.btn-whatsapp {{
  background: var(--whatsapp);
  color: #fff;
}}

.btn-whatsapp:hover {{
  background: #1fb855;
  transform: scale(1.02);
}}

.btn-email {{
  background: var(--surface2);
  color: var(--text);
  border: 1px solid var(--border);
}}

.btn-email:hover {{
  border-color: var(--primary);
  transform: scale(1.02);
}}

/* ── FOOTER ── */
footer {{
  border-top: 1px solid var(--border);
  padding: 5rem 2rem 3rem;
  position: relative;
  z-index: 1;
}}

.footer-grid {{
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 3rem;
  max-width: 900px;
  margin: 0 auto 3rem;
}}

.footer-brand h3 {{
  font-size: 1.1rem;
  font-weight: 800;
  margin-bottom: 0.75rem;
  letter-spacing: -0.02em;
}}

.footer-brand p {{
  color: var(--dim);
  font-size: 0.85rem;
  line-height: 1.7;
  max-width: 280px;
}}

.footer-col h4 {{
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--dim);
  margin-bottom: 1rem;
}}

.footer-col a {{
  display: block;
  color: var(--dim);
  text-decoration: none;
  font-size: 0.85rem;
  padding: 4px 0;
  transition: color 0.2s;
}}

.footer-col a:hover {{
  color: var(--accent);
}}

.footer-social {{
  display: flex;
  gap: 10px;
  margin-top: 1rem;
}}

.footer-social a {{
  width: 36px;
  height: 36px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dim);
  font-size: 0.9rem;
  transition: all 0.2s;
}}

.footer-social a:hover {{
  background: color-mix(in srgb, var(--primary) 10%, transparent);
  border-color: color-mix(in srgb, var(--primary) 20%, transparent);
  color: var(--accent);
}}

.footer-bottom {{
  text-align: center;
  padding-top: 2rem;
  border-top: 1px solid var(--border);
  color: var(--dim);
  font-size: 0.8rem;
}}

.credit {{
  margin-top: 0.5rem;
  font-size: 0.75rem;
  opacity: 0.5;
}}

/* ── ANIMATIONS ── */
.fade-in {{
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1);
}}

.fade-in.visible {{
  opacity: 1;
  transform: none;
}}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {{
  .hero {{
    min-height: 75vh;
    padding: 2rem 1.5rem;
  }}
  .hero h1 {{
    font-size: clamp(2rem, 10vw, 3rem);
  }}
  .section {{
    padding: 5rem 1.5rem;
  }}
  .features-grid {{
    grid-template-columns: 1fr;
  }}
  .feature-card:first-child {{
    grid-column: span 1;
  }}
  .gallery-grid {{
    grid-template-columns: repeat(2, 1fr);
  }}
  .gallery-item:first-child {{
    grid-column: span 2;
    grid-row: span 1;
  }}
  .contact-bar {{
    gap: 6px;
    padding: 12px 12px;
  }}
  .btn {{
    padding: 12px 16px;
    font-size: 0.85rem;
  }}
  .location-box {{
    padding: 2rem 1.5rem;
    margin: 1rem;
  }}
  .footer-grid {{
    grid-template-columns: 1fr;
    gap: 2rem;
  }}
  .nav {{
    left: 16px;
    right: 16px;
    transform: translateX(0) translateY(-80px);
    border-radius: 20px;
    padding: 8px 16px;
  }}
  .nav.visible {{
    transform: translateX(0) translateY(0);
  }}
  .nav-links a:not(.nav-cta) {{
    display: none;
  }}
  .hours-card {{
    margin: 0 1rem;
    padding: 2rem 1.5rem;
  }}
}}

@media (min-width: 769px) {{
  .contact-bar {{
    max-width: 480px;
    left: 50%;
    transform: translateX(-50%);
    bottom: 20px;
    border-radius: 18px;
    border: 1px solid var(--border);
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }}
}}
</style>
</head>
<body>

<!-- FLOATING NAV -->
<nav class="nav" id="mainNav">
  <div class="nav-logo">{business_name}</div>
  <div class="nav-links">
    <a href="#features">Hizmetler</a>
    <a href="#gallery">Galeri</a>
    <a href="#location">Konum</a>
    <a href="tel:{phone}" class="nav-cta">&#128222; Ara</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-category">{category}</div>
  <h1>
    <span class="hero-title-wrap"><span class="hero-title-inner"><span class="gradient-text">{business_name}</span></span></span>
  </h1>
  <div class="hero-rating">{stars_html}</div>
  <div class="hero-review">{review_text}</div>
  <a href="tel:{phone}" class="btn-cta">&#128222; Bizi Arayin</a>
</section>

<!-- FEATURES -->
<section class="section" id="features">
  <h2 class="section-title fade-in">Hizmetlerimiz</h2>
  <p class="section-sub fade-in">Size en iyi hizmeti sunmak icin buradayiz.</p>
  <div class="features-grid">
    {services_html}
  </div>
</section>

<!-- REVIEW HIGHLIGHT -->
<section class="review-section">
  <div class="section" style="padding-top:5rem;padding-bottom:5rem;">
    <div class="fade-in">
      <div class="review-big">{review_text}</div>
      <div class="review-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="review-count">Google Degerlendirmeleri</div>
    </div>
  </div>
</section>

<!-- TESTIMONIALS -->
<div class="testimonials-wrap">
  <div class="testimonials-track">
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="testimonial-text">"Harika bir deneyimdi. Kesinlikle tavsiye ederim. Profesyonel ve ilgili bir ekip."</div>
      <div class="testimonial-author">Mehmet Y.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="testimonial-text">"Cok memnun kaldik. Kaliteli hizmet ve uygun fiyat. Tekrar tercih ederiz."</div>
      <div class="testimonial-author">Ayse K.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9734;</div>
      <div class="testimonial-text">"Beklentilerimin uzerinde bir hizmet aldim. Personel cok ilgiliydi."</div>
      <div class="testimonial-author">Ali R.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="testimonial-text">"Uzun suredir geldim, her seferinde ayni kaliteyi aliyorum. Tesekkurler!"</div>
      <div class="testimonial-author">Fatma S.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="testimonial-text">"Harika bir deneyimdi. Kesinlikle tavsiye ederim. Profesyonel ve ilgili bir ekip."</div>
      <div class="testimonial-author">Mehmet Y.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="testimonial-text">"Cok memnun kaldik. Kaliteli hizmet ve uygun fiyat. Tekrar tercih ederiz."</div>
      <div class="testimonial-author">Ayse K.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9734;</div>
      <div class="testimonial-text">"Beklentilerimin uzerinde bir hizmet aldim. Personel cok ilgiliydi."</div>
      <div class="testimonial-author">Ali R.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
    <div class="testimonial-card">
      <div class="testimonial-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="testimonial-text">"Uzun suredir geldim, her seferinde ayni kaliteyi aliyorum. Tesekkurler!"</div>
      <div class="testimonial-author">Fatma S.</div>
      <div class="testimonial-role">Google Yorumu</div>
    </div>
  </div>
</div>

<!-- GALLERY -->
<section class="section" id="gallery">
  <h2 class="section-title fade-in">Galeri</h2>
  <p class="section-sub fade-in">Mekanimizdan ve hizmetlerimizden kareler.</p>
  <div class="gallery-grid fade-in">
    <div class="gallery-item">Foto 1</div>
    <div class="gallery-item">Foto 2</div>
    <div class="gallery-item">Foto 3</div>
    <div class="gallery-item">Foto 4</div>
    <div class="gallery-item">Foto 5</div>
    <div class="gallery-item">Foto 6</div>
  </div>
</section>

<!-- WORKING HOURS -->
<section class="section hours-section">
  <h2 class="section-title fade-in">Calisma Saatleri</h2>
  <p class="section-sub fade-in">Sizi agirlamak icin sabirirsizlaniyoruz.</p>
  <div class="hours-card fade-in">
    <div class="hours-row">
      <span class="hours-day">Pazartesi</span>
      <span class="hours-time">09:00 — 22:00</span>
    </div>
    <div class="hours-row">
      <span class="hours-day">Sali</span>
      <span class="hours-time">09:00 — 22:00</span>
    </div>
    <div class="hours-row">
      <span class="hours-day">Carsamba</span>
      <span class="hours-time">09:00 — 22:00</span>
    </div>
    <div class="hours-row">
      <span class="hours-day">Persembe</span>
      <span class="hours-time">09:00 — 22:00</span>
    </div>
    <div class="hours-row">
      <span class="hours-day">Cuma</span>
      <span class="hours-time">09:00 — 23:00</span>
    </div>
    <div class="hours-row">
      <span class="hours-day">Cumartesi</span>
      <span class="hours-time">10:00 — 23:00</span>
    </div>
    <div class="hours-row">
      <span class="hours-day">Pazar</span>
      <span class="hours-closed">Kapali</span>
    </div>
  </div>
</section>

<!-- LOCATION -->
<section class="section location-section" id="location">
  <h2 class="section-title fade-in">Konum</h2>
  <div class="fade-in">
    <div class="location-box">
      <div class="address">&#128205; {address}</div>
      <a class="directions" href="https://www.google.com/maps/search/{business_name}" target="_blank">
        &#128506; Google Maps'te Ac
      </a>
    </div>
    <div class="map-placeholder fade-in">
      <div class="map-icon">&#128506;</div>
      <span>Harita Gorunumu</span>
    </div>
  </div>
</section>

<!-- FAQ -->
<section class="section faq-section">
  <h2 class="section-title fade-in">Sik Sorulan Sorular</h2>
  <p class="section-sub fade-in">Merak ettiklerinizin cevaplari.</p>
  <div class="faq-list fade-in">
    <details>
      <summary>Randevu almam gerekiyor mu?</summary>
      <div class="faq-answer">Randevusuz da gelebilirsiniz ancak yogun saatlerde bekleme olabilir. Telefonla randevu almanizi tavsiye ederiz.</div>
    </details>
    <details>
      <summary>Otopark imkani var mi?</summary>
      <div class="faq-answer">Isletmemizin yakininda otopark bulunmaktadir. Detayli bilgi icin bizi arayabilirsiniz.</div>
    </details>
    <details>
      <summary>Odeme yontemleriniz nelerdir?</summary>
      <div class="faq-answer">Nakit, kredi karti ve banka karti ile odeme yapabilirsiniz. Taksit secenekleri de mevcuttur.</div>
    </details>
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="footer-grid">
    <div class="footer-brand">
      <h3>{business_name}</h3>
      <p>{category} alaninda kaliteli hizmet. {address}</p>
      <div class="footer-social">
        <a href="#" title="Instagram">&#9679;</a>
        <a href="#" title="Facebook">&#9679;</a>
        <a href="#" title="Google">&#9679;</a>
      </div>
    </div>
    <div class="footer-col">
      <h4>Hizli Erisim</h4>
      <a href="#features">Hizmetler</a>
      <a href="#gallery">Galeri</a>
      <a href="#location">Konum</a>
    </div>
    <div class="footer-col">
      <h4>Iletisim</h4>
      <a href="tel:{phone}">{phone}</a>
      <a href="mailto:{email}">{email}</a>
    </div>
  </div>
  <div class="footer-bottom">
    <p>&copy; {year} {business_name}. Tum haklari saklidir.</p>
    <p class="credit">{agency_credit}</p>
  </div>
</footer>

<!-- CONTACT BAR -->
<div class="contact-bar">
  {phone_html}
  {whatsapp_html}
  {email_html}
</div>

<!-- SCROLL ANIMATIONS + NAV -->
<script>
(function() {{
  var els = document.querySelectorAll('.fade-in');
  var nav = document.getElementById('mainNav');

  if ('IntersectionObserver' in window) {{
    var obs = new IntersectionObserver(function(entries) {{
      entries.forEach(function(e, i) {{
        if (e.isIntersecting) {{
          e.target.style.transitionDelay = (i * 0.05) + 's';
          e.target.classList.add('visible');
          obs.unobserve(e.target);
        }}
      }});
    }}, {{ threshold: 0.08 }});
    els.forEach(function(el) {{ obs.observe(el); }});
  }} else {{
    els.forEach(function(el) {{ el.classList.add('visible'); }});
  }}

  window.addEventListener('scroll', function() {{
    var st = window.pageYOffset || document.documentElement.scrollTop;
    if (st > 300) {{
      nav.classList.add('visible');
    }} else {{
      nav.classList.remove('visible');
    }}
  }});
}})();
</script>
</body>
</html>'''
