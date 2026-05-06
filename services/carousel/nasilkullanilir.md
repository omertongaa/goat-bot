# Carousel Generator — Nasıl Çalışır

## Genel Akış

```
JSON (içerik)
    ↓
generate.py — render fonksiyonları + şablon doldurma
    ↓
themes/<tema>/base.html — tüm slide'lar tek HTML'de birleşir
    ↓
export_slides.py — Playwright ile browser açar, her slide'ı PNG olarak yakalar
    ↓
slides/slide_1.png ... slide_N.png (1080×1350 px, 4:5)
```

Komut:
```bash
python generate.py content/konu.json
```

---

## Klasör Yapısı

```
carousel-template/
├── generate.py              ← Ana orchestrator: JSON okur, render eder, HTML üretir
├── export_slides.py         ← Playwright: HTML → PNG
├── brand.json               ← Marka konfigürasyonu (handle, tema, UI metinleri)
├── voice.md                 ← Marka sesi yönergeleri (Claude bunu okur)
├── setup.py                 ← Kurulum scripti
│
├── content/                 ← JSON içerik dosyaları (her carousel = 1 dosya)
│   └── ornek.json
│
├── themes/                  ← Tasarım temaları
│   ├── terminal-dark/       ← Her tema: base.html + theme.json
│   ├── editorial-cream/
│   ├── vibrant-gradient/
│   ├── minimal-mono/
│   └── data-viz/
│
├── slide_types/             ← Slide şablonları (HTML iskelet)
│   ├── cover.html
│   ├── inner_text.html
│   ├── inner_list.html
│   ├── inner_comparison.html
│   ├── inner_stats.html
│   ├── inner_quote.html
│   └── cta.html
│
├── components/              ← Render yardımcıları
│   ├── icon_badge.py        ← SVG ikonu satır içine gömer
│   └── shape_decoration.py  ← Dekoratif SVG'leri konumlandırır
│
├── assets/
│   ├── icons/               ← 28 Lucide ikonu (MIT lisanslı)
│   └── shapes/              ← 6 dekoratif SVG
│
└── slides/                  ← Üretilen PNG çıktılar
```

---

## generate.py — Çalışma Mantığı

1. `brand.json` okur — marka konfigürasyonu (handle, lang, UI metinleri)
2. JSON içerik dosyasını okur (`defaults` + `slides` dizisi)
3. Her slide için `type` alanına göre renderer fonksiyonu çağırır
4. Renderer, ilgili `slide_types/*.html` şablonunu okur ve `{{placeholder}}`'ları doldurur
5. `themes/<tema>/base.html` içindeki `{{slides}}`'a tüm HTML enjekte edilir
6. `{slug}_carousel.html` olarak kaydedilir
7. `export_slides.py` subprocess olarak çağrılır

Renderer tablosu:

| `type` değeri      | Şablon dosyası          |
|--------------------|-------------------------|
| `cover`            | `cover.html`            |
| `inner_text`       | `inner_text.html`       |
| `inner_list`       | `inner_list.html`       |
| `inner_comparison` | `inner_comparison.html` |
| `inner_stats`      | `inner_stats.html`      |
| `inner_quote`      | `inner_quote.html`      |
| `cta`              | `cta.html`              |

---

## brand.json — Yapısı

```json
{
  "handle": "@markahandle",
  "lang": "tr",
  "default_theme": "terminal-dark",
  "ui": {
    "swipe_text": "Kaydır",
    "swipe_arrow": "›",
    "cta_default_button": "Takip et",
    "cta_icon": "📌"
  },
  "voice_file": "voice.md"
}
```

- `handle`: Cover ve CTA slide'larında gösterilir. Her JSON'da `"defaults.handle"` yazılırsa o değer öncelikli; yazılmazsa brand.json'daki kullanılır.
- `default_theme`: JSON'da `"defaults.theme"` yoksa bu tema kullanılır.
- `ui.*`: Hardcoded olmayan UI metinleri — dil veya markaya göre değiştirin.

---

## export_slides.py — Çalışma Mantığı

```
Viewport: 1680×3200 px  (tüm slide'ların ekrana sığması için yeterince yüksek)
Scale factor: 1080/420 = 2.5714  (CSS px → output px dönüşümü)

Her .slide elementi için:
  1. bounding_box() ile X/Y pozisyonunu al
  2. page.screenshot(clip={x, y, width:420, height:525}) ile kırp
  3. Çıktı: 1080×1350 px PNG
```

Neden `page.screenshot` + clip, `element.screenshot()` değil?
`element.screenshot()` elemanın gerçek yüksekliğini kullanır — içerik kısa olunca slide'lar farklı boyutlarda çıkar. Clip ile her zaman sabit 1080×1350 garantilenir.

---

## Slide Boyutları

| CSS px  | Output px | Oran |
|---------|-----------|------|
| 420×525 | 1080×1350 | 4:5 dikey (Instagram standardı) |

Değiştirmeyin.

---

## 5 Tema — Özet

| Tema | Arka plan | Accent | Font | En iyi için |
|------|-----------|--------|------|-------------|
| `terminal-dark` | #0D1117 koyu | #F97316 turuncu | Oswald + JetBrains Mono | Dev, kod, teknik |
| `editorial-cream` | #F5F0E8 krem | #C44B1B rust | Oswald + Inter | Eğitim, rehber, tutorial |
| `vibrant-gradient` | Gradient koyu | #A855F7 mor + #06B6D4 cyan | Space Grotesk | Viral, trend, karşılaştırma |
| `minimal-mono` | #FAFAF7 beyaz | #16A34A yeşil | Fraunces serif | Quote, essay, fikir |
| `data-viz` | #0A0E1A koyu | #06B6D4 + #D946EF | Inter Tight + IBM Plex Mono | Rakam, istatistik, benchmark |

Her temanın mood_tags ve best_for/avoid_for detayları için `themes/<tema>/theme.json`'a bakın.

---

## Terminal Block

JSON'da her inner slide'a `"terminal"` nesnesi eklenebilir:

```json
"terminal": {
  "title": "terminal-basligi",
  "lines": [
    {"type": "prompt",  "text": "$ komut"},
    {"type": "output",  "text": "çıktı"},
    {"type": "success", "text": "✓ başarılı"},
    {"type": "error",   "text": "⚠ hata"},
    {"type": "warning", "text": "uyarı"},
    {"type": "comment", "text": "# yorum"},
    {"type": "cmd",     "text": "komut"}
  ]
}
```

Terminal yoksa slide'ın alt kısmında karanlık boşluk kalır. Terminal bloğu olan slide'lara ikon eklemeyin.

---

## Dekorasyon Sistemi

```json
"decoration": {
  "icons": ["zap", "cpu"],
  "shapes": ["dot-grid-corner"]
}
```

**28 ikon:** `zap` `code` `terminal` `cpu` `brain` `target` `rocket` `layers` `git-branch` `database` `sparkles` `trending-up` `check` `arrow-right` `lightbulb` `clock` `flame` `package` `shield` `key` `crown` `trending-down` `alert-triangle` `globe` `users` `download` `eye` `search`

**6 şekil:** `dot-grid-corner` `circle-glow` `diagonal-lines` `hexagon-cluster` `arrow-curved` `wave-bottom`

Limit: Slide başına maks 2 ikon + 1 şekil.

---

## JSON Şeması — Hızlı Referans

```json
{
  "defaults": {
    "handle": "@markahandle",
    "theme": "terminal-dark"
  },
  "slides": [
    {
      "type": "cover",
      "category": "Kategori",
      "eyebrow": "Kısa üst etiket",
      "title": "Başlık\nsatır kır",
      "subtitle": "Tek somut iddia.",
      "decoration": {"shapes": ["dot-grid-corner"]}
    },
    {
      "type": "inner_text",
      "label": "Sorun",
      "heading": "2-4 kelime\nbaşlık",
      "body": "Kısa cümle. <strong>Tek kelime</strong> kalın.\n\nParagraf kır.",
      "terminal": {"title": "...", "lines": [...]}
    },
    {
      "type": "inner_list",
      "label": "Adım 01",
      "heading": "Başlık",
      "items": [{"title": "Adım adı", "body": "Max 1 cümle."}],
      "terminal": {"title": "...", "lines": [...]}
    },
    {
      "type": "inner_comparison",
      "label": "Karşılaştırma",
      "heading": "Başlık",
      "left":  {"title": "Eskiden", "items": ["Madde 1"]},
      "right": {"title": "Yeni Yol", "items": ["Madde 1"]},
      "terminal": {"title": "...", "lines": [...]}
    },
    {
      "type": "inner_stats",
      "label": "Rakamlarla",
      "heading": "Başlık",
      "stats": [{"number": "10×", "label": "Açıklama"}],
      "body": "1-2 cümle bağlam.",
      "terminal": {"title": "...", "lines": [...]}
    },
    {
      "type": "inner_quote",
      "label": "Perspektif",
      "heading": "Başlık",
      "quote": "Alıntı metni.",
      "attr": "Kaynak",
      "body": "Kısa yorum."
    },
    {
      "type": "cta",
      "heading": "Başlık\nsatır kır",
      "body": "Tek aksiyon cümlesi.",
      "button_text": "\"KEYWORD\" Yaz",
      "decoration": {"shapes": ["circle-glow"]}
    }
  ]
}
```

### İçerik Limitleri

| Slide tipi         | Alan          | Limit                           |
|--------------------|---------------|---------------------------------|
| `cover`            | title         | Max 5 kelime/satır, max 2 satır |
| `cover`            | subtitle      | Max 2 satır                     |
| `inner_*`          | heading       | Max 4 kelime/satır, max 2 satır |
| `inner_text`       | body          | Max 5 kısa cümle                |
| `inner_list`       | items         | Max 4 item — 3 tercih edilir    |
| `inner_stats`      | stats         | Max 3 stat                      |
| `inner_comparison` | her yan       | Max 4 madde                     |
| terminal           | lines         | Max 4 satır                     |

---

## Bilinen Davranışlar

- **`height: 100%` override riski:** `.slide-inner`'a yeni `height` ekleme — `.slide { height: 525px }` geçerli, ikinci rule onu ezer.
- **`margin-top: auto` tek olmalı:** `.terminal-block`'a ikinci `margin-top` ekleme — son değer kazanır, `auto` iptal olur.
- **Yeni terminal tipi:** `base.html`'de ilgili `.terminal-line.{type}` CSS kuralı da eklenmeli.
- **Comparison grid `flex:1` yok:** Ekleme. Doğal yükseklikte durması tasarım kararı.
- **Google Fonts:** `base.html` CDN'den yükleniyor — internetsiz ortamda font fallback'e düşer.
