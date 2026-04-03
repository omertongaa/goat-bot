"""AdManager Agent — Ad campaign planning, optimization, and analysis."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class AdManagerAgent(BaseAgent):
    agent_id = "admanager"
    name = "AdManager"
    role = "Plans ad campaigns, generates ad copy, analyzes ad performance"
    category = "marketing"

    AD_PLATFORMS = {
        "google": {"name": "Google Ads", "types": ["search", "display", "shopping", "youtube"]},
        "meta": {"name": "Meta Ads", "types": ["feed", "stories", "reels", "carousel"]},
        "tiktok": {"name": "TikTok Ads", "types": ["in_feed", "topview", "spark"]},
        "linkedin": {"name": "LinkedIn Ads", "types": ["sponsored", "message", "text"]},
    }

    def run(self, platform: str = "meta", campaign_type: str = "lead_gen",
            budget: str = "1000", business_name: str = "", target_audience: str = "") -> dict:
        self.log("AdManager agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "My Agency")
        niche = config.get("niche", "dijital pazarlama")
        cities = config.get("target_cities", ["İstanbul"])

        if not target_audience:
            target_audience = f"{niche} sektöründe KOBİ sahipleri, {', '.join(cities)}"

        plat = self.AD_PLATFORMS.get(platform, self.AD_PLATFORMS["meta"])
        self.log(f"Platform: {plat['name']} | Campaign: {campaign_type} | Budget: ${budget}")

        # Generate ad campaign plan via Claude
        prompt = f"""Sen deneyimli bir dijital reklam uzmanısın.

İşletme: {business_name}
Sektör: {niche}
Platform: {plat['name']}
Kampanya türü: {campaign_type}
Aylık bütçe: ${budget}
Hedef kitle: {target_audience}
Hedef şehirler: {', '.join(cities)}

Detaylı bir reklam kampanya planı oluştur:

1. **Kampanya Stratejisi**
   - Hedef (awareness/traffic/conversion/lead_gen)
   - Funnel yapısı (TOFU/MOFU/BOFU)

2. **Hedef Kitle Segmentasyonu**
   - Demografik (yaş, cinsiyet, konum)
   - İlgi alanları
   - Davranışsal hedefleme
   - Lookalike/benzer kitle önerileri

3. **Reklam Setleri** (minimum 3 set)
   - Her set için: başlık, açıklama, CTA
   - A/B test varyasyonları

4. **Bütçe Dağılımı**
   - Günlük bütçe
   - Set bazında dağılım
   - Test bütçesi

5. **KPI'lar ve Hedefler**
   - CPL (Cost Per Lead) hedefi
   - CTR hedefi
   - ROAS hedefi
   - Dönüşüm oranı hedefi

6. **Optimizasyon Takvimi**
   - Haftalık kontrol noktaları
   - Scaling kriterleri

Türkçe ve detaylı yaz."""

        campaign_plan = self.call_claude(prompt)
        if not campaign_plan:
            campaign_plan = self._generate_fallback_plan(business_name, plat, campaign_type, budget, target_audience, cities)

        # Generate ad copies
        ad_copy_prompt = f"""Aşağıdaki kampanya için 5 farklı reklam metni yaz:

Platform: {plat['name']}
İşletme: {business_name}
Sektör: {niche}
Hedef: {campaign_type}

Her reklam için:
- Başlık (max 40 karakter)
- Açıklama (max 125 karakter)
- Uzun açıklama (max 250 karakter)
- CTA butonu önerisi

Dikkat çekici, aciliyet yaratan, fayda odaklı yaz."""

        ad_copies = self.call_claude(ad_copy_prompt)
        if not ad_copies:
            ad_copies = self._generate_fallback_copies(business_name, niche)

        # Save campaign data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        campaign_data = {
            "business_name": business_name,
            "platform": platform,
            "platform_name": plat["name"],
            "campaign_type": campaign_type,
            "budget": budget,
            "target_audience": target_audience,
            "cities": cities,
            "campaign_plan": campaign_plan,
            "ad_copies": ad_copies,
            "created_at": timestamp,
        }

        self.save_data(f"ads/{timestamp}_{platform}_{campaign_type}.json", campaign_data)

        # Try generating ad creative
        creative_path = None
        try:
            from services.image import generate_ad_creative
            creative_path = generate_ad_creative(business_name, niche, campaign_type)
            if creative_path:
                self.log(f"Ad creative generated: {creative_path}")
        except Exception as e:
            self.log(f"Ad creative generation skipped: {e}")

        results = {
            "status": "ok",
            "summary": f"{plat['name']} kampanya planı oluşturuldu — {business_name} (${budget}/ay)",
            "metrics": {
                "platform": plat["name"],
                "campaign_type": campaign_type,
                "budget": budget,
                "ad_copies_generated": 5,
                "creative_generated": bool(creative_path),
                "timestamp": datetime.now().isoformat(),
            },
            "campaign": campaign_data,
            "recommendations": [
                f"Günlük bütçe: ~${round(int(budget) / 30)} — düzenli harcama sağlayın",
                "İlk 7 gün öğrenme aşaması — değişiklik yapmayın",
                "A/B test ile en iyi reklam metnini bulun",
                "Haftalık optimizasyon yapın — düşük performanslıları durdurun",
                "Retargeting kampanyası ekleyin — dönüşüm oranını artırır",
            ],
        }

        self.save_output("admanager_report.json", results)
        self.log("AdManager agent completed")
        return results

    def _generate_fallback_plan(self, business_name, plat, campaign_type, budget, target_audience, cities):
        daily = round(int(budget) / 30)
        return f"""# Reklam Kampanya Planı — {business_name}

## Platform: {plat['name']}
## Kampanya Türü: {campaign_type}
## Aylık Bütçe: ${budget}

### 1. Strateji
- Hedef: Lead generation (potansiyel müşteri toplama)
- Funnel: TOFU (farkındalık) + MOFU (değerlendirme)
- Süre: 30 gün (test fazı)

### 2. Hedef Kitle
- Konum: {', '.join(cities)}
- Yaş: 25-55
- İlgi alanları: İş yönetimi, dijital pazarlama, girişimcilik
- Özel kitle: Website ziyaretçileri (retargeting)

### 3. Reklam Setleri
**Set A — Farkındalık:** Sektör problemi + çözüm
**Set B — Değer:** Ücretsiz kaynak / demo teklifi
**Set C — Sosyal kanıt:** Müşteri başarı hikayeleri

### 4. Bütçe Dağılımı
- Günlük: ${daily}
- Set A: %40 (${round(daily * 0.4)})
- Set B: %35 (${round(daily * 0.35)})
- Set C: %25 (${round(daily * 0.25)})

### 5. KPI Hedefleri
- CPL: $5-15
- CTR: %2+
- Dönüşüm: %3-5
- ROAS: 3x+

### 6. Optimizasyon
- Hafta 1: Veri toplama, değişiklik yok
- Hafta 2: Düşük CTR reklamları kapat
- Hafta 3: Kazananları scale et
- Hafta 4: Analiz ve raporlama
"""

    def _generate_fallback_copies(self, business_name, niche):
        return f"""## Reklam Metinleri — {business_name}

### Reklam 1 — Problem/Çözüm
- **Başlık:** Müşteri bulmak mı zor?
- **Açıklama:** {business_name} ile müşteri akışınızı otomatikleştirin.
- **CTA:** Ücretsiz Demo Al

### Reklam 2 — Sosyal Kanıt
- **Başlık:** 100+ işletme bize güveniyor
- **Açıklama:** {niche} sektöründe lider çözüm. Sonuçlar konuşsun.
- **CTA:** Başarı Hikayeleri

### Reklam 3 — Aciliyet
- **Başlık:** Bu ay %30 indirim
- **Açıklama:** Sınırlı süre! Profesyonel {niche} hizmeti.
- **CTA:** Hemen Başla

### Reklam 4 — Değer Önerisi
- **Başlık:** Rakipleriniz bunu zaten yapıyor
- **Açıklama:** AI destekli otomasyon ile işinizi büyütün.
- **CTA:** Ücretsiz Analiz

### Reklam 5 — Eğitim
- **Başlık:** 5 dakikada öğrenin
- **Açıklama:** Ücretsiz rehber: {niche} için growth stratejileri.
- **CTA:** Rehberi İndir
"""
