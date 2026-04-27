"""Outreach — Email Campaign Agent

Creates cold email campaigns via Instantly.ai.
Reads qualified leads, generates email sequences, launches campaigns.
"""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR
from services.email import (
    get_api_key, test_connection, create_campaign,
    add_leads_to_campaign, activate_campaign, list_campaigns,
)


class OutreachAgent(BaseAgent):
    agent_id = "outreach"
    name = "Outreach"
    role = "Email warmup + cold campaigns via Instantly.ai"
    category = "sales"

    def run(self, auto_activate=False) -> dict:
        """Tool-agnostic outreach: always generate the campaign (sequence + leads)
        first, then offer multiple delivery channels (Instantly, Composio Gmail,
        manual export). User picks during approval — system stays dynamic."""
        config = self.load_config()
        agency_name = config.get("agency_name") or config.get("name") or "goat Agency"
        owner_name = config.get("owner_name", "")
        niche = config.get("niche", "işletme")

        # Load qualified leads (still fall back gracefully if none)
        leads = self._load_hot_leads()
        if not leads:
            self.log("Hot lead yok — Scout + email enrichment otomatik")
            raw = self.ensure_leads(min_count=10, with_email=True)
            leads = [{"lead": l, "qualification": "hot", "score": 5}
                     for l in raw[:20]]
            if leads:
                self.log(f"Auto-fetch'ten {len(leads)} email'li lead bulundu")
        email_leads = [l for l in leads if l.get("lead", {}).get("email")]
        self.log(f"Yüklenen leadler: {len(leads)} (emaili olan: {len(email_leads)})")

        # Always generate the email sequence — value-first, no API blocking
        self.log("Email dizisi hazırlanıyor...")
        sequence = self._generate_sequence(agency_name, owner_name, niche)
        self.log(f"{len(sequence)} adımlı dizi hazır")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        campaign_name = f"goat_{niche}_{timestamp}"

        # Build the lead payload regardless of provider
        prepared_leads = []
        for l in email_leads:
            lead = l.get("lead", {})
            prepared_leads.append({
                "email": lead.get("email", ""),
                "first_name": (lead.get("name", "").split()[0] if lead.get("name") else ""),
                "company_name": lead.get("name", ""),
                "city": lead.get("location", ""),
                "category": lead.get("category", niche),
                "rating": lead.get("rating"),
            })

        # Detect available delivery channels — system suggests, user picks
        channels = self._available_channels(config)
        self.log(f"Mevcut gönderim kanalları: {', '.join(c['kind'] for c in channels) or 'yok'}")

        # If Instantly is configured AND wired, ALSO push as draft so it's ready
        instantly_campaign_id = None
        instantly_key = config.get("instantly_api_key") or get_api_key()
        if instantly_key and prepared_leads:
            try:
                self.log("Instantly.ai'da draft kampanya oluşturuluyor (opsiyonel)...")
                if test_connection(instantly_key):
                    cid = create_campaign(campaign_name, instantly_key)
                    if cid:
                        ok = add_leads_to_campaign(cid, prepared_leads, instantly_key)
                        if ok:
                            instantly_campaign_id = cid
                            self.log(f"Instantly draft hazır: {cid}")
            except Exception as e:
                self.log(f"Instantly hazırlığı atlandı: {e}")

        # Save campaign as artifact
        campaign_data = {
            "campaign_id": instantly_campaign_id or f"draft_{timestamp}",
            "campaign_name": campaign_name,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
            "agency": agency_name,
            "niche": niche,
            "leads_count": len(prepared_leads),
            "sequence": sequence,
            "leads": prepared_leads,
            "instantly_draft_id": instantly_campaign_id,
            "delivery_channels": channels,
        }
        self.save_data(f"campaigns/{campaign_data['campaign_id']}.json", campaign_data)

        if not prepared_leads:
            summary = f"Email dizisi hazır ({len(sequence)} adım). Henüz email'li lead yok — Scout/Filter çalıştır, sonra gönderebilirsin."
        elif instantly_campaign_id:
            summary = f"{len(prepared_leads)} lead için kampanya hazır + Instantly'ye draft olarak yüklendi. Onayınla aktifleşir."
        else:
            connect_options = ", ".join(c["label"] for c in channels) or "manuel indirme"
            summary = f"{len(prepared_leads)} lead için email dizisi hazır. Gönderim kanalı seç: {connect_options}."

        results = {
            "status": "ok",
            "summary": summary,
            "needs_approval": True,
            "approval_action": {
                "kind": "activate_campaign" if instantly_campaign_id else "deliver_campaign",
                "campaign_id": campaign_data["campaign_id"],
                "instantly_campaign_id": instantly_campaign_id,
                "preview": {
                    "leads_count": len(prepared_leads),
                    "sequence_steps": len(sequence),
                    "first_subject": sequence[0]["subject"] if sequence else "",
                    "channels": channels,
                },
            },
            "metrics": {
                "campaign_id": campaign_data["campaign_id"],
                "campaign_name": campaign_name,
                "leads_added": len(prepared_leads),
                "total_hot": len(leads),
                "with_email": len(email_leads),
                "sequence_steps": len(sequence),
                "status": "awaiting_approval",
            },
            "campaign_id": campaign_data["campaign_id"],
            "instantly_draft_id": instantly_campaign_id,
            "sequence": sequence,
            "leads": prepared_leads,
            "recommendations": [
                "Drawer'dan gönderim kanalı seç + onayla",
                "İstersen CSV/Markdown indir, manuel gönder",
                ("Instantly.ai aktif" if instantly_campaign_id else "Instantly key yoksa Composio Gmail veya export kullan"),
            ],
        }

        self.save_output("outreach_campaign_report.json", results)
        self.log("Kampanya raporu kaydedildi.")
        return results

    def _available_channels(self, config: dict) -> list:
        """Return delivery options the user can pick from. System suggests
        what's available, doesn't force a single tool."""
        import os
        out = []
        if config.get("instantly_api_key") or os.getenv("INSTANTLY_API_KEY"):
            out.append({"kind": "instantly", "label": "Instantly.ai",
                        "ready": True, "icon": "📨"})
        # Composio Gmail / SendGrid via connections
        if os.getenv("COMPOSIO_API_KEY") or config.get("composio_api_key"):
            try:
                from services import composio_tools as _ct
                cid = config.get("id") or "default"
                connected = _ct.list_connected_toolkits(cid)
                if "gmail" in connected:
                    out.append({"kind": "composio_gmail", "label": "Gmail (Composio)",
                                "ready": True, "icon": "📧"})
                else:
                    out.append({"kind": "composio_gmail", "label": "Gmail bağlanmadı — /apps üstünden bağla",
                                "ready": False, "icon": "📧"})
            except Exception:
                pass
        # Always offer manual export as a safety net
        out.append({"kind": "export_csv", "label": "CSV indir (manuel gönderim)",
                    "ready": True, "icon": "📥"})
        out.append({"kind": "export_md", "label": "Email dizisini Markdown indir",
                    "ready": True, "icon": "📝"})
        return out

    def _load_hot_leads(self) -> list:
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

    def _generate_sequence(self, agency_name, owner_name, niche):
        """Generate a 3-step email sequence. Uses Claude if available, otherwise templates."""
        # Try Claude for personalized sequence
        prompt = f"""Bir otomasyon ajansı için 3 adımlı soğuk email dizisi yaz.

Ajans: {agency_name}
Kurucu: {owner_name}
Hedef sektör: {niche}

Her email için subject ve body yaz. Türkçe olsun. Kısa, samimi, değer odaklı.
Email 1: Tanışma + fark ettiğin bir sorun
Email 2: 3 gün sonra, somut değer önerisi
Email 3: 7 gün sonra, son hatırlatma

JSON formatında dön:
[{{"step":1,"delay_days":0,"subject":"...","body":"..."}}, ...]"""

        response = self.call_claude(prompt, timeout=30)
        if response:
            try:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except (json.JSONDecodeError, AttributeError):
                pass

        # Fallback: template-based sequence
        sender = owner_name or "Ben"
        return [
            {
                "step": 1,
                "delay_days": 0,
                "subject": f"{niche} işletmeniz için otomasyon önerisi",
                "body": f"Merhaba {{{{first_name}}}},\n\n"
                        f"{{{{company_name}}}} işletmenizi inceledim. Google yorumlarınıza henüz otomatik yanıt verilmediğini fark ettim.\n\n"
                        f"Biz {agency_name} olarak {niche} işletmeleri için otomasyon çözümleri kuruyoruz. "
                        f"Müşterilerinize 5 dakika içinde profesyonel yanıt göndermek ister misiniz?\n\n"
                        f"15 dakikalık bir demo için müsait misiniz?\n\n"
                        f"Saygılarımla,\n{sender}",
            },
            {
                "step": 2,
                "delay_days": 3,
                "subject": "Re: Otomasyon ile ayda 20+ saat kazanın",
                "body": f"Merhaba {{{{first_name}}}},\n\n"
                        f"Geçen hafta yazdığım mesajı gördünüz mü?\n\n"
                        f"Sizin sektörünüzdeki bir işletme için kurduğumuz sistemle:\n"
                        f"- Google yorum yanıt süresi: 2 gün → 5 dakika\n"
                        f"- Ayda 20+ saat tasarruf\n"
                        f"- Müşteri memnuniyetinde %30 artış\n\n"
                        f"Size de benzer sonuçlar sağlayabilirim. Bu hafta 15 dakikanız var mı?\n\n"
                        f"{sender}",
            },
            {
                "step": 3,
                "delay_days": 7,
                "subject": "Re: Son sorum",
                "body": f"Merhaba {{{{first_name}}}},\n\n"
                        f"Son kez yazıyorum. Eğer otomasyon şu an önceliğiniz değilse tamamen anlıyorum.\n\n"
                        f"Ama ileride düşünürseniz, buradan bana ulaşabilirsiniz.\n\n"
                        f"Başarılar,\n{sender}",
            },
        ]
