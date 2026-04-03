"""Auditor — Website Analysis Agent

Runs SEO, broken link, and tech stack audits on lead websites.
Pure Python, no API keys needed. Generates pitch ammunition.
"""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR
from services.site_auditor import full_audit, check_seo, check_broken_links, detect_tech_stack


class AuditorAgent(BaseAgent):
    agent_id = "auditor"
    name = "Auditor"
    role = "Analyzes lead websites — SEO, broken links, tech stack"
    category = "acquisition"

    def run(self, url: str = "", max_leads: int = 10) -> dict:
        """Run audits on lead websites.

        If url is provided, audit that single URL.
        Otherwise, audit websites from the latest qualified leads.
        """
        if url:
            return self._audit_single(url)
        return self._audit_leads(max_leads)

    def _audit_single(self, url: str) -> dict:
        """Audit a single URL."""
        self.log(f"Auditing: {url}")
        report = full_audit(url)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"audits/{timestamp}_single.json", report)

        issues = report.get("seo", {}).get("issues", [])
        broken = report.get("broken_links", {}).get("broken_count", 0)
        techs = report.get("tech_stack", {}).get("technologies", [])

        return {
            "status": "ok",
            "summary": f"Audit tamamlandı: SEO skoru {report.get('seo', {}).get('score', '?')}/100, "
                       f"{broken} kırık link, {len(techs)} teknoloji tespit edildi",
            "metrics": {
                "url": url,
                "overall_score": report.get("overall_score", 0),
                "seo_score": report.get("seo", {}).get("score", 0),
                "broken_links": broken,
                "tech_count": len(techs),
            },
            "report": report,
            "recommendations": self._generate_recommendations(report),
        }

    def _audit_leads(self, max_leads: int) -> dict:
        """Audit websites from qualified leads."""
        leads = self._load_leads_with_websites()
        if not leads:
            return {
                "status": "error",
                "summary": "Website'li lead yok. Önce Scout ve Filter çalıştır.",
                "metrics": {},
                "recommendations": ["Scout → Filter pipeline'ını çalıştır"],
            }

        leads_to_audit = leads[:max_leads]
        self.log(f"{len(leads_to_audit)} lead sitesi analiz ediliyor...")

        results = []
        total_issues = 0
        total_broken = 0

        for lead_data in leads_to_audit:
            lead = lead_data.get("lead", lead_data)
            website = lead.get("website", "")
            name = lead.get("name", "?")

            if not website:
                continue

            self.log(f"Auditing: {name} ({website})")
            try:
                report = full_audit(website)
                seo_score = report.get("seo", {}).get("score", 0)
                broken_count = report.get("broken_links", {}).get("broken_count", 0)
                issues = report.get("seo", {}).get("issues", [])

                total_issues += len(issues)
                total_broken += broken_count

                results.append({
                    "lead_name": name,
                    "website": website,
                    "overall_score": report.get("overall_score", 0),
                    "seo_score": seo_score,
                    "broken_links": broken_count,
                    "tech_stack": report.get("tech_stack", {}).get("technologies", []),
                    "critical_issues": [i for i in issues if i.get("type") == "critical"],
                    "full_report": report,
                })
            except Exception as e:
                self.log(f"Error auditing {name}: {e}")
                results.append({
                    "lead_name": name,
                    "website": website,
                    "error": str(e),
                })

        # Sort by score (worst first — best pitch opportunities)
        results.sort(key=lambda x: x.get("overall_score", 100))

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"audits/{timestamp}_batch.json", {
            "audited_at": datetime.now().isoformat(),
            "total": len(results),
            "results": results,
        })

        # Find worst sites (best opportunities)
        worst = [r for r in results if r.get("overall_score", 100) < 60]

        summary_data = {
            "status": "ok",
            "summary": f"{len(results)} site analiz edildi. "
                       f"Ortalama SEO skoru: {self._avg(results, 'seo_score')}/100. "
                       f"Toplam {total_broken} kırık link, {total_issues} SEO sorunu bulundu.",
            "metrics": {
                "total_audited": len(results),
                "avg_seo_score": self._avg(results, "seo_score"),
                "total_broken_links": total_broken,
                "total_seo_issues": total_issues,
                "sites_below_60": len(worst),
                "audited_at": datetime.now().isoformat(),
            },
            "leads": results[:20],
            "recommendations": [],
        }

        if worst:
            top = worst[0]
            summary_data["recommendations"].append(
                f"En kötü site: {top.get('lead_name')} (skor: {top.get('overall_score')})"
                f" — bu lead'e hemen teklif hazırla"
            )
        summary_data["recommendations"].append(
            f"{len(worst)} lead'in sitesi 60 altında — hepsine audit raporu ile yaklaş"
        )
        summary_data["recommendations"].append(
            "Pitch agent'ı çalıştırırken audit sonuçlarını teklif'e ekle"
        )

        self.save_output("auditor_report.json", summary_data)
        return summary_data

    def _load_leads_with_websites(self) -> list:
        """Load qualified leads that have websites."""
        qual_dir = DATA_DIR / "leads" / "qualified"
        if not qual_dir.exists():
            return []
        files = sorted(qual_dir.glob("*.json"), reverse=True)
        if files:
            with open(files[0]) as f:
                data = json.load(f)
                return [l for l in data.get("leads", [])
                        if l.get("lead", {}).get("website")]
        return []

    def _generate_recommendations(self, report: dict) -> list[str]:
        """Generate actionable recommendations from an audit."""
        recs = []
        seo = report.get("seo", {})
        broken = report.get("broken_links", {})
        tech = report.get("tech_stack", {})

        if seo.get("score", 100) < 50:
            recs.append("SEO skoru çok düşük — bu lead'e SEO hizmeti sun")
        critical = [i for i in seo.get("issues", []) if i.get("type") == "critical"]
        if critical:
            recs.append(f"{len(critical)} kritik SEO sorunu var: {', '.join(i['issue'] for i in critical[:3])}")
        if broken.get("broken_count", 0) > 0:
            recs.append(f"{broken['broken_count']} kırık link tespit edildi — bakım hizmeti sun")

        categorized = tech.get("categorized", {})
        if "CMS" in categorized:
            cms = categorized["CMS"][0]
            recs.append(f"Site {cms} kullanıyor — {cms} uzmanı olarak yaklaş")
        if "Analytics" not in categorized:
            recs.append("Google Analytics yok — analitik kurulumu teklif et")

        return recs

    def _avg(self, results: list, key: str) -> int:
        vals = [r.get(key, 0) for r in results if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals)) if vals else 0
