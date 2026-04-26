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
OUTPUTS_BASE = Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))
OUTPUT_DIR = OUTPUTS_BASE / "sites"


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
    for svc in services:
        html += """
        <div class="service-card">
          <div class="service-icon">{icon}</div>
          <h3>{title}</h3>
          <p>{desc}</p>
        </div>""".format(
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
  --surface: #111114;
  --surface2: #1a1a1e;
  --text: #ededf0;
  --dim: #8a8a9c;
  --border: #2a2a34;
}}

html {{
  scroll-behavior: smooth;
}}

body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
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
}}

.hero::before {{
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(232,93,38,0.12) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 80%, rgba(232,93,38,0.06) 0%, transparent 50%);
  pointer-events: none;
}}

.hero::after {{
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120px;
  background: linear-gradient(to top, var(--bg), transparent);
}}

.hero-badge {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: rgba(232,93,38,0.1);
  border: 1px solid rgba(232,93,38,0.2);
  border-radius: 100px;
  font-size: 0.85rem;
  color: var(--primary-light);
  margin-bottom: 2rem;
  letter-spacing: 0.05em;
  position: relative;
  z-index: 1;
}}

.hero h1 {{
  font-size: clamp(2.5rem, 7vw, 5rem);
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin-bottom: 1.5rem;
  position: relative;
  z-index: 1;
}}

.hero h1 span {{
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.hero p {{
  font-size: clamp(1.05rem, 2.5vw, 1.25rem);
  color: var(--dim);
  max-width: 600px;
  margin-bottom: 2.5rem;
  position: relative;
  z-index: 1;
}}

.btn-primary {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 16px 36px;
  background: var(--primary);
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  border: none;
  border-radius: 12px;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
}}

.btn-primary:hover {{
  background: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(232,93,38,0.3);
}}

/* ── STATS BAR ── */
.stats-bar {{
  display: flex;
  justify-content: center;
  gap: 3rem;
  padding: 3rem 2rem;
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}}

.stat-item {{
  text-align: center;
}}

.stat-num {{
  font-size: 1.8rem;
  font-weight: 800;
  color: var(--primary);
}}

.stat-label {{
  font-size: 0.85rem;
  color: var(--dim);
  margin-top: 4px;
}}

/* ── SECTIONS ── */
.section {{
  padding: 6rem 2rem;
  max-width: 1100px;
  margin: 0 auto;
}}

.section-title {{
  font-size: clamp(1.8rem, 4vw, 2.5rem);
  font-weight: 800;
  text-align: center;
  margin-bottom: 1rem;
  letter-spacing: -0.02em;
}}

.section-sub {{
  text-align: center;
  color: var(--dim);
  max-width: 600px;
  margin: 0 auto 3rem;
  font-size: 1.05rem;
}}

/* ── SERVICES ── */
.services-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.5rem;
}}

.service-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 2rem;
  transition: all 0.3s ease;
}}

.service-card:hover {{
  border-color: var(--primary);
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0,0,0,0.3);
}}

.service-icon {{
  font-size: 2rem;
  margin-bottom: 1rem;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(232,93,38,0.1);
  border-radius: 14px;
}}

.service-card h3 {{
  font-size: 1.15rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
}}

.service-card p {{
  color: var(--dim);
  font-size: 0.95rem;
  line-height: 1.6;
}}

/* ── ABOUT ── */
.about-section {{
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}}

.about-inner {{
  max-width: 700px;
  margin: 0 auto;
  text-align: center;
}}

.about-inner h2 {{
  font-size: clamp(1.5rem, 3vw, 2rem);
  margin-bottom: 1.5rem;
}}

.about-inner p {{
  color: var(--dim);
  font-size: 1.05rem;
  line-height: 1.8;
}}

.about-name {{
  color: var(--primary);
  font-weight: 600;
}}

/* ── CONTACT ── */
.contact-section {{
  text-align: center;
}}

.contact-cta {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 18px 40px;
  background: var(--primary);
  color: #fff;
  font-size: 1.1rem;
  font-weight: 700;
  border-radius: 14px;
  text-decoration: none;
  transition: all 0.3s ease;
  margin-top: 2rem;
}}

.contact-cta:hover {{
  background: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(232,93,38,0.3);
}}

.contact-info {{
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin-top: 2.5rem;
  flex-wrap: wrap;
}}

.contact-item {{
  color: var(--dim);
  font-size: 0.95rem;
}}

/* ── FOOTER ── */
footer {{
  text-align: center;
  padding: 3rem 2rem;
  border-top: 1px solid var(--border);
  color: var(--dim);
  font-size: 0.85rem;
}}

/* ── ANIMATIONS ── */
.fade-in {{
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.6s ease, transform 0.6s ease;
}}

.fade-in.visible {{
  opacity: 1;
  transform: none;
}}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {{
  .stats-bar {{
    flex-wrap: wrap;
    gap: 1.5rem;
  }}
  .stat-item {{
    flex: 0 0 40%;
  }}
  .hero {{
    padding: 2rem 1.5rem;
  }}
  .section {{
    padding: 4rem 1.5rem;
  }}
  .contact-info {{
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }}
}}
</style>
</head>
<body>

<!-- HERO -->
<section class="hero">
  <div class="hero-badge">&#9889; {niche} Uzmani</div>
  <h1><span>{agency_name}</span></h1>
  <p>{tagline}. {cities_text} bolgesinde isletmenizi buyutuyoruz.</p>
  <a href="#contact" class="btn-primary">&#128172; Iletisime Gecin</a>
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

<!-- ABOUT -->
<section class="about-section">
  <div class="section" style="padding-top:5rem;padding-bottom:5rem;">
    <div class="about-inner fade-in">
      <h2>Hakkimizda</h2>
      <p>
        <span class="about-name">{agency_name}</span>, {niche} sektorundeki isletmelerin dijital dunyada buyumesine yardimci olan bir ajanstir.
        Modern AI araclari ve otomasyonlar ile musterilerimizin zamandan tasarruf etmesini ve gelirlerini artirmasini sagliyoruz.
      </p>
      <p style="margin-top:1rem;">
        Kurucumuz <span class="about-name">{owner_name}</span>, sektorde uzun yillardir aktif olarak calismaktadir.
      </p>
    </div>
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
  <p>&copy; {year} {agency_name}. Tum haklari saklidir.</p>
</footer>

<!-- SCROLL ANIMATIONS -->
<script>
(function() {{
  var els = document.querySelectorAll('.fade-in');
  if ('IntersectionObserver' in window) {{
    var obs = new IntersectionObserver(function(entries) {{
      entries.forEach(function(e) {{
        if (e.isIntersecting) {{
          e.target.classList.add('visible');
          obs.unobserve(e.target);
        }}
      }});
    }}, {{ threshold: 0.1 }});
    els.forEach(function(el) {{ obs.observe(el); }});
  }} else {{
    els.forEach(function(el) {{ el.classList.add('visible'); }});
  }}
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
  --surface: #111114;
  --surface2: #1a1a1e;
  --text: #ededf0;
  --dim: #8a8a9c;
  --border: #2a2a34;
  --whatsapp: #25d366;
}}

html {{ scroll-behavior: smooth; }}

body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  padding-bottom: 80px;
}}

/* ── HERO ── */
.hero {{
  min-height: 80vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 3rem 2rem;
  position: relative;
  overflow: hidden;
}}

.hero::before {{
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 30%, color-mix(in srgb, var(--primary) 15%, transparent) 0%, transparent 60%),
    radial-gradient(ellipse at 20% 80%, color-mix(in srgb, var(--secondary) 8%, transparent) 0%, transparent 50%);
  pointer-events: none;
}}

.hero::after {{
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 100px;
  background: linear-gradient(to top, var(--bg), transparent);
}}

.hero-category {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: color-mix(in srgb, var(--primary) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--primary) 25%, transparent);
  border-radius: 100px;
  font-size: 0.85rem;
  color: var(--accent);
  margin-bottom: 1.5rem;
  position: relative;
  z-index: 1;
}}

.hero h1 {{
  font-size: clamp(2.2rem, 6vw, 4.5rem);
  font-weight: 900;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin-bottom: 1rem;
  position: relative;
  z-index: 1;
}}

.hero-rating {{
  font-size: 1.3rem;
  margin-bottom: 1.5rem;
  position: relative;
  z-index: 1;
}}

.stars {{
  color: #fbbf24;
  letter-spacing: 2px;
}}

.rating-num {{
  color: var(--dim);
  font-size: 1rem;
  margin-left: 8px;
}}

.hero-review {{
  color: var(--dim);
  font-size: 0.95rem;
  margin-bottom: 2rem;
  position: relative;
  z-index: 1;
}}

.btn-cta {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 16px 36px;
  background: var(--primary);
  color: #fff;
  font-size: 1.05rem;
  font-weight: 700;
  border: none;
  border-radius: 12px;
  text-decoration: none;
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
}}

.btn-cta:hover {{
  background: var(--secondary);
  transform: translateY(-2px);
  box-shadow: 0 8px 30px color-mix(in srgb, var(--primary) 30%, transparent);
}}

/* ── FEATURES ── */
.section {{
  padding: 5rem 2rem;
  max-width: 1000px;
  margin: 0 auto;
}}

.section-title {{
  font-size: clamp(1.6rem, 4vw, 2.2rem);
  font-weight: 800;
  text-align: center;
  margin-bottom: 0.75rem;
}}

.section-sub {{
  text-align: center;
  color: var(--dim);
  max-width: 550px;
  margin: 0 auto 3rem;
}}

.features-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem;
}}

.feature-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.75rem;
  transition: all 0.3s ease;
}}

.feature-card:hover {{
  border-color: var(--primary);
  transform: translateY(-3px);
}}

.feature-icon {{
  font-size: 1.8rem;
  margin-bottom: 0.75rem;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--primary) 10%, transparent);
  border-radius: 12px;
}}

.feature-card h3 {{
  font-size: 1.05rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}}

.feature-card p {{
  color: var(--dim);
  font-size: 0.9rem;
  line-height: 1.6;
}}

/* ── REVIEW HIGHLIGHT ── */
.review-section {{
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  text-align: center;
}}

.review-big {{
  font-size: 4rem;
  font-weight: 900;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.review-stars {{
  font-size: 2rem;
  color: #fbbf24;
  letter-spacing: 4px;
  margin: 0.5rem 0;
}}

.review-count {{
  color: var(--dim);
  font-size: 1rem;
}}

/* ── LOCATION ── */
.location-section {{
  text-align: center;
}}

.location-box {{
  display: inline-block;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 2rem 3rem;
  margin-top: 1.5rem;
}}

.location-box .address {{
  font-size: 1.1rem;
  color: var(--text);
  margin-bottom: 0.5rem;
}}

.location-box .directions {{
  color: var(--primary);
  text-decoration: none;
  font-size: 0.95rem;
}}

.location-box .directions:hover {{
  text-decoration: underline;
}}

/* ── CONTACT BAR (sticky bottom mobile) ── */
.contact-bar {{
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  justify-content: center;
  gap: 10px;
  z-index: 100;
  backdrop-filter: blur(10px);
}}

.btn {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: 10px;
  text-decoration: none;
  transition: all 0.2s ease;
  white-space: nowrap;
}}

.btn-phone {{
  background: var(--primary);
  color: #fff;
}}

.btn-phone:hover {{
  background: var(--secondary);
}}

.btn-whatsapp {{
  background: var(--whatsapp);
  color: #fff;
}}

.btn-whatsapp:hover {{
  background: #1fb855;
}}

.btn-email {{
  background: var(--surface2);
  color: var(--text);
  border: 1px solid var(--border);
}}

.btn-email:hover {{
  border-color: var(--primary);
}}

/* ── FOOTER ── */
footer {{
  text-align: center;
  padding: 3rem 2rem;
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
  transform: translateY(20px);
  transition: opacity 0.6s ease, transform 0.6s ease;
}}

.fade-in.visible {{
  opacity: 1;
  transform: none;
}}

/* ── RESPONSIVE ── */
@media (max-width: 768px) {{
  .hero {{
    min-height: 70vh;
    padding: 2rem 1.5rem;
  }}
  .section {{
    padding: 3.5rem 1.5rem;
  }}
  .contact-bar {{
    gap: 6px;
    padding: 10px 12px;
  }}
  .btn {{
    padding: 10px 14px;
    font-size: 0.85rem;
  }}
  .location-box {{
    padding: 1.5rem;
    margin: 1rem;
  }}
}}

@media (min-width: 769px) {{
  .contact-bar {{
    max-width: 500px;
    left: 50%;
    transform: translateX(-50%);
    bottom: 16px;
    border-radius: 16px;
    border: 1px solid var(--border);
  }}
}}
</style>
</head>
<body>

<!-- HERO -->
<section class="hero">
  <div class="hero-category">{category}</div>
  <h1>{business_name}</h1>
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
  <div class="section" style="padding-top:4rem;padding-bottom:4rem;">
    <div class="fade-in">
      <div class="review-big">{review_text}</div>
      <div class="review-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
      <div class="review-count">Google Degerlendirmeleri</div>
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
  </div>
</section>

<!-- FOOTER -->
<footer>
  <p>&copy; {year} {business_name}. Tum haklari saklidir.</p>
  <p class="credit">{agency_credit}</p>
</footer>

<!-- CONTACT BAR -->
<div class="contact-bar">
  {phone_html}
  {whatsapp_html}
  {email_html}
</div>

<!-- SCROLL ANIMATIONS -->
<script>
(function() {{
  var els = document.querySelectorAll('.fade-in');
  if ('IntersectionObserver' in window) {{
    var obs = new IntersectionObserver(function(entries) {{
      entries.forEach(function(e) {{
        if (e.isIntersecting) {{
          e.target.classList.add('visible');
          obs.unobserve(e.target);
        }}
      }});
    }}, {{ threshold: 0.1 }});
    els.forEach(function(el) {{ obs.observe(el); }});
  }} else {{
    els.forEach(function(el) {{ el.classList.add('visible'); }});
  }}
}})();
</script>
</body>
</html>'''
