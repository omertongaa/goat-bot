"""Presenter Agent — gerçek, modern HTML pitch deck üretir.

JSON rapor değil, **kullanılabilir HTML sunum** çıkarır:
- Her slayt için zengin yapı (eyebrow + headline + body + footnote)
- Modern dark/gradient tasarım, slayt başına farklı layout
- Brand bar üstte, slide indicator altta — sayfa hiçbir zaman boş görünmez
- Klavye + sol/sağ butonlarıyla navigasyon, fullscreen
- Otomatik PDF export (Playwright headless Chromium)
- fal.ai ile hero/cta/quote/stats slaytlarına görsel
"""

import json
import re
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, OUTPUT_DIR


SLIDE_PROMPT = """Sen üst düzey sunum tasarımcısı + iş geliştirme uzmanısın.
McKinsey / Stripe / Linear seviyesinde sunum yapıyorsun.

İŞLETME: {business_name}
SEKTÖR: {niche}
SUNUM TÜRÜ: {template_name}
KONU: {topic}
HEDEF KİTLE: {audience}
HEDEF SLAYT SAYISI: {slide_count}

{slide_count} slaytlık DETAYLI ve PROFESYONEL bir sunum içeriği üret.
Her slayt gerçek satılabilir nitelikte olmalı — boilerplate "Bullet 1, 2, 3"
DEĞİL, sektöre özel, somut sayılar ve gerçek değer önerileri içermeli.
Her slayt **dolu** olmalı: headline yalnız başına bırakma, mutlaka body veya
bullets veya stats ile destekle. Boş slayt yasak.

ÇIKTI: SADECE geçerli JSON array döndür. Açıklama YOK.

Her slayt şu yapıda — TÜM ALANLAR DOLU OLSUN, gerekmeyen kısımları boş ("") bırak:
{{
  "layout": "hero|bullets|two-column|stats|quote|process|table|cta|summary",
  "eyebrow": "Üst etiket (kısa, büyük harf, 2-4 kelime — örn: '01 / GİRİŞ')",
  "headline": "Ana başlık (büyük puntoyla görünecek, 4-10 kelime)",
  "subhead": "Alt başlık veya tek cümle açıklama (10-20 kelime)",
  "body": "1-3 paragraflık zengin metin (mutlaka olsun — slayt asla yalnız başlıkla durmasın)",
  "bullets": [
    {{"title":"Madde başlığı","desc":"Tek satır açıklama (12-18 kelime)"}},
    ...   // layout=bullets için EN AZ 4 madde
  ],
  "left": "iki kolonlu layout için sol içerik (markdown)",
  "right": "iki kolonlu layout için sağ içerik (markdown)",
  "stats": [
    {{"value":"%73","label":"oran","desc":"Tek cümle bağlam"}},
    ...   // layout=stats için EN AZ 3 maksimum 4 stat
  ],
  "quote": "Alıntı metni (15-30 kelime)",
  "author": "Alıntı yazarı + ünvan",
  "process_steps": [
    {{"title":"Adım","desc":"15-25 kelime açıklama"}},
    ...   // layout=process için EN AZ 4 adım
  ],
  "rows": [["Paket adı","Fiyat","Kapsam"], ...],
  "cta_text": "Buton metni",
  "cta_subtitle": "CTA altı not (1 cümle)",
  "footnote": "Slayt altı küçük not — kaynak, tarih, dipnot (opsiyonel)",
  "speaker_notes": "Konuşmacı için 2-3 cümle ek bağlam"
}}

LAYOUT'LAR:
- "hero": kapak slaydı — eyebrow + büyük headline + subhead + body (3 cümle pitch)
- "bullets": liste — headline + 4-6 bullet (her biri title+desc)
- "two-column": karşılaştırma — headline + left + right (markdown ile **başlık** + - madde)
- "stats": rakamlar — headline + 3-4 stat (value + label + desc)
- "quote": alıntı — quote + author + body (alıntının bağlamı)
- "process": adımlar — headline + 4 adım (title + desc)
- "table": tablo — headline + rows (3 kolonlu: ad, fiyat, kapsam)
- "cta": çağrı — headline + body + cta_text + cta_subtitle
- "summary": özet — headline + body + 3 stat (kompakt karışım)

YAPIM SIRASI:
1. Slayt 1: **hero** — büyük başlık + alt başlık + 2 cümle pitch
2. Slayt 2: **bullets** — Problem (4-5 madde, sektöre özel)
3. Slayt 3: **two-column** — Mevcut durum vs Bizim yaklaşım
4. Slayt 4: **stats** — Etki rakamları (3-4 sayı, kaynak ile)
5. Slayt 5: **process** — 4 adım nasıl çalıştığımız
6. Slayt 6: **bullets** veya **summary** — Faydalar
7. Slayt 7: **quote** — Müşteri sözü + bağlam
8. Slayt 8: **table** — Paket/fiyat tablosu (3 paket)
9. Slayt 9: **cta** — Sonraki adım + buton

KURALLAR:
1. Her slayt **Türkçe**, **somut sayılarla**, sektöre özel
2. Boilerplate'ten KAÇIN: "Profesyonel ekip, kaliteli hizmet" YOK
3. Eyebrow her slaytta olsun — "01 / GİRİŞ" gibi sayfa numarası + bölüm
4. Headline asla yalnız bırakma — body veya bullets veya stats ile doldur
5. Body en az 80 karakter olsun (boş görünmesin)

Sadece JSON array döndür."""


class PresenterAgent(BaseAgent):
    agent_id = "presenter"
    name = "Presenter"
    role = "Profesyonel HTML sunumlar — pitch deck, teklif, rapor"
    category = "creative"

    TEMPLATES = {
        "pitch_deck":  {"name": "Pitch Deck", "slides": 9, "purpose": "Yatırımcı veya müşteri sunumu"},
        "proposal":    {"name": "Teklif Sunumu", "slides": 9, "purpose": "Hizmet teklifi + fiyatlandırma"},
        "report":      {"name": "Rapor Sunumu", "slides": 10, "purpose": "Performans / analiz raporu"},
        "training":    {"name": "Eğitim Sunumu", "slides": 10, "purpose": "Workshop / eğitim modülü"},
        "company":     {"name": "Şirket Tanıtımı", "slides": 9, "purpose": "Firma overview"},
        "case_study":  {"name": "Başarı Hikayesi", "slides": 8, "purpose": "Müşteri case study"},
    }

    def run(self, template: str = "pitch_deck", topic: str = "",
            business_name: str = "", audience: str = "",
            make_images: bool = True, make_pdf: bool = True,
            max_images: int = 4) -> dict:
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name") or config.get("name") or "GOAT"
        niche = config.get("niche") or "dijital pazarlama"
        if not topic:
            topic = f"{business_name} — {niche}"
        if not audience:
            audience = "İşletme sahipleri ve karar vericiler"

        tmpl = self.TEMPLATES.get(template, self.TEMPLATES["pitch_deck"])
        self.log(f"Sunum: {tmpl['name']} · konu: {topic[:60]}")

        prompt = SLIDE_PROMPT.format(
            business_name=business_name, niche=niche,
            template_name=tmpl["name"], topic=topic,
            audience=audience, slide_count=tmpl["slides"],
        )

        self.log("Claude'a zengin slayt içeriği soruyorum (60-120sn)...")
        raw = self.call_claude(prompt, timeout=180)

        slides = self._parse_slides(raw) if raw else []
        if not slides:
            self.log("Claude JSON dönmedi, fallback şablon devreye giriyor")
            slides = self._fallback_slides(business_name, niche, tmpl, topic)

        # Eksik alanları doldur — slide asla boş görünmesin
        slides = [self._enrich_slide(s, i, len(slides), business_name, niche) for i, s in enumerate(slides)]

        # Generate hero/key slide images via fal.ai
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9_-]", "_", topic.lower().replace(" ", "_"))[:30]

        if make_images:
            slides = self._inject_slide_images(slides, topic, business_name, niche, max_images, timestamp, slug)

        self.log(f"{len(slides)} slayt için HTML render ediliyor...")
        out_dir = OUTPUT_DIR / "presentations"
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{timestamp}_{slug or template}.html"
        html_path.write_text(self._render_html(slides, topic, business_name, niche, tmpl), encoding="utf-8")

        pdf_path = None
        if make_pdf:
            pdf_path = self._export_pdf(html_path, out_dir, timestamp, slug or template)

        images_count = sum(1 for s in slides if s.get("image_path"))
        pres_data = {
            "template": template, "template_name": tmpl["name"],
            "topic": topic, "business_name": business_name,
            "audience": audience, "slide_count": len(slides),
            "slides": slides, "html_path": str(html_path),
            "pdf_path": pdf_path,
            "images_generated": images_count,
            "created_at": timestamp,
        }
        self.save_data(f"presentations/{timestamp}_{template}.json", pres_data)

        artifacts = [{"kind": "presentation_html", "path": str(html_path), "name": html_path.name}]
        if pdf_path:
            artifacts.append({"kind": "presentation_pdf", "path": pdf_path, "name": Path(pdf_path).name})

        summary_parts = [f"{tmpl['name']} hazır: {len(slides)} slayt"]
        if images_count:
            summary_parts.append(f"{images_count} hero görsel")
        if pdf_path:
            summary_parts.append(f"PDF: {Path(pdf_path).name}")
        summary_parts.append("HTML preview")

        results = {
            "status": "ok",
            "summary": " · ".join(summary_parts),
            "metrics": {
                "template": tmpl["name"], "slides": len(slides),
                "html_path": str(html_path), "pdf_path": pdf_path,
                "images_generated": images_count,
                "html_kb": round(html_path.stat().st_size / 1024, 1),
                "pdf_kb": round(Path(pdf_path).stat().st_size / 1024, 1) if pdf_path else 0,
            },
            "artifacts": artifacts,
            "presentation": pres_data,
            "recommendations": [
                f"Files → {html_path.name} aç (interaktif)" if not pdf_path else f"Files → {Path(pdf_path).name} aç (PDF)",
                "Slayt sayısını artırmak için make_images=true (her slayda görsel)",
                "Marka renklerini özelleştirmek için template parametresi değiştir",
            ],
        }
        self.save_output("presenter_report.json", results)
        return results

    # ── Slide enrichment — eksik alanları doldur ──────────────
    def _enrich_slide(self, s: dict, idx: int, total: int, business: str, niche: str) -> dict:
        """Slide'ın boş alanlarını mantıklı default'larla doldur — slayt
        asla yarı-boş görünmesin."""
        layout = (s.get("layout") or "bullets").lower()
        s["layout"] = layout

        # Eyebrow — yoksa otomatik üret
        if not s.get("eyebrow"):
            section_map = {
                "hero": "GİRİŞ", "bullets": "DETAY", "two-column": "KARŞILAŞTIRMA",
                "stats": "RAKAMLAR", "process": "SÜREÇ", "quote": "REFERANS",
                "table": "PAKETLER", "cta": "SONRAKİ ADIM", "summary": "ÖZET",
            }
            s["eyebrow"] = f"{idx+1:02d} / {section_map.get(layout, 'BÖLÜM')}"

        # Headline yoksa fallback
        if not s.get("headline"):
            s["headline"] = f"{business} — {niche.title()}"

        # Body yoksa subhead'i fallback olarak yerleştir
        if not s.get("body") and s.get("subhead"):
            pass  # subhead zaten görünecek
        elif not s.get("body") and layout in ("hero", "cta", "quote", "summary"):
            s["body"] = f"{business} olarak {niche} alanında ölçülebilir sonuç üretiyoruz."

        # Bullets normalize — string list ise dict'e çevir
        if isinstance(s.get("bullets"), list):
            normalized = []
            for b in s["bullets"]:
                if isinstance(b, str):
                    normalized.append({"title": b, "desc": ""})
                elif isinstance(b, dict):
                    normalized.append({
                        "title": b.get("title") or b.get("text") or "",
                        "desc": b.get("desc") or b.get("description") or "",
                    })
            s["bullets"] = normalized

        return s

    # ── Hero / key slide images via fal.ai ────────────────────
    def _inject_slide_images(self, slides, topic, business, niche, max_images, timestamp, slug):
        try:
            from services.image import generate_image
        except ImportError:
            return slides

        priority_layouts = ("hero", "cta", "quote", "stats", "summary")
        candidates = sorted(
            range(len(slides)),
            key=lambda i: (
                slides[i].get("layout") not in priority_layouts,
                i,
            ),
        )[:max(1, min(int(max_images or 4), 8))]

        self.log(f"fal.ai ile {len(candidates)} slayt için hero görsel üretiliyor...")
        for idx in candidates:
            slide = slides[idx]
            layout = slide.get("layout", "")
            headline = slide.get("headline", "") or topic

            mood_map = {
                "hero": f"Cinematic editorial photo, dramatic lighting, abstract {niche} concept, dark background, premium professional, no text, no logos",
                "cta": f"Inviting modern workspace photo, soft warm light, person ready to take action, blurred background, professional, no text",
                "quote": f"Atmospheric portrait photo, soft natural light, contemplative mood, professional headshot style, neutral background, no text",
                "stats": f"Modern data visualization aesthetic, abstract geometric shapes, gradient orange-to-red on dark background, no text, no numbers",
                "summary": f"Clean editorial photo for {niche} business, modern dark aesthetic, gradient orange highlight, no text",
                "process": f"Clean isometric workflow illustration, modern flat design, {niche} business process, neutral palette, no text",
            }
            prompt = mood_map.get(layout, f"Clean editorial photo for {niche} business, modern aesthetic, dark background, no text")
            prompt = f"{prompt}. Topic: {headline[:80]}. {business} brand context."

            fname = f"slide_{timestamp}_{slug}_{idx + 1}.png"
            img_path = generate_image(prompt, size="landscape_16_9", filename=fname)
            if img_path:
                slide["image_path"] = img_path
                self.log(f"  slayt {idx + 1} ({layout}): görsel hazır")
            else:
                self.log(f"  slayt {idx + 1} ({layout}): görsel atlandı")
        return slides

    # ── PDF export via Playwright ─────────────────────────────
    def _export_pdf(self, html_path, out_dir, timestamp, slug):
        try:
            from services.html_to_pdf import html_to_pdf
        except ImportError:
            self.log("html_to_pdf servisi yok — PDF atlandı")
            return None

        pdf_path = out_dir / f"{timestamp}_{slug}.pdf"
        result = html_to_pdf(
            html_path=str(html_path), pdf_path=str(pdf_path),
            landscape=True, width_px=1920, height_px=1080,
            full_page=False, log=self.log,
        )
        return result

    # ──────────────────────────────────────────────────────

    def _parse_slides(self, raw: str) -> list:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group())
            if isinstance(data, list):
                return [s for s in data if isinstance(s, dict)]
        except json.JSONDecodeError:
            return []
        return []

    def _fallback_slides(self, business: str, niche: str, tmpl: dict, topic: str) -> list:
        """Claude yoksa boilerplate yerine kullanılabilir, topic'i işleyen taslak."""
        n = niche.lower()
        return [
            {"layout": "hero",
             "eyebrow": "01 / GİRİŞ",
             "headline": topic,
             "subhead": f"{business} ile {niche} alanında ölçülebilir büyüme",
             "body": f"Bu sunumda {business}'in {niche} sektöründe nasıl somut ROI ürettiğini, "
                     f"hangi süreçleri otomatikleştirdiğimizi ve sizin için ne anlama geldiğini paylaşacağız."},

            {"layout": "bullets",
             "eyebrow": "02 / PROBLEM",
             "headline": "Bugün karşılaştığınız zorluklar",
             "subhead": f"{niche} sektöründe en sık duyduğumuz 4 başlık",
             "bullets": [
                 {"title": "Manuel süreçler büyümeyi engelliyor",
                  "desc": "Ekibin %40'ı tekrarlayan işlerde kayboluyor — strateji için zaman kalmıyor."},
                 {"title": "Veri var ama karar yok",
                  "desc": "Birden fazla araç, birbirine bağlanmamış raporlar, gecikmeli içgörü."},
                 {"title": "Müşteri kazanımı pahalı",
                  "desc": "Reklam maliyetleri artarken dönüşüm oranı düşüyor — birim ekonomi bozuluyor."},
                 {"title": "Ölçeklenince kalite düşüyor",
                  "desc": "Süreçler dökümante değil, yeni ekip üyesi 3 ayda verim veriyor."},
             ]},

            {"layout": "two-column",
             "eyebrow": "03 / KARŞILAŞTIRMA",
             "headline": "Mevcut durum vs Bizim yaklaşım",
             "left": "**Standart yaklaşım**\n\n- Tek tip kampanya\n- Aylık manuel rapor\n- Kanal silosu\n- Aylar süren entegrasyon",
             "right": "**Bizim yaklaşımımız**\n\n- A/B test edilmiş 3 hipotez\n- Canlı dashboard\n- Çapraz kanal orkestrasyon\n- 2 haftada canlı"},

            {"layout": "stats",
             "eyebrow": "04 / ETKİ",
             "headline": "Sayılarla sonuç",
             "subhead": "Son 12 ayda 30+ müşteri verisi",
             "stats": [
                 {"value": "%70", "label": "Operasyonel hız", "desc": "Manuel süreçlerin otomasyonu"},
                 {"value": "3.5×", "label": "Lead konversiyon", "desc": "Skorlu lead → satış"},
                 {"value": "%40", "label": "Maliyet düşüşü", "desc": "İlk 3 ay içinde"},
                 {"value": "14gn", "label": "Canlıya çıkış", "desc": "İlk pilot süresi"},
             ]},

            {"layout": "process",
             "eyebrow": "05 / SÜREÇ",
             "headline": "Nasıl çalışıyoruz",
             "subhead": "4 hafta — keşiften ilk sonuca",
             "process_steps": [
                 {"title": "Keşif", "desc": "İş hedefleri, mevcut araçlar ve veri kaynakları haritalanır (1. hafta)."},
                 {"title": "Plan", "desc": "Ölçülebilir 3 KPI ve hipotez listesi — paydaş onayıyla kilitlenir."},
                 {"title": "Uygula", "desc": "İlk pilot 2 haftada canlı — sprint bazlı iterasyon."},
                 {"title": "Ölç", "desc": "Haftalık rapor + ay sonu retro — kararlar veriyle alınır."},
             ]},

            {"layout": "summary",
             "eyebrow": "06 / FAYDA",
             "headline": "Sizin için ne demek?",
             "body": f"Tek bir panelden tüm {n} operasyonunuzu görmek, manuel raporlama yerine "
                     "haftalık otomatik özet almak ve karar süreçlerinizi günler değil saatler içinde "
                     "tamamlamak. Bu sadece tasarruf değil — pazara öne geçme avantajı.",
             "stats": [
                 {"value": "12sa", "label": "Haftalık zaman", "desc": "Manuel raporlamadan"},
                 {"value": "%25", "label": "Daha hızlı karar", "desc": "Veri toplama → aksiyon"},
                 {"value": "1×", "label": "Tek panel", "desc": "Her şey bir yerde"},
             ]},

            {"layout": "quote",
             "eyebrow": "07 / REFERANS",
             "headline": "Müşterilerimiz ne diyor",
             "quote": "Sonuçlar 4 hafta içinde gelmeye başladı. İlk ay sonunda "
                      "ekip tekrar stratejiye odaklanabildi.",
             "author": "B. Yılmaz — Operasyon Direktörü",
             "body": "Pilot dönemi sonrası kalıcı abonelik — şu anda 3. yılında birlikte çalışıyoruz."},

            {"layout": "table",
             "eyebrow": "08 / PAKETLER",
             "headline": "Yatırım seçenekleri",
             "subhead": "Ölçeğinize göre 3 paket — 14 gün ücretsiz pilot",
             "rows": [
                 ["Başlangıç", "₺25.000 / ay", "1 kanal · haftalık rapor · email destek"],
                 ["Büyüme", "₺50.000 / ay", "3 kanal · canlı dashboard · Slack destek"],
                 ["Özel", "Görüşelim", "Tam orkestrasyon · özel entegrasyon · adanmış ekip"],
             ],
             "footnote": "Tüm paketler 14 gün ücretsiz pilot ile başlar. Memnun kalmazsanız ödeme yok."},

            {"layout": "cta",
             "eyebrow": "09 / SONRAKİ ADIM",
             "headline": "30 dakika — pilotunuzu birlikte planlayalım",
             "subhead": "Ücretsiz, taahhütsüz",
             "body": "Görüşmede mevcut araçlarınızı, hedeflerinizi ve ilk 30 günde "
                     "nasıl ölçülebilir bir sonuç çıkaracağımızı konuşacağız.",
             "cta_text": "Görüşme Planla",
             "cta_subtitle": f"hello@{business.lower().replace(' ', '')}.com"},
        ]

    # ── HTML render ────────────────────────────────────────────
    def _render_html(self, slides: list, topic: str, business: str, niche: str, tmpl: dict) -> str:
        slide_html_blocks = []
        total = len(slides)
        for i, s in enumerate(slides):
            slide_html_blocks.append(self._render_slide(s, i, total, business, tmpl))

        slides_html = "\n".join(slide_html_blocks)
        title = f"{topic} — {business}"
        date_str = datetime.now().strftime("%d.%m.%Y")

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #09090b; --surface: #14141a; --surface-2: #1c1c24; --surface-3: #242430;
  --text: #f5f5f7; --text-2: #c3c3cc; --dim: #888; --border: rgba(255,255,255,0.07);
  --accent: #f97316; --accent-2: #ef4444; --green: #22c55e; --blue: #3b82f6;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; }}
body {{
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  overflow: hidden; -webkit-font-smoothing: antialiased;
}}

.deck {{ width: 100vw; height: 100vh; position: relative; overflow: hidden; }}

/* Brand bar — top fixed */
.brand-bar {{
  position: fixed; top: 0; left: 0; right: 0; height: 48px; z-index: 90;
  display: flex; align-items: center; padding: 0 32px;
  background: rgba(9,9,11,0.6); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  font-size: 12px; color: var(--dim);
}}
.brand-bar .logo {{ font-weight: 800; color: var(--text); letter-spacing: -0.02em; }}
.brand-bar .sep {{ margin: 0 12px; color: var(--surface-3); }}
.brand-bar .meta {{ flex: 1; }}
.brand-bar .right {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; }}

/* Slide */
.slide {{
  position: absolute; inset: 0;
  padding: 88px 80px 72px;
  display: none; flex-direction: column; justify-content: center;
  background: var(--bg);
  opacity: 0; transition: opacity 0.4s ease;
}}
.slide.active {{ display: flex; opacity: 1; }}

/* Layout-specific backgrounds */
.slide[data-layout="hero"] {{
  background: radial-gradient(ellipse at 25% 15%, rgba(249,115,22,0.18), transparent 55%),
              radial-gradient(ellipse at 80% 85%, rgba(239,68,68,0.10), transparent 55%),
              var(--bg);
  align-items: flex-start;
}}
.slide[data-layout="cta"] {{
  background: linear-gradient(135deg, rgba(249,115,22,0.20), rgba(239,68,68,0.12)),
              radial-gradient(ellipse at 50% 60%, rgba(249,115,22,0.15), transparent 60%),
              var(--bg);
  align-items: center; text-align: center;
}}
.slide[data-layout="quote"] {{
  background: linear-gradient(180deg, var(--bg), var(--surface));
  align-items: center; justify-content: center; text-align: center;
}}
.slide[data-layout="stats"], .slide[data-layout="summary"], .slide[data-layout="process"] {{
  background: linear-gradient(180deg, var(--bg) 0%, var(--surface) 100%);
}}

/* Accent strip — left edge for non-hero/cta */
.slide:not([data-layout="hero"]):not([data-layout="cta"]):not([data-layout="quote"])::before {{
  content: ''; position: absolute; left: 0; top: 88px; bottom: 72px; width: 3px;
  background: linear-gradient(180deg, var(--accent), var(--accent-2));
  opacity: 0.7;
}}

/* Eyebrow tag */
.eyebrow {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--accent); letter-spacing: 0.15em; text-transform: uppercase;
  margin-bottom: 20px; font-weight: 500;
  display: inline-flex; align-items: center; gap: 10px;
}}
.eyebrow::before {{
  content: ''; width: 24px; height: 1px; background: var(--accent);
}}

/* Typography */
.slide h1 {{
  font-size: clamp(40px, 5.6vw, 88px); font-weight: 800;
  line-height: 1.05; letter-spacing: -0.03em;
  background: linear-gradient(135deg, var(--text) 0%, var(--accent) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  margin-bottom: 20px;
  max-width: 1400px;
}}
.slide h2 {{
  font-size: clamp(32px, 4.2vw, 56px); font-weight: 700;
  line-height: 1.1; letter-spacing: -0.02em;
  margin-bottom: 18px;
  max-width: 1200px;
}}
.slide h2 .accent {{ color: var(--accent); }}
.subhead {{
  font-size: clamp(18px, 1.9vw, 24px); font-weight: 500;
  color: var(--text-2); margin-bottom: 28px;
  max-width: 1100px; line-height: 1.4;
}}
.body-text {{
  font-size: clamp(15px, 1.5vw, 19px); line-height: 1.6;
  color: var(--text-2); max-width: 880px;
  margin-bottom: 16px;
}}

/* Bullets — title + desc */
ul.bullets {{
  list-style: none; padding-left: 0;
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px 32px;
  max-width: 1200px;
}}
ul.bullets.single {{ grid-template-columns: 1fr; max-width: 900px; }}
ul.bullets li {{
  padding: 16px 18px 16px 48px; position: relative;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px;
}}
ul.bullets li::before {{
  content: counter(bullet, decimal-leading-zero);
  counter-increment: bullet;
  position: absolute; left: 16px; top: 16px;
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: var(--accent); font-weight: 600;
}}
ul.bullets {{ counter-reset: bullet; }}
ul.bullets li .b-title {{
  font-size: 17px; font-weight: 600; color: var(--text);
  margin-bottom: 4px; line-height: 1.3;
}}
ul.bullets li .b-desc {{
  font-size: 14px; color: var(--text-2); line-height: 1.5;
}}

/* Two-column */
.two-col {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 32px;
  max-width: 1280px;
}}
.two-col > div {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 28px 28px 24px;
  font-size: clamp(15px, 1.4vw, 18px); color: var(--text-2);
  line-height: 1.6;
}}
.two-col h3 {{
  font-size: 17px; color: var(--accent); margin-bottom: 14px;
  font-weight: 700; letter-spacing: -0.01em;
  border-bottom: 1px solid var(--border); padding-bottom: 10px;
}}
.two-col ul {{ list-style: none; padding: 0; }}
.two-col li {{
  padding: 8px 0 8px 22px; position: relative; font-size: 16px;
}}
.two-col li::before {{
  content: '→'; position: absolute; left: 0; color: var(--accent);
}}

/* Stats */
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 20px; margin-top: 8px; max-width: 1280px;
}}
.stat-card {{
  background: linear-gradient(180deg, var(--surface) 0%, var(--surface-2) 100%);
  padding: 28px 24px; border-radius: 14px;
  border: 1px solid var(--border);
  position: relative; overflow: hidden;
}}
.stat-card::before {{
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: linear-gradient(180deg, var(--accent), var(--accent-2));
}}
.stat-card .v {{
  font-size: clamp(40px, 5vw, 72px); font-weight: 900;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
  line-height: 1; letter-spacing: -0.04em;
}}
.stat-card .l {{
  font-size: 13px; color: var(--text); margin-top: 14px;
  text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600;
}}
.stat-card .d {{
  font-size: 13px; color: var(--dim); margin-top: 6px; line-height: 1.5;
}}

/* Process */
.process {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px; max-width: 1280px;
}}
.process .step {{
  background: var(--surface); padding: 24px; border-radius: 14px;
  border: 1px solid var(--border); border-left: 3px solid var(--accent);
  position: relative;
}}
.process .step .num {{
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: var(--accent); letter-spacing: 0.1em; font-weight: 600;
}}
.process .step h4 {{
  font-size: 20px; margin: 8px 0 10px; font-weight: 700;
  letter-spacing: -0.01em;
}}
.process .step p {{ color: var(--text-2); font-size: 14px; line-height: 1.55; }}

/* Quote */
.q-block {{ max-width: 1000px; }}
.q-block .quote {{
  font-size: clamp(28px, 3.6vw, 52px); font-weight: 600; line-height: 1.25;
  letter-spacing: -0.01em; font-style: italic;
}}
.q-block .quote::before {{
  content: '"'; color: var(--accent);
  font-size: 1.4em; vertical-align: -0.1em; line-height: 0;
}}
.q-block .author {{
  font-size: 17px; color: var(--text-2); margin-top: 28px; font-weight: 500;
}}
.q-block .author::before {{
  content: '— '; color: var(--accent);
}}

/* Table */
table.tbl {{
  width: 100%; max-width: 1100px; border-collapse: collapse;
  font-size: 16px;
  background: var(--surface); border-radius: 12px; overflow: hidden;
  border: 1px solid var(--border);
}}
table.tbl tr {{ border-bottom: 1px solid var(--border); }}
table.tbl tr:last-child {{ border-bottom: none; }}
table.tbl tr:hover {{ background: var(--surface-2); }}
table.tbl td {{ padding: 18px 20px; color: var(--text-2); }}
table.tbl td:first-child {{ font-weight: 600; color: var(--text); }}
table.tbl td:nth-child(2) {{
  font-family: 'JetBrains Mono', monospace; color: var(--accent); font-weight: 700;
}}
table.tbl tr:first-child td:nth-child(2) {{ color: var(--accent); }}

/* Summary — combines body + stats */
.summary-grid {{
  display: grid; grid-template-columns: 1.2fr 1fr; gap: 48px;
  align-items: center; max-width: 1280px;
}}
.summary-grid .stats {{ grid-template-columns: 1fr; gap: 12px; }}
.summary-grid .stat-card {{ padding: 20px; }}
.summary-grid .stat-card .v {{ font-size: 40px; }}

/* CTA */
.cta-btn {{
  display: inline-block; margin-top: 24px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #fff; padding: 18px 48px; border-radius: 12px;
  font-size: 22px; font-weight: 700; letter-spacing: -0.01em;
  text-decoration: none;
  box-shadow: 0 16px 48px rgba(249,115,22,0.4);
  transition: transform 0.2s;
}}
.cta-btn:hover {{ transform: translateY(-2px); }}
.cta-sub {{ font-size: 15px; color: var(--text-2); margin-top: 14px; font-weight: 500; }}

/* Footnote */
.footnote {{
  position: absolute; bottom: 88px; left: 80px; right: 80px;
  font-size: 12px; color: var(--dim); font-style: italic;
}}

/* Slide footer (page indicator) */
.slide-footer {{
  position: fixed; bottom: 0; left: 0; right: 0; height: 48px;
  display: flex; align-items: center; padding: 0 32px;
  border-top: 1px solid var(--border);
  background: rgba(9,9,11,0.6); backdrop-filter: blur(12px);
  font-size: 12px; color: var(--dim); z-index: 90;
}}
.slide-footer .label {{ flex: 1; }}
.slide-footer .nums {{ font-family: 'JetBrains Mono', monospace; }}
.slide-footer .dots {{
  display: flex; gap: 6px; margin: 0 24px;
}}
.slide-footer .dot {{
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--surface-3); transition: background 0.2s;
}}
.slide-footer .dot.active {{ background: var(--accent); width: 18px; border-radius: 3px; }}

/* Nav buttons */
.nav {{
  position: fixed; bottom: 64px; left: 50%; transform: translateX(-50%);
  display: flex; gap: 8px; z-index: 100;
}}
.nav button {{
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text); padding: 10px 16px; border-radius: 8px;
  font-family: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}}
.nav button:hover {{ background: var(--surface-2); border-color: var(--accent); }}

.progress {{
  position: fixed; top: 48px; left: 0; height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  z-index: 200; transition: width 0.3s;
}}

@media print {{
  .nav, .progress, .brand-bar, .slide-footer {{ display: none !important; }}
  body, html {{ overflow: visible; height: auto; }}
  .deck {{ width: 100%; height: auto; overflow: visible; position: static; }}
  .slide {{
    display: flex !important; opacity: 1 !important;
    position: relative !important; inset: auto !important;
    width: 100%; height: 100vh;
    padding: 60px 60px 50px;
    page-break-after: always; page-break-inside: avoid;
    break-after: page;
  }}
  .slide:last-child {{ page-break-after: auto; break-after: auto; }}
  .footnote {{ bottom: 30px; left: 60px; right: 60px; }}
  .slide:not([data-layout="hero"]):not([data-layout="cta"]):not([data-layout="quote"])::before {{
    top: 60px; bottom: 50px;
  }}
}}
</style>
</head>
<body>

<div class="brand-bar">
  <span class="logo">{_escape(business)}</span>
  <span class="sep">·</span>
  <span>{_escape(tmpl["name"])}</span>
  <span class="meta"></span>
  <span class="right">{date_str}</span>
</div>

<div class="progress" id="progress"></div>

<div class="deck">
{slides_html}
</div>

<div class="nav">
  <button onclick="prev()">← Önceki</button>
  <button onclick="next()">Sonraki →</button>
  <button onclick="document.documentElement.requestFullscreen()">⛶ Tam ekran</button>
  <button onclick="window.print()">🖨 PDF</button>
</div>

<div class="slide-footer">
  <span class="label">{_escape(business)} · {_escape(tmpl["name"])}</span>
  <div class="dots" id="dots"></div>
  <span class="nums"><span id="curNum">1</span> / {total}</span>
</div>

<script>
let cur = 0;
const slides = document.querySelectorAll('.slide');
const total = slides.length;
const progress = document.getElementById('progress');
const dotsEl = document.getElementById('dots');
const curNumEl = document.getElementById('curNum');

// Build dots
for (let i = 0; i < total; i++) {{
  const d = document.createElement('div');
  d.className = 'dot';
  d.onclick = () => show(i);
  dotsEl.appendChild(d);
}}

function show(n) {{
  cur = Math.max(0, Math.min(n, total - 1));
  slides.forEach((s, i) => s.classList.toggle('active', i === cur));
  progress.style.width = ((cur + 1) / total * 100) + '%';
  curNumEl.textContent = cur + 1;
  dotsEl.querySelectorAll('.dot').forEach((d, i) => d.classList.toggle('active', i === cur));
}}
function next() {{ show(cur + 1); }}
function prev() {{ show(cur - 1); }}

document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') next();
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') prev();
  if (e.key === 'f') document.documentElement.requestFullscreen();
  if (e.key === 'Home') show(0);
  if (e.key === 'End') show(total - 1);
}});

show(0);
</script>
</body>
</html>"""

    def _render_slide(self, s: dict, idx: int, total: int, business: str, tmpl: dict) -> str:
        layout = (s.get("layout") or "bullets").lower()
        active = "active" if idx == 0 else ""

        bg_style = ""
        if s.get("image_path"):
            try:
                abs_p = Path(s["image_path"]).resolve()
                if layout == "hero":
                    bg_style = (f' style="background: linear-gradient(135deg, rgba(9,9,11,0.85), rgba(9,9,11,0.55)), '
                                f'url(file://{abs_p}) center/cover no-repeat;"')
                elif layout == "cta":
                    bg_style = (f' style="background: linear-gradient(135deg, rgba(249,115,22,0.6), rgba(239,68,68,0.4)), '
                                f'url(file://{abs_p}) center/cover no-repeat;"')
                elif layout == "quote":
                    bg_style = (f' style="background: linear-gradient(180deg, rgba(9,9,11,0.7), rgba(20,20,26,0.85)), '
                                f'url(file://{abs_p}) center/cover no-repeat;"')
                else:
                    bg_style = (f' style="background: linear-gradient(135deg, rgba(9,9,11,0.8), rgba(20,20,26,0.6)), '
                                f'url(file://{abs_p}) center/cover no-repeat;"')
            except Exception:
                bg_style = ""

        eyebrow = _eyebrow(s)
        body = ""

        if layout == "hero":
            body = f"""
{eyebrow}
<h1>{_escape(s.get('headline', ''))}</h1>
{_subhead(s)}
{_body_text(s)}
"""
        elif layout == "bullets":
            bullets = s.get("bullets") or []
            single_class = " single" if len(bullets) <= 3 else ""
            blist = "".join(_render_bullet(b) for b in bullets)
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<ul class="bullets{single_class}">{blist}</ul>
"""
        elif layout == "two-column":
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<div class="two-col">
<div>{_md_block(s.get('left', ''))}</div>
<div>{_md_block(s.get('right', ''))}</div>
</div>
"""
        elif layout == "stats":
            stats = s.get("stats") or []
            cards = "".join(_render_stat(st) for st in stats)
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<div class="stats">{cards}</div>
"""
        elif layout == "summary":
            stats = s.get("stats") or []
            cards = "".join(_render_stat(st) for st in stats)
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
<div class="summary-grid">
  <div>
    {_subhead(s)}
    {_body_text(s)}
  </div>
  <div class="stats">{cards}</div>
</div>
"""
        elif layout == "process":
            steps = s.get("process_steps") or []
            items = "".join(
                f'<div class="step"><div class="num">ADIM {n+1:02d}</div>'
                f'<h4>{_escape(st.get("title",""))}</h4>'
                f'<p>{_escape(st.get("desc",""))}</p></div>'
                for n, st in enumerate(steps)
            )
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<div class="process">{items}</div>
"""
        elif layout == "quote":
            body = f"""
<div class="q-block">
{eyebrow}
<div class="quote">{_escape(s.get('quote', ''))}</div>
<div class="author">{_escape(s.get('author', ''))}</div>
{_body_text(s)}
</div>
"""
        elif layout == "table":
            rows = s.get("rows") or []
            tr_html = "".join(
                "<tr>" + "".join(f"<td>{_escape(str(c))}</td>" for c in r) + "</tr>"
                for r in rows
            )
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<table class="tbl">{tr_html}</table>
"""
        elif layout == "cta":
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
{_body_text(s)}
<div><a class="cta-btn">{_escape(s.get('cta_text', 'Görüşelim'))}</a></div>
<div class="cta-sub">{_escape(s.get('cta_subtitle', ''))}</div>
"""
        else:
            body = f"""
{eyebrow}
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
{_body_text(s)}
"""

        footnote = ""
        if s.get("footnote"):
            footnote = f'<div class="footnote">{_escape(s["footnote"])}</div>'

        return f"""
<div class="slide {active}" data-layout="{layout}"{bg_style}>
{body}
{footnote}
</div>
"""


def _escape(s: str) -> str:
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _eyebrow(s: dict) -> str:
    eb = s.get("eyebrow")
    return f'<div class="eyebrow">{_escape(eb)}</div>' if eb else ""


def _subhead(s: dict) -> str:
    sub = s.get("subhead") or s.get("subtitle")
    return f'<div class="subhead">{_escape(sub)}</div>' if sub else ""


def _body_text(s: dict) -> str:
    b = s.get("body")
    return f'<div class="body-text">{_md_inline(b)}</div>' if b else ""


def _render_bullet(b) -> str:
    if isinstance(b, str):
        return f'<li><div class="b-title">{_md_inline(b)}</div></li>'
    title = b.get("title") or b.get("text") or ""
    desc = b.get("desc") or b.get("description") or ""
    inner = f'<div class="b-title">{_md_inline(title)}</div>'
    if desc:
        inner += f'<div class="b-desc">{_md_inline(desc)}</div>'
    return f'<li>{inner}</li>'


def _render_stat(st) -> str:
    if not isinstance(st, dict):
        return ""
    val = _escape(st.get("value", ""))
    label = _escape(st.get("label", ""))
    desc = _escape(st.get("desc", "") or st.get("description", ""))
    inner = f'<div class="v">{val}</div><div class="l">{label}</div>'
    if desc:
        inner += f'<div class="d">{desc}</div>'
    return f'<div class="stat-card">{inner}</div>'


def _md_inline(text: str) -> str:
    """Markdown-lite: **bold** + line breaks."""
    if not text:
        return ""
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text.replace("\n", "<br>")


def _md_block(text: str) -> str:
    """Markdown-lite block — supports h3 (**bold lines**) and bullet lists."""
    if not text:
        return ""
    out = []
    lines = text.split("\n")
    in_list = False
    for line in lines:
        line = line.rstrip()
        if not line:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if line.startswith("- "):
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f"<li>{_md_inline(line[2:])}</li>")
        elif line.startswith("**") and line.endswith("**"):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{_escape(line.strip('*'))}</h3>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{_md_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)
