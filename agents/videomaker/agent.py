"""VideoMaker Agent — Video content planning, scripting, and storyboarding.

Supports both short-form (reels, shorts, tiktok) and long-form (YouTube 8-30min) content.

Üretilen artifact'lar:
- Markdown script (.md)
- Görsel storyboard HTML preview (her sahne için fal.ai still görsel + narration + kamera notu)
- Opsiyonel: make_mp4=True ise VideoProducer agent ile gerçek MP4
"""

import html as _html
import json
import re
from datetime import datetime
from pathlib import Path

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
            language: str = "tr", make_mp4: bool = False,
            make_stills: bool = True, max_stills: int = 6,
            max_clips: int = 2) -> dict:
        """
        make_stills=True (varsayılan) → her sahne için fal.ai still görsel üret (max_stills sınırı)
        make_mp4=False (varsayılan) → SADECE storyboard HTML üretilir (~30sn).
                                       True yapılırsa fal.ai Luma Dream Machine ile clipler
                                       üretilip concat edilir (~3-5dk, ~$0.30/clip × max_clips).
        """
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

        # Store options for downstream methods
        self._make_stills = make_stills
        self._max_stills = max(1, min(int(max_stills or 6), 12))
        self._make_mp4 = make_mp4
        self._max_clips = max(1, min(int(max_clips or 4), 6))

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

        # Save script as standalone markdown
        scripts_dir = OUTPUT_DIR / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        md_path = scripts_dir / f"{timestamp}_{slug}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {topic}\n\n## Outline\n{outline}\n\n## Full Script\n{script}\n\n## Visual Plan\n{visual_plan}\n\n## Retention\n{retention}\n\n## Metadata\n{metadata}")
        self.log(f"Script saved: {md_path}")

        # Storyboard scenes (with optional fal.ai stills)
        storyboard_scenes = self._scenes_for_storyboard(scenes, topic, business_name, fmt)
        storyboard_html_path = self._render_storyboard_html(
            storyboard_scenes, business_name, topic, video_type, fmt, slug, timestamp
        )

        # Real MP4 via fal.ai Kling + ffmpeg concat (default on)
        mp4_path = None
        if self._make_mp4:
            mp4_path = self._trigger_videoproducer(storyboard_scenes, topic,
                                                    slug=slug, timestamp=timestamp, fmt=fmt)

        video_data["storyboard_html"] = str(storyboard_html_path)
        video_data["mp4_path"] = mp4_path
        video_data["scenes_with_stills"] = storyboard_scenes
        self.save_data(f"videos/{timestamp}_{slug}_longform.json", video_data)

        results = {
            "status": "ok",
            "summary": f"YouTube long-form: storyboard HTML hazır ({len(storyboard_scenes)} sahne)" + (f", MP4: {Path(mp4_path).name}" if mp4_path else ""),
            "metrics": {
                "video_type": video_type,
                "format": fmt,
                "topic": topic,
                "script_words": len(script.split()) if isinstance(script, str) else 0,
                "scenes_count": len(scenes) if isinstance(scenes, list) else 0,
                "stills_generated": sum(1 for s in storyboard_scenes if s.get("image_path")),
                "thumbnail_generated": bool(thumbnail_path),
                "mp4_generated": bool(mp4_path),
                "md_path": str(md_path),
                "storyboard_html": str(storyboard_html_path),
                "timestamp": datetime.now().isoformat(),
            },
            "artifacts": {
                "script_md": str(md_path),
                "storyboard_html": str(storyboard_html_path),
                "thumbnail": thumbnail_path,
                "mp4": mp4_path,
            },
            "video": video_data,
            "recommendations": [
                "Storyboard HTML'i Files'tan açıp sahne sahne incele",
                "Hook (ilk 30s) izleyiciyi tutmalı — retention burada düşer",
                "Her 2-3 dakikada pattern interrupt ekleyin (grafik, b-roll, soru)",
                "Gerçek MP4 için: make_mp4=true parametresiyle yeniden çalıştır (~$1-3)",
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
        slug = re.sub(r'[^a-z0-9]+', '_', topic.lower())[:30].strip('_') or video_type

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

        # Build structured scenes from short-form script + render storyboard HTML
        short_scenes = self._scenes_from_short_script(scripts, storyboard, topic, business_name, fmt)
        storyboard_scenes = self._scenes_for_storyboard(short_scenes, topic, business_name, fmt)
        storyboard_html_path = self._render_storyboard_html(
            storyboard_scenes, business_name, topic, video_type, fmt, slug, timestamp
        )

        # Real MP4 via fal.ai Kling + ffmpeg concat (default on)
        mp4_path = None
        if self._make_mp4:
            mp4_path = self._trigger_videoproducer(storyboard_scenes, topic,
                                                    slug=slug, timestamp=timestamp, fmt=fmt)

        video_data = {
            "business_name": business_name,
            "video_type": video_type,
            "format": fmt,
            "topic": topic,
            "target_audience": target_audience,
            "scripts": scripts,
            "storyboard": storyboard,
            "scenes_with_stills": storyboard_scenes,
            "storyboard_html": str(storyboard_html_path),
            "thumbnail_path": thumbnail_path,
            "mp4_path": mp4_path,
            "created_at": timestamp,
        }
        self.save_data(f"videos/{timestamp}_{video_type}.json", video_data)

        results = {
            "status": "ok",
            "summary": f"{video_type} storyboard hazır ({len(storyboard_scenes)} sahne) — {business_name}" + (f", MP4: {Path(mp4_path).name}" if mp4_path else ""),
            "metrics": {
                "video_type": video_type,
                "scripts_count": count,
                "format": fmt,
                "scenes_count": len(storyboard_scenes),
                "stills_generated": sum(1 for s in storyboard_scenes if s.get("image_path")),
                "thumbnail_generated": bool(thumbnail_path),
                "mp4_generated": bool(mp4_path),
                "mp4_path": mp4_path,
                "storyboard_html": str(storyboard_html_path),
                "timestamp": datetime.now().isoformat(),
            },
            "artifacts": {
                "storyboard_html": str(storyboard_html_path),
                "thumbnail": thumbnail_path,
                "mp4": mp4_path,
            },
            "video": video_data,
            "recommendations": [
                f"Format: {fmt['ratio']} — {fmt['platform']} için optimize",
                f"Süre: {fmt['duration']} — dikkat süresi kısa tut",
                "Storyboard HTML'i Files'tan aç — sahne sahne görsel preview",
                "İlk 3 saniye kritik — hook ile başla",
                "Gerçek MP4 için: make_mp4=true (~$1-3 maliyet)",
            ],
        }

        self.save_output("videomaker_report.json", results)
        self.log("Short-form pipeline completed")
        return results

    # ═══════════════════════════════════════════════════════
    # STORYBOARD HTML + STILL IMAGES + MP4 TRIGGER
    # ═══════════════════════════════════════════════════════

    def _scenes_for_storyboard(self, scenes, topic, business_name, fmt):
        """Sahneleri normalize et + opsiyonel olarak fal.ai still görsel üret.
        Maliyet kontrolü: max self._max_stills sahne için görsel."""
        if not isinstance(scenes, list) or not scenes:
            scenes = [{
                "id": "1", "type": "intro", "title": topic,
                "narration": "", "videoPrompt": f"Cinematic shot of {topic}",
            }]

        normalized = []
        still_budget = self._max_stills if getattr(self, '_make_stills', True) else 0
        stills_made = 0

        for i, sc in enumerate(scenes):
            scene = {
                "id": str(sc.get("id", i + 1)),
                "type": sc.get("type", "image"),
                "title": sc.get("title") or sc.get("titleCardText") or sc.get("endCardMessage") or f"Sahne {i + 1}",
                "narration": sc.get("narration", ""),
                "videoPrompt": sc.get("videoPrompt", ""),
                "duration_sec": sc.get("duration_sec") or self._estimate_duration(sc, fmt),
                "camera": sc.get("camera", ""),
                "transition": sc.get("transition", "Cut"),
                "image_path": None,
            }

            # Generate still for scenes that have a video prompt and budget allows
            if (still_budget > 0 and stills_made < still_budget
                and scene["videoPrompt"] and scene["type"] not in ("titleCard", "endCard")):
                img = self._generate_scene_still(scene["videoPrompt"], topic, fmt, i)
                if img:
                    scene["image_path"] = img
                    stills_made += 1

            normalized.append(scene)

        self.log(f"Storyboard hazır: {len(normalized)} sahne, {stills_made} still görsel")
        return normalized

    def _generate_scene_still(self, prompt, topic, fmt, idx):
        """fal.ai ile sahne için tek still görsel üret."""
        try:
            from services.image import generate_image
            ratio = fmt.get("ratio", "16:9")
            size = "portrait_16_9" if ratio == "9:16" else "landscape_16_9"
            # fal.ai accepted size names: "square", "landscape_16_9", "portrait_9_16"
            if size == "portrait_16_9":
                size = "portrait_9_16"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = re.sub(r'[^a-z0-9]+', '_', topic.lower())[:20].strip('_')
            fname = f"scene_{slug}_{idx + 1}_{ts}.png"
            path = generate_image(prompt[:500], size=size, filename=fname)
            return path
        except Exception as e:
            self.log(f"Sahne {idx + 1} stilli atlandı: {e}")
            return None

    def _estimate_duration(self, scene, fmt):
        """Tahmini sahne süresi."""
        narration = scene.get("narration", "")
        words = len(str(narration).split())
        if words > 0:
            # ~150 words per minute → 0.4s per word
            return max(2, min(int(words * 0.4), 12))
        # No narration → typical scene length
        if scene.get("type") in ("titleCard", "endCard"):
            return 3
        return 5

    def _scenes_from_short_script(self, scripts, storyboard, topic, business_name, fmt):
        """Kısa-form script blob'undan structured scene listesi parse et.
        Format: '## Sahne N — başlık' veya 'Sahne N (...)' satırlarına dayanır."""
        scenes = []
        if not isinstance(scripts, str):
            scripts = str(scripts or "")

        # Try storyboard string first (more visual-focused)
        text = storyboard if isinstance(storyboard, str) and len(storyboard) > 100 else scripts

        # Split on scene markers
        parts = re.split(r'\n(?=##?\s*(?:Sahne|Scene|Video)\s*\d)', text, flags=re.IGNORECASE)

        for i, part in enumerate(parts[:8]):
            part = part.strip()
            if not part:
                continue

            # Title — first heading or first line
            title_m = re.search(r'^##?\s*(.+?)$', part, re.MULTILINE)
            title = title_m.group(1).strip() if title_m else part.split('\n', 1)[0][:80]

            # Narration / körüklüğü
            narration = ""
            narr_m = re.search(r'(?:Script|Konuşma|Narration)[:\s]+(.+?)(?:\n\n|\Z)', part, re.IGNORECASE | re.DOTALL)
            if narr_m:
                narration = narr_m.group(1).strip()[:300]
            else:
                # Take first paragraph after the title
                lines = [l for l in part.split('\n') if l.strip() and not l.startswith('#')]
                if lines:
                    narration = lines[0][:300]

            # Visual / camera
            cam = ""
            cam_m = re.search(r'(?:Kamera|Camera|Görsel|Visual)[:\s]+(.+?)(?:\n|$)', part, re.IGNORECASE)
            if cam_m:
                cam = cam_m.group(1).strip()[:120]

            # Build a video prompt from title + narration + business context
            video_prompt = (f"Cinematic professional shot for {fmt.get('platform', 'social media')} video. "
                            f"Topic: {topic}. Scene: {title}. "
                            f"{cam if cam else 'Medium shot, natural lighting, modern aesthetic'}. "
                            f"High quality, 4K, shot on iPhone 15 Pro, realistic, authentic.")

            scenes.append({
                "id": str(i + 1),
                "type": "intro" if i == 0 else ("endCard" if i == len(parts) - 1 else "image"),
                "title": title,
                "narration": narration,
                "videoPrompt": video_prompt,
                "camera": cam,
            })

        # Fallback: synthesize 5 generic scenes if parser failed (less than 3 scenes)
        if len(scenes) < 3:
            self.log(f"Scene parser yetersiz ({len(scenes)} sahne), fallback storyboard'a düşüyorum")
            scenes = [
                {"id": "1", "type": "intro", "title": "Hook — Dikkat Çek",
                 "narration": f"{topic} ile ilgili çoğu işletmenin yaptığı hatayı gördüm",
                 "videoPrompt": f"Eye-catching opening shot for {topic}, person looking surprised at camera, modern environment, dramatic lighting, shot on iPhone 15 Pro",
                 "camera": "Yakın çekim, ekstrem close-up"},
                {"id": "2", "type": "image", "title": "Problem — Acıyı Göster",
                 "narration": "Müşteriler bunu fark ediyor ama söylemiyor",
                 "videoPrompt": f"B-roll authentic moment of {topic} related problem in {business_name} context, candid, shallow depth of field, warm natural lighting",
                 "camera": "Medium shot, B-roll"},
                {"id": "3", "type": "image", "title": "Çözüm — Yöntem",
                 "narration": f"{business_name} bu sorunu 3 adımda çözüyor",
                 "videoPrompt": f"Clean modern solution demo for {topic}, organized workspace, professional, optimistic mood, shot on iPhone 16 Pro",
                 "camera": "Wide shot, ekran kaydı"},
                {"id": "4", "type": "image", "title": "Sonuç — Kanıt",
                 "narration": "Test ettim, ortalama %35 fark gördüm",
                 "videoPrompt": f"Statistics graph or before/after comparison for {topic}, data visualization, clean infographic style",
                 "camera": "Close-up grafik"},
                {"id": "5", "type": "endCard", "title": "CTA",
                 "narration": "Profildeki linke tıkla, ücretsiz başla",
                 "videoPrompt": "",
                 "camera": "Logo + CTA card"},
            ]
        return scenes

    def _trigger_videoproducer(self, scenes, topic, slug=None, timestamp=None, fmt=None):
        """fal.ai Kling clipleri + ffmpeg concat ile gerçek MP4 üret.

        Bu fonksiyon `services/fal_video.py` kullanır — Remotion gerektirmez.
        Birden fazla sahne için her birine 5s Kling clip üretilir, sonra
        imageio-ffmpeg ile birleştirilir."""
        try:
            from services.fal_video import make_video_from_scenes

            # Format ratio'yu fal.ai formatına çevir
            ratio = "9:16" if (fmt and fmt.get("ratio") == "9:16") else "16:9"
            if not slug:
                slug = re.sub(r'[^a-z0-9]+', '_', topic.lower())[:30].strip('_') or "video"
            if not timestamp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            self.log(f"fal.ai Kling MP4 üretimi başlıyor — max {self._max_clips} clip × 5s (~${self._max_clips * 0.5:.2f})")
            result = make_video_from_scenes(
                scenes=scenes, topic=topic, slug=slug, timestamp=timestamp,
                ratio=ratio, duration="5", max_clips=self._max_clips,
                log=self.log,
            )
            if result and result.get("mp4_path"):
                self.log(f"MP4 hazır: {result['mp4_path']} ({result.get('clips_count')} clip, ~{result.get('total_seconds')}s)")
                return result["mp4_path"]
            self.log("MP4 üretimi başarısız")
            return None
        except Exception as e:
            self.log(f"MP4 üretimi exception: {e}")
            return None

    def _render_storyboard_html(self, scenes, business_name, topic, video_type, fmt, slug, timestamp):
        """Modern, Polsia-tarzı görsel storyboard HTML."""
        biz = _html.escape(business_name)
        topic_e = _html.escape(topic)
        ratio = fmt.get("ratio", "16:9")
        is_vertical = ratio == "9:16"

        scene_cards = ""
        for i, sc in enumerate(scenes):
            title = _html.escape(str(sc.get("title", "")))
            narration = _html.escape(str(sc.get("narration", "")))
            cam = _html.escape(str(sc.get("camera", "")))
            duration = sc.get("duration_sec", 5)
            scene_type = _html.escape(str(sc.get("type", "image")))
            transition = _html.escape(str(sc.get("transition", "Cut")))
            prompt_e = _html.escape(str(sc.get("videoPrompt", "")))

            # Image block
            img_path = sc.get("image_path")
            if img_path:
                try:
                    abs_path = Path(img_path).resolve()
                    img_html = f'<img src="file://{abs_path}" alt="Scene {i+1}" loading="lazy">'
                except Exception:
                    img_html = f'<div class="placeholder">Sahne {i+1}</div>'
            else:
                img_html = f'<div class="placeholder">{title[:30] or f"Sahne {i+1}"}</div>'

            scene_cards += f"""
            <article class="scene" style="aspect-ratio: {('9/16' if is_vertical else '16/9')}">
              <div class="scene-frame">
                {img_html}
                <div class="scene-overlay">
                  <span class="scene-number">{i+1:02d}</span>
                  <span class="scene-type">{scene_type}</span>
                  <span class="scene-duration">{duration}s</span>
                </div>
              </div>
              <div class="scene-meta">
                <h3>{title}</h3>
                {f'<p class="narration">"{narration}"</p>' if narration else ''}
                {f'<div class="camera-note"><strong>Kamera:</strong> {cam}</div>' if cam else ''}
                <details class="prompt-details">
                  <summary>fal.ai prompt</summary>
                  <pre>{prompt_e}</pre>
                </details>
                <div class="transition">→ {transition}</div>
              </div>
            </article>"""

        total_duration = sum(s.get("duration_sec", 5) for s in scenes)

        # Build timeline cells with real durations
        timeline_cells = "".join(
            f'<div class="timeline-cell" style="--w: {s.get("duration_sec", 5)}">'
            f'<div class="num">{i+1:02d}</div>'
            f'<div class="dur">{s.get("duration_sec", 5)}s</div></div>'
            for i, s in enumerate(scenes)
        )

        return self._write_storyboard_file(
            biz=biz, topic_e=topic_e, video_type=video_type, fmt=fmt,
            scene_cards=scene_cards, scenes_count=len(scenes),
            total_duration=total_duration, is_vertical=is_vertical,
            timeline_cells=timeline_cells,
            slug=slug, timestamp=timestamp
        )

    def _write_storyboard_file(self, biz, topic_e, video_type, fmt, scene_cards,
                                scenes_count, total_duration, is_vertical,
                                timeline_cells, slug, timestamp):
        ratio = _html.escape(fmt.get("ratio", "16:9"))
        platform = _html.escape(fmt.get("platform", ""))
        duration_str = _html.escape(fmt.get("duration", ""))

        html_doc = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{topic_e} — Storyboard · {biz}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0a0a0c;
  --surface: #131318;
  --card: #1a1a22;
  --text: #f0eee8;
  --muted: #6b7280;
  --accent: #e85d26;
  --accent2: #34d399;
  --rule: rgba(255,255,255,0.08);
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}}
.shell {{ max-width: 1440px; margin: 0 auto; padding: 48px 32px 80px; }}

header.cover {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 32px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--rule);
  margin-bottom: 48px;
}}
.cover-left .kicker {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 12px;
}}
.cover-left h1 {{
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin: 0 0 8px;
  line-height: 1.1;
  max-width: 800px;
}}
.cover-left .biz {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--muted);
}}
.stats {{
  display: flex;
  gap: 24px;
  font-family: 'JetBrains Mono', monospace;
}}
.stat {{ text-align: right; }}
.stat .v {{ font-size: 22px; font-weight: 700; color: var(--text); }}
.stat .l {{ font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); margin-top: 4px; }}

.format-strip {{
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 14px;
  padding: 16px 24px;
  margin-bottom: 32px;
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
  align-items: center;
}}
.format-strip .pill {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(232,93,38,0.15);
  color: var(--accent);
  border: 1px solid rgba(232,93,38,0.3);
}}
.format-strip .item {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--muted);
}}
.format-strip .item strong {{ color: var(--text); }}

.timeline {{
  display: flex;
  gap: 4px;
  padding: 16px;
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 14px;
  margin-bottom: 48px;
  overflow-x: auto;
}}
.timeline-cell {{
  flex: var(--w, 1);
  min-width: 60px;
  background: linear-gradient(135deg, rgba(232,93,38,0.25), rgba(232,93,38,0.08));
  border: 1px solid rgba(232,93,38,0.3);
  border-radius: 8px;
  padding: 8px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--text);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}}
.timeline-cell .num {{ font-size: 11px; font-weight: 700; }}
.timeline-cell .dur {{ font-size: 9px; opacity: 0.7; }}

.scenes {{
  display: grid;
  grid-template-columns: {('repeat(auto-fill, minmax(260px, 1fr))' if is_vertical else 'repeat(auto-fill, minmax(360px, 1fr))')};
  gap: 28px;
}}
.scene {{
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: 18px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform 0.15s, border-color 0.15s;
}}
.scene:hover {{ transform: translateY(-3px); border-color: rgba(232,93,38,0.3); }}
.scene-frame {{
  position: relative;
  background: #000;
  overflow: hidden;
}}
.scene-frame img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.placeholder {{
  width: 100%; height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a22, #2a2a35);
  color: var(--muted);
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  text-align: center;
  padding: 24px;
  min-height: 240px;
}}
.scene-overlay {{
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
}}
.scene-overlay span {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 6px;
  backdrop-filter: blur(12px);
  background: rgba(0,0,0,0.6);
  color: #fff;
}}
.scene-number {{ background: var(--accent) !important; color: #000 !important; }}
.scene-duration {{ margin-left: auto; }}

.scene-meta {{ padding: 20px 22px 24px; flex: 1; display: flex; flex-direction: column; }}
.scene-meta h3 {{
  font-size: 17px;
  font-weight: 700;
  margin: 0 0 12px;
  letter-spacing: -0.01em;
  color: var(--text);
}}
.narration {{
  font-style: italic;
  font-size: 14px;
  line-height: 1.55;
  color: #c5c2bb;
  margin: 0 0 12px;
  border-left: 3px solid var(--accent);
  padding-left: 12px;
}}
.camera-note {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 12px;
}}
.camera-note strong {{ color: var(--accent2); font-weight: 600; }}
.prompt-details {{
  margin-top: auto;
  border-top: 1px solid var(--rule);
  padding-top: 12px;
}}
.prompt-details summary {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  cursor: pointer;
  list-style: none;
}}
.prompt-details summary::-webkit-details-marker {{ display: none; }}
.prompt-details summary::before {{ content: '▸ '; font-family: monospace; }}
.prompt-details[open] summary::before {{ content: '▾ '; }}
.prompt-details pre {{
  margin: 8px 0 0;
  padding: 10px 12px;
  background: rgba(0,0,0,0.4);
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: #aaa;
  white-space: pre-wrap;
  word-break: break-word;
}}
.transition {{
  text-align: center;
  margin-top: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}

footer {{
  margin-top: 64px;
  padding-top: 32px;
  border-top: 1px solid var(--rule);
  display: flex;
  justify-content: space-between;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--muted);
}}

@media (max-width: 720px) {{
  .shell {{ padding: 32px 18px 60px; }}
  .cover-left h1 {{ font-size: 30px; }}
  .scenes {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="shell">
  <header class="cover">
    <div class="cover-left">
      <div class="kicker">video storyboard · {_html.escape(video_type)}</div>
      <h1>{topic_e}</h1>
      <div class="biz">{biz}</div>
    </div>
    <div class="stats">
      <div class="stat"><div class="v">{scenes_count}</div><div class="l">Sahne</div></div>
      <div class="stat"><div class="v">{total_duration}s</div><div class="l">Toplam</div></div>
      <div class="stat"><div class="v">{ratio}</div><div class="l">Oran</div></div>
    </div>
  </header>

  <div class="format-strip">
    <span class="pill">{_html.escape(video_type)}</span>
    <span class="item"><strong>Süre:</strong> {duration_str}</span>
    <span class="item"><strong>Platform:</strong> {platform}</span>
    <span class="item"><strong>Oran:</strong> {ratio}</span>
  </div>

  <div class="timeline">
    {timeline_cells}
  </div>

  <section class="scenes">
    {scene_cards}
  </section>

  <footer>
    <span>goat-bot videomaker · {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
    <span>{_html.escape(slug)}</span>
  </footer>
</div>
</body>
</html>"""

        out_dir = OUTPUT_DIR / "videos"
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / f"{timestamp}_{slug}_storyboard.html"
        html_path.write_text(html_doc, encoding="utf-8")
        self.log(f"Storyboard HTML: {html_path}")
        return str(html_path)

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
