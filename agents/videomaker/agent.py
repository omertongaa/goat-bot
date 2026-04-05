"""VideoMaker Agent — Video content planning, scripting, and storyboarding.

Supports both short-form (reels, shorts, tiktok) and long-form (YouTube 8-30min) content.
"""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class VideoMakerAgent(BaseAgent):
    agent_id = "videomaker"
    name = "VideoMaker"
    role = "Creates video scripts, storyboards — short-form and YouTube long-form"
    category = "creative"

    # Video format presets
    FORMATS = {
        "reels": {"duration": "15-60s", "ratio": "9:16", "platform": "Instagram/TikTok"},
        "youtube_short": {"duration": "30-60s", "ratio": "9:16", "platform": "YouTube Shorts"},
        "youtube": {"duration": "8-15min", "ratio": "16:9", "platform": "YouTube"},
        "youtube_long": {"duration": "15-30min", "ratio": "16:9", "platform": "YouTube (Deep Dive)"},
        "youtube_tutorial": {"duration": "10-20min", "ratio": "16:9", "platform": "YouTube (Tutorial)"},
        "youtube_documentary": {"duration": "15-45min", "ratio": "16:9", "platform": "YouTube (Documentary)"},
        "youtube_podcast": {"duration": "30-90min", "ratio": "16:9", "platform": "YouTube (Podcast/Talk)"},
        "youtube_listicle": {"duration": "8-15min", "ratio": "16:9", "platform": "YouTube (Listicle)"},
        "tiktok": {"duration": "15-60s", "ratio": "9:16", "platform": "TikTok"},
        "ad_video": {"duration": "15-30s", "ratio": "16:9", "platform": "Google/Meta Ads"},
        "testimonial": {"duration": "30-90s", "ratio": "16:9", "platform": "Website/Social"},
        "explainer": {"duration": "60-120s", "ratio": "16:9", "platform": "Website/YouTube"},
        "presentation": {"duration": "3-10min", "ratio": "16:9", "platform": "Meeting/Webinar"},
    }

    # Long-form types that trigger the detailed pipeline
    LONGFORM_TYPES = {"youtube", "youtube_long", "youtube_tutorial", "youtube_documentary", "youtube_podcast", "youtube_listicle"}

    def run(self, video_type: str = "reels", business_name: str = "",
            topic: str = "", target_audience: str = "", count: int = 3,
            language: str = "tr") -> dict:
        self.log("VideoMaker agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "My Agency")
        if not topic:
            topic = config.get("niche", "dijital pazarlama")
        if not target_audience:
            target_audience = "KOBİ sahipleri ve girişimciler"

        fmt = self.FORMATS.get(video_type, self.FORMATS["reels"])
        self.log(f"Format: {video_type} | Duration: {fmt['duration']} | Ratio: {fmt['ratio']}")

        # Route to long-form or short-form pipeline
        if video_type in self.LONGFORM_TYPES:
            return self._longform_pipeline(video_type, fmt, business_name, topic, target_audience, language)
        else:
            return self._shortform_pipeline(video_type, fmt, business_name, topic, target_audience, count)

    # ═══════════════════════════════════════════════════════
    # LONG-FORM YOUTUBE PIPELINE
    # ═══════════════════════════════════════════════════════

    def _longform_pipeline(self, video_type, fmt, business_name, topic, target_audience, language):
        self.log(f"Long-form pipeline: {video_type} — {topic}")
        lang = "Türkçe" if language == "tr" else "English"

        # Step 1: Research & Outline
        outline = self._generate_outline(video_type, topic, target_audience, fmt, lang, business_name)

        # Step 2: Full script with timestamps
        script = self._generate_longform_script(video_type, topic, outline, target_audience, fmt, lang, business_name)

        # Step 3: B-roll & visual plan
        visual_plan = self._generate_visual_plan(video_type, topic, outline, lang)

        # Step 4: Retention strategy
        retention = self._generate_retention_strategy(video_type, topic, fmt, lang)

        # Step 5: YouTube metadata (title, desc, tags, thumbnail brief)
        metadata = self._generate_youtube_metadata(topic, video_type, lang, business_name)

        # Step 6: Remotion scene breakdown (for VideoProducer integration)
        scenes = self._generate_remotion_scenes(outline, topic)

        # Generate thumbnail
        thumbnail_path = None
        try:
            from services.image import generate_image
            thumb_prompt = f"YouTube thumbnail, professional, bold text, high contrast, topic: {topic}, eye-catching, {business_name}, clean modern design"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            thumbnail_path = generate_image(thumb_prompt, size="landscape_16_9",
                                            filename=f"thumb_longform_{timestamp}.png")
            if thumbnail_path:
                self.log(f"Thumbnail generated: {thumbnail_path}")
        except Exception as e:
            self.log(f"Thumbnail generation skipped: {e}")

        # Save everything
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topic.lower().replace(" ", "_")[:30]
        video_data = {
            "business_name": business_name,
            "video_type": video_type,
            "format": fmt,
            "topic": topic,
            "target_audience": target_audience,
            "language": language,
            "outline": outline,
            "script": script,
            "visual_plan": visual_plan,
            "retention": retention,
            "metadata": metadata,
            "scenes": scenes,
            "thumbnail_path": thumbnail_path,
            "created_at": timestamp,
        }

        self.save_data(f"videos/{timestamp}_{slug}_longform.json", video_data)

        # Save script as standalone markdown
        scripts_dir = OUTPUT_DIR / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        md_path = scripts_dir / f"{timestamp}_{slug}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {topic}\n\n## Outline\n{outline}\n\n## Full Script\n{script}\n\n## Visual Plan\n{visual_plan}\n\n## Retention\n{retention}\n\n## Metadata\n{metadata}")
        self.log(f"Script saved: {md_path}")

        results = {
            "status": "ok",
            "summary": f"YouTube long-form video planı hazır: {topic} ({fmt['duration']})",
            "metrics": {
                "video_type": video_type,
                "format": fmt,
                "topic": topic,
                "script_words": len(script.split()) if isinstance(script, str) else 0,
                "scenes_count": len(scenes) if isinstance(scenes, list) else 0,
                "thumbnail_generated": bool(thumbnail_path),
                "md_path": str(md_path),
                "timestamp": datetime.now().isoformat(),
            },
            "video": video_data,
            "recommendations": [
                "Script'i sesli prova edin — süreyi doğrulayın",
                "Hook (ilk 30s) izleyiciyi tutmalı — retention burada düşer",
                "Her 2-3 dakikada pattern interrupt ekleyin (grafik, b-roll, soru)",
                "Chapters/zaman damgaları SEO için kritik",
                "VideoProducer agent ile bu plan'dan otomatik video üretebilirsiniz",
                f"Tahmini süre: {fmt['duration']}",
            ],
        }

        self.save_output("videomaker_report.json", results)
        self.log("Long-form pipeline completed")
        return results

    def _generate_outline(self, video_type, topic, audience, fmt, lang, business_name):
        """Step 1: Research-backed outline with chapters."""
        type_instructions = {
            "youtube": "Standart YouTube videosu — eğitim/bilgi odaklı",
            "youtube_long": "Derin dalış — her bölüm detaylı analiz",
            "youtube_tutorial": "Adım adım tutorial — ekran kaydı ağırlıklı",
            "youtube_documentary": "Mini belgesel — hikaye anlatımı, dramatik yapı",
            "youtube_podcast": "Sohbet formatı — konuşma ağırlıklı, doğal akış",
            "youtube_listicle": "Liste videosu — X şey, X hata, X ipucu formatı",
        }

        prompt = f"""Sen deneyimli bir YouTube içerik stratejistisin. Detaylı video outline'ı oluştur.

Konu: {topic}
Format: {type_instructions.get(video_type, 'YouTube videosu')}
Hedef süre: {fmt['duration']}
Hedef kitle: {audience}
Kanal: {business_name}
Dil: {lang}

Şunları içeren detaylı outline:

1. **Video Tezi** — Bu video ne anlatıyor, izleyici ne kazanıyor (1 cümle)

2. **Hook Stratejisi** (ilk 30 saniye)
   - Açılış cümlesi (dikkat çekici, merak uyandıran)
   - "Bu videoda öğrenecekleriniz" önizleme
   - Neden şimdi izlemeli (aciliyet)

3. **Bölümler/Chapters** (her biri 2-4 dakika)
   Her bölüm için:
   - Zaman damgası (0:00 formatında)
   - Bölüm başlığı
   - Ana argüman/bilgi (2-3 cümle)
   - Destekleyici veri/örnek/hikaye
   - Görsel önerisi (ne gösterilecek)
   - Pattern interrupt noktası (grafik, soru, b-roll değişimi)

4. **Geçiş Cümleleri** — bölümler arası bağlayıcılar

5. **CTA Noktaları** (video içinde 2-3 yerde)
   - Abone ol + bildirim
   - Yorum bırak (engagement sorusu)
   - İlgili video/playlist

6. **Kapanış** (son 60 saniye)
   - Özet (3 ana takeaway)
   - Final CTA
   - Sonraki video teaseri

7. **SEO Notları**
   - Ana anahtar kelime
   - İkincil anahtar kelimeler (5-7)
   - Chapters başlıkları (YouTube arama için optimize)

{lang} yaz. Detaylı ve actionable."""

        result = self.call_claude(prompt, timeout=180)
        if not result:
            return self._fallback_outline(video_type, topic, fmt, business_name)
        return result

    def _generate_longform_script(self, video_type, topic, outline, audience, fmt, lang, business_name):
        """Step 2: Full word-for-word script."""
        prompt = f"""Bu outline'a dayanarak kelimesi kelimesine konuşma script'i yaz.

Konu: {topic}
Format: {video_type} ({fmt['duration']})
Dil: {lang}
Kanal: {business_name}

OUTLINE:
{outline[:3000]}

Kurallar:
- Kelimesi kelimesine konuşma metni (teleprompter'dan okunacak gibi)
- Her bölüm başında [BÖLÜM: başlık] ve [ZAMAN: 0:00] belirt
- Görsel değişim noktalarında [B-ROLL: açıklama] veya [EKRAN: açıklama] notu ekle
- Doğal konuşma dili — yazı dili değil, konuşma dili
- Pattern interrupt noktalarında [GRAFİK: açıklama] veya [LOWER THIRD: metin] notu
- Vurgu yapılacak kelimeleri **kalın** yaz
- Kısa cümleler — nefes noktaları bırak
- Her 2-3 dakikada engagement hook (soru, şaşırtıcı bilgi)
- Dakika başına ~150 kelime (doğal konuşma hızı)

{lang} yaz. Doğal, enerjik, bilgilendirici ton."""

        result = self.call_claude(prompt, timeout=180)
        if not result:
            return self._fallback_script(topic, fmt, business_name)
        return result

    def _generate_visual_plan(self, video_type, topic, outline, lang):
        """Step 3: B-roll, graphics, and visual plan."""
        prompt = f"""Bu video için detaylı görsel plan oluştur.

Konu: {topic}
Format: {video_type}

OUTLINE (kısaltılmış):
{outline[:2000]}

Her bölüm için:
1. **Kamera** — talking head / ekran kaydı / B-roll oranı
2. **B-Roll listesi** — hangi görüntüler gerekli (stock veya çekim)
3. **Grafik/Animasyon** — hangi noktada ne tür grafik
4. **Lower Third** — isim, istatistik, anahtar nokta overlay'leri
5. **Ekran kaydı** — (tutorial ise) hangi uygulama/site
6. **Geçiş efektleri** — bölümler arası

Ayrıca:
- Thumbnail konsepti (arka plan + metin + yüz ifadesi)
- Intro animasyon önerisi (3-5 saniye)
- Outro template (subscribe + sonraki video)
- Alt yazı stili önerisi

{lang} yaz."""

        result = self.call_claude(prompt, timeout=120)
        if not result:
            return f"""# Görsel Plan — {topic}

## Kamera Dağılımı
- %50 Talking head (kameraya konuşma)
- %30 B-Roll (destekleyici görüntü)
- %20 Ekran kaydı / grafik

## B-Roll İhtiyaçları
- Konu ile ilgili stock footage (Pexels, Pixabay)
- Ekran kaydı (ilgili websiteler, araçlar)
- Animasyonlu grafikler (istatistikler, listeler)

## Grafik Noktaları
- Her bölüm başında: bölüm başlık kartı
- İstatistiklerde: animasyonlu sayı
- Listelerde: madde madde overlay
- Alıntılarda: tam ekran quote kartı

## Thumbnail
- Sol: yüz (şaşkın/heyecanlı ifade)
- Sağ: konu ile ilgili görsel
- Metin: MAX 4 kelime, sarı/beyaz bold
- Arka plan: koyu gradient
"""
        return result

    def _generate_retention_strategy(self, video_type, topic, fmt, lang):
        """Step 4: Audience retention optimization."""
        prompt = f"""YouTube izleyici tutma (retention) stratejisi oluştur.

Konu: {topic}
Format: {video_type} ({fmt['duration']})

1. **İlk 30 Saniye** (en kritik — %30-40 burada kaybedilir)
   - Hook teknikleri (3 alternatif)
   - "İzlemeye devam edin çünkü..." cümlesi
   - Preview/teaser (videonun en ilginç anından snippet)

2. **Pattern Interrupt Takvimi**
   Her 2-3 dakikada bir interrupt:
   - Kamera açısı değişimi
   - B-roll geçişi
   - Grafik/animasyon
   - Soru sorma ("Siz ne düşünüyorsunuz?")
   - Şaşırtıcı bilgi ("Bunu biliyor muydunuz?")
   - Ses tonu değişimi
   - Zaman damgası: tam hangi dakikada ne yapılacak

3. **Engagement Hooks** (yorum + like tetikleyiciler)
   - Dakika X: "Yorumlarda yazın..."
   - Dakika Y: "Beğendiyseniz like atın"
   - Dakika Z: "Abone olun, bildirim açın"

4. **Retention Düşme Noktaları** (önlem)
   - Giriş uzun olmasın (max 60s)
   - Bölüm geçişlerinde merak uyandır ("En ilginç kısım geliyor...")
   - Ortada enerji düşmesin — en güçlü bölümü ortaya koy
   - Sonunda "bonus" vaat et

5. **End Screen Stratejisi** (son 20 saniye)
   - İlgili video önerisi
   - Playlist linki
   - Abone butonu animasyonu

{lang} yaz."""

        result = self.call_claude(prompt, timeout=120)
        if not result:
            return f"""# Retention Stratejisi — {topic}

## İlk 30 Saniye
- Hook: Şok edici istatistik veya soru ile başla
- Preview: "Bu videoda X, Y, Z öğreneceksiniz"
- Aciliyet: "Bunu bilmezseniz Z olur"

## Pattern Interrupt Takvimi
- 0:30 — B-roll geçişi
- 2:00 — Grafik/istatistik
- 4:00 — Soru sor ("Siz de böyle yapıyor musunuz?")
- 6:00 — B-roll + ses değişimi
- 8:00 — Şaşırtıcı bilgi
- 10:00 — CTA (abone ol)
- 12:00 — Kamera açısı değiştir

## Engagement Hooks
- Dk 3: "Yorumlarda yazın: X mi Y mi?"
- Dk 7: "Beğendiyseniz like atın — algoritmaya yardımcı olur"
- Dk 11: "Abone olun, her hafta yeni video"

## Retention Düşme Önlemleri
- Intro max 60 saniye
- En güçlü bölüm ortada (dk 5-8)
- "Bonus" sona yakın ("Bir de bunu bilin...")
"""
        return result

    def _generate_youtube_metadata(self, topic, video_type, lang, business_name):
        """Step 5: SEO-optimized YouTube metadata."""
        prompt = f"""YouTube SEO metadata oluştur:

Konu: {topic}
Kanal: {business_name}

1. **Başlık** (5 alternatif, max 60 karakter)
   - Sayı kullan (5, 10, 100)
   - Güçlü kelime (gizli, şok, gerçek, hata)
   - Ana keyword başta

2. **Açıklama** (ilk 2 satır arama sonuçlarında görünür)
   - Hook cümlesi
   - Chapters zaman damgaları
   - İlgili linkler
   - Abone CTA
   - Hashtag'ler

3. **Tags** (20-30 tag, uzun kuyruk keyword'ler dahil)

4. **Thumbnail metin** (max 4 kelime, BÜYÜK HARF)

{lang} yaz."""

        result = self.call_claude(prompt, timeout=60)
        if not result:
            return f"""# YouTube Metadata — {topic}

## Başlıklar
1. {topic} — Bilmeniz Gereken Her Şey (2025)
2. {topic}: Adım Adım Rehber
3. {topic} Hakkında 5 Şok Edici Gerçek
4. {topic} Nasıl Yapılır? Detaylı Anlatım
5. Neden {topic} Öğrenmelisiniz?

## Açıklama
{topic} hakkında kapsamlı rehber.

## Tags
{topic}, {topic} nasıl, {topic} rehber, {topic} türkçe, {business_name}

## Thumbnail
{topic[:20].upper()}
"""
        return result

    def _generate_remotion_scenes(self, outline, topic):
        """Step 6: Break outline into Remotion-compatible scene list for VideoProducer."""
        scenes = [
            {"id": "1", "type": "intro", "videoPrompt": f"Cinematic aerial establishing shot related to {topic}, dramatic lighting, 4K", "narration": "", "needsVideo": True},
            {"id": "2", "type": "titleCard", "videoPrompt": "", "narration": "", "titleCardText": topic.upper(), "needsVideo": False},
        ]

        # Extract chapters from outline and create scenes
        if isinstance(outline, str):
            import re
            chapters = re.findall(r'(?:Bölüm|Chapter|##)\s*\d+[:\s—-]+(.+?)(?:\n|$)', outline, re.IGNORECASE)
            for i, chapter in enumerate(chapters[:8], 3):
                chapter_clean = chapter.strip()[:80]
                scenes.append({
                    "id": str(i),
                    "type": "image",
                    "videoPrompt": f"Professional cinematic shot illustrating: {chapter_clean}, high quality, detailed",
                    "narration": chapter_clean,
                    "needsVideo": True,
                })

        scenes.append({
            "id": str(len(scenes) + 1),
            "type": "endCard",
            "videoPrompt": "",
            "narration": "",
            "endCardMessage": "Abone Olun!",
            "endCardTag": topic,
            "needsVideo": False,
        })

        return scenes

    # ═══════════════════════════════════════════════════════
    # SHORT-FORM PIPELINE (original)
    # ═══════════════════════════════════════════════════════

    def _shortform_pipeline(self, video_type, fmt, business_name, topic, target_audience, count):
        self.log(f"Short-form pipeline: {video_type}")

        prompt = f"""Sen profesyonel bir video içerik üreticisisin.

İşletme: {business_name}
Konu: {topic}
Format: {video_type} ({fmt['duration']}, {fmt['ratio']})
Platform: {fmt['platform']}
Hedef kitle: {target_audience}

{count} adet video script'i oluştur. Her biri için:

1. **Başlık** (hook — ilk 3 saniye)
2. **Script** (konuşma metni, sahne sahne)
3. **Görsel notlar** (ne gösterilecek)
4. **Müzik/ses önerisi**
5. **CTA** (call-to-action)
6. **Hashtag önerileri** (5-10 adet)

Kısa, dikkat çekici, viral potansiyeli yüksek içerikler yaz.
Türkçe yaz."""

        scripts = self.call_claude(prompt)
        if not scripts:
            scripts = self._generate_fallback_scripts(business_name, topic, video_type, fmt, count)

        storyboard_prompt = f"""Bu video için görsel storyboard oluştur:
İşletme: {business_name}
Format: {video_type}
Konu: {topic}

Her sahne için:
- Sahne numarası ve süresi
- Görsel açıklama (kamera açısı, arka plan)
- Metin/overlay
- Geçiş efekti

3-6 sahne yeterli."""

        storyboard = self.call_claude(storyboard_prompt)
        if not storyboard:
            storyboard = self._generate_fallback_storyboard(business_name, video_type)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_data = {
            "business_name": business_name,
            "video_type": video_type,
            "format": fmt,
            "topic": topic,
            "target_audience": target_audience,
            "scripts": scripts,
            "storyboard": storyboard,
            "created_at": timestamp,
        }

        self.save_data(f"videos/{timestamp}_{video_type}.json", video_data)

        thumbnail_path = None
        try:
            from services.image import generate_image
            thumb_prompt = f"YouTube thumbnail, professional, {business_name}, topic: {topic}, eye-catching, bold text"
            thumbnail_path = generate_image(thumb_prompt, size="landscape_16_9",
                                            filename=f"thumb_{video_type}_{timestamp}.png")
            if thumbnail_path:
                self.log(f"Thumbnail generated: {thumbnail_path}")
        except Exception as e:
            self.log(f"Thumbnail generation skipped: {e}")

        results = {
            "status": "ok",
            "summary": f"{count} adet {video_type} script'i oluşturuldu — {business_name}",
            "metrics": {
                "video_type": video_type,
                "scripts_count": count,
                "format": fmt,
                "thumbnail_generated": bool(thumbnail_path),
                "timestamp": datetime.now().isoformat(),
            },
            "video": video_data,
            "recommendations": [
                f"Format: {fmt['ratio']} — {fmt['platform']} için optimize",
                f"Süre: {fmt['duration']} — dikkat süresi kısa tut",
                "İlk 3 saniye kritik — hook ile başla",
                "Altyazı ekle — %85 video sessiz izleniyor",
                "Tutarlı paylaşım takvimi oluştur",
            ],
        }

        self.save_output("videomaker_report.json", results)
        self.log("Short-form pipeline completed")
        return results

    # ═══════════════════════════════════════════════════════
    # FALLBACKS
    # ═══════════════════════════════════════════════════════

    def _fallback_outline(self, video_type, topic, fmt, business_name):
        return f"""# Video Outline — {topic}

## Video Tezi
{topic} hakkında kapsamlı rehber — izleyici konunun temellerini ve pratik uygulamalarını öğrenecek.

## Hook (0:00-0:30)
"Herkese merhaba! Bugün {topic} hakkında konuşacağız. Bu videonun sonunda [fayda] öğrenmiş olacaksınız."

## Bölümler

### Bölüm 1: Giriş & Neden Önemli (0:30-3:00)
- {topic} nedir?
- Neden öğrenmelisiniz?
- [GRAFİK: İstatistik]

### Bölüm 2: Temel Bilgiler (3:00-6:00)
- Ana konseptler
- Örneklerle açıklama
- [B-ROLL: Ekran kaydı]

### Bölüm 3: Pratik Uygulama (6:00-9:00)
- Adım adım nasıl yapılır
- Gerçek örnek demo
- [EKRAN: Canlı demo]

### Bölüm 4: İleri Seviye İpuçları (9:00-11:00)
- Pro ipuçları
- Sık yapılan hatalar
- [GRAFİK: Hata listesi]

### Bölüm 5: Sonuç & CTA (11:00-12:00)
- 3 ana takeaway
- Abone ol + bildirim
- Sonraki video teaseri

## SEO
- Ana keyword: {topic}
- Chapters başlıkları YouTube arama için optimize
"""

    def _fallback_script(self, topic, fmt, business_name):
        return f"""# Full Script — {topic}

[BÖLÜM: Hook]
[ZAMAN: 0:00]

Herkese merhaba! Ben {business_name}'dan. Bugün {topic} hakkında konuşacağız.

Bu videonun sonunda tam olarak ne yapmanız gerektiğini bileceksiniz. Ama önce, şunu bilin...

[B-ROLL: Konu ile ilgili görüntü]

[BÖLÜM: Giriş]
[ZAMAN: 0:30]

{topic} neden bu kadar önemli? Çünkü...

[GRAFİK: İstatistik görseli]

(Devamı Claude CLI ile oluşturulur — tüm bölümler kelimesi kelimesine yazılır)

[BÖLÜM: Kapanış]
[ZAMAN: {fmt['duration'].split('-')[1]}]

Özetlemek gerekirse: birincisi [X], ikincisi [Y], üçüncüsü [Z].

Bu video işinize yaradıysa **like atın**, kanalıma **abone olun** ve **bildirim zilini** açın.

Bir sonraki videoda [teaser konu] anlatacağım. Görüşmek üzere!

[END SCREEN: 20 saniye — abone + sonraki video]
"""

    def _generate_fallback_scripts(self, business_name, topic, video_type, fmt, count):
        scripts = []
        hooks = [
            "Bu hatayı yapıyorsanız müşteri kaybediyorsunuz...",
            "3 adımda satışlarınızı %50 artırın",
            f"{topic} hakkında kimsenin söylemediği gerçek",
        ]
        for i in range(min(count, len(hooks))):
            scripts.append(f"""## Video {i + 1}: {hooks[i]}

**Hook (0-3s):** {hooks[i]}

**Script:**
- Sahne 1 (0-3s): Hook — dikkat çek
- Sahne 2 (3-10s): Problem — hedef kitlenin acısını anlat
- Sahne 3 (10-20s): Çözüm — {business_name} nasıl yardımcı olur
- Sahne 4 (20-{fmt['duration'].split('-')[0]}s): Sonuç + CTA

**CTA:** "Profildeki linke tıkla" / "Takip et, daha fazlası gelecek"

**Hashtag:** #{topic.replace(' ', '')} #dijitalpazarlama #işletme #büyüme #girişimci
""")
        return "\n---\n".join(scripts)

    def _generate_fallback_storyboard(self, business_name, video_type):
        return f"""# Storyboard — {business_name} ({video_type})

## Sahne 1 — Hook (0-3s)
- Kamera: Yakın çekim / yüz
- Overlay: Dikkat çekici başlık metni
- Geçiş: Jump cut

## Sahne 2 — Problem (3-8s)
- Kamera: B-roll / ekran kaydı
- Overlay: Problem açıklaması
- Geçiş: Smooth zoom

## Sahne 3 — Çözüm (8-15s)
- Kamera: Ürün/servis demosu
- Overlay: Adım adım açıklama
- Geçiş: Slide

## Sahne 4 — Sonuç + CTA (15-20s)
- Kamera: Konuşan kişi / logo
- Overlay: CTA metni + link
- Geçiş: Fade out
"""
