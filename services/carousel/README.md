# Carousel Template

JSON dosyasından Instagram carousel'ı otomatik üretir — 1080×1350 px PNG çıktılarıyla.

Claude Code skill entegrasyonu sayesinde tek komutla çalışır:

```
/markam-carousel "Sabah rutininin 3 sırrı"
```

---

## Ne Yapar?

1. Claude, konuyu alır ve slide planı önerir
2. Onayından sonra JSON yazar → PNG'leri üretir
3. `output/{konu}/slide_01.png ... slide_N.png` hazır

---

## Gereksinimler

| Araç | Versiyon | Kontrol |
|------|----------|---------|
| Python | 3.10+ | `python --version` |
| Playwright | son | `pip install playwright && playwright install chromium` |
| Claude Code | son | [claude.ai/code](https://claude.ai/code) |

---

## Kurulum (4 Adım)

**1. Repoyu klonla**

```bash
git clone https://github.com/Arif-Ata-Kosker/carousel-template.git
cd carousel-template
```

**2. Kurulum scriptini çalıştır**

```bash
python setup.py
```

Script sırayla şunları yapar:
- `brand.json` oluşturur (handle, dil, tema sorar)
- `voice.md` şablonunu kopyalar
- Claude Code skill dosyasını `~/.claude/skills/` altına yazar

**3. Marka sesini tanımla**

`voice.md` dosyasını aç ve markanın sesini doldur:
- Hedef kitle, ton, hook kalıpları, CTA biçimi, kaçınılan kelimeler

**4. İlk carousel'ı üret**

Claude Code'u aç ve yaz:

```
/<slug>-carousel "konu başlığı"
```

---

## 5 Hazır Tema

| Tema | En iyi için |
|------|-------------|
| `terminal-dark` | Dev, kod, teknik içerik |
| `editorial-cream` | Eğitim, rehber, tutorial |
| `vibrant-gradient` | Viral, trend, karşılaştırma |
| `minimal-mono` | Quote, essay, fikir |
| `data-viz` | İstatistik, araştırma, rakam |

`brand.json` içindeki `default_theme` değerini değiştirerek tema seçersin.

---

## 7 Slide Tipi

| Tip | Kullanım |
|-----|----------|
| `cover` | Kapak slide'ı |
| `inner_text` | Metin + terminal bloğu |
| `inner_list` | Madde listesi |
| `inner_comparison` | Önce/sonra karşılaştırması |
| `inner_stats` | Rakam/istatistik |
| `inner_quote` | Alıntı |
| `cta` | Kapanış + takip çağrısı |

---

## Manuel Kullanım (Skill Olmadan)

```bash
python generate.py content/ornek.json
```

`content/ornek.json` dosyasına bakarak kendi JSON'ını hazırlayabilirsin.

---

## Detaylı Belgeler

- [KURULUM.md](KURULUM.md) — Kurulum, özelleştirme, sorun giderme
- [nasilkullanilir.md](nasilkullanilir.md) — Mimari, JSON şeması, slide limitleri
