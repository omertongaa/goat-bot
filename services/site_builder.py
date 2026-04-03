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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700;800;900&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
  --bg: #09090b;
  --surface: #111114;
  --surface2: #1a1a1f;
  --border: rgba(255,255,255,0.06);
  --border-light: rgba(255,255,255,0.1);
  --text: #f0f0f0;
  --dim: #8a8a98;
  --accent: #e85d26;
  --accent2: #ff7a45;
  --gold: #fbbf24;
  --green: #34d399;
}}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}}

body::after {{
  content: '';
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.03;
  background: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 200px;
}}

::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: var(--accent); border-radius: 3px; }}

.container {{ max-width: 1200px; margin: 0 auto; padding: 0 clamp(1rem, 4vw, 2rem); }}

/* ── NAV ── */
.nav {{
  position: fixed; top: 0; left: 0; right: 0;
  z-index: 1000;
  padding: 1rem 0;
  transition: all 0.4s ease;
  transform: translateY(-100%);
  opacity: 0;
}}
.nav.visible {{
  transform: translateY(0);
  opacity: 1;
}}
.nav-inner {{
  max-width: 1200px; margin: 0 auto;
  padding: 0.75rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(17,17,20,0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  border-radius: 100px;
  margin-left: clamp(1rem, 4vw, 2rem);
  margin-right: clamp(1rem, 4vw, 2rem);
}}
.nav-logo {{ font-family: 'Playfair Display', serif; font-weight: 700; font-size: 1.1rem; }}
.nav-cta {{
  padding: 0.5rem 1.5rem;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  border-radius: 100px;
  font-weight: 600;
  font-size: 0.85rem;
  transition: transform 0.2s, box-shadow 0.2s;
}}
.nav-cta:hover {{ transform: scale(1.05); box-shadow: 0 0 20px rgba(232,93,38,0.4); }}

/* ── HERO ── */
.hero {{
  min-height: 100vh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center;
  position: relative;
  padding: 2rem;
  overflow: hidden;
}}
.hero::before {{
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, rgba(232,93,38,0.15), transparent),
    radial-gradient(ellipse 60% 40% at 20% 50%, rgba(251,191,36,0.08), transparent),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(232,93,38,0.1), transparent);
  z-index: 0;
}}
.hero > * {{ position: relative; z-index: 1; }}
.hero-sub {{
  font-size: clamp(0.85rem, 2vw, 1rem);
  color: var(--dim);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 1.5rem;
}}
.hero-title {{
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: clamp(3rem, 10vw, 7rem);
  line-height: 1.05;
  margin-bottom: 1.5rem;
  background: linear-gradient(135deg, var(--text) 0%, var(--accent) 50%, var(--gold) 100%);
  background-size: 300% 300%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 6s ease infinite;
}}
@keyframes shimmer {{
  0%, 100% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
}}
.hero-desc {{
  font-size: clamp(1rem, 2.5vw, 1.25rem);
  color: var(--dim);
  max-width: 600px;
  margin-bottom: 2.5rem;
}}
.hero-cta {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 1rem 2.5rem;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
  text-decoration: none;
  border-radius: 100px;
  font-weight: 700;
  font-size: 1.05rem;
  transition: transform 0.3s, box-shadow 0.3s;
}}
.hero-cta:hover {{ transform: translateY(-2px); box-shadow: 0 12px 40px rgba(232,93,38,0.35); }}
.scroll-indicator {{
  position: absolute; bottom: 2rem; left: 50%; transform: translateX(-50%);
  width: 24px; height: 40px;
  border: 2px solid var(--dim);
  border-radius: 12px;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 6px;
}}
.scroll-indicator span {{
  width: 4px; height: 8px;
  background: var(--accent);
  border-radius: 2px;
  animation: scrollPulse 2s ease infinite;
}}
@keyframes scrollPulse {{
  0%, 100% {{ transform: translateY(0); opacity: 1; }}
  50% {{ transform: translateY(10px); opacity: 0.3; }}
}}

/* ── SECTIONS ── */
section {{ padding: clamp(4rem, 10vw, 8rem) 0; position: relative; }}
.section-title {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 800;
  margin-bottom: 1rem;
}}
.section-sub {{ color: var(--dim); font-size: 1.05rem; margin-bottom: 3rem; }}

/* ── STATS ── */
.stats-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.5rem;
}}
.stat-card {{
  background: rgba(255,255,255,0.03);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 2rem 1.5rem;
  text-align: center;
  transition: transform 0.3s, border-color 0.3s;
}}
.stat-card:hover {{ transform: scale(1.02); border-color: var(--accent); }}
.stat-num {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(2rem, 4vw, 3rem);
  font-weight: 800;
  background: linear-gradient(135deg, var(--accent), var(--gold));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.stat-label {{ color: var(--dim); font-size: 0.9rem; margin-top: 0.5rem; }}

/* ── SERVICES BENTO ── */
.services-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}}
.service-card {{
  background: rgba(255,255,255,0.03);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5rem 2rem;
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}}
.service-card:hover {{
  transform: scale(1.02);
  border-color: var(--accent);
  box-shadow: 0 0 30px rgba(232,93,38,0.1);
}}
.service-card.span-2 {{ grid-column: span 2; }}
.service-icon {{ font-size: 2.5rem; margin-bottom: 1rem; }}
.service-card h3 {{ font-family: 'Playfair Display', serif; font-size: 1.3rem; margin-bottom: 0.75rem; }}
.service-card p {{ color: var(--dim); font-size: 0.95rem; line-height: 1.7; }}

/* ── PROCESS ── */
.process-section {{
  position: relative;
}}
.process-section::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 100%;
  background: polygon(0 5%, 100% 0, 100% 95%, 0 100%);
  clip-path: polygon(0 5%, 100% 0, 100% 95%, 0 100%);
  background: var(--surface);
  z-index: -1;
}}
.process-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2rem;
  position: relative;
}}
.process-grid::before {{
  content: '';
  position: absolute;
  top: 2.5rem; left: 10%; right: 10%;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--gold), var(--green), var(--accent));
}}
.process-step {{ text-align: center; position: relative; z-index: 1; }}
.step-num {{
  width: 50px; height: 50px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 1.2rem;
  margin-bottom: 1.5rem;
  color: #fff;
}}
.process-step h3 {{ font-family: 'Playfair Display', serif; font-size: 1.2rem; margin-bottom: 0.5rem; }}
.process-step p {{ color: var(--dim); font-size: 0.85rem; }}

/* ── ABOUT ── */
.about-split {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: center;
}}
.about-quote {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(1.5rem, 3vw, 2.5rem);
  font-weight: 700;
  line-height: 1.3;
  font-style: italic;
  color: var(--accent);
}}
.about-text {{ color: var(--dim); font-size: 1.05rem; line-height: 1.8; }}
.about-text strong {{ color: var(--text); }}

/* ── TESTIMONIALS ── */
.testimonials-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}}
.testimonial-card {{
  background: rgba(255,255,255,0.03);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2rem;
  transition: transform 0.3s, border-color 0.3s;
}}
.testimonial-card:hover {{ transform: scale(1.02); border-color: var(--accent); }}
.t-stars {{ color: var(--gold); font-size: 1.2rem; margin-bottom: 1rem; }}
.t-text {{ color: var(--dim); font-size: 0.95rem; line-height: 1.7; margin-bottom: 1.5rem; font-style: italic; }}
.t-author {{ font-weight: 600; font-size: 0.9rem; }}
.t-role {{ color: var(--dim); font-size: 0.8rem; }}

/* ── CONTACT CTA ── */
.contact-section {{
  text-align: center;
  position: relative;
}}
.contact-section::before {{
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 60% 50% at 50% 50%, rgba(232,93,38,0.1), transparent);
}}
.contact-section > * {{ position: relative; z-index: 1; }}
.contact-section .section-title {{ margin-bottom: 1rem; }}
.contact-desc {{ color: var(--dim); font-size: 1.1rem; margin-bottom: 2.5rem; }}
.contact-btn {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 1rem 3rem;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff; text-decoration: none;
  border-radius: 100px;
  font-weight: 700; font-size: 1.1rem;
  transition: transform 0.3s, box-shadow 0.3s;
}}
.contact-btn:hover {{ transform: translateY(-2px); box-shadow: 0 12px 40px rgba(232,93,38,0.35); }}
.contact-cities {{ color: var(--dim); font-size: 0.9rem; margin-top: 1.5rem; }}

/* ── FOOTER ── */
footer {{
  border-top: 1px solid var(--border);
  padding: 4rem 0 2rem;
}}
.footer-grid {{
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 3rem;
  margin-bottom: 3rem;
}}
.footer-brand {{ font-family: 'Playfair Display', serif; font-size: 1.3rem; font-weight: 700; margin-bottom: 0.75rem; }}
.footer-tagline {{ color: var(--dim); font-size: 0.9rem; }}
.footer-col h4 {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 2px; color: var(--dim); margin-bottom: 1rem; }}
.footer-col a {{ display: block; color: var(--text); text-decoration: none; font-size: 0.9rem; margin-bottom: 0.5rem; transition: color 0.2s; }}
.footer-col a:hover {{ color: var(--accent); }}
.footer-bottom {{
  text-align: center;
  padding-top: 2rem;
  border-top: 1px solid var(--border);
  color: var(--dim);
  font-size: 0.8rem;
}}

/* ── REVEAL ── */
.reveal {{
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 0.6s ease, transform 0.6s ease;
}}
.reveal.active {{
  opacity: 1;
  transform: translateY(0);
}}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {{
  .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .services-grid {{ grid-template-columns: 1fr; }}
  .service-card.span-2 {{ grid-column: span 1; }}
  .process-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .process-grid::before {{ display: none; }}
  .about-split {{ grid-template-columns: 1fr; gap: 2rem; }}
  .testimonials-grid {{ grid-template-columns: 1fr; }}
  .footer-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<!-- NAV -->
<nav class="nav" id="mainNav">
  <div class="nav-inner">
    <div class="nav-logo">{agency_name}</div>
    <a href="#contact" class="nav-cta">Iletisime Gecin</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero" id="hero">
  <p class="hero-sub">{niche} &middot; {cities_text}</p>
  <h1 class="hero-title">{agency_name}</h1>
  <p class="hero-desc">{tagline}</p>
  <a href="#contact" class="hero-cta">Ucretsiz Analiz Alin &#8594;</a>
  <div class="scroll-indicator"><span></span></div>
</section>

<!-- STATS -->
<section id="stats">
  <div class="container">
    <div class="stats-grid">
      <div class="stat-card reveal">
        <div class="stat-num">50+</div>
        <div class="stat-label">Mutlu Musteri</div>
      </div>
      <div class="stat-card reveal">
        <div class="stat-num">{num_cities}</div>
        <div class="stat-label">Sehir</div>
      </div>
      <div class="stat-card reveal">
        <div class="stat-num">7/24</div>
        <div class="stat-label">Destek</div>
      </div>
      <div class="stat-card reveal">
        <div class="stat-num">{niche}</div>
        <div class="stat-label">Uzmanlik Alani</div>
      </div>
    </div>
  </div>
</section>

<!-- SERVICES -->
<section id="services">
  <div class="container">
    <div class="section-title reveal">Hizmetlerimiz</div>
    <div class="section-sub reveal">Isletmenizi buyutmek icin ihtiyaciniz olan her sey</div>
    <div class="services-grid">
      {services_html}
    </div>
  </div>
</section>

<!-- PROCESS -->
<section class="process-section" id="process">
  <div class="container">
    <div class="section-title reveal" style="text-align:center;">Nasil Calisiyoruz?</div>
    <div class="section-sub reveal" style="text-align:center;">Basariya giden 4 adim</div>
    <div class="process-grid">
      <div class="process-step reveal">
        <div class="step-num">1</div>
        <h3>Analiz</h3>
        <p>Isletmenizi ve sektorunuzu detayli inceliyoruz</p>
      </div>
      <div class="process-step reveal">
        <div class="step-num">2</div>
        <h3>Strateji</h3>
        <p>Size ozel dijital strateji olusturuyoruz</p>
      </div>
      <div class="process-step reveal">
        <div class="step-num">3</div>
        <h3>Uygulama</h3>
        <p>Stratejiyi hayata geciriyoruz</p>
      </div>
      <div class="process-step reveal">
        <div class="step-num">4</div>
        <h3>Sonuc</h3>
        <p>Olculebilir sonuclarla buyume sagliyoruz</p>
      </div>
    </div>
  </div>
</section>

<!-- ABOUT -->
<section id="about">
  <div class="container">
    <div class="about-split">
      <div class="about-quote reveal">
        &#8220;Her isletme dijital dunyada hak ettigi yeri almali.&#8221;
      </div>
      <div class="about-text reveal">
        <strong>{agency_name}</strong>, {owner_name} liderliginde {niche} sektorune odaklanmis bir dijital ajansdir. {cities_text} bolgesinde isletmelerin dijital donusumunu hizlandiriyoruz.<br><br>
        Amacimiz, yerel isletmelerin buyuk markalarla ayni dijital araclara erisebilmesini saglamak. Veriye dayali stratejiler ve modern teknolojilerle musterilerimizin online varligini guclendiriyoruz.
      </div>
    </div>
  </div>
</section>

<!-- TESTIMONIALS -->
<section id="testimonials">
  <div class="container">
    <div class="section-title reveal" style="text-align:center;">Musterilerimiz Ne Diyor?</div>
    <div class="section-sub reveal" style="text-align:center;">Birlikte basardik</div>
    <div class="testimonials-grid">
      <div class="testimonial-card reveal">
        <div class="t-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
        <p class="t-text">&#8220;Dijital varligimizi sifirdan insa ettiler. 3 ayda online siparislerimiz %200 artti. Harika bir ekip!&#8221;</p>
        <div class="t-author">Mehmet Yilmaz</div>
        <div class="t-role">Restoran Sahibi, Istanbul</div>
      </div>
      <div class="testimonial-card reveal">
        <div class="t-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
        <p class="t-text">&#8220;Profesyonel, hizli ve sonuc odakli. Google'da ilk sayfaya ciktik, hasta sayimiz ikiye katlandi.&#8221;</p>
        <div class="t-author">Ayse Kara</div>
        <div class="t-role">Dis Klinigi, Ankara</div>
      </div>
      <div class="testimonial-card reveal">
        <div class="t-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
        <p class="t-text">&#8220;Sosyal medya yonetimimizi devraldilar, takipci sayimiz 10 kat artti. Kesinlikle tavsiye ediyorum.&#8221;</p>
        <div class="t-author">Ali Demir</div>
        <div class="t-role">Otel Muduru, Antalya</div>
      </div>
    </div>
  </div>
</section>

<!-- CONTACT -->
<section class="contact-section" id="contact">
  <div class="container" style="padding-top:4rem;padding-bottom:4rem;">
    <div class="section-title reveal">Iletisime Gecin</div>
    <p class="contact-desc reveal">Isletmenizi bir sonraki seviyeye tasimayi konusalim</p>
    <a href="mailto:info@{agency_name}.com" class="contact-btn reveal">Bize Yazin &#9993;</a>
    <p class="contact-cities reveal">{cities_text}</p>
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="footer-brand">{agency_name}</div>
        <p class="footer-tagline">{tagline}</p>
      </div>
      <div class="footer-col">
        <h4>Sayfalar</h4>
        <a href="#services">Hizmetler</a>
        <a href="#process">Surecimiz</a>
        <a href="#about">Hakkimizda</a>
        <a href="#testimonials">Referanslar</a>
      </div>
      <div class="footer-col">
        <h4>Iletisim</h4>
        <a href="#contact">Bize Ulasin</a>
        <a href="mailto:info@{agency_name}.com">E-posta</a>
        <a href="#">{cities_text}</a>
      </div>
    </div>
    <div class="footer-bottom">
      &copy; {year} {agency_name}. Tum haklari saklidir.
    </div>
  </div>
</footer>

<script>
// Floating nav
const nav = document.getElementById('mainNav');
const hero = document.getElementById('hero');
const observer1 = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (!e.isIntersecting) nav.classList.add('visible');
    else nav.classList.remove('visible');
  }});
}}, {{ threshold: 0.1 }});
observer1.observe(hero);

// Scroll reveals with stagger
const reveals = document.querySelectorAll('.reveal');
const revealObs = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      e.target.classList.add('active');
      revealObs.unobserve(e.target);
    }}
  }});
}}, {{ threshold: 0.1 }});

reveals.forEach((el, i) => {{
  const parent = el.parentElement;
  const siblings = Array.from(parent.children).filter(c => c.classList.contains('reveal'));
  const idx = siblings.indexOf(el);
  el.style.transitionDelay = (idx * 0.1) + 's';
  revealObs.observe(el);
}});
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700;800;900&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
{audit_html}
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
  --primary: {primary};
  --secondary: {secondary};
  --accent: {accent};
  --bg: {bg};
  --surface: rgba(255,255,255,0.03);
  --border: rgba(255,255,255,0.06);
  --border-light: rgba(255,255,255,0.1);
  --text: #f0f0f0;
  --dim: #8a8a98;
}}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: 'DM Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  padding-bottom: 80px;
}}

body::after {{
  content: '';
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.03;
  background: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-size: 200px;
}}

::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: var(--primary); border-radius: 3px; }}

.container {{ max-width: 1200px; margin: 0 auto; padding: 0 clamp(1rem, 4vw, 2rem); }}

/* ── NAV ── */
.nav {{
  position: fixed; top: 0; left: 0; right: 0;
  z-index: 1000;
  padding: 1rem 0;
  transition: all 0.4s ease;
  transform: translateY(-100%);
  opacity: 0;
}}
.nav.visible {{
  transform: translateY(0);
  opacity: 1;
}}
.nav-inner {{
  max-width: 1200px; margin: 0 auto;
  padding: 0.75rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(17,17,20,0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  border-radius: 100px;
  margin-left: clamp(1rem, 4vw, 2rem);
  margin-right: clamp(1rem, 4vw, 2rem);
}}
.nav-logo {{ font-family: 'Playfair Display', serif; font-weight: 700; font-size: 1.1rem; }}
.nav-cta {{
  padding: 0.5rem 1.5rem;
  background: var(--primary);
  color: #fff;
  text-decoration: none;
  border-radius: 100px;
  font-weight: 600;
  font-size: 0.85rem;
  transition: transform 0.2s, box-shadow 0.2s;
}}
.nav-cta:hover {{ transform: scale(1.05); box-shadow: 0 0 20px rgba(232,93,38,0.4); }}

/* ── HERO ── */
.hero {{
  min-height: 80vh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center;
  position: relative;
  padding: 2rem;
  overflow: hidden;
}}
.hero::before {{
  content: '';
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, color-mix(in srgb, var(--primary) 20%, transparent), transparent),
    radial-gradient(ellipse 60% 40% at 20% 60%, color-mix(in srgb, var(--secondary) 12%, transparent), transparent),
    radial-gradient(ellipse 50% 50% at 80% 80%, color-mix(in srgb, var(--accent) 8%, transparent), transparent);
  z-index: 0;
}}
.hero > * {{ position: relative; z-index: 1; }}
.category-badge {{
  display: inline-block;
  padding: 0.4rem 1.2rem;
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--border-light);
  border-radius: 100px;
  font-size: 0.85rem;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 1.5rem;
}}
.hero-title {{
  font-family: 'Playfair Display', serif;
  font-weight: 900;
  font-size: clamp(3rem, 10vw, 7rem);
  line-height: 1.05;
  margin-bottom: 1.5rem;
  background: linear-gradient(135deg, var(--text) 0%, var(--primary) 50%, var(--accent) 100%);
  background-size: 300% 300%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 6s ease infinite;
}}
@keyframes shimmer {{
  0%, 100% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
}}
.hero-rating {{ margin-bottom: 0.5rem; }}
.hero-rating .stars {{ color: var(--accent); font-size: 1.5rem; }}
.hero-rating .rating-num {{ font-size: 1.2rem; font-weight: 700; margin-left: 0.5rem; }}
.hero-review-text {{ color: var(--dim); font-size: 0.95rem; margin-bottom: 2rem; }}
.hero-cta {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 1rem 2.5rem;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #fff;
  text-decoration: none;
  border-radius: 100px;
  font-weight: 700;
  font-size: 1.05rem;
  transition: transform 0.3s, box-shadow 0.3s;
}}
.hero-cta:hover {{ transform: translateY(-2px); box-shadow: 0 12px 40px color-mix(in srgb, var(--primary) 40%, transparent); }}

/* ── SECTIONS ── */
section {{ padding: clamp(4rem, 10vw, 8rem) 0; position: relative; }}
.section-title {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 800;
  margin-bottom: 1rem;
}}
.section-sub {{ color: var(--dim); font-size: 1.05rem; margin-bottom: 3rem; }}

/* ── FEATURES BENTO ── */
.features-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}}
.feature-card {{
  background: var(--surface);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5rem 2rem;
  transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}}
.feature-card:hover {{
  transform: scale(1.02);
  border-color: var(--primary);
  box-shadow: 0 0 30px color-mix(in srgb, var(--primary) 15%, transparent);
}}
.feature-card:first-child {{ grid-column: span 2; }}
.feature-icon {{ font-size: 2.5rem; margin-bottom: 1rem; }}
.feature-card h3 {{ font-family: 'Playfair Display', serif; font-size: 1.3rem; margin-bottom: 0.75rem; }}
.feature-card p {{ color: var(--dim); font-size: 0.95rem; line-height: 1.7; }}

/* ── REVIEW HIGHLIGHT ── */
.review-section {{
  text-align: center;
  position: relative;
}}
.review-section::before {{
  content: '';
  position: absolute; inset: 0;
  clip-path: polygon(0 8%, 100% 0, 100% 92%, 0 100%);
  background: rgba(255,255,255,0.015);
  z-index: -1;
}}
.review-big {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(5rem, 15vw, 10rem);
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  margin-bottom: 1rem;
}}
.review-stars {{ font-size: 2rem; color: var(--accent); margin-bottom: 0.5rem; }}
.review-label {{ color: var(--dim); font-size: 1rem; }}

/* ── GALLERY ── */
.gallery-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 200px;
  gap: 1rem;
}}
.gallery-item {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  color: var(--dim);
  font-size: 0.9rem;
  transition: transform 0.3s, border-color 0.3s;
  overflow: hidden;
}}
.gallery-item:hover {{ transform: scale(1.02); border-color: var(--primary); }}
.gallery-item:first-child {{
  grid-column: span 2;
  grid-row: span 2;
}}

/* ── HOURS ── */
.hours-card {{
  max-width: 500px;
  margin: 0 auto;
  background: var(--surface);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 2.5rem;
}}
.hours-row {{
  display: flex; justify-content: space-between;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.95rem;
}}
.hours-row:last-child {{ border-bottom: none; }}
.hours-day {{ font-weight: 600; }}
.hours-time {{ color: var(--dim); }}
.hours-closed {{ color: #ef4444; }}

/* ── LOCATION ── */
.location-section {{ text-align: center; }}
.location-address {{ color: var(--dim); font-size: 1.1rem; margin-bottom: 1.5rem; }}
.map-link {{
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.75rem 2rem;
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text);
  text-decoration: none;
  border-radius: 100px;
  font-weight: 600;
  transition: border-color 0.3s, transform 0.2s;
}}
.map-link:hover {{ border-color: var(--primary); transform: scale(1.02); }}

/* ── FOOTER ── */
footer {{
  border-top: 1px solid var(--border);
  padding: 2rem 0;
  text-align: center;
  color: var(--dim);
  font-size: 0.8rem;
}}
footer .credit {{ margin-top: 0.5rem; opacity: 0.6; }}

/* ── CONTACT BAR ── */
.contact-bar {{
  position: fixed; bottom: 0; left: 0; right: 0;
  z-index: 1000;
  padding: 0.75rem 1rem;
  background: rgba(17,17,20,0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--border-light);
  display: flex; align-items: center; justify-content: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}}
.contact-bar .btn {{
  padding: 0.6rem 1.5rem;
  border-radius: 100px;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.85rem;
  transition: transform 0.2s, box-shadow 0.2s;
  display: inline-flex; align-items: center; gap: 0.4rem;
}}
.btn-phone {{
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #fff;
}}
.btn-whatsapp {{
  background: linear-gradient(135deg, #25d366, #128c7e);
  color: #fff;
}}
.btn-email {{
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text);
}}
.contact-bar .btn:hover {{ transform: scale(1.05); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}

/* ── REVEAL ── */
.reveal {{
  opacity: 0;
  transform: translateY(30px);
  transition: opacity 0.6s ease, transform 0.6s ease;
}}
.reveal.active {{
  opacity: 1;
  transform: translateY(0);
}}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {{
  .features-grid {{ grid-template-columns: 1fr; }}
  .feature-card:first-child {{ grid-column: span 1; }}
  .gallery-grid {{ grid-template-columns: repeat(2, 1fr); grid-auto-rows: 150px; }}
  .gallery-item:first-child {{ grid-column: span 2; grid-row: span 1; }}
  .contact-bar {{ gap: 0.5rem; padding: 0.5rem; }}
  .contact-bar .btn {{ padding: 0.5rem 1rem; font-size: 0.8rem; }}
}}
</style>
</head>
<body>

<!-- NAV -->
<nav class="nav" id="mainNav">
  <div class="nav-inner">
    <div class="nav-logo">{business_name}</div>
    <a href="tel:{phone}" class="nav-cta">&#128222; Hemen Ara</a>
  </div>
</nav>

<!-- HERO -->
<section class="hero" id="hero">
  <div class="category-badge">{category}</div>
  <h1 class="hero-title">{business_name}</h1>
  <div class="hero-rating">{stars_html}</div>
  <p class="hero-review-text">{review_text}</p>
  <a href="tel:{phone}" class="hero-cta">&#128222; Hemen Arayin</a>
</section>

<!-- FEATURES -->
<section id="features">
  <div class="container">
    <div class="section-title reveal">Hizmetlerimiz</div>
    <div class="section-sub reveal">Size en iyi deneyimi sunmak icin buradayiz</div>
    <div class="features-grid">
      {services_html}
    </div>
  </div>
</section>

<!-- REVIEW HIGHLIGHT -->
<section class="review-section" id="reviews">
  <div class="container">
    <div class="review-big reveal">{stars_html}</div>
    <div class="review-stars reveal">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
    <div class="review-label reveal">Google Degerlendirmeleri</div>
  </div>
</section>

<!-- GALLERY -->
<section id="gallery">
  <div class="container">
    <div class="section-title reveal">Galeri</div>
    <div class="section-sub reveal">Mekanımızdan kareler</div>
    <div class="gallery-grid">
      <div class="gallery-item reveal">Foto 1</div>
      <div class="gallery-item reveal">Foto 2</div>
      <div class="gallery-item reveal">Foto 3</div>
      <div class="gallery-item reveal">Foto 4</div>
      <div class="gallery-item reveal">Foto 5</div>
      <div class="gallery-item reveal">Foto 6</div>
    </div>
  </div>
</section>

<!-- WORKING HOURS -->
<section id="hours">
  <div class="container">
    <div class="section-title reveal" style="text-align:center;">Calisma Saatleri</div>
    <div class="section-sub reveal" style="text-align:center;">Sizi agirlamak icin haziriz</div>
    <div class="hours-card reveal">
      <div class="hours-row">
        <span class="hours-day">Pazartesi - Cuma</span>
        <span class="hours-time">09:00 - 18:00</span>
      </div>
      <div class="hours-row">
        <span class="hours-day">Cumartesi</span>
        <span class="hours-time">10:00 - 14:00</span>
      </div>
      <div class="hours-row">
        <span class="hours-day">Pazar</span>
        <span class="hours-time hours-closed">Kapali</span>
      </div>
    </div>
  </div>
</section>

<!-- LOCATION -->
<section class="location-section" id="location">
  <div class="container">
    <div class="section-title reveal">Konum</div>
    <p class="location-address reveal">{address}</p>
    <a href="https://www.google.com/maps/search/{business_name}+{address}" target="_blank" class="map-link reveal">
      &#128205; Google Maps'te Ac
    </a>
  </div>
</section>

<!-- FOOTER -->
<footer>
  <div class="container">
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

<script>
// Floating nav
const nav = document.getElementById('mainNav');
const hero = document.getElementById('hero');
const obs1 = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (!e.isIntersecting) nav.classList.add('visible');
    else nav.classList.remove('visible');
  }});
}}, {{ threshold: 0.1 }});
obs1.observe(hero);

// Scroll reveals with stagger
const reveals = document.querySelectorAll('.reveal');
const revealObs = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{
    if (e.isIntersecting) {{
      e.target.classList.add('active');
      revealObs.unobserve(e.target);
    }}
  }});
}}, {{ threshold: 0.1 }});

reveals.forEach((el, i) => {{
  const parent = el.parentElement;
  const siblings = Array.from(parent.children).filter(c => c.classList.contains('reveal'));
  const idx = siblings.indexOf(el);
  el.style.transitionDelay = (idx * 0.1) + 's';
  revealObs.observe(el);
}});
</script>
</body>
</html>'''
