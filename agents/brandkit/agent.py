"""BrandKit Agent — Production-grade brand board.

Üretiliyor:
- Renk paleti (canlı swatch + hex + RGB + kullanım)
- Tipografi (Google Fonts canlı yüklü, scale preview)
- Logo (fal.ai ile oluşturulup gömülü)
- Ses tonu (Yap/Yapma örnekleri)
- Sosyal medya post mockup'ları
- Email imza önizleme
- Buton ve UI komponent örnekleri

Tek bir tek-dosya HTML brand board, modern stilde.
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


# ── Industry-aware color palettes ───────────────────────────────────────────
PALETTES = {
    "modern": {
        "primary": "#e85d26", "primary_label": "Marka Turuncusu",
        "secondary": "#1a1a2e", "secondary_label": "Gece Lacivert",
        "accent": "#34d399", "accent_label": "Vurgu Yeşili",
        "ink": "#16161a", "muted": "#6b7280", "paper": "#fafaf7",
    },
    "minimal": {
        "primary": "#111111", "primary_label": "Saf Siyah",
        "secondary": "#666666", "secondary_label": "Antrasit",
        "accent": "#e85d26", "accent_label": "Akzent Turuncu",
        "ink": "#111111", "muted": "#999999", "paper": "#ffffff",
    },
    "bold": {
        "primary": "#ff3366", "primary_label": "Elektrik Pembesi",
        "secondary": "#6c5ce7", "secondary_label": "Mor Vurgu",
        "accent": "#ffeaa7", "accent_label": "Sarı Pop",
        "ink": "#0a0a0c", "muted": "#636e72", "paper": "#fff8f0",
    },
    "corporate": {
        "primary": "#0f4c81", "primary_label": "Kurumsal Mavi",
        "secondary": "#1f2937", "secondary_label": "Çelik Gri",
        "accent": "#10b981", "accent_label": "İlerleme Yeşili",
        "ink": "#0f172a", "muted": "#64748b", "paper": "#f8fafc",
    },
    "warm": {
        "primary": "#c0392b", "primary_label": "Toprak Kırmızı",
        "secondary": "#e67e22", "secondary_label": "Toprak Turuncu",
        "accent": "#f39c12", "accent_label": "Karamel",
        "ink": "#2c3e50", "muted": "#95a5a6", "paper": "#fdf6f0",
    },
    "tech": {
        "primary": "#6c5ce7", "primary_label": "Neo Mor",
        "secondary": "#00cec9", "secondary_label": "Cyan",
        "accent": "#fd79a8", "accent_label": "Pembe Glow",
        "ink": "#0a0a0c", "muted": "#636e72", "paper": "#0f0f12",
    },
    "natural": {
        "primary": "#16a34a", "primary_label": "Orman Yeşili",
        "secondary": "#854d0e", "secondary_label": "Toprak Kahve",
        "accent": "#facc15", "accent_label": "Buğday",
        "ink": "#1a1a1a", "muted": "#737373", "paper": "#fafaf0",
    },
}

# Style → Google Fonts pairing
FONT_PAIRINGS = {
    "modern": {"display": "Inter", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Lora"},
    "minimal": {"display": "Inter", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Inter"},
    "bold": {"display": "Space Grotesk", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Lora"},
    "corporate": {"display": "Manrope", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Lora"},
    "warm": {"display": "Playfair Display", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Lora"},
    "tech": {"display": "Space Grotesk", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Lora"},
    "natural": {"display": "Fraunces", "body": "Inter", "mono": "JetBrains Mono", "italic_friendly": "Lora"},
}


def _hex_to_rgb(hex_str: str) -> str:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgb({r}, {g}, {b})"
    except Exception:
        return hex_str


class BrandKitAgent(BaseAgent):
    agent_id = "brandkit"
    name = "BrandKit"
    role = "Creates complete brand identity — colors, fonts, guidelines, assets"
    category = "creative"

    def run(self, business_name: str = "", industry: str = "",
            style: str = "modern", values: str = "") -> dict:
        self.log("BrandKit agent başladı")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name") or config.get("name") or "My Agency"
        if not industry:
            industry = config.get("niche") or (config.get("target_industries") or ["dijital pazarlama"])[0]
        if not values:
            values = "profesyonel, yenilikçi, güvenilir"

        if style not in PALETTES:
            style = "modern"
        palette = PALETTES[style]
        fonts = FONT_PAIRINGS[style]

        self.log(f"Marka: {business_name} | Sektör: {industry} | Stil: {style}")

        # 1) Claude'dan brand JSON al
        brand_spec = self._generate_brand_spec(business_name, industry, style, values)

        # 2) fal.ai logo
        logo_path = self._generate_logo(business_name, industry, style, palette)

        # 3) HTML brand board
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_doc = self._render_brand_board(business_name, industry, style, values,
                                            palette, fonts, brand_spec, logo_path)
        out_dir = OUTPUT_DIR / "brandkit"
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{timestamp}_brand_board.html"
        html_path.write_text(html_doc, encoding="utf-8")
        self.log(f"Brand board HTML: {html_path}")

        # 4) Persist JSON
        brand_data = {
            "business_name": business_name,
            "industry": industry,
            "style": style,
            "values": values,
            "palette": palette,
            "fonts": fonts,
            "brand_spec": brand_spec,
            "html_path": str(html_path),
            "logo_path": logo_path,
            "created_at": timestamp,
        }
        self.save_data(f"brandkit/{timestamp}_brand.json", brand_data)

        results = {
            "status": "ok",
            "summary": f"Marka kimliği kiti hazır — {business_name} ({style}, {len(palette)} renk + {len(set(fonts.values()))} font)",
            "metrics": {
                "business_name": business_name,
                "style": style,
                "colors_count": 6,
                "fonts_count": len(set(fonts.values())),
                "logo_generated": bool(logo_path),
                "html_path": str(html_path),
                "timestamp": datetime.now().isoformat(),
            },
            "artifacts": {
                "brand_board_html": str(html_path),
                "logo": logo_path,
            },
            "brand": brand_data,
            "recommendations": [
                "Brand board HTML'i Files'tan açıp ekiple paylaş",
                "Renk hex kodlarını Figma/Canva paletine kaydet",
                "Sosyal medya profil resmi ve banner'ı bu palet ile yenile",
                "Email imza şablonunu HTML'den kopyalayıp Gmail/Outlook'a yapıştır",
                "Yılda 1 kez güncelleme yap — markalar evrim geçirir",
            ],
        }
        self.save_output("brandkit_report.json", results)
        self.log("BrandKit tamamlandı")
        return results

    # ── Claude'dan brand spec çek ───────────────────────────────────────────
    def _generate_brand_spec(self, business_name, industry, style, values):
        prompt = f"""Sen üst düzey marka stratejistisin. Aşağıdaki marka için kapsamlı brand spec'i SAF JSON olarak döndür.

İŞLETME: {business_name}
SEKTÖR: {industry}
STİL: {style}
DEĞERLER: {values}

Çıktı JSON yapısı (HİÇBİR ek metin, sadece JSON):
{{
  "tagline": "1 satırlık marka sloganı (max 8 kelime)",
  "elevator_pitch": "30 saniyelik tanıtım metni (60-80 kelime)",
  "story": "3 paragraflık marka hikayesi (mission/vision/values dahil)",
  "personality": ["sıfat1", "sıfat2", "sıfat3", "sıfat4", "sıfat5"],
  "tone": {{
    "do": ["yapılması gereken 1", "yapılması gereken 2", "yapılması gereken 3", "yapılması gereken 4"],
    "dont": ["kaçınılması gereken 1", "kaçınılması gereken 2", "kaçınılması gereken 3", "kaçınılması gereken 4"]
  }},
  "voice_examples": [
    {{"context": "Soğuk email açılışı", "example": "..."}},
    {{"context": "Hata bildirimi", "example": "..."}},
    {{"context": "Sosyal medya post hook", "example": "..."}},
    {{"context": "Müşteri teşekkürü", "example": "..."}}
  ],
  "vocabulary": {{
    "use": ["kelime 1", "kelime 2", "kelime 3", "kelime 4", "kelime 5"],
    "avoid": ["kelime 1", "kelime 2", "kelime 3", "kelime 4"]
  }},
  "social_post_caption": "Örnek Instagram caption (50-80 kelime, emoji dahil)",
  "logo_concept": "Logo görseli için ideal konsept açıklaması (1 paragraf)"
}}

Türkçe yaz. Klişeden uzak, marka kişiliğini yansıtan içerik."""

        raw = self.call_claude(prompt, timeout=120)
        if raw:
            cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict) and data.get("tagline"):
                    return data
            except Exception as e:
                self.log(f"Brand spec JSON parse hatası: {e}")

        return self._fallback_spec(business_name, industry, style)

    def _fallback_spec(self, business_name, industry, style):
        return {
            "tagline": f"{industry.title()} için akıllı çözümler.",
            "elevator_pitch": f"{business_name}, {industry} alanında {style} bir yaklaşımla işletmelerin büyümesine yardımcı oluyor. AI destekli iş akışları ve uzman ekiple, hedeflerinize ulaşmanızı hızlandırıyoruz.",
            "story": f"{business_name}, {industry} sektöründe yenilikçi çözümler sunmak için kuruldu. Misyonumuz: işletmelerin teknolojiyi anlaşılır ve uygulanabilir kılarak sürdürülebilir büyüme sağlamak. Vizyonumuz: Türkiye'de KOBİ'ler için en güvenilir AI partneri olmak. Değerlerimiz: şeffaflık, sonuç odaklılık, sürekli öğrenme.",
            "personality": ["güvenilir", "yenilikçi", "açık sözlü", "pragmatik", "destekleyici"],
            "tone": {
                "do": ["Net ve doğrudan ol", "Veriyle konuş", "Müşteriye 'sen' diye hitap et", "Hatayı sahiplen"],
                "dont": ["Pazarlama jargonu kullanma", "'Belki' gibi belirsiz kelimelerden kaçın", "Aşırı resmi olma", "Klişe başlangıçlar yapma"],
            },
            "voice_examples": [
                {"context": "Soğuk email", "example": "Merhaba [İsim], web sitenize 5 dakika baktım. 3 hızlı kazanım gördüm — 10dk konuşalım mı?"},
                {"context": "Hata bildirimi", "example": "Bu bizden kaynaklı bir hata. Sorumluluk bizde, çözümü 24 saat içinde ileteceğiz."},
                {"context": "Sosyal medya hook", "example": "5 yıllık ajansım, 1 müşteriden öğrendiğim şu şeyi paylaşayım..."},
                {"context": "Teşekkür", "example": "Bizi tercih ettiğiniz için teşekkürler. Sorularınız varsa direkt benim mailime yazın."},
            ],
            "vocabulary": {
                "use": ["sonuç", "veri", "test", "büyüme", "partner"],
                "avoid": ["dijital dönüşüm", "sinerji", "paradigma", "innovasyon"],
            },
            "social_post_caption": f"Bu hafta {industry} için 3 şey öğrendik 👇\n\n1️⃣ Konuşmak yetmez, ölçmek lazım\n2️⃣ Hız > mükemmellik\n3️⃣ Müşteri her zaman haklı değil — ama dinlemek zorundasın\n\nSiz ne katarsınız? 👇\n\n#{industry.replace(' ', '')} #girişimcilik",
            "logo_concept": f"Modern, sade, {style} estetikli wordmark. Geometric harf yapısı + tek bir ikonik vurgu (nokta, alt çizgi veya minimal sembol). Tek renk olarak da çalışmalı.",
        }

    # ── fal.ai logo ─────────────────────────────────────────────────────────
    def _generate_logo(self, business_name, industry, style, palette):
        try:
            from services.image import generate_image
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            primary = palette["primary"]
            paper = palette["paper"]
            prompt = (f"Minimalist professional logo design for '{business_name}', "
                      f"{industry} industry, {style} aesthetic, vector style, "
                      f"primary color {primary}, on {paper} background, "
                      f"clean wordmark with subtle icon mark, ultra clean, no tagline, no extra text")
            path = generate_image(prompt, size="square",
                                  filename=f"logo_concept_{ts}.png")
            if path:
                self.log(f"Logo: {path}")
            return path
        except Exception as e:
            self.log(f"Logo üretimi atlandı: {e}")
            return None

    # ── Brand Board HTML render ─────────────────────────────────────────────
    def _render_brand_board(self, business_name, industry, style, values,
                            palette, fonts, spec, logo_path):
        # Google Fonts URL — load all needed
        font_families = sorted(set(fonts.values()))
        fam_url_parts = []
        for f in font_families:
            family = f.replace(" ", "+")
            if f in ("Lora",):
                fam_url_parts.append(f"family={family}:ital,wght@0,400;0,600;1,400")
            else:
                fam_url_parts.append(f"family={family}:wght@400;500;600;700;800")
        fonts_url = "https://fonts.googleapis.com/css2?" + "&".join(fam_url_parts) + "&display=swap"

        biz = html.escape(business_name)
        ind = html.escape(industry)
        st = html.escape(style)
        vals = html.escape(values)
        tagline = html.escape(spec.get("tagline", ""))
        elevator = html.escape(spec.get("elevator_pitch", ""))
        story = html.escape(spec.get("story", "")).replace("\n\n", "</p><p>").replace("\n", "<br>")
        personality_chips = "".join(
            f'<span class="chip">{html.escape(p)}</span>'
            for p in spec.get("personality", [])[:7]
        )

        # Tone do/dont
        do_items = "".join(f"<li>{html.escape(x)}</li>" for x in spec.get("tone", {}).get("do", []))
        dont_items = "".join(f"<li>{html.escape(x)}</li>" for x in spec.get("tone", {}).get("dont", []))

        # Voice examples
        voice_cards = ""
        for v in spec.get("voice_examples", []):
            voice_cards += f"""
            <div class="voice-card">
              <div class="voice-context">{html.escape(v.get("context", ""))}</div>
              <div class="voice-text">"{html.escape(v.get("example", ""))}"</div>
            </div>"""

        # Vocabulary
        use_words = "".join(f'<span class="word use">{html.escape(w)}</span>'
                            for w in spec.get("vocabulary", {}).get("use", []))
        avoid_words = "".join(f'<span class="word avoid">{html.escape(w)}</span>'
                              for w in spec.get("vocabulary", {}).get("avoid", []))

        # Color cards
        color_cards = ""
        primary_keys = [
            ("primary", palette["primary_label"], "Ana marka rengi. Logolar, başlıklar, birincil CTA."),
            ("secondary", palette["secondary_label"], "Destekleyici renk. Footer, kart arka planı, navigasyon."),
            ("accent", palette["accent_label"], "Vurgu rengi. Hover, başarı, badge, küçük detaylar."),
            ("ink", "Metin", "Tüm gövde metni. Kontrast oranı en az 7:1."),
            ("muted", "İkincil Metin", "Etiketler, alt metin, açıklamalar."),
            ("paper", "Arka Plan", "Sayfa zemini, kart arka planları."),
        ]
        for key, label, usage in primary_keys:
            hex_v = palette[key]
            rgb_v = _hex_to_rgb(hex_v)
            text_color = "#ffffff" if key in ("primary", "secondary", "ink") else "#1a1a1a"
            if key == "paper":
                text_color = "#1a1a1a"
            color_cards += f"""
            <div class="color-card">
              <div class="swatch" style="background: {hex_v}; color: {text_color};">
                <span class="swatch-hex">{hex_v}</span>
              </div>
              <div class="swatch-meta">
                <div class="swatch-name">{html.escape(label)}</div>
                <div class="swatch-rgb">{rgb_v}</div>
                <div class="swatch-usage">{html.escape(usage)}</div>
              </div>
            </div>"""

        # Logo block — prepare 4 variants (light/dark/brand/gradient) outside f-string
        biz_initials = biz[:2].upper()
        if logo_path:
            try:
                rel = Path(logo_path).resolve()
                logo_img_html = f'<img src="file://{rel}" alt="{biz} logo" class="logo-img">'
                logo_light = logo_img_html
                logo_dark = logo_img_html
                logo_brand = logo_img_html
                logo_gradient = logo_img_html
            except Exception:
                logo_path = None
        if not logo_path:
            paper_color = palette["paper"]
            logo_light = f'<div class="logo-fallback">{biz_initials}</div>'
            logo_dark = f'<div class="logo-fallback" style="color:{paper_color}">{biz_initials}</div>'
            logo_brand = f'<div class="logo-fallback" style="color:#fff">{biz_initials}</div>'
            logo_gradient = f'<div class="logo-fallback" style="color:#fff">{biz_initials}</div>'

        social_caption = html.escape(spec.get("social_post_caption", "")).replace("\n", "<br>")
        logo_concept = html.escape(spec.get("logo_concept", ""))

        # Determine if dark mode (paper is dark)
        is_dark = palette["paper"].lower() in ("#0a0a0c", "#0f0f12", "#000000", "#111111")

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brand Board — {biz}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts_url}" rel="stylesheet">
<style>
:root {{
  --primary: {palette["primary"]};
  --secondary: {palette["secondary"]};
  --accent: {palette["accent"]};
  --ink: {palette["ink"]};
  --muted: {palette["muted"]};
  --paper: {palette["paper"]};
  --rule: rgba(0,0,0,0.08);
  --display: '{fonts["display"]}', system-ui, sans-serif;
  --body: '{fonts["body"]}', system-ui, sans-serif;
  --mono: '{fonts["mono"]}', monospace;
  --serif: '{fonts["italic_friendly"]}', Georgia, serif;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: var(--body);
  background: #f5f5f0;
  color: var(--ink);
  line-height: 1.6;
}}
.cover {{
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color: #ffffff;
  padding: 96px 64px;
  position: relative;
  overflow: hidden;
}}
.cover::after {{
  content: "";
  position: absolute;
  bottom: -120px; right: -120px;
  width: 360px; height: 360px;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.15;
}}
.cover-eyebrow {{
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  opacity: 0.85;
  margin-bottom: 16px;
}}
.cover h1 {{
  font-family: var(--display);
  font-size: 88px;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin: 0 0 12px;
  line-height: 1;
}}
.cover .tagline {{
  font-family: var(--serif);
  font-size: 26px;
  font-style: italic;
  font-weight: 400;
  opacity: 0.95;
  margin: 0 0 32px;
  max-width: 720px;
}}
.cover .meta {{
  display: flex; gap: 32px;
  font-family: var(--mono);
  font-size: 13px;
  opacity: 0.85;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}}
.cover .meta span strong {{ display: block; font-size: 11px; opacity: 0.7; margin-bottom: 4px; }}

section {{
  padding: 80px 64px;
  max-width: 1280px;
  margin: 0 auto;
}}
.section-eyebrow {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--primary);
  margin-bottom: 12px;
}}
.section-title {{
  font-family: var(--display);
  font-size: 44px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 16px;
  line-height: 1.1;
}}
.section-lead {{
  font-family: var(--serif);
  font-size: 19px;
  color: #555;
  max-width: 720px;
  margin: 0 0 56px;
  line-height: 1.6;
}}

/* Personality */
.chips {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 32px; }}
.chip {{
  font-family: var(--display);
  font-size: 14px;
  font-weight: 600;
  padding: 8px 16px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--rule);
  color: var(--ink);
}}

.story-card {{
  background: var(--paper);
  border-radius: 24px;
  padding: 48px;
  border: 1px solid var(--rule);
}}
.story-card .label {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--primary);
  margin-bottom: 12px;
}}
.story-card p {{
  font-family: var(--serif);
  font-size: 18px;
  line-height: 1.75;
  color: {("#e5e7eb" if is_dark else "var(--ink)")};
}}

/* Colors grid */
.colors-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 20px;
}}
.color-card {{
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid var(--rule);
  transition: transform 0.15s;
}}
.color-card:hover {{ transform: translateY(-4px); }}
.swatch {{
  height: 160px;
  display: flex;
  align-items: flex-end;
  padding: 16px;
}}
.swatch-hex {{
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 500;
  background: rgba(0,0,0,0.25);
  padding: 6px 10px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
}}
.swatch-meta {{ padding: 18px; }}
.swatch-name {{
  font-family: var(--display);
  font-weight: 700;
  font-size: 16px;
  color: var(--ink);
}}
.swatch-rgb {{
  font-family: var(--mono);
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}}
.swatch-usage {{
  font-family: var(--body);
  font-size: 13px;
  color: #555;
  margin-top: 10px;
  line-height: 1.5;
}}

/* Typography */
.type-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 32px;
}}
.type-card {{
  background: #fff;
  border-radius: 24px;
  padding: 40px;
  border: 1px solid var(--rule);
}}
.type-card .label {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 12px;
}}
.type-card .font-name {{
  font-family: var(--mono);
  font-size: 13px;
  color: var(--primary);
  margin-bottom: 24px;
}}
.preview-display {{
  font-family: var(--display);
  font-size: 56px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1;
  margin: 0 0 12px;
  color: var(--ink);
}}
.preview-display-sub {{
  font-family: var(--display);
  font-size: 22px;
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 18px;
}}
.preview-body {{
  font-family: var(--body);
  font-size: 16px;
  line-height: 1.7;
  color: #444;
}}
.scale {{
  display: flex; flex-direction: column; gap: 10px;
  margin-top: 24px;
  border-top: 1px dashed var(--rule);
  padding-top: 20px;
}}
.scale-row {{
  display: flex; align-items: baseline; gap: 16px;
  font-family: var(--display);
  color: var(--ink);
}}
.scale-row .pt {{ font-family: var(--mono); font-size: 11px; color: var(--muted); width: 50px; }}
.scale-row .demo {{ flex: 1; }}
.scale-h1 {{ font-size: 40px; font-weight: 800; }}
.scale-h2 {{ font-size: 28px; font-weight: 700; }}
.scale-h3 {{ font-size: 20px; font-weight: 600; }}
.scale-body {{ font-size: 16px; font-weight: 400; font-family: var(--body); }}
.scale-small {{ font-size: 13px; font-weight: 400; font-family: var(--body); color: var(--muted); }}

/* Logo block */
.logo-block {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}}
.logo-tile {{
  background: #fff;
  border-radius: 24px;
  border: 1px solid var(--rule);
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}}
.logo-tile.dark {{ background: var(--ink); }}
.logo-tile.brand {{ background: var(--primary); }}
.logo-img {{ max-width: 65%; max-height: 65%; object-fit: contain; }}
.logo-fallback {{
  font-family: var(--display);
  font-size: 96px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--primary);
}}
.logo-tile.dark .logo-fallback {{ color: var(--paper); }}
.logo-tile.brand .logo-fallback {{ color: #fff; }}
.logo-concept {{
  font-family: var(--serif);
  font-size: 16px;
  line-height: 1.7;
  color: #555;
  margin-top: 24px;
  padding: 24px;
  background: rgba(0,0,0,0.03);
  border-radius: 16px;
  border-left: 4px solid var(--primary);
}}

/* Voice & Tone */
.tone-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}}
.tone-col {{
  background: #fff;
  border-radius: 24px;
  padding: 32px;
  border: 1px solid var(--rule);
}}
.tone-col.do {{ border-top: 4px solid #10b981; }}
.tone-col.dont {{ border-top: 4px solid #ef4444; }}
.tone-col h3 {{
  font-family: var(--display);
  font-size: 22px;
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}}
.tone-col.do h3 {{ color: #047857; }}
.tone-col.dont h3 {{ color: #b91c1c; }}
.tone-col ul {{ padding: 0; margin: 0; list-style: none; }}
.tone-col li {{
  padding: 12px 0;
  border-bottom: 1px solid var(--rule);
  font-family: var(--body);
  font-size: 15px;
  position: relative;
  padding-left: 28px;
}}
.tone-col.do li::before {{ content: "✓"; position: absolute; left: 0; color: #10b981; font-weight: 700; }}
.tone-col.dont li::before {{ content: "✗"; position: absolute; left: 0; color: #ef4444; font-weight: 700; }}
.tone-col li:last-child {{ border-bottom: 0; }}

/* Voice examples */
.voice-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  margin-top: 32px;
}}
.voice-card {{
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  border: 1px solid var(--rule);
  border-left: 4px solid var(--accent);
}}
.voice-context {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}}
.voice-text {{
  font-family: var(--serif);
  font-size: 18px;
  line-height: 1.55;
  font-style: italic;
  color: var(--ink);
}}

/* Vocabulary */
.vocab {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  margin-top: 24px;
}}
.vocab-col h4 {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin: 0 0 16px;
}}
.vocab-col.use h4 {{ color: #047857; }}
.vocab-col.avoid h4 {{ color: #b91c1c; }}
.word {{
  display: inline-block;
  padding: 8px 14px;
  margin: 4px 6px 4px 0;
  border-radius: 8px;
  font-family: var(--body);
  font-weight: 500;
  font-size: 14px;
}}
.word.use {{ background: #d1fae5; color: #065f46; }}
.word.avoid {{ background: #fee2e2; color: #991b1b; text-decoration: line-through; }}

/* UI Components preview */
.ui-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}}
.ui-card {{
  background: #fff;
  border-radius: 24px;
  padding: 32px;
  border: 1px solid var(--rule);
}}
.ui-card .label {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 18px;
}}

.btn {{
  font-family: var(--display);
  font-size: 15px;
  font-weight: 600;
  padding: 14px 28px;
  border-radius: 12px;
  border: 0;
  cursor: pointer;
  display: inline-block;
  text-decoration: none;
}}
.btn.primary {{ background: var(--primary); color: #fff; }}
.btn.secondary {{ background: var(--secondary); color: #fff; }}
.btn.ghost {{ background: transparent; color: var(--primary); border: 2px solid var(--primary); padding: 12px 26px; }}
.btn-row {{ display: flex; gap: 12px; flex-wrap: wrap; }}

.badge {{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.05em;
  margin-right: 6px;
}}
.badge.primary {{ background: var(--primary); color: #fff; }}
.badge.accent {{ background: var(--accent); color: var(--ink); }}
.badge.ghost {{ background: rgba(0,0,0,0.08); color: var(--ink); }}

.input-demo {{
  font-family: var(--body);
  font-size: 15px;
  padding: 14px 18px;
  border-radius: 12px;
  border: 1.5px solid var(--rule);
  width: 100%;
  background: #fafafa;
}}
.input-demo:focus {{ outline: none; border-color: var(--primary); }}

/* Social mock */
.social-mock {{
  background: #fff;
  border-radius: 16px;
  border: 1px solid var(--rule);
  padding: 0;
  overflow: hidden;
  max-width: 480px;
}}
.social-header {{
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--rule);
}}
.social-avatar {{
  width: 40px; height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--display);
  font-weight: 700;
  font-size: 14px;
}}
.social-handle {{
  font-family: var(--display);
  font-weight: 600;
  font-size: 14px;
}}
.social-handle small {{ display: block; color: var(--muted); font-weight: 400; font-size: 12px; }}
.social-image {{
  height: 320px;
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-family: var(--display);
  font-size: 36px;
  font-weight: 800;
  text-align: center;
  padding: 32px;
}}
.social-caption {{
  padding: 16px;
  font-family: var(--body);
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink);
}}

/* Email signature mock */
.signature {{
  font-family: var(--body);
  border-left: 3px solid var(--primary);
  padding: 16px 20px;
  background: #fff;
  border-radius: 0 12px 12px 0;
}}
.signature .name {{ font-family: var(--display); font-weight: 700; font-size: 16px; color: var(--ink); }}
.signature .title {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}
.signature .contact {{ font-family: var(--mono); font-size: 12px; margin-top: 8px; color: #444; }}
.signature .contact a {{ color: var(--primary); text-decoration: none; }}

/* Footer */
.brand-footer {{
  background: var(--ink);
  color: #ddd;
  padding: 48px 64px;
  margin-top: 80px;
}}
.brand-footer .top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  font-family: var(--mono);
  font-size: 13px;
}}
.brand-footer .biz {{ font-family: var(--display); font-size: 24px; font-weight: 700; color: #fff; }}
.brand-footer .meta {{ opacity: 0.6; font-size: 12px; margin-top: 16px; }}

@media (max-width: 768px) {{
  .cover {{ padding: 64px 28px; }}
  .cover h1 {{ font-size: 56px; }}
  .cover .tagline {{ font-size: 20px; }}
  section {{ padding: 56px 28px; }}
  .section-title {{ font-size: 32px; }}
  .logo-block, .tone-grid, .vocab {{ grid-template-columns: 1fr; }}
  .brand-footer {{ padding: 32px 28px; }}
}}
</style>
</head>
<body>

<header class="cover">
  <div class="cover-eyebrow">brand identity board · {st.upper()}</div>
  <h1>{biz}</h1>
  <p class="tagline">{tagline or "—"}</p>
  <div class="meta">
    <span><strong>Sektör</strong>{ind}</span>
    <span><strong>Stil</strong>{st}</span>
    <span><strong>Değerler</strong>{vals}</span>
  </div>
</header>

<section>
  <div class="section-eyebrow">01 · Hikaye</div>
  <h2 class="section-title">Marka Hikayesi</h2>
  <p class="section-lead">{elevator}</p>
  <div class="chips">{personality_chips}</div>
  <div class="story-card">
    <div class="label">Manifesto</div>
    <p>{story}</p>
  </div>
</section>

<section>
  <div class="section-eyebrow">02 · Logo</div>
  <h2 class="section-title">Logo & İşaret</h2>
  <p class="section-lead">Logo üç farklı arka planda da net okunabilir olmalı. Minimum boyut: 32px (digital), 1cm (print).</p>
  <div class="logo-block">
    <div class="logo-tile">{logo_light}</div>
    <div class="logo-tile dark">{logo_dark}</div>
    <div class="logo-tile brand">{logo_brand}</div>
    <div class="logo-tile" style="background: linear-gradient(135deg, var(--primary), var(--accent));">{logo_gradient}</div>
  </div>
  <div class="logo-concept"><strong>Logo konsepti:</strong> {logo_concept}</div>
</section>

<section>
  <div class="section-eyebrow">03 · Renkler</div>
  <h2 class="section-title">Renk Paleti</h2>
  <p class="section-lead">Marka iletişiminin omurgası. Birincil renk %60, ikincil %30, accent %10 oranında kullan.</p>
  <div class="colors-grid">{color_cards}</div>
</section>

<section>
  <div class="section-eyebrow">04 · Tipografi</div>
  <h2 class="section-title">Yazı Sistemi</h2>
  <p class="section-lead">Display fontu başlıklarda, body fontu metinde. Aşırı font karışımı yapma — 2 font yeter.</p>
  <div class="type-grid">
    <div class="type-card">
      <div class="label">Display / Başlık</div>
      <div class="font-name">{html.escape(fonts["display"])} · Google Fonts</div>
      <h3 class="preview-display" style="font-family: '{fonts["display"]}', sans-serif;">Aa Bb Cc</h3>
      <div class="preview-display-sub" style="font-family: '{fonts["display"]}', sans-serif;">Marka başlık örneği</div>
      <div class="scale">
        <div class="scale-row"><span class="pt">H1 / 40</span><span class="demo scale-h1" style="font-family: '{fonts["display"]}', sans-serif;">Ana Başlık</span></div>
        <div class="scale-row"><span class="pt">H2 / 28</span><span class="demo scale-h2" style="font-family: '{fonts["display"]}', sans-serif;">Bölüm Başlığı</span></div>
        <div class="scale-row"><span class="pt">H3 / 20</span><span class="demo scale-h3" style="font-family: '{fonts["display"]}', sans-serif;">Alt Başlık</span></div>
      </div>
    </div>
    <div class="type-card">
      <div class="label">Body / Gövde</div>
      <div class="font-name">{html.escape(fonts["body"])} · Google Fonts</div>
      <h3 class="preview-display" style="font-family: '{fonts["body"]}', sans-serif; font-size: 48px;">Aa Bb Cc</h3>
      <p class="preview-body" style="font-family: '{fonts["body"]}', sans-serif;">Bu paragraf gövde fontu örneğidir. Uzun metinlerde okunabilirlik kritik. Satır yüksekliği 1.7, satır uzunluğu maksimum 65 karakter olmalı. Kontrast oranı en az 7:1 (WCAG AAA).</p>
      <div class="scale">
        <div class="scale-row"><span class="pt">Body / 16</span><span class="demo scale-body">Standart gövde metni — okuma için optimize.</span></div>
        <div class="scale-row"><span class="pt">Small / 13</span><span class="demo scale-small">İkincil bilgi, etiketler, alt metin.</span></div>
        <div class="scale-row"><span class="pt">Mono / 14</span><span class="demo" style="font-family: var(--mono); font-size: 14px;">code · veri · timestamp</span></div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="section-eyebrow">05 · Ses & Ton</div>
  <h2 class="section-title">Marka Sesi</h2>
  <p class="section-lead">Aynı marka, aynı ses. Email, sosyal, destek, sözleşme — hepsi aynı kişiden çıkmış gibi olsun.</p>
  <div class="tone-grid">
    <div class="tone-col do">
      <h3>Yap</h3>
      <ul>{do_items}</ul>
    </div>
    <div class="tone-col dont">
      <h3>Yapma</h3>
      <ul>{dont_items}</ul>
    </div>
  </div>
  <div class="voice-grid">{voice_cards}</div>
</section>

<section>
  <div class="section-eyebrow">06 · Sözlük</div>
  <h2 class="section-title">Kelime Tercihleri</h2>
  <p class="section-lead">Markamızın "diline" giren ve girmeyen kelimeler. İçerik üretirken referans al.</p>
  <div class="vocab">
    <div class="vocab-col use">
      <h4>Kullan</h4>
      <div>{use_words}</div>
    </div>
    <div class="vocab-col avoid">
      <h4>Kaçın</h4>
      <div>{avoid_words}</div>
    </div>
  </div>
</section>

<section>
  <div class="section-eyebrow">07 · UI Komponentleri</div>
  <h2 class="section-title">Arayüz Sistemi</h2>
  <p class="section-lead">Web ve uygulamalarda kullanılacak temel komponentler bu paletten beslenir.</p>
  <div class="ui-grid">
    <div class="ui-card">
      <div class="label">Butonlar</div>
      <div class="btn-row">
        <button class="btn primary">Birincil CTA</button>
        <button class="btn secondary">İkincil</button>
        <button class="btn ghost">Ghost</button>
      </div>
    </div>
    <div class="ui-card">
      <div class="label">Badge & Etiket</div>
      <span class="badge primary">YENİ</span>
      <span class="badge accent">PRO</span>
      <span class="badge ghost">v2.1</span>
    </div>
    <div class="ui-card">
      <div class="label">Form Input</div>
      <input class="input-demo" placeholder="ornek@email.com" />
    </div>
    <div class="ui-card">
      <div class="label">E-posta İmzası</div>
      <div class="signature">
        <div class="name">[İsim Soyisim]</div>
        <div class="title">Pozisyon · {biz}</div>
        <div class="contact">isim@{biz.lower().replace(" ", "")[:15]}.com<br>+90 5XX XXX XX XX</div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="section-eyebrow">08 · Sosyal Medya</div>
  <h2 class="section-title">Sosyal Post Şablonu</h2>
  <p class="section-lead">Marka tonu + görsel sistem birleştirildiğinde post böyle görünür.</p>
  <div class="social-mock">
    <div class="social-header">
      <div class="social-avatar">{biz[:2].upper()}</div>
      <div class="social-handle">@{biz.lower().replace(" ", "")}<small>{ind}</small></div>
    </div>
    <div class="social-image">{tagline or biz}</div>
    <div class="social-caption">{social_caption}</div>
  </div>
</section>

<footer class="brand-footer">
  <div class="top">
    <div class="biz">{biz}</div>
    <div>brand board · {datetime.now().strftime('%Y-%m-%d')}</div>
  </div>
  <div class="meta">Built with goat-bot BrandKit agent · {st} · {ind}</div>
</footer>

</body>
</html>"""
