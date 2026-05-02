"""Content Agent — Long-form Markdown + styled HTML preview.

Rewrite: artık sadece JSON döndürmüyor; gerçekten okunabilir, zengin
Markdown + render edilmiş güzel HTML üretip Files'a kaydediyor.
"""

import html
import re
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


# ── Tip bazlı detaylı promptlar ──────────────────────────────────────────────
TYPE_PROMPTS = {
    "blog": {
        "name": "Blog Yazısı",
        "target_words": "1500-2200",
        "instructions": """Uzun-form blog yazısı oluştur (en az 1500 kelime).

YAPI:
- # H1 başlık (SEO için keyword başta, dikkat çekici)
- *Yazıyı 1 cümlede özetleyen italic dek*
- ## Giriş (200-300 kelime, hook + okuyucunun acısına dokun)
- ## 4-6 ana bölüm (her biri ## H2, 250-350 kelime)
  - Her bölümde gerçek örnek/case study/sayısal veri olsun
  - 1-2 alt başlık (### H3)
  - Liste, tablo, alıntı (>) gibi zengin formatting kullan
- ## Pratik Adımlar — checklistler ile (- [ ] format)
- ## Sık Yapılan Hatalar — 3-5 madde + nasıl önlenir
- ## Sonuç — 3 ana takeaway + okuyucuya net CTA
- ---
- **SEO Meta:** title (60 karakter), description (155 karakter), 8 anahtar kelime

KURALLAR:
- "Sen", "siz" odaklı (B2B Türkçe ton)
- Kısa cümleler, ortalama 15-20 kelime
- Veri, istatistik, gerçek örnekler — uydurma yok ama mevcut bilgileri özgün şekilde sun
- Klişe yok ("dijital dönüşüm önemlidir" gibi cümleler yasak)
- Her bölüm başında okuyucu "neden bunu okumalıyım?" sorusunun cevabını alsın
""",
    },
    "email": {
        "name": "Email İçeriği",
        "target_words": "350-500",
        "instructions": """Soğuk outreach veya nurture email seti yaz.

YAPI:
- ## Subject Line Alternatifleri (5 adet, A/B test için farklı yaklaşımlar)
- ## Preview Text (50 karakter, subject'i destekleyen)
- ---
- ## Email Gövdesi
  - 1 cümlelik açılış (alıcının ismi + spesifik trigger)
  - 2-3 paragraflık gövde (problem → çözüm → kanıt)
  - **CTA butonu metni** + alternatif metin
  - PS notu (en yüksek tıklama oranı buradan gelir)
- ---
- ## 3 Aşamalı Sequence (Day 0 / Day 3 / Day 7 versiyonları)
- ---
- **Notlar:** Kişiselleştirme alanları {{first_name}}, {{company}} formatında

KURALLAR:
- Maksimum 150 kelime ana email gövdesi
- "Umarım iyisindir" yasak
- Her email tek bir CTA — birden fazla istek yok
- Sosyal kanıt (sayı, müşteri ismi) eklenmeli
""",
    },
    "social": {
        "name": "Sosyal Medya İçeriği",
        "target_words": "varies",
        "instructions": """Tek bir platform için 5 farklı paylaşım yaz.

YAPI (her paylaşım için):
- ### Paylaşım N: [Tipi — Eğitim/Engagement/Sosyal Kanıt/Behind/Promosyon]
- **Hook (ilk satır):** ...
- **Gövde:** (platform limitine göre — Instagram 2200, LinkedIn 3000, Twitter 280)
- **CTA:** ...
- **Hashtag seti:** 8-12 mix (büyük/orta/niche)
- **Görsel notu:** ne çekilmeli/tasarlanmalı

KURALLAR:
- Her paylaşım farklı içerik kovasından
- İlk satır scroll-stop — soru, sayı veya cesur iddia
- Emoji ölçülü (paylaşım başına max 3-4)
""",
    },
    "landing": {
        "name": "Landing Page Metni",
        "target_words": "600-900",
        "instructions": """Conversion odaklı tek sayfa landing copy yaz.

YAPI:
- ## Hero (üstten ekrana sığacak)
  - **H1:** ana değer önerisi (10 kelime altı)
  - **H2:** alt başlık — kim için + ne kazandırır
  - **CTA buton metni** + ikincil link
- ## Problem (3 paragraf — okuyucu kendini görmeli)
- ## Çözüm (1 paragraf + bullet liste)
- ## 3 Ana Özellik (her biri ### başlık + 2 cümle + fayda)
- ## Sosyal Kanıt (testimonial örneği + 3 metric)
- ## Nasıl Çalışır (3-4 adım numaralandırılmış)
- ## Fiyatlandırma (3 plan tablosu — Markdown table)
- ## SSS (5-7 soru/cevap)
- ## Final CTA (urgency + risk reversal)

KURALLAR:
- Her bölüm tek bir mesaja hizmet etmeli
- "Biz" yerine "siz/sen" — okuyucunun kazancı vurgulansın
- Risk reversal: para iade, 14 gün ücretsiz, vs.
""",
    },
    "newsletter": {
        "name": "Newsletter",
        "target_words": "700-1100",
        "instructions": """Haftalık newsletter — kişisel, sohbet havasında.

YAPI:
- # Başlık (merak uyandıran soru veya iddia)
- *İlk cümle — kişisel hook*
- 2-3 paragraflık ana hikaye/içgörü
- ---
- ## 🔥 Bu Hafta Öne Çıkanlar (3 link/kaynak — emoji + 1 cümle)
- ---
- ## 🛠 Bu Hafta Denedik (1 araç/teknik — kullanım + sonuç)
- ---
- ## 💡 Hızlı Düşünce
- 1 paragraflık tek bir fikir
- ---
- **PS:** kişisel not + soru (cevap için tetikleyici)

KURALLAR:
- 1. tekil şahıs — yazar arkadaş gibi konuşsun
- "Ben dün şunu fark ettim..." tarzı açılış
- Klişe başlangıç ("Merhaba arkadaşlar" gibi) yasak
""",
    },
    "case_study": {
        "name": "Başarı Hikayesi",
        "target_words": "900-1300",
        "instructions": """B2B case study — sayılarla desteklenmiş başarı hikayesi.

YAPI:
- # Başlık formatı: "[Şirket]: [X sonuç] [Y süre içinde]"
- ## Tek Satır Özet (TL;DR)
- ## Müşteri (sektör, büyüklük, pazar)
- ## Karşılaştıkları Zorluk (3 paragraf — spesifik, sayısal)
- ## Çözüm Yaklaşımı (### 3-4 adım)
- ## Uygulama (timeline + neler yapıldı)
- ## Sonuçlar (### kalın metric tablosu)
  | Metrik | Önce | Sonra | Değişim |
  |--------|------|-------|---------|
- ## Müşteri Yorumu (gerçek isim + pozisyon + 2-3 cümle alıntı)
- ## Anahtar Öğrenmeler (3-5 madde)
- ## Sonraki Adım — okuyucu için CTA

KURALLAR:
- Sayılar uydurulmasın — örnekleyici şablon olarak işaretle
- Her başlık altında "neden önemli" cümlesi
""",
    },
    "product_desc": {
        "name": "Ürün/Hizmet Açıklaması",
        "target_words": "300-500",
        "instructions": """Ürün/hizmet sayfası açıklaması.

YAPI:
- # Ürün adı + 1 cümle pitch
- **Kim için:** hedef kullanıcı
- **Ne sağlar:** ana değer (3 madde)
- ## Özellikler (her biri ###)
- ## Faydalar (özelliklerin kullanıcı kazanımına çevirisi)
- ## Kullanım Senaryoları (3 farklı persona)
- ## Fiyat / Kapsam
- ## CTA

KURALLAR:
- Özellik-Fayda çevirisi şart: "X yapar" değil "X yaparak Y kazanırsınız"
""",
    },
    "seo": {
        "name": "SEO Pillar Page",
        "target_words": "2000-3000",
        "instructions": """SEO odaklı pillar/cluster içeriği.

YAPI:
- # H1 — primary keyword + modifier (örn. "2026")
- *Meta description: 155 karakter*
- ## Giriş (300 kelime) — primary keyword ilk 100 kelimede
- ## 6-8 ana bölüm (her biri ## H2)
  - H2'ler secondary keywords içersin
  - Her bölümde ### H3 alt başlıklar
  - FAQ-style soru-cevap yapısı (Google "People Also Ask" için)
  - Internal/external link önerileri [INTERNAL LINK: anchor text]
  - Schema markup önerisi (FAQPage, HowTo)
- ## Sonuç + CTA
- ---
- **SEO Brief:**
  - Primary keyword + arama hacmi tahmini
  - 8-12 secondary keyword
  - LSI keywords listesi
  - Önerilen meta title (60c) + meta description (155c)
  - Schema markup tipi
""",
    },
    "calendar": {
        "name": "İçerik Takvimi",
        "target_words": "varies",
        "instructions": """30 günlük detaylı içerik takvimi (Markdown tablosu).

YAPI:
- # 30 Günlük İçerik Takvimi — [İşletme]
- ## Strateji Özeti (3 paragraf — neden bu yaklaşım, hedef metrikler, ana temalar)
- ## İçerik Dağılımı (% — eğitim/engagement/sosyal kanıt/eğlence/promosyon)
- ## Detaylı Takvim — Markdown tablosu

  | Gün | Tarih | Platform | Tip | Hook | Açıklama | CTA | Görsel | Saat |
  |-----|-------|----------|-----|------|----------|-----|--------|------|
  | 1   | ...   | ...      | ... | ...  | ...      | ... | ...    | ...  |

  (30 satır — haftada 5 gün, 4 hafta + 2 bonus)
- ## Hashtag Bankaları (kategori bazlı)
- ## Yeniden Kullanım Önerileri (1 içerik → 5 farklı format)

KURALLAR:
- Her gün için spesifik konu — generic "engagement post" yasak
- Haftalar arası çeşitlilik
""",
    },
}


class ContentAgent(BaseAgent):
    agent_id = "content"
    name = "Content"
    role = "Writes blog posts, social media content, email copy, and marketing text"
    category = "creative"

    CONTENT_TYPES = {k: {"name": v["name"], "word_count": v["target_words"]}
                     for k, v in TYPE_PROMPTS.items()}

    def run(self, content_type: str = "blog", topic: str = "",
            tone: str = "profesyonel", language: str = "tr",
            platform: str = "", count: int = 1) -> dict:
        self.log("Content agent başladı")
        config = self.load_config()

        business_name = config.get("agency_name") or config.get("name") or "My Agency"
        niche = config.get("niche") or (config.get("target_industries") or ["dijital pazarlama"])[0]

        if content_type not in TYPE_PROMPTS:
            content_type = "blog"
        spec = TYPE_PROMPTS[content_type]

        if not topic:
            topic = f"{niche} için 2026 trendleri ve uygulanabilir taktikler"

        self.log(f"Tip: {spec['name']} | Konu: {topic} | İşletme: {business_name}")

        # Generate
        markdown = self._generate(content_type, spec, business_name, niche, topic,
                                  tone, language, platform, count)

        # Save artifacts (md + html preview)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r'[^a-z0-9]+', '_', topic.lower())[:40].strip('_') or content_type
        md_path, html_path = self._save_artifacts(markdown, content_type, slug, timestamp,
                                                  business_name, topic)

        # Persist JSON for downstream
        content_data = {
            "content_type": content_type,
            "content_name": spec["name"],
            "topic": topic,
            "tone": tone,
            "language": language,
            "platform": platform,
            "business_name": business_name,
            "markdown": markdown,
            "md_path": str(md_path),
            "html_path": str(html_path),
            "created_at": timestamp,
        }
        self.save_data(f"content/{timestamp}_{content_type}.json", content_data)

        word_count = len(markdown.split())
        results = {
            "status": "ok",
            "summary": f"{spec['name']} hazır — '{topic}' ({word_count} kelime, HTML preview dahil)",
            "metrics": {
                "content_type": content_type,
                "topic": topic,
                "word_count": word_count,
                "platform": platform,
                "md_path": str(md_path),
                "html_path": str(html_path),
                "timestamp": datetime.now().isoformat(),
            },
            "artifacts": {
                "markdown": str(md_path),
                "html": str(html_path),
            },
            "content_data": content_data,
            "recommendations": [
                "HTML preview'i Files sekmesinden açıp gözden geçir",
                "SEO için anahtar kelimeleri başlıklarda kontrol et",
                "Görsel ekle — Designer agent ile cover üretebilirsin",
                "CTA linklerini gerçek URL'lerle değiştir",
                "Yayından önce 1 kez yüksek sesle oku",
            ],
        }
        self.save_output("content_report.json", results)
        self.log(f"Content tamamlandı: {word_count} kelime, .md ve .html üretildi")
        return results

    # ── İçerik üretimi ──────────────────────────────────────────────────────
    def _generate(self, content_type, spec, business_name, niche, topic, tone, language, platform, count):
        lang = "Türkçe" if language == "tr" else "English"

        platform_line = f"Platform: {platform}\n" if platform else ""
        count_line = f"Adet: {count}\n" if count and count > 1 else ""

        prompt = f"""Sen üst düzey içerik yazarı + SEO uzmanısın. Türkçe iş dünyası için yazı üretiyorsun.

İŞLETME: {business_name}
SEKTÖR: {niche}
KONU: {topic}
İÇERİK TİPİ: {spec['name']}
TON: {tone}
HEDEF KELIME: {spec['target_words']}
{platform_line}{count_line}

{spec['instructions']}

EVRENSEL KURALLAR:
- Saf Markdown çıktısı ver — başına/sonuna açıklama EKLEME, ``` blokları ekleme
- {lang} yaz
- Hedef kelime sayısına ulaş — kısa kalma
- Özgün, somut, uygulanabilir — generic blog dolgusu yasak
- Tablolar Markdown tablo formatında, listeler "-" ile, kod blokları ``` ile
- Sadece ve sadece istenen içeriği üret"""

        result = self.call_claude(prompt, timeout=240)
        if result and len(result.split()) > 200:
            return result.strip()

        self.log("Claude CLI yetersiz çıktı verdi — fallback şablona düşülüyor")
        return self._fallback(content_type, spec, business_name, niche, topic)

    # ── Artifact yazımı ─────────────────────────────────────────────────────
    def _save_artifacts(self, markdown, content_type, slug, timestamp, business_name, topic):
        # Markdown
        md_dir = OUTPUT_DIR / "content"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / f"{timestamp}_{slug}.md"
        md_path.write_text(markdown, encoding="utf-8")
        self.log(f"Markdown: {md_path}")

        # HTML preview
        html_doc = self._render_html(markdown, business_name, topic, content_type)
        html_path = md_dir / f"{timestamp}_{slug}.html"
        html_path.write_text(html_doc, encoding="utf-8")
        self.log(f"HTML preview: {html_path}")
        return md_path, html_path

    # ── Markdown → HTML render (lightweight, dependency-free) ───────────────
    def _render_html(self, md_text: str, business_name: str, topic: str, content_type: str) -> str:
        body = _md_to_html(md_text)
        kind_label = TYPE_PROMPTS.get(content_type, {}).get("name", content_type)
        title = html.escape(topic)
        biz = html.escape(business_name)
        date_str = datetime.now().strftime("%d %B %Y")

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — {biz}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Lora:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #f8f7f4;
  --paper: #ffffff;
  --ink: #16161a;
  --muted: #6b7280;
  --accent: #e85d26;
  --rule: #e5e7eb;
  --code-bg: #0f172a;
  --code-fg: #e2e8f0;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: 'Lora', Georgia, serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.7;
  font-size: 18px;
}}
.wrap {{ max-width: 760px; margin: 0 auto; padding: 64px 32px 96px; }}
.kicker {{
  display: inline-block;
  font-family: 'Inter', sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  padding: 6px 12px;
  border: 1px solid var(--accent);
  border-radius: 999px;
  margin-bottom: 24px;
}}
.byline {{
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  color: var(--muted);
  margin: 32px 0 56px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--rule);
}}
article h1 {{
  font-family: 'Inter', sans-serif;
  font-size: 44px;
  font-weight: 800;
  line-height: 1.15;
  margin: 0 0 16px;
  letter-spacing: -0.02em;
}}
article h2 {{
  font-family: 'Inter', sans-serif;
  font-size: 28px;
  font-weight: 700;
  margin: 56px 0 16px;
  letter-spacing: -0.01em;
}}
article h3 {{
  font-family: 'Inter', sans-serif;
  font-size: 21px;
  font-weight: 600;
  margin: 32px 0 12px;
}}
article h4 {{ font-family: 'Inter', sans-serif; font-size: 17px; font-weight: 600; margin: 24px 0 8px; }}
article p {{ margin: 0 0 18px; }}
article a {{ color: var(--accent); text-decoration: none; border-bottom: 1px solid currentColor; }}
article ul, article ol {{ padding-left: 24px; margin: 0 0 18px; }}
article li {{ margin: 6px 0; }}
article blockquote {{
  border-left: 4px solid var(--accent);
  padding: 8px 20px;
  margin: 24px 0;
  background: rgba(232,93,38,0.05);
  font-style: italic;
  color: #444;
}}
article code {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.88em;
  background: #f1f1ee;
  padding: 2px 6px;
  border-radius: 4px;
}}
article pre {{
  background: var(--code-bg);
  color: var(--code-fg);
  padding: 18px 22px;
  border-radius: 10px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  line-height: 1.55;
}}
article pre code {{ background: transparent; padding: 0; color: inherit; }}
article table {{
  width: 100%;
  border-collapse: collapse;
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  margin: 24px 0;
}}
article th, article td {{
  text-align: left;
  padding: 12px 14px;
  border-bottom: 1px solid var(--rule);
}}
article th {{ background: #faf9f6; font-weight: 600; }}
article hr {{
  border: 0;
  border-top: 1px solid var(--rule);
  margin: 48px 0;
}}
article em {{ color: #555; }}
article strong {{ color: var(--ink); }}
.footer {{
  margin-top: 80px;
  padding-top: 32px;
  border-top: 1px solid var(--rule);
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  color: var(--muted);
  display: flex;
  justify-content: space-between;
}}
@media (max-width: 640px) {{
  .wrap {{ padding: 40px 20px 60px; }}
  article h1 {{ font-size: 32px; }}
  article h2 {{ font-size: 22px; }}
  body {{ font-size: 17px; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <span class="kicker">{html.escape(kind_label)}</span>
  <article>{body}</article>
  <div class="byline" style="margin-top:48px;border:0;padding:0">
    <strong>{biz}</strong> · {date_str}
  </div>
  <div class="footer">
    <span>goat content engine</span>
    <span>{html.escape(content_type)}</span>
  </div>
</div>
</body>
</html>"""

    # ── Fallback şablonu ────────────────────────────────────────────────────
    def _fallback(self, content_type, spec, business_name, niche, topic):
        return f"""# {topic}

*{spec['name']} — {business_name} ({niche})*

> Not: Claude CLI bu sefer yetersiz çıktı verdi, bu fallback şablon Files'a yazıldı. Tekrar çalıştırmak için agent'ı yeniden tetikle.

## Giriş

{niche} sektöründe başarı, doğru stratejiyi tutarlılıkla uygulamaktan geçer. Bu yazı `{topic}` konusunu {business_name} perspektifinden uygulanabilir adımlarla ele alıyor.

## Neden Şimdi Önemli

Pazar dinamikleri her ay değişiyor. Geçen yıl işe yarayan taktik bu yıl ortalama performans gösterebilir. Bu yüzden:

- Veri-odaklı kararlar şart
- Hızlı iterasyon rakipleri geride bırakır
- Müşteri davranışı her zamankinden hızlı değişiyor

## Pratik Adımlar

1. Mevcut durumu ölç (baseline metrikler)
2. Hipotez oluştur (neyi neden değiştireceksin)
3. Küçük testlerle doğrula
4. Kazananı ölçeklendir

## Sık Yapılan Hatalar

- **Test etmeden ölçeklemek** — küçük örneklemde iyi sonuç büyükte garanti değil
- **Tek metriğe takılmak** — vanity metric yerine business metric
- **Çok değişkeni aynı anda değiştirmek** — neyin işe yaradığını anlayamazsın

## Sonuç

`{topic}` üzerinde çalışırken üç şeyi unutma: ölç, dene, iterasyon. {business_name} olarak bu süreçte yanındayız.

---

**SEO Meta:**
- Title: {topic} — {business_name}
- Description: {niche} için {topic} hakkında uygulanabilir rehber.
- Anahtar Kelimeler: {niche}, {topic}, strateji, taktik, 2026
"""


# ── Mini Markdown → HTML dönüştürücü (bağımsız) ─────────────────────────────
def _md_to_html(md: str) -> str:
    """Bağımlılıksız basit Markdown→HTML. Tablo, kod bloku, başlık,
    kalın/italik, link, liste, blockquote, hr, satır içi kod destekler."""
    lines = md.split("\n")
    out = []
    i = 0
    in_code = False
    code_buf = []

    def flush_para(buf):
        if not buf:
            return ""
        text = "\n".join(buf).strip()
        if not text:
            return ""
        return f"<p>{_inline(text)}</p>"

    para_buf = []

    def close_para():
        nonlocal para_buf
        if para_buf:
            out.append(flush_para(para_buf))
            para_buf = []

    while i < len(lines):
        line = lines[i]

        # Code fence
        if line.startswith("```"):
            close_para()
            if not in_code:
                in_code = True
                code_buf = []
            else:
                code_html = html.escape("\n".join(code_buf))
                out.append(f"<pre><code>{code_html}</code></pre>")
                in_code = False
                code_buf = []
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Heading
        m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m:
            close_para()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # HR
        if re.match(r'^---+$', stripped) or re.match(r'^\*\*\*+$', stripped):
            close_para()
            out.append("<hr>")
            i += 1
            continue

        # Table
        if "|" in line and i + 1 < len(lines) and re.match(r'^\s*\|?\s*[-:]+\s*\|', lines[i + 1]):
            close_para()
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2  # skip separator
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row_cells)
                i += 1
            tbl = "<table><thead><tr>"
            tbl += "".join(f"<th>{_inline(c)}</th>" for c in header_cells)
            tbl += "</tr></thead><tbody>"
            for r in rows:
                tbl += "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
            tbl += "</tbody></table>"
            out.append(tbl)
            continue

        # Blockquote
        if stripped.startswith(">"):
            close_para()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote_lines))}</blockquote>")
            continue

        # Unordered list
        if re.match(r'^\s*[-*+]\s+', line):
            close_para()
            items = []
            while i < len(lines) and re.match(r'^\s*[-*+]\s+', lines[i]):
                items.append(re.sub(r'^\s*[-*+]\s+', '', lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ul>")
            continue

        # Ordered list
        if re.match(r'^\s*\d+\.\s+', line):
            close_para()
            items = []
            while i < len(lines) and re.match(r'^\s*\d+\.\s+', lines[i]):
                items.append(re.sub(r'^\s*\d+\.\s+', '', lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ol>")
            continue

        # Blank → close paragraph
        if not stripped:
            close_para()
            i += 1
            continue

        para_buf.append(line)
        i += 1

    close_para()
    return "\n".join(o for o in out if o)


def _inline(text: str) -> str:
    """Inline Markdown: **bold**, *italic*, `code`, [link](url)."""
    # Escape first, then apply patterns on escaped text
    s = html.escape(text)
    # Code spans (do before others so we don't process inside)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    # Bold
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', s)
    # Italic
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'<em>\1</em>', s)
    # Links [text](url)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s
