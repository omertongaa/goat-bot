"""SiteBuilder — Landing Page Generator Agent

Generates professional landing pages for:
1. Agency site — the user's own agency website
2. Client sites — landing pages for leads as a deliverable
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR
from services.site_builder import generate_agency_site, generate_client_site


class SiteBuilderAgent(BaseAgent):
    agent_id = "sitebuilder"
    name = "SiteBuilder"
    role = "Generates professional landing pages for your agency and clients"
    category = "delivery"

    def run(self, site_type="agency", lead_index=0, manual_data=None, **kwargs):
        # type: (str, int, dict, object) -> dict
        """Generate a landing page.

        Args:
            site_type: 'agency' or 'client'
            lead_index: which hot lead to use (for client sites)
            manual_data: optional dict with business info (name, category, phone, email, address etc.)
        """
        config = self.load_config()

        if site_type == "agency":
            return self._build_agency_site(config)
        elif site_type == "client":
            if manual_data:
                return self._build_client_site_manual(config, manual_data)
            return self._build_client_site(config, lead_index)
        else:
            return {
                "status": "error",
                "summary": "Gecersiz site tipi. 'agency' veya 'client' kullanin.",
                "metrics": {},
                "recommendations": [],
            }

    def _build_agency_site(self, config):
        # type: (dict) -> dict
        """Build agency landing page from config."""
        if not config.get("agency_name"):
            return {
                "status": "error",
                "summary": "Ajans bilgileri eksik. Once ayarlari tamamlayin.",
                "metrics": {},
                "recommendations": ["Ayarlardan ajans adini ve nisini girin."],
            }

        self.log("Building agency site for: " + config.get("agency_name", ""))

        # Try Claude for custom copy
        custom_tagline = None
        prompt = (
            "Sen bir dijital pazarlama ajansinin web sitesi icin kisa bir slogan yazacaksin.\n"
            "Ajans adi: {name}\nNis: {niche}\nSehirler: {cities}\n\n"
            "Sadece 1 cumle yaz, Turkce, 10-15 kelime arasi. Baska bir sey yazma."
        ).format(
            name=config.get("agency_name", ""),
            niche=config.get("niche", ""),
            cities=", ".join(config.get("target_cities", [])),
        )
        custom_tagline = self.call_claude(prompt, timeout=30)

        if custom_tagline:
            config = dict(config)
            # We don't modify the tagline in the template directly,
            # but could store it for future use
            self.log("Claude generated custom tagline: " + custom_tagline)

        path = generate_agency_site(config)

        if not path:
            return {
                "status": "error",
                "summary": "Site olusturulamadi.",
                "metrics": {},
                "recommendations": [],
            }

        # Build preview URL
        filename = Path(path).name
        preview_url = "/site/" + filename

        report = {
            "status": "ok",
            "summary": "{name} icin ajans sitesi olusturuldu.".format(name=config.get("agency_name", "")),
            "metrics": {
                "site_type": "agency",
                "site_path": path,
                "filename": filename,
                "preview_url": preview_url,
                "agency_name": config.get("agency_name", ""),
            },
            "recommendations": [
                "Siteyi tarayicida onizleyin.",
                "Iletisim bilgilerini guncelleyin.",
                "Domain alip yayina alin.",
            ],
        }

        self.save_output("sitebuilder_report.json", report)
        return report

    def _build_client_site_manual(self, config, data):
        # type: (dict, dict) -> dict
        """Build a client landing page from manually provided data."""
        lead_name = data.get("name", data.get("business_name", "İşletme"))
        self.log("Building client site from manual data: " + lead_name)

        lead = {
            "name": lead_name,
            "category": data.get("category", ""),
            "phone": data.get("phone", ""),
            "email": data.get("email", ""),
            "address": data.get("address", ""),
            "website": data.get("website", ""),
            "rating": data.get("rating", 0),
            "review_count": data.get("review_count", 0),
        }

        path = generate_client_site(lead, config, None)

        if not path:
            return {
                "status": "error",
                "summary": "Müşteri sitesi oluşturulamadı.",
                "metrics": {},
                "recommendations": [],
            }

        filename = Path(path).name
        preview_url = "/site/" + filename

        report = {
            "status": "ok",
            "summary": "{name} için müşteri sitesi oluşturuldu.".format(name=lead_name),
            "metrics": {
                "site_type": "client",
                "site_path": path,
                "filename": filename,
                "preview_url": preview_url,
                "lead_name": lead_name,
                "source": "manual",
            },
            "recommendations": [
                "Siteyi tarayıcıda önizleyin.",
                "Müşteriye teklif ile birlikte gönderin.",
            ],
        }

        self.save_output("sitebuilder_report.json", report)
        return report

    def _build_client_site(self, config, lead_index=0):
        # type: (dict, int) -> dict
        """Build a client landing page from hot leads."""
        # Load qualified leads
        qual_dir = DATA_DIR / "leads" / "qualified"
        if not qual_dir.exists() or not list(qual_dir.glob("*.json")):
            return {
                "status": "needs_input",
                "summary": "Puanlanmış lead yok. Manuel bilgi girerek de site oluşturabilirsin.",
                "metrics": {},
                "recommendations": [
                    "Scout ile lead ara, veya",
                    "Manuel bilgi gir: işletme adı, kategori, telefon, email",
                ],
                "needs_manual": True,
            }

        files = sorted(qual_dir.glob("*.json"), reverse=True)
        if not files:
            return {
                "status": "needs_input",
                "summary": "Puanlanmış lead dosyası bulunamadı. Manuel bilgi girebilirsin.",
                "metrics": {},
                "recommendations": ["Scout ile lead ara veya manuel bilgi gir."],
                "needs_manual": True,
            }

        with open(files[0]) as f:
            data = json.load(f)

        leads = data.get("leads", [])
        # Filter hot leads first, then warm
        hot = [l for l in leads if l.get("qualification") == "hot"]
        warm = [l for l in leads if l.get("qualification") == "warm"]
        candidates = hot + warm

        if not candidates:
            candidates = leads

        if not candidates:
            return {
                "status": "error",
                "summary": "Uygun lead bulunamadi.",
                "metrics": {},
                "recommendations": ["Scout ile daha fazla lead arayin."],
            }

        # Pick the lead
        idx = min(lead_index, len(candidates) - 1)
        entry = candidates[idx]
        lead = entry.get("lead", entry)
        lead_name = lead.get("name", lead.get("title", "Unknown"))

        self.log("Building client site for: " + lead_name)

        # Check for audit data
        audit_data = None
        audit_dir = DATA_DIR / "audits"
        if audit_dir.exists():
            audit_files = sorted(audit_dir.glob("*.json"), reverse=True)
            for af in audit_files:
                try:
                    with open(af) as f:
                        ad = json.load(f)
                    # Check if audit matches this lead's website
                    if ad.get("url") and lead.get("website") and lead["website"] in ad["url"]:
                        audit_data = ad
                        break
                except Exception:
                    pass

        path = generate_client_site(lead, config, audit_data)

        if not path:
            return {
                "status": "error",
                "summary": "Musteri sitesi olusturulamadi.",
                "metrics": {},
                "recommendations": [],
            }

        filename = Path(path).name
        preview_url = "/site/" + filename

        report = {
            "status": "ok",
            "summary": "{name} icin musteri sitesi olusturuldu.".format(name=lead_name),
            "metrics": {
                "site_type": "client",
                "site_path": path,
                "filename": filename,
                "preview_url": preview_url,
                "lead_name": lead_name,
                "lead_score": entry.get("score", 0),
                "has_audit": audit_data is not None,
            },
            "recommendations": [
                "Siteyi tarayicida onizleyin.",
                "Musteriye teklif ile birlikte gonderin.",
                "Fiyatlandirmaya site hizmetini ekleyin.",
            ],
        }

        self.save_output("sitebuilder_report.json", report)
        return report
