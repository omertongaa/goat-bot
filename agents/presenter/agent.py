"""Presenter Agent — gerçek, modern HTML pitch deck üretir.

JSON rapor değil, **kullanılabilir HTML sunum** çıkarır:
- Her slayt için zengin yapı (Claude CLI ile JSON dönüşü)
- Modern dark/gradient tasarım, slayt başına farklı layout
- Klavye + sol/sağ butonlarıyla navigasyon, fullscreen
- Otomatik PDF export butonu (browser print)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, OUTPUT_DIR


SLIDE_PROMPT = """Sen üst düzey sunum tasarımcısı + iş geliştirme uzmanısın.

İŞLETME: {business_name}
SEKTÖR: {niche}
SUNUM TÜRÜ: {template_name}
KONU: {topic}
HEDEF KİTLE: {audience}
HEDEF SLAYT SAYISI: {slide_count}

10-12 slaytlık DETAYLI ve PROFESYONEL bir sunum içeriği üret. Her slayt
gerçek satılabilir/sunulabilir nitelikte olmalı — boilerplate "Bullet 1, 2, 3"
DEĞİL, sektöre özel, somut sayılar ve gerçek değer önerileri içermeli.

ÇIKTI: SADECE geçerli JSON array döndür. Açıklama YOK.

Her slayt şu yapıda:
{{
  "layout": "title|hero|two-column|stats|quote|bullets|cta|table|process",
  "headline": "Ana başlık (büyük puntoyla görünecek)",
  "subhead": "Alt başlık veya tek cümle açıklama (opsiyonel)",
  "body": "1-3 paragraflık zengin metin (layout=bullets değilse)",
  "bullets": ["madde 1", "madde 2", ...],   // layout=bullets veya two-column için
  "left": "iki kolonlu layout için sol içerik",
  "right": "iki kolonlu layout için sağ içerik",
  "stats": [{{"value":"%73","label":"oran"}}, ...],   // layout=stats için
  "quote": "Alıntı metni",                  // layout=quote için
  "author": "Alıntı yazarı",
  "process_steps": [{{"title":"Adım","desc":"..."}}], // layout=process için
  "rows": [["başlık","değer"], ...],        // layout=table için
  "cta_text": "Buton metni",                // layout=cta için
  "cta_subtitle": "CTA altı not",
  "speaker_notes": "Konuşmacı için 2-3 cümle ek bağlam"
}}

KURALLAR:
1. İlk slayt **layout: "hero"** olmalı — büyük başlık + alt başlık + kısa açıklama
2. Slayt 2: problem (bullets veya body)
3. Slayt 3-4: çözüm / yaklaşım
4. Slayt 5-6: somut faydalar (stats veya bullets)
5. Slayt 7-8: süreç (process)
6. Slayt 9: sosyal kanıt / case study (quote)
7. Slayt 10: yatırım / fiyatlandırma (table)
8. Son slayt: **layout: "cta"** + somut bir sonraki adım
9. Her slayt **Türkçe**, **somut sayılarla**, sektöre özel
10. Boilerplate'ten KAÇIN: "Profesyonel ekip, kaliteli hizmet" gibi geneleller YOK

Sadece JSON array döndür."""


class PresenterAgent(BaseAgent):
    agent_id = "presenter"
    name = "Presenter"
    role = "Profesyonel HTML sunumlar — pitch deck, teklif, rapor"
    category = "creative"

    TEMPLATES = {
        "pitch_deck":  {"name": "Pitch Deck", "slides": 11, "purpose": "Yatırımcı veya müşteri sunumu"},
        "proposal":    {"name": "Teklif Sunumu", "slides": 9, "purpose": "Hizmet teklifi + fiyatlandırma"},
        "report":      {"name": "Rapor Sunumu", "slides": 12, "purpose": "Performans / analiz raporu"},
        "training":    {"name": "Eğitim Sunumu", "slides": 12, "purpose": "Workshop / eğitim modülü"},
        "company":     {"name": "Şirket Tanıtımı", "slides": 10, "purpose": "Firma overview"},
        "case_study":  {"name": "Başarı Hikayesi", "slides": 9, "purpose": "Müşteri case study"},
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

        # Claude'a zengin slide JSON dönüş prompt'u
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

        # Generate hero/key slide images via fal.ai (gerçek aksiyon)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9_-]", "_", topic.lower().replace(" ", "_"))[:30]

        if make_images:
            slides = self._inject_slide_images(slides, topic, business_name, niche, max_images, timestamp, slug)

        # Render the actual HTML deck — gerçek iş çıktısı
        self.log(f"{len(slides)} slayt için HTML render ediliyor...")
        out_dir = OUTPUT_DIR / "presentations"
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{timestamp}_{slug or template}.html"
        html_path.write_text(self._render_html(slides, topic, business_name, niche, tmpl), encoding="utf-8")

        # Export PDF — Playwright headless Chromium
        pdf_path = None
        if make_pdf:
            pdf_path = self._export_pdf(html_path, out_dir, timestamp, slug or template)

        # Persist data + report
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

    # ── Hero / key slide images via fal.ai ────────────────────
    def _inject_slide_images(self, slides, topic, business, niche, max_images, timestamp, slug):
        """Hero/quote/cta layout slaytlara fal.ai ile görsel inject et.
        Maliyet kontrolü: en fazla `max_images` slayt için görsel üretilir."""
        try:
            from services.image import generate_image
        except ImportError:
            return slides

        priority_layouts = ("hero", "cta", "quote", "stats")
        # Score slides — priority layouts first, then in order
        candidates = sorted(
            range(len(slides)),
            key=lambda i: (
                slides[i].get("layout") not in priority_layouts,  # priority first (False < True)
                i,
            ),
        )[:max(1, min(int(max_images or 4), 8))]

        self.log(f"fal.ai ile {len(candidates)} slayt için hero görsel üretiliyor...")
        for idx in candidates:
            slide = slides[idx]
            layout = slide.get("layout", "")
            headline = slide.get("headline", "") or topic

            # Layout-aware image prompt
            mood_map = {
                "hero": f"Cinematic editorial photo, dramatic lighting, abstract {niche} concept, dark background, premium professional, no text, no logos",
                "cta": f"Inviting modern workspace photo, soft warm light, person ready to take action, blurred background, professional, no text",
                "quote": f"Atmospheric portrait photo, soft natural light, contemplative mood, professional headshot style, neutral background, no text",
                "stats": f"Modern data visualization aesthetic, abstract geometric shapes, gradient orange-to-red on dark background, no text, no numbers",
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
        """HTML deck'i PDF'e çevir (Playwright headless Chromium)."""
        try:
            from services.html_to_pdf import html_to_pdf
        except ImportError:
            self.log("html_to_pdf servisi yok — PDF atlandı")
            return None

        pdf_path = out_dir / f"{timestamp}_{slug}.pdf"
        # Slayt boyutu: 16:9 1920×1080
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
        """Claude yoksa boilerplate yerine kullanılabilir bir taslak."""
        return [
            {"layout": "hero", "headline": topic, "subhead": business,
             "body": f"{tmpl['name']} — {tmpl['purpose']}"},
            {"layout": "bullets", "headline": "Bugünkü Durum",
             "bullets": [f"{niche} sektöründe rekabet artıyor",
                         "Manuel süreçler büyümeyi engelliyor",
                         "Veri-odaklı kararlar lüks değil zorunluluk"]},
            {"layout": "two-column", "headline": "Yaklaşımımız",
             "left": "**Süreç**\n\n- Analiz\n- Strateji\n- Uygulama\n- Optimizasyon",
             "right": "**Araçlar**\n\n- AI destekli orkestrasyon\n- Tek panelden takip\n- Otomatik raporlama"},
            {"layout": "stats", "headline": "Sayılarla Etki",
             "stats": [
                 {"value": "%70", "label": "Operasyonel hız artışı"},
                 {"value": "3.5×", "label": "Lead konversiyon"},
                 {"value": "%40", "label": "Maliyet düşüşü"},
             ]},
            {"layout": "process", "headline": "Çalışma Şeklimiz",
             "process_steps": [
                 {"title": "1. Keşif", "desc": "İşin kalbini tanı"},
                 {"title": "2. Plan", "desc": "Ölçülebilir hedefler"},
                 {"title": "3. Uygula", "desc": "Hızlı iterasyon"},
                 {"title": "4. Ölç", "desc": "Veri ile karar"},
             ]},
            {"layout": "quote", "quote": "Sonuçlar 4 hafta içinde gelmeye başladı.",
             "author": "Bir müşterimiz"},
            {"layout": "table", "headline": "Paketler",
             "rows": [["Başlangıç", "₺X / ay"], ["Büyüme", "₺Y / ay"], ["Özel", "Görüşelim"]]},
            {"layout": "cta", "headline": "Sıradaki adım?",
             "subhead": "30 dakikalık keşif görüşmesi",
             "cta_text": "Görüşme Planla", "cta_subtitle": "Ücretsiz, taahhütsüz"},
        ]

    def _render_html(self, slides: list, topic: str, business: str, niche: str, tmpl: dict) -> str:
        slide_html_blocks = []
        total = len(slides)
        for i, s in enumerate(slides):
            slide_html_blocks.append(self._render_slide(s, i, total))

        slides_html = "\n".join(slide_html_blocks)
        title = f"{topic} — {business}"

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #09090b; --surface: #14141a; --surface-2: #1c1c24;
  --text: #f5f5f7; --text-2: #c3c3cc; --dim: #888;
  --accent: #f97316; --accent-2: #ef4444; --green: #22c55e;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; }}
body {{
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  overflow: hidden; -webkit-font-smoothing: antialiased;
}}

.deck {{ width: 100vw; height: 100vh; position: relative; overflow: hidden; }}

.slide {{
  position: absolute; inset: 0; padding: 80px 110px;
  display: none; flex-direction: column; justify-content: center;
  background: var(--bg);
}}
.slide.active {{ display: flex; }}

/* Per-slide gradient backgrounds */
.slide[data-layout="hero"] {{
  background: radial-gradient(ellipse at 30% 20%, rgba(249,115,22,0.15), transparent 50%),
              radial-gradient(ellipse at 80% 80%, rgba(239,68,68,0.10), transparent 50%),
              var(--bg);
  align-items: flex-start;
}}
.slide[data-layout="cta"] {{
  background: linear-gradient(135deg, rgba(249,115,22,0.18), rgba(239,68,68,0.12)),
              var(--bg);
  align-items: center; text-align: center;
}}
.slide[data-layout="quote"] {{
  background: linear-gradient(180deg, var(--bg), var(--surface));
  align-items: center; justify-content: center; text-align: center;
}}
.slide[data-layout="stats"], .slide[data-layout="process"] {{
  background: linear-gradient(180deg, var(--bg) 0%, var(--surface) 100%);
}}

/* Typography */
.slide h1 {{
  font-size: clamp(40px, 6vw, 96px); font-weight: 800;
  line-height: 1.05; letter-spacing: -0.03em;
  background: linear-gradient(135deg, var(--text) 0%, var(--accent) 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  margin-bottom: 24px;
}}
.slide h2 {{
  font-size: clamp(32px, 4.5vw, 64px); font-weight: 700;
  line-height: 1.1; letter-spacing: -0.02em;
  margin-bottom: 28px;
}}
.slide h2 .accent {{ color: var(--accent); }}
.slide .subhead {{
  font-size: clamp(20px, 2.2vw, 28px); font-weight: 500;
  color: var(--text-2); margin-bottom: 20px;
}}
.slide .body {{
  font-size: clamp(16px, 1.6vw, 22px); line-height: 1.55;
  color: var(--text-2); max-width: 880px;
}}
.slide ul.bullets {{
  list-style: none; padding-left: 0;
  font-size: clamp(18px, 1.9vw, 26px); line-height: 1.55;
}}
.slide ul.bullets li {{
  padding: 14px 0 14px 36px; position: relative;
  color: var(--text-2);
  border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.slide ul.bullets li:last-child {{ border-bottom: none; }}
.slide ul.bullets li::before {{
  content: '→'; position: absolute; left: 0; top: 14px;
  color: var(--accent); font-weight: 800;
}}
.slide ul.bullets li strong {{ color: var(--text); font-weight: 700; }}

.slide .two-col {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 64px;
}}
.slide .two-col > div {{
  font-size: clamp(16px, 1.5vw, 20px); color: var(--text-2);
  line-height: 1.6;
}}
.slide .two-col h3 {{ font-size: 1.4em; color: var(--accent); margin-bottom: 16px; font-weight: 700; }}

.slide .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 32px; margin-top: 24px; }}
.slide .stat-card {{
  background: var(--surface-2); padding: 36px 28px; border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
}}
.slide .stat-card .v {{
  font-size: clamp(48px, 6vw, 88px); font-weight: 900;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  -webkit-background-clip: text; background-clip: text; color: transparent;
  line-height: 1; letter-spacing: -0.04em;
}}
.slide .stat-card .l {{
  font-size: 14px; color: var(--dim); margin-top: 12px;
  text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500;
}}

.slide .process {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }}
.slide .process .step {{
  background: var(--surface); padding: 28px 24px; border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.06); border-left: 3px solid var(--accent);
}}
.slide .process .step .num {{
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--accent); letter-spacing: 0.08em;
}}
.slide .process .step h4 {{
  font-size: 22px; margin: 6px 0 10px; font-weight: 700;
}}
.slide .process .step p {{ color: var(--text-2); font-size: 15px; line-height: 1.5; }}

.slide .quote {{
  font-size: clamp(28px, 3.8vw, 56px); font-weight: 600; line-height: 1.25;
  letter-spacing: -0.01em; max-width: 900px;
  font-style: italic;
}}
.slide .quote::before {{ content: '"'; color: var(--accent); font-size: 1.3em; vertical-align: -0.1em; }}
.slide .author {{ font-size: 18px; color: var(--dim); margin-top: 32px; }}

.slide table.tbl {{
  width: 100%; max-width: 800px; border-collapse: collapse; font-size: 18px;
}}
.slide table.tbl tr {{ border-bottom: 1px solid rgba(255,255,255,0.08); }}
.slide table.tbl td {{
  padding: 18px 12px; color: var(--text-2);
}}
.slide table.tbl td:first-child {{ font-weight: 600; color: var(--text); }}
.slide table.tbl td:last-child {{ text-align: right; font-family: 'JetBrains Mono', monospace; color: var(--accent); font-weight: 700; }}

.slide .cta-btn {{
  display: inline-block; margin-top: 28px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #fff; padding: 18px 48px; border-radius: 12px;
  font-size: 22px; font-weight: 700; letter-spacing: -0.01em;
  text-decoration: none;
  box-shadow: 0 16px 48px rgba(249,115,22,0.4);
}}
.slide .cta-sub {{ font-size: 14px; color: var(--dim); margin-top: 12px; }}

/* Slide footer */
.slide-num {{
  position: absolute; bottom: 28px; right: 32px;
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: var(--dim); opacity: 0.5;
}}
.slide-brand {{
  position: absolute; bottom: 28px; left: 32px;
  font-size: 12px; color: var(--dim); opacity: 0.5;
  letter-spacing: 0.04em;
}}

/* Nav */
.nav {{
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  display: flex; gap: 8px; z-index: 100;
}}
.nav button {{
  background: var(--surface); border: 1px solid rgba(255,255,255,0.08);
  color: var(--text); padding: 10px 16px; border-radius: 8px;
  font-family: inherit; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}}
.nav button:hover {{ background: var(--surface-2); border-color: var(--accent); }}

.progress {{
  position: fixed; top: 0; left: 0; height: 3px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  z-index: 200; transition: width 0.3s;
}}

@media print {{
  .nav, .progress {{ display: none; }}
  body, html {{ overflow: visible; height: auto; }}
  .deck {{ width: 100%; height: auto; overflow: visible; position: static; }}
  .slide {{
    display: flex !important;
    position: relative !important;
    inset: auto !important;
    width: 100%;
    height: 100vh;
    page-break-after: always;
    page-break-inside: avoid;
    break-after: page;
  }}
  .slide:last-child {{ page-break-after: auto; break-after: auto; }}
}}
</style>
</head>
<body>

<div class="progress" id="progress"></div>

<div class="deck">
{slides_html}
</div>

<div class="nav">
  <button onclick="prev()">←</button>
  <button onclick="next()">→</button>
  <button onclick="document.documentElement.requestFullscreen()">⛶ Tam ekran</button>
  <button onclick="window.print()">🖨 PDF</button>
</div>

<script>
let cur = 0;
const slides = document.querySelectorAll('.slide');
const total = slides.length;
const progress = document.getElementById('progress');

function show(n) {{
  cur = Math.max(0, Math.min(n, total - 1));
  slides.forEach((s, i) => s.classList.toggle('active', i === cur));
  progress.style.width = ((cur + 1) / total * 100) + '%';
}}
function next() {{ show(cur + 1); }}
function prev() {{ show(cur - 1); }}

document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') next();
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') prev();
  if (e.key === 'f') document.documentElement.requestFullscreen();
}});

show(0);
</script>
</body>
</html>"""

    def _render_slide(self, s: dict, idx: int, total: int) -> str:
        layout = (s.get("layout") or "bullets").lower()
        active = "active" if idx == 0 else ""

        # Slayt arka planı — fal.ai görseli varsa overlay ile kullan
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

        body = ""
        if layout == "hero":
            body = f"""
<h1>{_escape(s.get('headline', ''))}</h1>
{_subhead(s)}
{_body_text(s)}
"""
        elif layout == "bullets":
            bullets = s.get("bullets") or []
            blist = "".join(f"<li>{_md_inline(b)}</li>" for b in bullets)
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<ul class="bullets">{blist}</ul>
"""
        elif layout == "two-column":
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<div class="two-col">
<div>{_md_block(s.get('left', ''))}</div>
<div>{_md_block(s.get('right', ''))}</div>
</div>
"""
        elif layout == "stats":
            stats = s.get("stats") or []
            cards = "".join(
                f'<div class="stat-card"><div class="v">{_escape(st.get("value",""))}</div>'
                f'<div class="l">{_escape(st.get("label",""))}</div></div>'
                for st in stats
            )
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<div class="stats">{cards}</div>
"""
        elif layout == "process":
            steps = s.get("process_steps") or []
            items = "".join(
                f'<div class="step"><div class="num">ADIM {n+1}</div>'
                f'<h4>{_escape(st.get("title",""))}</h4>'
                f'<p>{_escape(st.get("desc",""))}</p></div>'
                for n, st in enumerate(steps)
            )
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<div class="process">{items}</div>
"""
        elif layout == "quote":
            body = f"""
<div class="quote">{_escape(s.get('quote', ''))}</div>
<div class="author">— {_escape(s.get('author', ''))}</div>
"""
        elif layout == "table":
            rows = s.get("rows") or []
            tr_html = "".join(
                "<tr>" + "".join(f"<td>{_escape(str(c))}</td>" for c in r) + "</tr>"
                for r in rows
            )
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
<table class="tbl">{tr_html}</table>
"""
        elif layout == "cta":
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
{_body_text(s)}
<a class="cta-btn">{_escape(s.get('cta_text', 'Görüşelim'))}</a>
<div class="cta-sub">{_escape(s.get('cta_subtitle', ''))}</div>
"""
        else:
            body = f"""
<h2>{_escape(s.get('headline', ''))}</h2>
{_subhead(s)}
{_body_text(s)}
"""

        return f"""
<div class="slide {active}" data-layout="{layout}"{bg_style}>
{body}
<div class="slide-num">{idx+1} / {total}</div>
</div>
"""


def _escape(s: str) -> str:
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _subhead(s: dict) -> str:
    sub = s.get("subhead") or s.get("subtitle")
    return f'<div class="subhead">{_escape(sub)}</div>' if sub else ""


def _body_text(s: dict) -> str:
    b = s.get("body")
    return f'<div class="body">{_md_inline(b)}</div>' if b else ""


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
                out.append('<ul class="bullets">')
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
