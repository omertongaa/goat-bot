"""Social Agent — Social media management, scheduling, and strategy."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class SocialAgent(BaseAgent):
    agent_id = "social"
    name = "Social"
    role = "Social media strategy, content planning, and audience growth"
    category = "marketing"

    PLATFORMS = {
        "instagram": {"name": "Instagram", "post_types": ["feed", "story", "reel", "carousel"], "max_hashtags": 30},
        "tiktok": {"name": "TikTok", "post_types": ["video", "photo", "carousel"], "max_hashtags": 10},
        "linkedin": {"name": "LinkedIn", "post_types": ["post", "article", "carousel", "poll"], "max_hashtags": 5},
        "twitter": {"name": "X (Twitter)", "post_types": ["tweet", "thread", "poll"], "max_hashtags": 3},
        "facebook": {"name": "Facebook", "post_types": ["post", "reel", "story", "event"], "max_hashtags": 10},
        "youtube": {"name": "YouTube", "post_types": ["video", "short", "community"], "max_hashtags": 15},
    }

    def run(self, action: str = "strategy", platform: str = "instagram",
            business_name: str = "", niche: str = "") -> dict:
        self.log("Social agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "My Agency")
        if not niche:
            niche = config.get("niche", "dijital pazarlama")

        plat = self.PLATFORMS.get(platform, self.PLATFORMS["instagram"])
        self.log(f"Action: {action} | Platform: {plat['name']}")

        if action == "strategy":
            content = self._generate_strategy(business_name, niche, plat, platform)
        elif action == "hashtags":
            content = self._generate_hashtags(niche, plat, platform)
        elif action == "bio":
            content = self._generate_bio(business_name, niche, plat, platform)
        elif action == "audit":
            content = self._audit_profile(business_name, niche, plat, platform)
        elif action == "growth":
            content = self._growth_plan(business_name, niche, plat, platform)
        else:
            content = self._generate_strategy(business_name, niche, plat, platform)

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        social_data = {
            "action": action,
            "platform": platform,
            "platform_name": plat["name"],
            "business_name": business_name,
            "niche": niche,
            "content": content,
            "created_at": timestamp,
        }

        self.save_data(f"social/{timestamp}_{platform}_{action}.json", social_data)

        results = {
            "status": "ok",
            "summary": f"{plat['name']} {action} planı oluşturuldu — {business_name}",
            "metrics": {
                "platform": plat["name"],
                "action": action,
                "post_types": plat["post_types"],
                "timestamp": datetime.now().isoformat(),
            },
            "social": social_data,
            "recommendations": [
                "Tutarlılık anahtar — haftada minimum 3-5 paylaşım",
                "Engagement > takipçi sayısı — yorumlara cevap verin",
                "Trending audio/hashtag kullanın",
                "Analytics'i haftalık kontrol edin",
                "UGC (kullanıcı içeriği) teşvik edin",
            ],
        }

        self.save_output("social_report.json", results)
        self.log("Social agent completed")
        return results

    def _generate_strategy(self, business_name, niche, plat, platform):
        prompt = f"""Sosyal medya stratejisi oluştur:

İşletme: {business_name}
Sektör: {niche}
Platform: {plat['name']}
Post türleri: {', '.join(plat['post_types'])}

Detaylı strateji:
1. **Profil Optimizasyonu** — bio, profil resmi, highlight'lar
2. **İçerik Stratejisi** — pillar topics, içerik karışımı (80/20 kuralı)
3. **Paylaşım Takvimi** — haftada kaç post, hangi günler, saatler
4. **Hashtag Stratejisi** — branded, niche, trending (max {plat['max_hashtags']})
5. **Engagement Stratejisi** — yorum, DM, collaboration
6. **Büyüme Taktikleri** — organik + paid
7. **KPI'lar** — takipçi artışı, engagement rate, reach, saves
8. **3 Aylık Yol Haritası**

Türkçe, pratik ve actionable yaz."""

        result = self.call_claude(prompt)
        if not result:
            return f"""# {plat['name']} Stratejisi — {business_name}

## İçerik Karışımı
- %40 Eğitim (ipuçları, rehberler)
- %20 Behind the scenes
- %20 Sosyal kanıt (testimonial, sonuçlar)
- %10 Eğlence/trend
- %10 Promosyon/CTA

## Paylaşım Takvimi
- Pzt/Çar/Cum: Feed post
- Sal/Per: Story
- Haftada 2: Reel/Video

## Hashtag Stratejisi
- 5 branded hashtag
- 10 niche hashtag
- 5-10 trending hashtag
- Toplam max {plat['max_hashtags']}

## KPI Hedefleri (3 ay)
- Engagement rate: %3-5
- Takipçi artışı: %10/ay
- Reach: %20 artış
"""
        return result

    def _generate_hashtags(self, niche, plat, platform):
        prompt = f"""{plat['name']} için hashtag seti oluştur:
Sektör: {niche}
Max hashtag: {plat['max_hashtags']}

3 set oluştur:
1. **Awareness seti** — geniş kitleye ulaşma
2. **Niche seti** — hedef kitleye ulaşma
3. **Engagement seti** — etkileşim artırma

Her sette: büyük (1M+), orta (100K-1M), küçük (10K-100K) hacimli hashtagler olsun.
Türkçe ve İngilizce karışık."""

        result = self.call_claude(prompt)
        return result or f"# Hashtag Setleri — {niche}\n\n#{niche.replace(' ', '')} #dijitalpazarlama #business #growth"

    def _generate_bio(self, business_name, niche, plat, platform):
        prompt = f"""{plat['name']} bio/profil metni yaz:
İşletme: {business_name}
Sektör: {niche}

5 farklı versiyon:
1. Profesyonel
2. Yaratıcı
3. Minimalist
4. Değer odaklı
5. Kişisel/samimi

Her biri max 150 karakter. Emoji kullan. CTA ekle.
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# Bio Önerileri — {business_name}\n\n{niche} | AI destekli çözümler | DM ile iletişime geçin"

    def _audit_profile(self, business_name, niche, plat, platform):
        prompt = f"""{plat['name']} profil audit checklist'i oluştur:
İşletme: {business_name}
Sektör: {niche}

Kontrol listesi:
1. Profil resmi
2. Bio/açıklama
3. Link
4. Highlight/öne çıkanlar
5. Son 9 post grid uyumu
6. İçerik kalitesi
7. Hashtag kullanımı
8. Engagement oranı
9. Post sıklığı
10. CTA varlığı

Her madde için: ✅ yapılması gereken + ❌ kaçınılması gereken
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# Profil Audit — {plat['name']}\n\nDetaylı audit için Claude CLI gerekli."

    def _growth_plan(self, business_name, niche, plat, platform):
        prompt = f"""90 günlük organik büyüme planı:
İşletme: {business_name}
Platform: {plat['name']}
Sektör: {niche}

Ay 1: Foundation (profil + içerik)
Ay 2: Growth (engagement + collaboration)
Ay 3: Scale (paid boost + optimization)

Her ay için haftalık görevler.
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# 90 Gün Büyüme Planı — {plat['name']}\n\nDetaylı plan için Claude CLI gerekli."
