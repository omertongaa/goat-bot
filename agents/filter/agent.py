"""Filter — Lead Qualification Agent

Scores and ranks leads based on outreach-readiness.
Pure Python, no LLM needed.
"""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR


class FilterAgent(BaseAgent):
    agent_id = "filter"
    name = "Filter"
    role = "Scores and qualifies leads for outreach"
    category = "acquisition"

    # Scoring rules
    SCORING = {
        "has_email": 5,
        "has_website": 3,
        "has_phone": 1,
        "good_rating": 2,       # 3.5 - 4.5 range (room for improvement)
        "established": 2,       # 20+ reviews
        "high_reviews": 1,      # 50+ reviews
        "weak_seo": 2,          # SEO score below 60 = opportunity
        "no_analytics": 1,      # No Google Analytics = opportunity
    }

    def run(self) -> dict:
        self.log("Loading latest raw leads...")

        leads = self._load_latest_leads()
        if not leads:
            return {
                "status": "error",
                "summary": "No leads to filter. Run Scout first.",
                "metrics": {},
                "leads": [],
                "recommendations": ["Run Scout agent first to find leads"],
            }

        self.log(f"Scoring {len(leads)} leads...")

        scored = []
        for lead in leads:
            score, breakdown = self._score_lead(lead)
            qualification = "hot" if score >= 8 else "warm" if score >= 5 else "cold"

            scored.append({
                "score": score,
                "qualification": qualification,
                "score_breakdown": breakdown,
                "outreach_ready": score >= 8 and bool(lead.get("email")),
                "lead": {k: v for k, v in lead.items() if k != "raw"},
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Save qualified leads
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"leads/qualified/{timestamp}_qualified.json", {
            "filtered_at": datetime.now().isoformat(),
            "total": len(scored),
            "leads": scored,
        })

        # Stats
        hot = [l for l in scored if l["qualification"] == "hot"]
        warm = [l for l in scored if l["qualification"] == "warm"]
        cold = [l for l in scored if l["qualification"] == "cold"]
        outreach_ready = [l for l in scored if l["outreach_ready"]]

        results = {
            "status": "ok",
            "summary": f"Qualified {len(scored)} leads: {len(hot)} hot, {len(warm)} warm, {len(cold)} cold",
            "metrics": {
                "total_scored": len(scored),
                "hot": len(hot),
                "warm": len(warm),
                "cold": len(cold),
                "outreach_ready": len(outreach_ready),
                "avg_score": round(sum(l["score"] for l in scored) / len(scored), 1) if scored else 0,
                "filtered_at": datetime.now().isoformat(),
            },
            "leads": scored[:20],  # Top 20 in report
            "recommendations": [],
        }

        if outreach_ready:
            results["recommendations"].append(
                f"{len(outreach_ready)} leads ready for outreach — they have email + high score"
            )
        if hot:
            top = hot[0]["lead"]
            results["recommendations"].append(
                f"Top lead: {top.get('name', '?')} (score: {hot[0]['score']}) — start here"
            )
        results["recommendations"].append(
            "Run Outreach agent to create an email campaign for hot leads"
        )

        self.save_output("filter_qualified_report.json", results)
        self.log(f"Done: {len(hot)} hot, {len(warm)} warm, {len(cold)} cold")
        return results

    def _score_lead(self, lead: dict):
        score = 0
        breakdown = {}

        if lead.get("email"):
            score += self.SCORING["has_email"]
            breakdown["has_email"] = self.SCORING["has_email"]

        if lead.get("website"):
            score += self.SCORING["has_website"]
            breakdown["has_website"] = self.SCORING["has_website"]

        if lead.get("phone"):
            score += self.SCORING["has_phone"]
            breakdown["has_phone"] = self.SCORING["has_phone"]

        rating = lead.get("rating", 0)
        if 3.5 <= rating <= 4.5:
            score += self.SCORING["good_rating"]
            breakdown["good_rating"] = self.SCORING["good_rating"]

        reviews = lead.get("review_count", 0)
        if reviews >= 20:
            score += self.SCORING["established"]
            breakdown["established"] = self.SCORING["established"]
        if reviews >= 50:
            score += self.SCORING["high_reviews"]
            breakdown["high_reviews"] = self.SCORING["high_reviews"]

        # Quick SEO check for leads with websites (bonus scoring)
        if lead.get("website"):
            try:
                from services.site_auditor import check_seo, detect_tech_stack
                seo = check_seo(lead["website"])
                if seo.get("score", 100) < 60:
                    score += self.SCORING["weak_seo"]
                    breakdown["weak_seo"] = self.SCORING["weak_seo"]
                tech = detect_tech_stack(lead["website"])
                techs = tech.get("technologies", [])
                if "Google Analytics" not in techs and "Google Tag Manager" not in techs:
                    score += self.SCORING["no_analytics"]
                    breakdown["no_analytics"] = self.SCORING["no_analytics"]
            except Exception:
                pass  # Don't fail scoring if audit fails

        return score, breakdown

    def _load_latest_leads(self) -> list:
        """Load leads from the most recent raw scrape."""
        raw_dir = DATA_DIR / "leads" / "raw"
        if not raw_dir.exists():
            return []
        files = sorted(raw_dir.glob("*.json"), reverse=True)
        if files:
            with open(files[0]) as f:
                data = json.load(f)
                return data.get("leads", [])
        return []
