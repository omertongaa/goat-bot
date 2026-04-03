"""Presenter Agent — Presentation and slide deck generation."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class PresenterAgent(BaseAgent):
    agent_id = "presenter"
    name = "Presenter"
    role = "Creates professional presentations, pitch decks, and slide content"
    category = "creative"

    TEMPLATES = {
        "pitch_deck": {"name": "Pitch Deck", "slides": 10, "purpose": "Yatırımcı / müşteri sunumu"},
        "proposal": {"name": "Teklif Sunumu", "slides": 8, "purpose": "Hizmet teklifi"},
        "report": {"name": "Rapor Sunumu", "slides": 12, "purpose": "Performans / analiz raporu"},
        "training": {"name": "Eğitim Sunumu", "slides": 15, "purpose": "Workshop / eğitim"},
        "company": {"name": "Şirket Tanıtım", "slides": 10, "purpose": "Firma tanıtımı"},
        "case_study": {"name": "Başarı Hikayesi", "slides": 8, "purpose": "Müşteri case study"},
    }

    def run(self, template: str = "pitch_deck", topic: str = "",
            business_name: str = "", audience: str = "") -> dict:
        self.log("Presenter agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "My Agency")
        niche = config.get("niche", "dijital pazarlama")

        if not topic:
            topic = f"{business_name} — {niche} hizmetleri"
        if not audience:
            audience = "Potansiyel müşteriler ve karar vericiler"

        tmpl = self.TEMPLATES.get(template, self.TEMPLATES["pitch_deck"])
        self.log(f"Template: {tmpl['name']} | Slides: {tmpl['slides']} | Topic: {topic}")

        # Generate slide content via Claude
        prompt = f"""Sen profesyonel bir sunum tasarımcısısın.

İşletme: {business_name}
Sektör: {niche}
Sunum türü: {tmpl['name']}
Amaç: {tmpl['purpose']}
Konu: {topic}
Hedef kitle: {audience}
Slayt sayısı: {tmpl['slides']}

Her slayt için şunları yaz:
1. **Slayt başlığı**
2. **Ana mesaj** (1-2 cümle)
3. **Bullet points** (3-5 madde)
4. **Konuşmacı notları** (ne söylenmeli)
5. **Görsel önerisi** (ne gösterilmeli)

Ayrıca:
- Sunum açılış cümlesi (hook)
- Kapanış / CTA
- Tasarım notları (renk, font önerisi)

Profesyonel, ikna edici, görsel odaklı yaz. Türkçe."""

        slides_content = self.call_claude(prompt)
        if not slides_content:
            slides_content = self._generate_fallback_slides(business_name, niche, tmpl, topic)

        # Generate HTML presentation
        html_path = self._generate_html_presentation(business_name, topic, slides_content, tmpl, niche)

        # Save presentation data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pres_data = {
            "template": template,
            "template_name": tmpl["name"],
            "topic": topic,
            "business_name": business_name,
            "audience": audience,
            "slides_content": slides_content,
            "html_path": html_path,
            "created_at": timestamp,
        }

        self.save_data(f"presentations/{timestamp}_{template}.json", pres_data)

        results = {
            "status": "ok",
            "summary": f"{tmpl['name']} oluşturuldu — {topic} ({tmpl['slides']} slayt)",
            "metrics": {
                "template": tmpl["name"],
                "slides": tmpl["slides"],
                "html_generated": bool(html_path),
                "timestamp": datetime.now().isoformat(),
            },
            "presentation": pres_data,
            "recommendations": [
                "Sunumu kendi marka renklerinize uyarlayın",
                "Her slaytta tek bir ana mesaj olsun",
                "Görselleri ekleyin — metin yoğunluğunu azaltın",
                "Konuşmacı notlarını prova edin",
                "10-20-30 kuralı: 10 slayt, 20 dakika, 30pt font",
            ],
        }

        self.save_output("presenter_report.json", results)
        self.log("Presenter agent completed")
        return results

    def _generate_html_presentation(self, business_name, topic, content, tmpl, niche):
        """Generate a self-contained HTML presentation."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topic.lower().replace(" ", "_")[:30]

        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{topic} — {business_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0c; color: #e8e8e8; }}
.slide {{ min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 60px 80px; border-bottom: 1px solid #222; }}
.slide:nth-child(odd) {{ background: linear-gradient(135deg, #0a0a0c 0%, #1a1a2e 100%); }}
.slide:nth-child(even) {{ background: linear-gradient(135deg, #111114 0%, #0d1b2a 100%); }}
.slide h1 {{ font-size: 3em; color: #e85d26; margin-bottom: 20px; }}
.slide h2 {{ font-size: 2.2em; color: #e85d26; margin-bottom: 30px; }}
.slide p {{ font-size: 1.3em; line-height: 1.8; color: #ccc; max-width: 800px; }}
.slide ul {{ font-size: 1.2em; line-height: 2; list-style: none; padding-left: 0; }}
.slide ul li::before {{ content: "→ "; color: #e85d26; font-weight: bold; }}
.slide .subtitle {{ font-size: 1.5em; color: #8a8a98; margin-top: 10px; }}
.slide .cta {{ display: inline-block; margin-top: 30px; padding: 15px 40px; background: #e85d26; color: #fff; font-size: 1.2em; border-radius: 8px; text-decoration: none; }}
.slide .footer {{ position: absolute; bottom: 30px; font-size: 0.9em; color: #555; }}
.nav {{ position: fixed; bottom: 20px; right: 20px; z-index: 100; display: flex; gap: 10px; }}
.nav button {{ padding: 10px 20px; background: #e85d26; color: #fff; border: none; border-radius: 5px; cursor: pointer; font-size: 1em; }}
.nav button:hover {{ background: #ff7a45; }}
</style>
</head>
<body>

<div class="slide">
<h1>{topic}</h1>
<p class="subtitle">{business_name} — {niche}</p>
<p>{tmpl['name']} | {tmpl['slides']} Slayt</p>
</div>

<div class="slide">
<h2>İçerik</h2>
<div style="white-space: pre-wrap; font-size: 1.1em; line-height: 1.8;">
{content[:3000] if content else "Sunum içeriği burada görünecek."}
</div>
</div>

<div class="slide">
<h2>Sonraki Adımlar</h2>
<ul>
<li>Detaylı görüşme planlayalım</li>
<li>İhtiyaç analizi yapalım</li>
<li>Size özel teklif hazırlayalım</li>
</ul>
<a class="cta" href="#">İletişime Geçin</a>
</div>

<div class="nav">
<button onclick="window.scrollBy(0, -window.innerHeight)">↑</button>
<button onclick="window.scrollBy(0, window.innerHeight)">↓</button>
</div>

</body>
</html>"""

        out_dir = OUTPUT_DIR / "presentations"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{timestamp}_{slug}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        self.log(f"HTML presentation saved: {path}")
        return str(path)

    def _generate_fallback_slides(self, business_name, niche, tmpl, topic):
        return f"""# {topic}

## Slayt 1 — Kapak
**{business_name}**
{niche} alanında profesyonel çözümler

## Slayt 2 — Problem
- İşletmelerin %70'i dijital varlığını yönetemiyor
- Zaman ve kaynak israfı
- Rakiplerin gerisinde kalma riski

## Slayt 3 — Çözüm
- AI destekli otomasyon
- End-to-end hizmet paketi
- Ölçülebilir sonuçlar

## Slayt 4 — Hizmetlerimiz
- Lead generation & outreach
- Website & SEO optimizasyonu
- Sosyal medya yönetimi
- Reklam kampanya yönetimi

## Slayt 5 — Nasıl Çalışıyoruz
1. İhtiyaç analizi
2. Strateji oluşturma
3. Uygulama & optimizasyon
4. Raporlama & büyüme

## Slayt 6 — Sonuçlar
- %300 lead artışı
- %50 maliyet düşüşü
- 2 hafta içinde ilk sonuçlar

## Slayt 7 — Fiyatlandırma
- Starter: Temel paket
- Growth: Büyüme paketi
- Enterprise: Kurumsal çözüm

## Slayt 8 — CTA
Hemen başlayalım!
İletişim: {business_name}
"""
