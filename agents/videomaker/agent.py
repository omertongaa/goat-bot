"""VideoMaker Agent — Video content planning, scripting, and storyboarding."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class VideoMakerAgent(BaseAgent):
    agent_id = "videomaker"
    name = "VideoMaker"
    role = "Creates video scripts, storyboards, and short-form content plans"
    category = "creative"

    # Video format presets
    FORMATS = {
        "reels": {"duration": "15-60s", "ratio": "9:16", "platform": "Instagram/TikTok"},
        "youtube_short": {"duration": "30-60s", "ratio": "9:16", "platform": "YouTube Shorts"},
        "youtube": {"duration": "5-15min", "ratio": "16:9", "platform": "YouTube"},
        "tiktok": {"duration": "15-60s", "ratio": "9:16", "platform": "TikTok"},
        "ad_video": {"duration": "15-30s", "ratio": "16:9", "platform": "Google/Meta Ads"},
        "testimonial": {"duration": "30-90s", "ratio": "16:9", "platform": "Website/Social"},
        "explainer": {"duration": "60-120s", "ratio": "16:9", "platform": "Website/YouTube"},
        "presentation": {"duration": "3-10min", "ratio": "16:9", "platform": "Meeting/Webinar"},
    }

    def run(self, video_type: str = "reels", business_name: str = "",
            topic: str = "", target_audience: str = "", count: int = 3) -> dict:
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

        # Generate video scripts via Claude
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

        # Generate storyboard brief
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

        # Save results
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

        # Try generating thumbnail via fal.ai
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
        self.log("VideoMaker agent completed")
        return results

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
