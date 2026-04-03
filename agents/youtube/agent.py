"""YouTube Agent — YouTube channel management, upload, SEO, scheduling."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, BASE_DIR, DATA_DIR, OUTPUT_DIR


class YouTubeAgent(BaseAgent):
    agent_id = "youtube"
    name = "YouTube"
    role = "YouTube automation — upload, SEO optimization, scheduling, analytics"
    category = "production"

    # YouTube category IDs
    CATEGORIES = {
        "education": "27",
        "science": "28",
        "entertainment": "24",
        "howto": "26",
        "news": "25",
        "people": "22",
        "comedy": "23",
        "gaming": "20",
        "music": "10",
        "sports": "17",
        "travel": "19",
        "tech": "28",
    }

    def run(self, action: str = "optimize", video_path: str = "",
            title: str = "", topic: str = "", language: str = "tr",
            category: str = "education", schedule_time: str = "") -> dict:
        self.log("YouTube agent started")
        config = self.load_config()
        business_name = config.get("agency_name", "My Agency")

        if action == "optimize":
            return self._optimize_metadata(title, topic, language, category, business_name)
        elif action == "upload":
            return self._upload_video(video_path, title, topic, language, category, schedule_time)
        elif action == "thumbnail":
            return self._generate_thumbnail(title, topic, business_name)
        elif action == "strategy":
            return self._channel_strategy(business_name, topic, language)
        elif action == "calendar":
            return self._content_calendar(business_name, topic, language)
        elif action == "script":
            return self._generate_script(topic, language, business_name)
        elif action == "shorts":
            return self._plan_shorts(topic, language, business_name)
        else:
            return self._optimize_metadata(title, topic, language, category, business_name)

    # ═══════════════════════════════════════
    # ACTION: optimize — SEO metadata generation
    # ═══════════════════════════════════════

    def _optimize_metadata(self, title, topic, language, category, business_name):
        self.log(f"Optimizing metadata: {topic or title}")

        lang = "Türkçe" if language == "tr" else "English"
        subject = topic or title or "video"

        prompt = f"""Sen YouTube SEO uzmanısın. Aşağıdaki video için optimize edilmiş metadata oluştur.

Konu: {subject}
Dil: {lang}
Kanal: {business_name}
Kategori: {category}

Şunları oluştur:

1. **Başlık** (5 alternatif, max 60 karakter, tıklama oranı yüksek)
   - Sayı kullan (5, 10, 100)
   - Güçlü kelimeler (şok, gizli, inanılmaz)
   - Keyword başta olsun

2. **Açıklama** (2000+ karakter)
   - İlk 2 satır çok önemli (arama sonuçlarında görünür)
   - Zaman damgaları (Chapters)
   - İlgili linkler bölümü
   - Abone CTA
   - Hashtag'ler

3. **Etiketler/Tags** (20-30 tag)
   - Ana keyword
   - Long-tail keywords
   - Rakip kanalların kullandığı taglar
   - Trending keywords

4. **Hashtag'ler** (3-5 adet, başlığın altında görünür)

5. **Thumbnail metin önerisi**
   - Max 4-5 kelime
   - Kontrast renk önerisi
   - Yüz ifadesi önerisi (varsa)

6. **Yayınlama önerileri**
   - En iyi yayın saati
   - En iyi gün
   - İlk 24 saat stratejisi

{lang} yaz."""

        metadata = self.call_claude(prompt)
        if not metadata:
            metadata = self._fallback_metadata(subject, category, language, business_name)

        # Save metadata
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = subject.lower().replace(" ", "_")[:30]
        meta_data = {
            "topic": subject,
            "language": language,
            "category": category,
            "business_name": business_name,
            "metadata": metadata,
            "created_at": timestamp,
        }

        self.save_data(f"youtube/{timestamp}_{slug}_metadata.json", meta_data)

        results = {
            "status": "ok",
            "summary": f"YouTube metadata oluşturuldu: {subject}",
            "metrics": {
                "topic": subject,
                "category": category,
                "language": language,
                "timestamp": datetime.now().isoformat(),
            },
            "youtube": meta_data,
            "recommendations": [
                "Başlık: İlk 40 karakterde ana keyword olsun",
                "Thumbnail: Yüz + büyük metin + kontrast renk = yüksek CTR",
                "Açıklama: İlk 2 satır SEO için kritik",
                "Tags: Rakip analizi yapın — benzer videoların taglarını kullanın",
                "İlk 24 saat: Tüm sosyal medyada paylaşın",
            ],
        }

        self.save_output("youtube_report.json", results)
        self.log("Metadata optimization completed")
        return results

    # ═══════════════════════════════════════
    # ACTION: upload — Upload via YouTube API
    # ═══════════════════════════════════════

    def _upload_video(self, video_path, title, topic, language, category, schedule_time):
        self.log(f"Upload requested: {video_path or 'no path'}")

        # Find latest rendered video if no path
        if not video_path:
            videos_dir = OUTPUT_DIR / "videos"
            if videos_dir.exists():
                rendered = sorted(videos_dir.glob("*.mp4"), reverse=True)
                if rendered:
                    video_path = str(rendered[0])

            # Also check Remotion output
            if not video_path:
                remotion_out = BASE_DIR / "Remotion-Video-main 2" / "my-video" / "out" / "video.mp4"
                if remotion_out.exists():
                    video_path = str(remotion_out)

        if not video_path or not Path(video_path).exists():
            return {
                "status": "error",
                "summary": "Video dosyası bulunamadı — önce VideoProducer ile render yapın",
                "metrics": {},
                "recommendations": [
                    "VideoProducer agent'ı ile video render edin",
                    "Veya video_path parametresi ile dosya yolu belirtin",
                ],
            }

        # Generate metadata first
        subject = topic or title or "Video"
        meta_result = self._optimize_metadata(title or subject, topic, language, category,
                                               self.load_config().get("agency_name", "My Agency"))

        # Try upload via yt-dlp or YouTube API
        upload_result = self._try_upload(video_path, title or subject, category, schedule_time)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        upload_data = {
            "video_path": video_path,
            "title": title or subject,
            "category": category,
            "schedule_time": schedule_time,
            "upload_result": upload_result,
            "metadata": meta_result.get("youtube", {}),
            "created_at": timestamp,
        }

        self.save_data(f"youtube/{timestamp}_upload.json", upload_data)

        return {
            "status": upload_result.get("status", "pending"),
            "summary": upload_result.get("summary", "Upload hazırlandı"),
            "metrics": {
                "video_path": video_path,
                "file_size_mb": round(Path(video_path).stat().st_size / 1024 / 1024, 1),
                "schedule_time": schedule_time or "hemen",
            },
            "youtube": upload_data,
            "recommendations": [
                "Video yüklendikten sonra thumbnail ekleyin",
                "İlk 24 saat içinde tüm sosyal medyada paylaşın",
                "Yorumlara cevap verin — engagement artırır",
            ],
        }

    def _try_upload(self, video_path, title, category, schedule_time):
        """Try uploading via google-api-python-client or return manual instructions."""
        # Check for YouTube API credentials
        creds_path = DATA_DIR / "config" / "youtube_credentials.json"
        token_path = DATA_DIR / "config" / "youtube_token.json"

        if not creds_path.exists():
            return {
                "status": "manual",
                "summary": "YouTube API credentials bulunamadı — manuel upload gerekli",
                "instructions": [
                    "1. Google Cloud Console'dan YouTube Data API v3 etkinleştirin",
                    "2. OAuth 2.0 credentials oluşturun (Desktop app)",
                    "3. credentials.json'ı data/config/youtube_credentials.json olarak kaydedin",
                    "4. İlk çalıştırmada tarayıcıda yetkilendirme yapın",
                    f"5. Video: {video_path}",
                    f"6. Başlık: {title}",
                ],
            }

        # Try google API upload
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

            creds = None
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as f:
                    f.write(creds.to_json())

            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": title,
                    "categoryId": self.CATEGORIES.get(category, "27"),
                    "defaultLanguage": "tr",
                },
                "status": {
                    "privacyStatus": "private",  # Start as private for safety
                    "selfDeclaredMadeForKids": False,
                },
            }

            if schedule_time:
                body["status"]["privacyStatus"] = "private"
                body["status"]["publishAt"] = schedule_time

            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
            response = request.execute()

            video_id = response.get("id", "")
            self.log(f"Upload successful: https://youtube.com/watch?v={video_id}")

            return {
                "status": "ok",
                "summary": f"Video yüklendi: https://youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
            }

        except ImportError:
            return {
                "status": "manual",
                "summary": "google-api-python-client kurulu değil",
                "instructions": [
                    "pip install google-api-python-client google-auth-oauthlib",
                    f"Video: {video_path}",
                ],
            }
        except Exception as e:
            return {
                "status": "error",
                "summary": f"Upload hatası: {str(e)[:200]}",
            }

    # ═══════════════════════════════════════
    # ACTION: thumbnail — Generate thumbnail
    # ═══════════════════════════════════════

    def _generate_thumbnail(self, title, topic, business_name):
        self.log(f"Generating thumbnail: {title or topic}")

        subject = title or topic or "Video"

        # Generate via fal.ai
        thumb_path = None
        try:
            from services.image import generate_image
            prompt = (
                f"YouTube video thumbnail, professional, eye-catching, "
                f"bold text '{subject[:30]}', bright colors, high contrast, "
                f"clean design, 1280x720, click-worthy, {business_name}"
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            thumb_path = generate_image(prompt, size="landscape_16_9",
                                        filename=f"yt_thumb_{timestamp}.png")
            if thumb_path:
                self.log(f"Thumbnail generated: {thumb_path}")
        except Exception as e:
            self.log(f"Thumbnail generation failed: {e}")

        # Generate thumbnail brief via Claude
        brief_prompt = f"""YouTube thumbnail tasarım brief'i oluştur:

Başlık: {subject}
Kanal: {business_name}

Brief:
1. Arka plan rengi / gradient
2. Ana metin (max 4 kelime, BÜYÜK HARF)
3. Font stili ve boyutu
4. İkon / görsel element
5. Renk şeması (yüksek kontrast)
6. Yüz ifadesi önerisi (varsa)
7. A/B test varyasyonu

Kısa ve net yaz. Türkçe."""

        brief = self.call_claude(brief_prompt)
        if not brief:
            brief = f"""# Thumbnail Brief — {subject}

## Metin: {subject[:20].upper()}
## Arka plan: Koyu mavi → turuncu gradient
## Font: Bold Sans-Serif, 72pt
## Renk: Beyaz metin, turuncu vurgu
## Element: Konu ile ilgili ikon/sembol
## Kontrast: Yüksek — 3 metreden okunabilir olmalı
"""

        return {
            "status": "ok",
            "summary": f"Thumbnail {'oluşturuldu' if thumb_path else 'brief hazırlandı'}: {subject}",
            "metrics": {
                "image_generated": bool(thumb_path),
                "image_path": thumb_path,
            },
            "thumbnail_brief": brief,
            "recommendations": [
                "Thumbnail'de max 4-5 kelime kullanın",
                "Kontrast renk: sarı/turuncu metin + koyu arka plan",
                "Yüz ekleyin — CTR %30 artırır",
                "A/B test yapın — Community tab ile oy toplayın",
                "Boyut: 1280x720, max 2MB",
            ],
        }

    # ═══════════════════════════════════════
    # ACTION: strategy — Channel strategy
    # ═══════════════════════════════════════

    def _channel_strategy(self, business_name, topic, language):
        self.log("Generating channel strategy")
        lang = "Türkçe" if language == "tr" else "English"
        niche = self.load_config().get("niche", topic or "dijital pazarlama")

        prompt = f"""YouTube kanal stratejisi oluştur:

Kanal: {business_name}
Niche: {niche}
Dil: {lang}

Kapsamlı strateji:
1. **Kanal Konumlandırma** — USP, hedef kitle, ton
2. **İçerik Sütunları** (3-5 pillar topic)
3. **Video Formatları** — kısa/uzun/shorts karışımı
4. **Yayın Takvimi** — haftalık plan
5. **SEO Stratejisi** — keyword hedefleme
6. **Büyüme Taktikleri** — ilk 1000 abone
7. **Monetizasyon** — gelir kaynakları
8. **Ekipman/Araç** önerileri
9. **3 Aylık Yol Haritası**

{lang} yaz, actionable ve spesifik."""

        strategy = self.call_claude(prompt)
        if not strategy:
            strategy = f"""# YouTube Kanal Stratejisi — {business_name}

## Niche: {niche}

### İçerik Sütunları
1. Eğitim videoları (How-to)
2. Sektör haberleri ve trendler
3. Case study / başarı hikayeleri
4. Araç incelemeleri
5. Behind the scenes

### Yayın Takvimi
- Pzt: Kısa ipucu (Shorts)
- Çar: Ana video (8-15 dk)
- Cum: Shorts
- Pzr: Community post

### İlk 1000 Abone
1. Tutarlı yayın (haftada 2+ video)
2. Niche odaklı — dağılma
3. Trend konulara hızlı tepki
4. Diğer kanallarla collab
5. Sosyal medyada paylaşım
"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"youtube/{timestamp}_strategy.json", {"strategy": strategy, "business_name": business_name})

        return {
            "status": "ok",
            "summary": f"YouTube kanal stratejisi oluşturuldu — {business_name}",
            "metrics": {"niche": niche, "timestamp": datetime.now().isoformat()},
            "strategy": strategy,
            "recommendations": [
                "İlk 30 video: tutarlılık > kalite",
                "Shorts ile keşfet sayfasına çıkın",
                "İlk 48 saat kritik — tüm platformlarda paylaşın",
                "Thumbnail A/B testi yapın",
            ],
        }

    # ═══════════════════════════════════════
    # ACTION: calendar — Content calendar
    # ═══════════════════════════════════════

    def _content_calendar(self, business_name, topic, language):
        self.log("Generating YouTube content calendar")
        lang = "Türkçe" if language == "tr" else "English"
        niche = self.load_config().get("niche", topic or "dijital pazarlama")

        prompt = f"""30 günlük YouTube içerik takvimi oluştur:

Kanal: {business_name}
Niche: {niche}
Dil: {lang}

Her video için:
- Gün ve tür (Video / Short / Community)
- Başlık (SEO optimize)
- Kısa açıklama (1 cümle)
- Tahmini süre
- Zorluk seviyesi (kolay/orta/zor)

Haftada: 2 video + 3 shorts + 2 community post
{lang} yaz."""

        calendar = self.call_claude(prompt)
        if not calendar:
            calendar = f"""# 30 Günlük YouTube Takvimi — {business_name}

## Hafta 1
- **Pzt:** Short — {niche} için 1 dakikada ipucu
- **Sal:** Community — Haftanın anketi
- **Çar:** Video — {niche} başlangıç rehberi (10dk)
- **Per:** Short — Hızlı tutorial
- **Cum:** Community — Kaynak paylaşımı
- **Cmt:** Video — Araç incelemesi (8dk)
- **Paz:** Short — Motivasyon / alıntı

## Hafta 2-4
(Aynı formatta, farklı konularla devam)
"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"youtube/{timestamp}_calendar.json", {"calendar": calendar, "business_name": business_name})

        return {
            "status": "ok",
            "summary": f"30 günlük YouTube takvimi oluşturuldu — {business_name}",
            "metrics": {"niche": niche, "days": 30},
            "calendar": calendar,
            "recommendations": [
                "Takvime sadık kalın — tutarlılık çok önemli",
                "Batch filming yapın — haftada 1 gün çekim",
                "Shorts'ları ana videodan kesin — ek iş yükü yok",
            ],
        }

    # ═══════════════════════════════════════
    # ACTION: script — Video script generation
    # ═══════════════════════════════════════

    def _generate_script(self, topic, language, business_name):
        self.log(f"Generating script: {topic}")
        lang = "Türkçe" if language == "tr" else "English"

        prompt = f"""YouTube videosu için detaylı script yaz:

Konu: {topic}
Kanal: {business_name}
Dil: {lang}
Hedef süre: 8-12 dakika

Script formatı:
1. **HOOK (0:00-0:30)** — İlk 30 saniye (çok önemli!)
   - Dikkat çekici açılış
   - "Bu videoda öğrenecekleriniz..."
   - Neden izlemeli

2. **GİRİŞ (0:30-1:30)**
   - Konuya giriş
   - Neden önemli

3. **ANA İÇERİK (1:30-9:00)**
   - Bölüm 1 (3 dakika)
   - Bölüm 2 (3 dakika)
   - Bölüm 3 (2 dakika)

4. **SONUÇ + CTA (9:00-10:00)**
   - Özet
   - Abone ol + bildirim aç
   - Sonraki video teaser

Her bölüm için:
- Konuşma metni (kelimesi kelimesine)
- [Ekran] notları (ne gösterilecek)
- [B-Roll] notları (ek görsel)
- Zaman damgası

{lang} yaz."""

        script = self.call_claude(prompt)
        if not script:
            script = f"""# Video Script: {topic}

## HOOK (0:00-0:30)
[Kameraya bakarak]
"Herkese merhaba! Bugün {topic} hakkında konuşacağız. Bu video sonunda, [ana fayda]."

## GİRİŞ (0:30-1:30)
[B-Roll: Konu ile ilgili görsel]
"{topic} neden önemli? Çünkü [sebep]..."

## ANA İÇERİK
### Bölüm 1 (1:30-4:00)
[Ekran kaydı / demo]
"İlk olarak, [konu]..."

### Bölüm 2 (4:00-7:00)
"Şimdi ikinci noktaya geçelim..."

### Bölüm 3 (7:00-9:00)
"Son olarak, [konu]..."

## SONUÇ + CTA (9:00-10:00)
"Özetlemek gerekirse: [3 ana nokta].
Beğendiyseniz like atın, abone olun, bildirim zilini açın.
Bir sonraki videoda [teaser]."
"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topic.lower().replace(" ", "_")[:30] if topic else "untitled"
        self.save_data(f"youtube/{timestamp}_{slug}_script.json", {"script": script, "topic": topic})

        # Save as markdown
        scripts_dir = OUTPUT_DIR / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        md_path = scripts_dir / f"{timestamp}_{slug}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(script)

        return {
            "status": "ok",
            "summary": f"Video script oluşturuldu: {topic}",
            "metrics": {"topic": topic, "word_count": len(script.split()), "md_path": str(md_path)},
            "script": script,
            "recommendations": [
                "Script'i sesli prova edin — süreyi ölçün",
                "Hook (ilk 30s) en kritik kısım — dikkat çekmeli",
                "Doğal konuşun — script'i ezberlemek yerine özümseyerek anlatın",
                "VideoProducer agent ile bu script'ten otomatik video üretin",
            ],
        }

    # ═══════════════════════════════════════
    # ACTION: shorts — Plan YouTube Shorts
    # ═══════════════════════════════════════

    def _plan_shorts(self, topic, language, business_name):
        self.log(f"Planning Shorts: {topic}")
        lang = "Türkçe" if language == "tr" else "English"
        niche = self.load_config().get("niche", topic or "dijital pazarlama")

        prompt = f"""10 adet YouTube Shorts fikri ve script'i oluştur:

Kanal: {business_name}
Niche: {niche}
Dil: {lang}

Her Short için:
- Başlık (dikkat çekici)
- Script (15-60 saniye, kelimesi kelimesine)
- Hook (ilk 2 saniye)
- Görsel açıklama
- Trending ses/müzik önerisi
- Hashtag'ler

Türler karışık olsun:
- Hızlı ipucu
- Before/After
- "Bunu biliyor muydunuz?"
- Trend + niche combo
- Listicle (3 şey, 5 hata, vs.)

{lang} yaz."""

        shorts = self.call_claude(prompt)
        if not shorts:
            shorts = f"""# YouTube Shorts Planı — {business_name}

## Short 1: "{niche} hakkında 3 şey"
**Hook:** "Bunu bilmiyorsanız para kaybediyorsunuz"
**Script:** (15s) 3 madde, hızlı geçiş
**Hashtag:** #shorts #{niche.replace(' ', '')} #ipucu

## Short 2: "1 dakikada öğren"
**Hook:** "60 saniyede {niche} öğrenin"
**Script:** Hızlı tutorial
**Hashtag:** #shorts #tutorial #öğren

(8 Short daha — Claude CLI ile oluşturulur)
"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"youtube/{timestamp}_shorts.json", {"shorts": shorts, "topic": topic})

        return {
            "status": "ok",
            "summary": f"10 YouTube Shorts planlandı — {niche}",
            "metrics": {"niche": niche, "shorts_count": 10},
            "shorts": shorts,
            "recommendations": [
                "Günde 1-3 Short paylaşın — keşfet algoritması sever",
                "İlk 2 saniye hook çok kritik",
                "Trending ses kullanın — reach artırır",
                "Dikey format (9:16) — 1080x1920",
                "Ana videodan Short kesmek en kolay yöntem",
            ],
        }

    # ═══════════════════════════════════════
    # HELPER: Fallback metadata
    # ═══════════════════════════════════════

    def _fallback_metadata(self, subject, category, language, business_name):
        return f"""# YouTube Metadata — {subject}

## Başlık Alternatifleri
1. {subject} — Bilmeniz Gereken Her Şey
2. {subject}: Adım Adım Rehber
3. {subject} Hakkında 5 Şok Edici Gerçek
4. {subject} Nasıl Yapılır? (2025 Güncel)
5. {subject} — Kimsenin Söylemediği Gerçekler

## Açıklama
{subject} hakkında kapsamlı rehber. Bu videoda {subject} konusunu detaylı inceliyoruz.

⏱️ Zaman Damgaları:
0:00 Giriş
0:30 {subject} nedir?
2:00 Neden önemli?
5:00 Nasıl yapılır?
8:00 İpuçları
9:30 Sonuç

🔔 Abone olun: [Kanal linki]

## Tags
{subject}, {subject} nasıl, {subject} rehber, {subject} türkçe, {business_name}

## Hashtag
#{subject.replace(' ', '')} #türkçe #{category}
"""
