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
        sequence = self._generate_sequence(config)
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

    def _generate_sequence(self, config):
        """Generate a multi-step email sequence from config.

        Reads `outreach_strategy` section of config (if present) for rich personalization:
          - hook, pain_point, key_numbers, social_proof, cta_style, cta_examples,
            tone, language, sequence_steps, sequence_delays_days
        Falls back to basic 3-step generic template if outreach_strategy is missing.

        Uses Claude if available, otherwise templates.
        """
        agency_name = config.get("agency_name") or config.get("name") or "goat Agency"
        owner_name = config.get("owner_name", "")
        niche = config.get("niche", "işletme")
        sender = owner_name or "Ben"

        # Extract optional outreach_strategy enrichment
        strategy = config.get("outreach_strategy", {}) or {}
        pain_point = strategy.get("pain_point", "")
        key_numbers = strategy.get("key_numbers", []) or []
        social_proof = strategy.get("social_proof", []) or []
        cta_style = strategy.get("cta_style", "")
        cta_examples = strategy.get("cta_examples", []) or []
        tone = strategy.get("tone", "samimi, değer odaklı, kısa")
        language = strategy.get("language", "turkish")
        steps = int(strategy.get("sequence_steps", 3))
        delays = strategy.get("sequence_delays_days") or [0, 3, 7, 14][:steps]
        target_titles = config.get("target_titles", []) or []
        value_prop = config.get("value_proposition", "")

        # Build language directive
        lang_directive = "Türkçe olsun." if language == "turkish" else f"Dil: {language}."

        # Build enrichment blocks (only included if present)
        enrichment_blocks = []
        if value_prop:
            enrichment_blocks.append(f"Değer önerisi: {value_prop}")
        if pain_point:
            enrichment_blocks.append(f"Konuşulacak ana dert: {pain_point}")
        if key_numbers:
            nums = "\n".join(f"  - {n}" for n in key_numbers)
            enrichment_blocks.append(f"Kullanılabilecek somut sayılar:\n{nums}")
        if social_proof:
            proof = "\n".join(f"  - {p}" for p in social_proof)
            enrichment_blocks.append(f"Sosyal kanıt vakaları (gerçek müşteri sonuçları):\n{proof}")
        if cta_examples:
            ctas = "\n".join(f"  - {c}" for c in cta_examples)
            enrichment_blocks.append(f"CTA örnekleri ({cta_style} stilinde):\n{ctas}")
        if target_titles:
            enrichment_blocks.append(f"Hedef alıcı unvanları: {', '.join(target_titles)}")

        enrichment = "\n\n".join(enrichment_blocks)

        # Sequence step plan (delays per step)
        step_plan_lines = []
        for i in range(steps):
            delay = delays[i] if i < len(delays) else (i * 3)
            if i == 0:
                purpose = "Tanışma + dert kıvılcımı (kısa, somut, jenerik açılış YOK)"
            elif i == steps - 1:
                purpose = "Son hatırlatma — yumuşak, baskıcı olmayan kapanış"
            else:
                purpose = "Değer ekleme — somut sayı, sosyal kanıt veya yeni bir açı"
            step_plan_lines.append(f"Email {i+1} (gün {delay}): {purpose}")
        step_plan = "\n".join(step_plan_lines)

        prompt = f"""Bir B2B ajansı için {steps} adımlı soğuk email dizisi yaz.

Ajans: {agency_name}
Kurucu: {owner_name}
Hedef sektör/niş: {niche}

{enrichment}

Sekans planı:
{step_plan}

Ton: {tone}
{lang_directive} Her mail kısa olsun (5-7 cümle). Subject 40-60 karakter. "{{{{first_name}}}}" ve "{{{{company_name}}}}" placeholder'larını kullan — alıcıya kişisel hissi versin.

Önemli kurallar:
- Generic açılış YASAK ("Umarım iyisinizdir" gibi). Direkt dert veya somut soruyla başla.
- Tek CTA, basit. "30 dk demo" yerine yumuşak evet/hayır sorusu tercih et.
- Sosyal kanıt varsa SADECE BİR vaka kullan her mail'de (üst üste yığma).
- İmza: "{sender}\\n{agency_name}"

JSON formatında dön (başka açıklama eklemeden):
[{{"step":1,"delay_days":{delays[0] if delays else 0},"subject":"...","body":"..."}}, ...]"""

        response = self.call_claude(prompt, timeout=45)
        if response:
            try:
                import re
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except (json.JSONDecodeError, AttributeError):
                pass

        # === Fallback: template-based sequence ===
        # If outreach_strategy is rich, build a config-driven fallback.
        # Otherwise fall back to the legacy generic 3-step template.
        if pain_point and social_proof:
            return self._fallback_from_strategy(
                agency_name, sender, niche, pain_point,
                key_numbers, social_proof, cta_examples,
                steps, delays
            )

        # Legacy generic fallback (original behavior, kept for backward compat)
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

    def _fallback_from_strategy(self, agency_name, sender, niche,
                                  pain_point, key_numbers, social_proof,
                                  cta_examples, steps, delays):
        """Build a fallback sequence using outreach_strategy config (no Claude needed).

        Produces a coherent multi-step sequence by rotating through:
          - pain_point (step 1)
          - key_numbers (step 2)
          - social_proof (middle steps)
          - soft breakup (final step)
        """
        proof_one = social_proof[0] if social_proof else ""
        proof_two = social_proof[1] if len(social_proof) > 1 else proof_one
        number_block = "\n".join(f"- {n}" for n in key_numbers[:3]) if key_numbers else ""
        cta = cta_examples[0] if cta_examples else "Bu hafta 15 dakikanız var mı?"
        cta_soft = cta_examples[-1] if len(cta_examples) > 1 else cta

        sequence = []

        # Step 1 — pain point hook
        sequence.append({
            "step": 1,
            "delay_days": delays[0] if delays else 0,
            "subject": f"{{{{company_name}}}} satışçısı haftada kaç saatini kaybediyor?",
            "body": (
                f"Merhaba {{{{first_name}}}},\n\n"
                f"{pain_point}\n\n"
                f"Biz {agency_name} olarak {niche} alanında çalışan firmalara "
                f"bu derdi otomasyonla çözüyoruz.\n\n"
                f"{cta}\n\n"
                f"Saygılarımla,\n{sender}\n{agency_name}"
            ),
        })

        # Step 2 — concrete numbers + first proof
        if steps >= 2:
            sequence.append({
                "step": 2,
                "delay_days": delays[1] if len(delays) > 1 else 3,
                "subject": "Re: Geçen mesajımın somut karşılığı",
                "body": (
                    f"Merhaba {{{{first_name}}}},\n\n"
                    f"Geçen hafta yazdığım dert bir tahmin değildi, sektör verisi:\n\n"
                    f"{number_block}\n\n"
                    + (f"Vaka: {proof_one}\n\n" if proof_one else "")
                    + f"{cta}\n\n"
                    f"{sender}"
                ),
            })

        # Step 3 — second proof + alternative angle
        if steps >= 3:
            sequence.append({
                "step": 3,
                "delay_days": delays[2] if len(delays) > 2 else 7,
                "subject": "Sizinki gibi bir firma için somut sonuç",
                "body": (
                    f"Merhaba {{{{first_name}}}},\n\n"
                    f"{proof_two if proof_two else proof_one}\n\n"
                    f"{{{{company_name}}}} için de benzer bir kurguyu konuşmaya açık olur muyuz?\n\n"
                    f"{cta_soft}\n\n"
                    f"{sender}"
                ),
            })

        # Step 4 — soft breakup
        if steps >= 4:
            sequence.append({
                "step": 4,
                "delay_days": delays[3] if len(delays) > 3 else 14,
                "subject": "Re: Son sorum",
                "body": (
                    f"Merhaba {{{{first_name}}}},\n\n"
                    f"Son kez yazıyorum. Eğer satış otomasyonu şu an önceliğiniz değilse tamamen anlıyorum.\n\n"
                    f"İlerleyen aylarda düşünürseniz buradan ulaşabilirsiniz.\n\n"
                    f"Başarılar,\n{sender}\n{agency_name}"
                ),
            })

        return sequence
