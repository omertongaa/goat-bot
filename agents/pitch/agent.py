"""Pitch — Proposal Generator Agent

Generates service proposals for specific leads.
Uses Claude CLI for text, fal.ai for cover image.
"""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR
from services.image import generate_proposal_cover
from services.pdf_generator import markdown_to_pdf


class PitchAgent(BaseAgent):
    agent_id = "pitch"
    name = "Pitch"
    role = "Generates service proposals and pitch decks"
    category = "sales"

    def run(self, lead_index=0) -> dict:
        config = self.load_config()
        leads = self._load_hot_leads()

        if not leads:
            return {
                "status": "error",
                "summary": "Sıcak lead yok. Önce Scout ve Filter çalıştır.",
                "metrics": {},
                "recommendations": ["Önce lead bul ve puanla"],
            }

        # Pick the lead
        if lead_index >= len(leads):
            lead_index = 0
        lead_data = leads[lead_index]
        lead = lead_data.get("lead", {})

        self.log(f"Teklif hazırlanıyor: {lead.get('name', '?')}")

        agency = config.get("agency_name", "goat Agency")
        owner = config.get("owner_name", "")
        niche = config.get("niche", "")

        # Generate proposal text via Claude
        proposal = self._generate_proposal(agency, owner, niche, lead)

        # Generate cover image via fal.ai
        self.log("Kapak görseli oluşturuluyor...")
        cover_path = generate_proposal_cover(agency, lead.get("name", ""), lead.get("category", niche))
        if cover_path:
            self.log(f"Kapak görseli: {cover_path}")

        # Append audit data if available
        audit_section = self._get_audit_section(lead)
        if audit_section:
            proposal += audit_section

        # Save proposal
        slug = lead.get("name", "lead").lower().replace(" ", "_")[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        proposal_path = DATA_DIR / "proposals" / f"{slug}_{timestamp}.md"
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(proposal_path, "w", encoding="utf-8") as f:
            f.write(proposal)
        self.log(f"Teklif kaydedildi: {proposal_path}")

        # Generate PDF
        self.log("PDF oluşturuluyor...")
        pdf_path = markdown_to_pdf(proposal, output_filename=f"{slug}_{timestamp}")
        if pdf_path:
            self.log(f"PDF hazır: {pdf_path}")

        results = {
            "status": "ok",
            "summary": f"Teklif hazır: {lead.get('name', '?')} için {agency} proposal (MD + PDF)",
            "metrics": {
                "lead_name": lead.get("name", "?"),
                "lead_email": lead.get("email", "—"),
                "lead_category": lead.get("category", "—"),
                "lead_score": lead_data.get("score", 0),
                "proposal_path": str(proposal_path),
                "pdf_path": pdf_path,
                "cover_image": cover_path,
            },
            "proposal": proposal,
            "recommendations": [
                "Teklifi incele ve düzenle",
                f"Email: {lead.get('email', '—')}",
                f"Telefon: {lead.get('phone', '—')}",
                "Teklifi göndermeye hazırsan outreach kullan",
            ],
        }

        self.save_output("pitch_proposal_report.json", results)
        return results

    def _generate_proposal(self, agency, owner, niche, lead):
        """Generate proposal markdown via Claude or template."""
        lead_name = lead.get("name", "İşletme")
        lead_category = lead.get("category", niche)
        lead_rating = lead.get("rating", 0)
        lead_reviews = lead.get("review_count", 0)
        lead_address = lead.get("address", "")

        prompt = f"""Bir otomasyon ajansı için profesyonel iş teklifi yaz. Markdown formatında, Türkçe.

Ajans: {agency}
Kurucu: {owner}
Müşteri: {lead_name}
Sektör: {lead_category}
Adres: {lead_address}
Google Puanı: {lead_rating}/5 ({lead_reviews} yorum)

Teklif şunları içersin:
1. Kapak (ajans adı, müşteri adı, tarih)
2. Yönetici Özeti (1 paragraf — ne sunuyoruz, neden)
3. Mevcut Durum Analizi (müşterinin muhtemel sorunları)
4. Çözüm Önerisi (3 paket halinde)
5. Fiyatlandırma (Başlangıç $300/ay, Pro $500/ay, Kurumsal $1000/ay)
6. Zaman Çizelgesi (4 haftalık)
7. Neden Biz (kısa)
8. Sonraki Adımlar

Profesyonel, samimi, somut ol. Gereksiz şeyler yazma."""

        response = self.call_claude(prompt, timeout=45)
        if response:
            return response

        # Fallback template
        today = datetime.now().strftime("%d.%m.%Y")
        return f"""# İş Teklifi

**{agency}** → **{lead_name}**
Tarih: {today}

---

## Yönetici Özeti

{lead_name} için otomasyon çözümleri sunuyoruz. Google'da {lead_rating}/5 puanınız ve {lead_reviews} yorumunuz var — bu güçlü bir temel. Otomasyonla müşteri deneyiminizi bir üst seviyeye çıkarabiliriz.

---

## Mevcut Durum

- Google yorumlarına yanıt süresi muhtemelen uzun veya hiç yanıt verilmiyor
- Sosyal medya yönetimi manuel ve zaman alıcı
- Müşteri takibi sistematik değil
- Tekrarlayan işler çalışan zamanını yiyor

---

## Çözüm Önerimiz

### Paket 1: Başlangıç — $300/ay
- Google yorum otomatik yanıtlama
- Haftalık performans raporu
- Email destek

### Paket 2: Profesyonel — $500/ay
- Google yorum otomasyonu
- Sosyal medya planlama (haftalık 5 paylaşım)
- Aylık strateji toplantısı
- Öncelikli destek

### Paket 3: Kurumsal — $1,000/ay
- Tüm Pro özellikleri
- WhatsApp müşteri desteği otomasyonu
- Özel dashboard
- CRM entegrasyonu
- 7/24 destek

---

## Zaman Çizelgesi

| Hafta | İş |
|-------|-----|
| 1 | Analiz + kurulum |
| 2 | Otomasyon geliştirme |
| 3 | Test + optimizasyon |
| 4 | Canlıya alma + eğitim |

---

## Neden {agency}?

- {lead_category} sektöründe uzmanlaşmış otomasyon çözümleri
- Kurulum + sürekli bakım tek elde
- Sonuç odaklı: ölçülebilir metriklerle çalışıyoruz

---

## Sonraki Adımlar

1. 15 dakikalık demo görüşmesi
2. İhtiyaç analizi
3. Pilot uygulama (1 otomasyon)
4. Tam geçiş

İletişim: {owner} — {agency}
"""

    def _get_audit_section(self, lead: dict) -> str:
        """Load audit data for this lead and return a markdown section."""
        website = lead.get("website", "")
        if not website:
            return ""

        # Check for existing audit data
        audit_dir = DATA_DIR / "audits"
        if not audit_dir.exists():
            # Run a quick audit
            try:
                from services.site_auditor import full_audit
                report = full_audit(website)
            except Exception:
                return ""
        else:
            # Look for this site in existing audit files
            report = None
            for f in sorted(audit_dir.glob("*.json"), reverse=True):
                with open(f) as fh:
                    data = json.load(fh)
                    # Single audit
                    if data.get("url") and website in data.get("url", ""):
                        report = data
                        break
                    # Batch audit
                    for r in data.get("results", []):
                        if website in r.get("website", ""):
                            report = r.get("full_report", {})
                            break
                if report:
                    break

            if not report:
                try:
                    from services.site_auditor import full_audit
                    report = full_audit(website)
                except Exception:
                    return ""

        seo = report.get("seo", {})
        broken = report.get("broken_links", {})
        tech = report.get("tech_stack", {})

        section = f"""

---

## Site Analiz Raporu

> Bu rapor **{website}** için otomatik olarak oluşturulmuştur.

### SEO Skoru: {seo.get('score', '?')}/100

"""
        issues = seo.get("issues", [])
        if issues:
            section += "| Seviye | Sorun |\n|--------|-------|\n"
            for issue in issues:
                level = {"critical": "🔴 Kritik", "warning": "🟡 Uyarı", "info": "ℹ️ Bilgi"}.get(
                    issue.get("type", ""), issue.get("type", "")
                )
                section += f"| {level} | {issue.get('issue', '')} |\n"
            section += "\n"

        if broken.get("broken_count", 0) > 0:
            section += f"### Kırık Linkler: {broken['broken_count']} adet\n\n"

        if tech.get("technologies"):
            section += f"### Teknoloji Altyapısı\n\n"
            section += ", ".join(tech["technologies"]) + "\n\n"

        return section

    def _load_hot_leads(self):
        """Load hot leads from latest qualified file."""
        qual_dir = DATA_DIR / "leads" / "qualified"
        if not qual_dir.exists():
            return []
        files = sorted(qual_dir.glob("*.json"), reverse=True)
        if files:
            with open(files[0]) as f:
                data = json.load(f)
                return [l for l in data.get("leads", []) if l.get("qualification") == "hot"]
        return []
