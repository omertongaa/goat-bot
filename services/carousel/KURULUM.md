# Carousel Template — Kurulum Rehberi

Bu kılavuz, carousel-template/ klasörünü aldıktan sonra kendi markanız için sıfırdan kurmanızı sağlar.

---

## Gereksinimler

- **Python 3.10 veya üzeri** — `python --version` ile kontrol edin
- **Claude Code** — [claude.ai/code](https://claude.ai/code) adresinden indirin
- **Terminal** — Windows: PowerShell veya Git Bash / Mac–Linux: bash veya zsh

---

## Kurulum (4 Adım)

### Adım 1 — Klasörü kopyalayın

Bu `carousel-template/` klasörünü istediğiniz bir yere taşıyın:

```
~/Desktop/markam-carousel/
```

Klasörün adını markanıza göre değiştirebilirsiniz.

### Adım 2 — Terminale girin

```bash
cd ~/Desktop/markam-carousel
```

### Adım 3 — Kurulum scriptini çalıştırın

```bash
python setup.py
```

Script sırayla şunları yapar:
1. `brand.json` yoksa interaktif olarak oluşturur (handle, dil, tema sorar)
2. `voice.md` yoksa şablondan kopyalar
3. `~/.claude/skills/<slug>-carousel/SKILL.md` dosyasını yazar
4. Test carousel üretir (slides/ klasörünü kontrol edin)

Script tamamlandığında ekranda hangi komutla başlayacağınızı gösterir.

### Adım 4 — Marka sesini tanımlayın

`voice.md` dosyasını açın ve markanızın sesini doldurun:

- Hedef kitle kim?
- Ton nasıl? (samimi / resmi / teknik / eğlenceli)
- Hook kalıpları
- CTA biçimi
- Kaçınılan kelimeler

Bu dosya doldurulmadan carousel üretimi başlamaz (skill okur, uygular).

---

## İlk Carousel

Claude Code'u açın ve yazın:

```
/<slug>-carousel "konu başlığı"
```

Örnek:
```
/markam-carousel "Sabah rutininin 3 sırrı"
```

Akış:
1. Slide planı sohbette görünür
2. "evet" diyince JSON yazılır → PNG'ler üretilir
3. `output/{konu-adi}/` klasöründe slide_01.png ... slide_N.png hazır

---

## Manuel Kullanım (skill olmadan)

```bash
python generate.py content/konu-adi.json
```

Önce `content/` klasöründe markanızın JSON dosyasını hazırlayın. Şema için `content/ornek.json`'a bakın.

---

## Branding Özelleştirme

### Marka bilgileri
`brand.json` dosyasını düzenleyin:

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
  }
}
```

### Tema değiştirme
`brand.json` içinde `"default_theme"` değerini değiştirin:

| Tema | En iyi için |
|------|-------------|
| `terminal-dark` | Teknik, kod, dev araçları |
| `editorial-cream` | Eğitim, rehber, tutorial |
| `vibrant-gradient` | Viral, trend, karşılaştırma |
| `minimal-mono` | Quote, essay, fikir |
| `data-viz` | İstatistik, araştırma, rakam |

### Renk paleti değiştirme
`themes/<tema>/base.html` dosyasını açın, `:root` bloğundaki CSS değişkenlerini düzenleyin:

```css
:root {
  --accent: #F97316;     /* ana vurgu rengi */
  --bg-primary: #0D1117; /* arka plan */
  --text-primary: #E6EDF3; /* ana metin */
}
```

### Font değiştirme
`themes/<tema>/base.html` dosyasının `<head>` bölümündeki Google Fonts URL'sini ve `--font-*` değişkenlerini güncelleyin.

### Dil değiştirme
`brand.json` içinde `"lang"` alanını değiştirin (örn. `"en"`). HTML `lang` attribute'u otomatik güncellenir.

### UI metinleri
`brand.json` içindeki `"ui"` bloğunda swipe_text, cta_default_button ve cta_icon alanlarını değiştirin.

---

## Yeni Tema Ekleme

```
themes/
└── yeni-tema/
    ├── theme.json   ← mevcut bir temadan kopyalayın, mood_tags ve best_for doldurun
    └── base.html    ← terminal-dark/base.html'i şablon olarak alın, CSS değiştirin
```

`generate.py content/konu.json` çalıştırırken JSON'da `"theme": "yeni-tema"` yazın.

---

## Skill Güncelleme

`brand.json`'ı değiştirdiniz ve skill'i yenilemek istiyorsanız:

```bash
python setup.py
```

Script mevcut brand.json'ı okur, skill dosyasını günceller.

---

## Sorun Giderme

**"playwright bulunamadı" hatası**
```bash
pip install playwright
playwright install chromium
```

**PNG'ler boş çıkıyor**
Font yüklemesi zaman aşımına uğramış olabilir. `export_slides.py` içindeki `wait_for_timeout(3500)` değerini `5000` yapın.

**Türkçe karakter bozuk**
JSON dosyanızın UTF-8 kodlamasıyla kaydedildiğinden emin olun. Terminalde:
```bash
python -X utf8 generate.py content/konu.json
```

**Skill çalışmıyor**
```bash
ls ~/.claude/skills/
```
`<slug>-carousel/SKILL.md` dosyasının orada olup olmadığını kontrol edin. Yoksa `python setup.py` ile yeniden kurun.

**Slide sayısı değişiyor**
`export_slides.py` HTML'deki `.slide` elementlerini sayar. JSON'daki her slide bir `.slide` elementi üretir. Beklenen ve gerçek sayılar farklıysa HTML çıktısını kontrol edin.
