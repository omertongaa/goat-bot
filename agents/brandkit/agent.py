"""BrandKit Agent — Brand identity creation and management."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class BrandKitAgent(BaseAgent):
    agent_id = "brandkit"
    name = "BrandKit"
    role = "Creates complete brand identity — colors, fonts, guidelines, assets"
    category = "creative"

    def run(self, business_name: str = "", industry: str = "",
            style: str = "modern", values: str = "") -> dict:
        self.log("BrandKit agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "My Agency")
        if not industry:
            industry = config.get("niche", "dijital pazarlama")
        if not values:
            values = "profesyonel, yenilikçi, güvenilir"

        self.log(f"Brand: {business_name} | Industry: {industry} | Style: {style}")

        # Generate brand identity via Claude
        prompt = f"""Sen profesyonel bir marka kimliği tasarımcısısın.

İşletme: {business_name}
Sektör: {industry}
Stil: {style}
Değerler: {values}

Kapsamlı bir marka kimliği kiti oluştur:

1. **Marka Hikayesi** (mission, vision, values — 2-3 paragraf)

2. **Renk Paleti**
   - Ana renk (primary) + hex kodu
   - İkincil renk (secondary) + hex kodu
   - Accent renk + hex kodu
   - Nötr renkler (background, text, muted)
   - Renk kullanım kuralları

3. **Tipografi**
   - Başlık fontu (Google Fonts'tan)
   - Gövde fontu
   - Accent/display font
   - Font boyutları (H1-H6, body, small)

4. **Logo Kılavuzu**
   - Logo konsepti açıklaması
   - Minimum boyut
   - Clear space kuralları
   - Arka plan kuralları (açık/koyu)

5. **Ton & Ses (Tone of Voice)**
   - İletişim tonu (formal/informal/friendly)
   - Kullanılacak kelimeler
   - Kaçınılacak kelimeler
   - Örnek cümleler

6. **Sosyal Medya Kılavuzu**
   - Profil resmi stili
   - Post tasarım kuralları
   - Story/reel format
   - Grid düzeni önerisi

7. **Email Şablonu**
   - Header rengi
   - Font seçimi
   - İmza formatı

Türkçe, detaylı ve uygulanabilir yaz."""

        brand_guide = self.call_claude(prompt)
        if not brand_guide:
            brand_guide = self._generate_fallback_brand(business_name, industry, style)

        # Generate color palette data
        colors = self._extract_or_generate_colors(style, industry)

        # Generate brand board HTML
        html_path = self._generate_brand_board(business_name, industry, colors, brand_guide)

        # Try generating logo concept image
        logo_path = None
        try:
            from services.image import generate_image
            logo_prompt = f"Minimalist professional logo design for {business_name}, {industry}, {style} style, clean vector, solid background"
            logo_path = generate_image(logo_prompt, size="square",
                                       filename=f"logo_concept_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            if logo_path:
                self.log(f"Logo concept generated: {logo_path}")
        except Exception as e:
            self.log(f"Logo generation skipped: {e}")

        # Save brand kit
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brand_data = {
            "business_name": business_name,
            "industry": industry,
            "style": style,
            "values": values,
            "colors": colors,
            "brand_guide": brand_guide,
            "html_path": html_path,
            "logo_path": logo_path,
            "created_at": timestamp,
        }

        self.save_data(f"brandkit/{timestamp}_brand.json", brand_data)

        results = {
            "status": "ok",
            "summary": f"Marka kimliği kiti oluşturuldu — {business_name} ({style})",
            "metrics": {
                "business_name": business_name,
                "style": style,
                "colors_defined": len(colors),
                "brand_board_generated": bool(html_path),
                "logo_generated": bool(logo_path),
                "timestamp": datetime.now().isoformat(),
            },
            "brand": brand_data,
            "recommendations": [
                "Tüm iletişim kanallarında tutarlı kullanım sağlayın",
                "Renk paletini Canva/Figma'ya kaydedin",
                "Profesyonel logo tasarımı için brief'i kullanın",
                "Brand kit'i ekip ile paylaşın",
                "Yılda bir güncelleme yapın",
            ],
        }

        self.save_output("brandkit_report.json", results)
        self.log("BrandKit agent completed")
        return results

    def _extract_or_generate_colors(self, style, industry):
        """Generate a color palette based on style and industry."""
        palettes = {
            "modern": {
                "primary": "#e85d26", "secondary": "#1a1a2e",
                "accent": "#00ff41", "background": "#fafafa",
                "text": "#1a1a1a", "muted": "#8a8a98",
            },
            "minimal": {
                "primary": "#2d2d2d", "secondary": "#666666",
                "accent": "#e85d26", "background": "#ffffff",
                "text": "#1a1a1a", "muted": "#999999",
            },
            "bold": {
                "primary": "#ff3366", "secondary": "#6c5ce7",
                "accent": "#ffeaa7", "background": "#0a0a0c",
                "text": "#ffffff", "muted": "#636e72",
            },
            "corporate": {
                "primary": "#0066cc", "secondary": "#003366",
                "accent": "#00cc66", "background": "#f5f7fa",
                "text": "#1a1a1a", "muted": "#6c757d",
            },
            "warm": {
                "primary": "#e85d26", "secondary": "#c0392b",
                "accent": "#f39c12", "background": "#fdf6f0",
                "text": "#2c3e50", "muted": "#95a5a6",
            },
            "tech": {
                "primary": "#6c5ce7", "secondary": "#00cec9",
                "accent": "#fd79a8", "background": "#0a0a0c",
                "text": "#dfe6e9", "muted": "#636e72",
            },
        }
        return palettes.get(style, palettes["modern"])

    def _generate_brand_board(self, business_name, industry, colors, guide):
        """Generate an HTML brand board."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Brand Kit — {business_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #fafafa; color: #1a1a1a; }}
.header {{ background: {colors['primary']}; color: #fff; padding: 60px; text-align: center; }}
.header h1 {{ font-size: 3em; }}
.header p {{ font-size: 1.3em; opacity: 0.9; margin-top: 10px; }}
.section {{ padding: 40px 60px; }}
.section h2 {{ font-size: 1.8em; color: {colors['primary']}; margin-bottom: 20px; border-bottom: 2px solid {colors['primary']}; padding-bottom: 10px; }}
.colors {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.color-card {{ width: 150px; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
.color-swatch {{ height: 100px; }}
.color-info {{ padding: 12px; background: #fff; text-align: center; }}
.color-info .name {{ font-weight: bold; font-size: 0.9em; }}
.color-info .hex {{ color: #888; font-size: 0.85em; font-family: monospace; }}
.guide {{ white-space: pre-wrap; line-height: 1.8; font-size: 1.05em; max-width: 800px; }}
.footer {{ background: {colors['secondary']}; color: #fff; padding: 30px 60px; text-align: center; }}
</style>
</head>
<body>

<div class="header">
<h1>{business_name}</h1>
<p>Brand Identity Kit — {industry}</p>
</div>

<div class="section">
<h2>Renk Paleti</h2>
<div class="colors">
{"".join(f'''<div class="color-card"><div class="color-swatch" style="background:{v}"></div><div class="color-info"><div class="name">{k.title()}</div><div class="hex">{v}</div></div></div>''' for k, v in colors.items())}
</div>
</div>

<div class="section">
<h2>Marka Kılavuzu</h2>
<div class="guide">{guide[:5000] if guide else "Brand guide here."}</div>
</div>

<div class="footer">
<p>{business_name} — Brand Kit &copy; {datetime.now().year}</p>
</div>

</body>
</html>"""

        out_dir = OUTPUT_DIR / "brandkit"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{timestamp}_brand_board.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        self.log(f"Brand board saved: {path}")
        return str(path)

    def _generate_fallback_brand(self, business_name, industry, style):
        return f"""# Marka Kimliği Kiti — {business_name}

## Marka Hikayesi
{business_name}, {industry} sektöründe AI destekli çözümler sunan yenilikçi bir ajans/işletmedir. Amacımız teknolojiyi erişilebilir kılarak işletmelerin büyümesine yardımcı olmaktır.

## Renk Kullanım Kuralları
- Ana renk: Başlıklar, butonlar, CTA elementleri
- İkincil renk: Arka plan, footer, alt elementler
- Accent: Vurgulama, hover efektleri, başarı mesajları

## Tipografi
- Başlık: Poppins Bold (Google Fonts)
- Gövde: Inter Regular
- Accent: Space Grotesk

## Ton & Ses
- Profesyonel ama samimi
- Teknik terimlerden kaçın
- Kısa, net cümleler
- Aktif dil kullan
- "Biz" yerine "siz" odaklı

## Sosyal Medya
- Profil: Logo, minimal arka plan
- Post: Brand renkleri, tutarlı grid
- Story: Informal, behind-the-scenes
"""
