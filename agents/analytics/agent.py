"""Analytics Agent — Business analytics, competitor analysis, market research."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class AnalyticsAgent(BaseAgent):
    agent_id = "analytics"
    name = "Analytics"
    role = "Business analytics — competitor analysis, market research, performance tracking"
    category = "intelligence"

    def run(self, analysis_type: str = "competitor", target: str = "",
            industry: str = "", location: str = "") -> dict:
        self.log("Analytics agent started")
        config = self.load_config()

        if not industry:
            industry = config.get("niche", "dijital pazarlama")
        if not location:
            cities = config.get("target_cities", ["İstanbul"])
            location = ", ".join(cities)
        business_name = config.get("agency_name", "My Agency")

        analysis_types = {
            "competitor": "Rakip Analizi",
            "market": "Pazar Araştırması",
            "swot": "SWOT Analizi",
            "pricing": "Fiyatlandırma Analizi",
            "trend": "Trend Analizi",
            "performance": "Performans Raporu",
        }

        analysis_name = analysis_types.get(analysis_type, "Genel Analiz")
        self.log(f"Analysis: {analysis_name} | Industry: {industry} | Location: {location}")

        # Run analysis via Claude
        if analysis_type == "competitor":
            report = self._competitor_analysis(business_name, industry, location, target)
        elif analysis_type == "market":
            report = self._market_research(business_name, industry, location)
        elif analysis_type == "swot":
            report = self._swot_analysis(business_name, industry, location)
        elif analysis_type == "pricing":
            report = self._pricing_analysis(business_name, industry, location)
        elif analysis_type == "trend":
            report = self._trend_analysis(industry, location)
        elif analysis_type == "performance":
            report = self._performance_report(business_name)
        else:
            report = self._market_research(business_name, industry, location)

        # Enrich with existing data
        internal_stats = self._gather_internal_stats()

        # Save analysis
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_data = {
            "analysis_type": analysis_type,
            "analysis_name": analysis_name,
            "business_name": business_name,
            "industry": industry,
            "location": location,
            "report": report,
            "internal_stats": internal_stats,
            "created_at": timestamp,
        }

        self.save_data(f"analytics/{timestamp}_{analysis_type}.json", analysis_data)

        results = {
            "status": "ok",
            "summary": f"{analysis_name} tamamlandı — {industry} sektörü, {location}",
            "metrics": {
                "analysis_type": analysis_type,
                "industry": industry,
                "location": location,
                "internal_leads": internal_stats.get("total_leads", 0),
                "internal_deals": internal_stats.get("total_deals", 0),
                "timestamp": datetime.now().isoformat(),
            },
            "report": analysis_data,
            "recommendations": self._generate_recommendations(analysis_type, internal_stats),
        }

        self.save_output("analytics_report.json", results)
        self.log("Analytics agent completed")
        return results

    def _competitor_analysis(self, business_name, industry, location, target):
        prompt = f"""Sen deneyimli bir iş analisti olarak rakip analizi yap.

İşletme: {business_name}
Sektör: {industry}
Konum: {location}
{"Hedef rakip: " + target if target else ""}

Detaylı rakip analizi raporu:
1. **Sektör Genel Bakış** — pazar büyüklüğü, büyüme oranı
2. **Ana Rakipler** (5-7 rakip) — güçlü/zayıf yönler
3. **Rekabet Avantajları** — ne yapılabilir farklı
4. **Fiyat Karşılaştırması** — sektör ortalamaları
5. **Dijital Varlık** — web, sosyal medya, SEO durumu
6. **Fırsat Alanları** — henüz karşılanmamış ihtiyaçlar
7. **Aksiyon Planı** — kısa vadeli (1-3 ay)

Türkçe, veriye dayalı ve actionable yaz."""

        result = self.call_claude(prompt)
        if not result:
            return f"""# Rakip Analizi — {business_name}

## Sektör: {industry} | Konum: {location}

### Pazar Değerlendirmesi
- {industry} sektörü büyüme trendinde
- Dijital dönüşüm fırsatları mevcut
- KOBİ segmentinde rekabet orta düzeyde

### Rekabet Durumu
- Büyük oyuncular: Kurumsal çözümler, yüksek fiyat
- Orta segment: Freelancer'lar, tutarsız kalite
- Fırsat: AI destekli, uygun fiyatlı, kaliteli hizmet

### Dijital Varlık Analizi
- Rakiplerin %60'ı SEO'da zayıf
- Sosyal medya tutarlılığı düşük
- Content marketing fırsatı büyük

### Aksiyon Planı
1. Güçlü online varlık oluştur (website + SEO)
2. Content marketing stratejisi başlat
3. Referans sistemi kur
4. Niche uzmanlaşma ile farklılaş
"""
        return result

    def _market_research(self, business_name, industry, location):
        prompt = f"""Pazar araştırması raporu oluştur:
İşletme: {business_name} | Sektör: {industry} | Konum: {location}

1. Pazar büyüklüğü ve büyüme
2. Hedef müşteri profili (persona)
3. Müşteri acı noktaları (pain points)
4. Talep trendleri
5. Giriş bariyerleri
6. Fiyatlandırma aralıkları
7. Dağıtım kanalları
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# Pazar Araştırması — {industry}\nKonum: {location}\n\nDetaylı analiz için Claude CLI gerekli."

    def _swot_analysis(self, business_name, industry, location):
        prompt = f"""SWOT analizi yap:
İşletme: {business_name} | Sektör: {industry} | Konum: {location}

Her kategori için minimum 5 madde:
- Strengths (Güçlü Yönler)
- Weaknesses (Zayıf Yönler)
- Opportunities (Fırsatlar)
- Threats (Tehditler)

+ Stratejik öneriler (SO, WO, ST, WT stratejileri)
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"""# SWOT Analizi — {business_name}

## Güçlü Yönler
- AI destekli otomasyon
- Düşük operasyonel maliyet
- Hızlı teslimat

## Zayıf Yönler
- Yeni marka bilinirliği
- Sınırlı portföy

## Fırsatlar
- Dijital dönüşüm talebi artıyor
- KOBİ segmenti hizmet arıyor
- Uzaktan çalışma ile coğrafi sınır yok

## Tehditler
- Büyük ajansların fiyat düşürmesi
- Freelancer rekabeti
- Ekonomik belirsizlik
"""

    def _pricing_analysis(self, business_name, industry, location):
        prompt = f"""Fiyatlandırma analizi yap:
İşletme: {business_name} | Sektör: {industry} | Konum: {location}

1. Sektör fiyat aralıkları (servis bazında)
2. Fiyatlandırma modelleri (saatlik, proje, retainer)
3. Önerilen fiyat stratejisi
4. Paket önerileri (3 tier)
5. Upsell/cross-sell fırsatları
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# Fiyatlandırma Analizi — {industry}\n\nDetaylı analiz için Claude CLI gerekli."

    def _trend_analysis(self, industry, location):
        prompt = f"""2024-2025 trend analizi:
Sektör: {industry} | Konum: {location}

1. Yükselen trendler (top 10)
2. Düşen trendler
3. Teknoloji trendleri
4. Tüketici davranış değişimleri
5. Sosyal medya trendleri
6. AI/otomasyon etkileri
7. Tahminler (6-12 ay)
Türkçe yaz."""

        result = self.call_claude(prompt)
        return result or f"# Trend Analizi — {industry}\n\nDetaylı analiz için Claude CLI gerekli."

    def _performance_report(self, business_name):
        stats = self._gather_internal_stats()
        return f"""# Performans Raporu — {business_name}

## Lead Pipeline
- Toplam lead: {stats.get('total_leads', 0)}
- Nitelikli lead: {stats.get('qualified_leads', 0)}
- Hot: {stats.get('hot', 0)} | Warm: {stats.get('warm', 0)} | Cold: {stats.get('cold', 0)}

## Deals
- Toplam deal: {stats.get('total_deals', 0)}
- Kazanılan: {stats.get('won_deals', 0)}
- Pipeline değeri: ${stats.get('pipeline_value', 0)}
- Kazanılan değer: ${stats.get('won_value', 0)}
- Win rate: {stats.get('win_rate', 0)}%

## Öneriler
- {'Lead sayısını artırın — Scout agent ile daha fazla arama yapın' if stats.get('total_leads', 0) < 50 else 'Lead sayısı yeterli — kaliteye odaklanın'}
- {'Outreach başlatın — hot leadlere email gönderin' if stats.get('hot', 0) > 0 else 'Daha fazla lead puanlayın — Filter agent çalıştırın'}
"""

    def _gather_internal_stats(self):
        stats = {
            "total_leads": 0, "qualified_leads": 0,
            "hot": 0, "warm": 0, "cold": 0,
            "total_deals": 0, "won_deals": 0,
            "pipeline_value": 0, "won_value": 0, "win_rate": 0,
        }

        # Load lead stats
        reports_dir = OUTPUT_DIR / "reports"
        scout_report = reports_dir / "scout_leads_report.json"
        if scout_report.exists():
            with open(scout_report) as f:
                data = json.load(f)
                stats["total_leads"] = data.get("metrics", {}).get("total_found", 0)

        filter_report = reports_dir / "filter_qualified_report.json"
        if filter_report.exists():
            with open(filter_report) as f:
                data = json.load(f)
                m = data.get("metrics", {})
                stats["qualified_leads"] = m.get("total_scored", 0)
                stats["hot"] = m.get("hot", 0)
                stats["warm"] = m.get("warm", 0)
                stats["cold"] = m.get("cold", 0)

        # Load deal stats
        deals_path = DATA_DIR / "pipeline" / "deals.json"
        if deals_path.exists():
            with open(deals_path) as f:
                deals = json.load(f)
                stats["total_deals"] = len(deals)
                stats["won_deals"] = sum(1 for d in deals if d.get("status") == "won")
                stats["pipeline_value"] = sum(d.get("value", 0) for d in deals if d.get("status") in ("proposal", "negotiation"))
                stats["won_value"] = sum(d.get("value", 0) for d in deals if d.get("status") == "won")
                closed = sum(1 for d in deals if d.get("status") in ("won", "lost"))
                if closed > 0:
                    stats["win_rate"] = round(stats["won_deals"] / closed * 100)

        return stats

    def _generate_recommendations(self, analysis_type, stats):
        recs = []
        if stats.get("total_leads", 0) == 0:
            recs.append("Henüz lead yok — Scout agent ile lead toplama başlatın")
        if stats.get("hot", 0) > 0 and stats.get("total_deals", 0) == 0:
            recs.append(f"{stats['hot']} hot lead var — teklif göndermeye başlayın")
        if stats.get("win_rate", 0) > 0 and stats["win_rate"] < 20:
            recs.append("Win rate düşük — teklif kalitesini ve hedeflemeyi gözden geçirin")

        recs.extend([
            "Haftalık performans raporu alışkanlığı edinin",
            "Rakip analizini ayda bir güncelleyin",
            "Trend analizine göre hizmet portföyünü revize edin",
        ])
        return recs
