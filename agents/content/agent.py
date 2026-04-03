"""Content Agent — Blog posts, social media content, copywriting."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class ContentAgent(BaseAgent):
    agent_id = "content"
    name = "Content"
    role = "Writes blog posts, social media content, email copy, and marketing text"
    category = "creative"

    CONTENT_TYPES = {
        "blog": {"name": "Blog Yazısı", "word_count": "800-1500"},
        "social": {"name": "Sosyal Medya İçeriği", "word_count": "50-300"},
        "email": {"name": "Email İçeriği", "word_count": "200-500"},
        "landing": {"name": "Landing Page Metni", "word_count": "300-800"},
        "newsletter": {"name": "Newsletter", "word_count": "500-1000"},
        "case_study": {"name": "Başarı Hikayesi", "word_count": "500-1000"},
        "product_desc": {"name": "Ürün/Hizmet Açıklaması", "word_count": "100-300"},
        "seo": {"name": "SEO İçerik", "word_count": "1000-2000"},
        "calendar": {"name": "İçerik Takvimi", "word_count": "N/A"},
    }

    def run(self, content_type: str = "blog", topic: str = "",
            tone: str = "profesyonel", language: str = "tr",
            platform: str = "", count: int = 1) -> dict:
        self.log("Content agent started")
        config = self.load_config()

        business_name = config.get("agency_name", "My Agency")
        niche = config.get("niche", "dijital pazarlama")

        if not topic:
            topic = f"{niche} trendleri ve ipuçları"

        ct = self.CONTENT_TYPES.get(content_type, self.CONTENT_TYPES["blog"])
        self.log(f"Content type: {ct['name']} | Topic: {topic} | Count: {count}")

        if content_type == "calendar":
            content = self._generate_calendar(business_name, niche, platform or "instagram")
        elif content_type == "social" and count > 1:
            content = self._generate_social_batch(business_name, niche, topic, platform or "instagram", count)
        else:
            content = self._generate_content(business_name, niche, topic, content_type, ct, tone, language, platform)

        # Save content
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_data = {
            "content_type": content_type,
            "content_name": ct["name"],
            "topic": topic,
            "tone": tone,
            "language": language,
            "platform": platform,
            "business_name": business_name,
            "content": content,
            "created_at": timestamp,
        }

        self.save_data(f"content/{timestamp}_{content_type}.json", content_data)

        # Save as markdown if blog/newsletter/case_study
        if content_type in ("blog", "newsletter", "case_study", "seo"):
            md_dir = OUTPUT_DIR / "content"
            md_dir.mkdir(parents=True, exist_ok=True)
            slug = topic.lower().replace(" ", "_")[:30]
            md_path = md_dir / f"{timestamp}_{slug}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.log(f"Markdown saved: {md_path}")

        results = {
            "status": "ok",
            "summary": f"{ct['name']} oluşturuldu — '{topic}' ({business_name})",
            "metrics": {
                "content_type": content_type,
                "topic": topic,
                "word_count": len(content.split()) if content else 0,
                "platform": platform,
                "timestamp": datetime.now().isoformat(),
            },
            "content_data": content_data,
            "recommendations": [
                "İçeriği yayınlamadan önce gözden geçirin",
                "SEO için anahtar kelimeleri doğal şekilde yerleştirin",
                "Görseller ekleyin — engagement %80 artırır",
                "CTA (call-to-action) eklemeyi unutmayın",
                "Tutarlı yayın takvimi oluşturun",
            ],
        }

        self.save_output("content_report.json", results)
        self.log("Content agent completed")
        return results

    def _generate_content(self, business_name, niche, topic, content_type, ct, tone, language, platform):
        lang = "Türkçe" if language == "tr" else "English"
        prompt = f"""Sen deneyimli bir içerik yazarısın.

İşletme: {business_name}
Sektör: {niche}
İçerik türü: {ct['name']}
Konu: {topic}
Ton: {tone}
Dil: {lang}
Kelime sayısı: {ct['word_count']}
{"Platform: " + platform if platform else ""}

{self._get_content_instructions(content_type)}

{lang} yaz. SEO dostu, okuyucu odaklı, değer katan içerik oluştur."""

        result = self.call_claude(prompt)
        if not result:
            return self._fallback_content(business_name, niche, topic, content_type)
        return result

    def _get_content_instructions(self, content_type):
        instructions = {
            "blog": """Blog yazısı oluştur:
- Dikkat çekici başlık (H1)
- Giriş paragrafı (hook)
- 3-5 alt başlık (H2)
- Her bölümde 2-3 paragraf
- Pratik ipuçları ve örnekler
- Sonuç + CTA
- Meta description (155 karakter)
- 5-7 anahtar kelime""",
            "social": """Sosyal medya paylaşımı yaz:
- Hook (ilk cümle çok önemli)
- Ana mesaj
- CTA
- Emoji kullanımı (ölçülü)
- Hashtag önerileri (5-10)""",
            "email": """Email içeriği yaz:
- Konu satırı (subject line) — 5 alternatif
- Preview text
- Email gövdesi
- CTA butonu metni
- PS notu""",
            "landing": """Landing page metni yaz:
- Hero section (başlık + alt başlık)
- Problem bölümü
- Çözüm bölümü
- Özellikler (3-5 madde)
- Sosyal kanıt
- CTA bölümü
- SSS (3-5 soru)""",
            "newsletter": """Newsletter yaz:
- Dikkat çekici başlık
- Giriş (kısa, samimi)
- Ana içerik (2-3 bölüm)
- İpucu/kaynak önerisi
- CTA""",
            "case_study": """Başarı hikayesi/case study yaz:
- Müşteri tanıtımı
- Problem/zorluklar
- Çözüm yaklaşımı
- Sonuçlar (sayısal veriler)
- Müşteri yorumu (testimonial)""",
            "product_desc": """Ürün/hizmet açıklaması yaz:
- Kısa ve etkili başlık
- Değer önerisi (1 cümle)
- Özellikler ve faydalar
- Fiyatlandırma ipucu
- CTA""",
            "seo": """SEO optimizeli içerik yaz:
- Ana anahtar kelime odaklı
- H1, H2, H3 yapısı
- İlk 100 kelimede anahtar kelime
- Internal/external link önerileri
- Meta title + description
- Alt text önerileri""",
        }
        return instructions.get(content_type, instructions["blog"])

    def _generate_calendar(self, business_name, niche, platform):
        prompt = f"""30 günlük içerik takvimi oluştur:

İşletme: {business_name}
Sektör: {niche}
Platform: {platform}

Her gün için:
- Tarih (Gün 1, Gün 2...)
- İçerik türü (post/carousel/reel/story)
- Konu/başlık
- Kısa açıklama
- En iyi paylaşım saati

Haftada 5 gün paylaşım yap (Pzt-Cum).
Çeşitlilik sağla: eğitim, behind-the-scenes, sosyal kanıt, eğlence, promosyon.
Türkçe yaz."""

        result = self.call_claude(prompt)
        if not result:
            return f"""# 30 Günlük İçerik Takvimi — {business_name}

## Hafta 1
- **Pzt:** Eğitim postu — {niche} için 5 ipucu
- **Sal:** Carousel — Adım adım rehber
- **Çar:** Behind-the-scenes — Ekip/süreç
- **Per:** Reel — Kısa ipucu videosu
- **Cum:** Başarı hikayesi — Müşteri sonuçları

## Hafta 2-4
(Aynı formatta devam — Claude CLI ile detaylı takvim oluşturulur)

## Paylaşım Saatleri
- Pzt-Cum: 10:00, 13:00, 18:00
- Hafta sonu: 11:00, 16:00
"""
        return result

    def _generate_social_batch(self, business_name, niche, topic, platform, count):
        prompt = f"""{count} adet {platform} paylaşımı yaz:

İşletme: {business_name}
Sektör: {niche}
Konu: {topic}

Her paylaşım farklı açıdan yaklaşsın:
1. Eğitim / ipucu
2. Soru / engagement
3. Motivasyon
4. Behind the scenes
5. Promosyon

Her biri için: metin + emoji + hashtag.
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# {count} Sosyal Medya Paylaşımı — {topic}\n\n(Claude CLI ile oluşturulur)"

    def _fallback_content(self, business_name, niche, topic, content_type):
        return f"""# {topic}

*{business_name} tarafından hazırlanmıştır.*

## Giriş

{niche} sektöründe başarılı olmanın anahtarı doğru strateji ve tutarlılıktır. Bu yazıda {topic} hakkında bilmeniz gerekenleri paylaşıyoruz.

## Ana Bölüm

### 1. Doğru Hedef Kitle
Başarının ilk adımı ideal müşteri profilinizi net tanımlamaktır.

### 2. Değer Önerisi
Rakiplerinizden ne farkınız var? Bunu net ifade edin.

### 3. Tutarlı İletişim
Düzenli ve kaliteli içerik, güven inşa eder.

## Sonuç

{topic} konusunda daha fazla bilgi almak için bizimle iletişime geçin.

---
*{business_name} — {niche} uzmanı*
"""
