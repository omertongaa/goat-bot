"""LeadScorer — Claude Haiku based 0-100 scoring.

Runs after Filter (or stand-alone). Re-orders Filter's qualified leads
using rich criteria the rule-based Filter can't capture: niche fit,
website quality, social presence, business maturity. Cheap (Haiku) and
fast — batches up to 25 leads in one call.

Falls back to rule-based scoring if no Anthropic key.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR
from core import cost_tracker


SYSTEM_PROMPT = """Sen bir B2B lead scoring uzmanısın. Sana JSON formatında lead listesi veriyorum.
Her lead için 0-100 arası score ver. Kriterler:
- Website kalitesi (var mı, modern mi)
- İletişim bilgileri (email, telefon, sosyal medya)
- Niche fit (hedef niş ile uyum)
- Business maturity (review sayısı, rating)
- Outreach potansiyeli

ÇIKTI FORMATI: Sadece geçerli JSON dön, başka hiçbir şey yazma:
{"scores": [{"name": "...", "score": 0-100, "reason": "kısa Türkçe gerekçe", "tier": "hot|warm|cold"}]}
hot >= 80, warm 60-79, cold < 60.
"""


class LeadScorerAgent(BaseAgent):
    agent_id = "leadscorer"
    name = "LeadScorer"
    role = "Claude Haiku ile lead'leri 0-100 puanla, hot/warm/cold sırala"
    category = "acquisition"

    def run(self, max_leads: int = 50, niche: str = "") -> dict:
        config = self.load_config()
        niche = niche or config.get("niche") or config.get("agency_niche") or ""

        leads = self._load_qualified_leads(max_leads)
        if not leads:
            return {
                "status": "warning",
                "summary": "Skorlanacak qualified lead yok. Önce Scout + Filter çalıştır.",
                "metrics": {"scored": 0},
                "leads": [],
                "recommendations": ["Scout → Filter pipeline'ını çalıştır"],
            }

        self.log(f"{len(leads)} lead Haiku'ya gönderiliyor (niche={niche})")
        api_key = os.environ.get("ANTHROPIC_API_KEY") or config.get("anthropic_api_key")

        scores = []
        if api_key:
            scores = self._score_with_haiku(leads, niche, api_key)
        if not scores:
            self.log("Haiku skorlama yapılamadı, rule-based fallback")
            scores = self._score_rule_based(leads)

        scored = self._merge_scores(leads, scores)
        scored.sort(key=lambda x: x.get("ai_score", 0), reverse=True)

        hot = [s for s in scored if (s.get("tier") or "").lower() == "hot"]
        warm = [s for s in scored if (s.get("tier") or "").lower() == "warm"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_data(f"leads/scored/{timestamp}_scored.json", scored)
        self.save_output(f"leadscorer_{timestamp}.json", {
            "total": len(scored),
            "hot": len(hot),
            "warm": len(warm),
            "leads": scored[:20],
        })

        return {
            "status": "ok",
            "summary": f"{len(scored)} lead skorlandı: {len(hot)} hot, {len(warm)} warm",
            "metrics": {
                "scored": len(scored),
                "hot": len(hot),
                "warm": len(warm),
                "avg_score": round(sum(s.get("ai_score", 0) for s in scored) / max(len(scored), 1), 1),
            },
            "leads": scored,
            "recommendations": [
                f"İlk {min(10, len(hot))} hot lead için Outreach çalıştır",
                "Warm lead'lere Pitch agent ile ek araştırma yap",
            ],
        }

    def _load_qualified_leads(self, limit: int) -> list:
        qdir = DATA_DIR / "leads" / "qualified"
        if not qdir.exists():
            return []
        files = sorted(qdir.glob("*.json"), reverse=True)
        if not files:
            return []
        try:
            data = json.loads(files[0].read_text())
        except Exception:
            return []
        leads = data if isinstance(data, list) else (data.get("leads") or [])
        return leads[:limit]

    def _score_with_haiku(self, leads: list, niche: str, api_key: str) -> list:
        try:
            import anthropic
        except Exception:
            return []
        client = anthropic.Anthropic(api_key=api_key)
        compact = [{
            "name": l.get("name", ""),
            "email": bool(l.get("email")),
            "phone": bool(l.get("phone")),
            "website": l.get("website", "") or "",
            "rating": l.get("rating") or 0,
            "reviews": l.get("review_count") or l.get("reviews_count") or 0,
            "category": l.get("category", ""),
            "city": l.get("city", "") or l.get("location", ""),
        } for l in leads]
        prompt = f"Niş: {niche or 'genel'}\nLead listesi:\n{json.dumps(compact, ensure_ascii=False)[:14000]}"
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            usage = getattr(msg, "usage", None)
            if usage:
                cost_tracker.record("claude.token_in", units=getattr(usage, "input_tokens", 0))
                cost_tracker.record("claude.token_out", units=getattr(usage, "output_tokens", 0))
            text = msg.content[0].text if msg.content else ""
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text)
            return parsed.get("scores", [])
        except Exception as e:
            self.log(f"Haiku error: {e}")
            return []

    def _score_rule_based(self, leads: list) -> list:
        out = []
        for l in leads:
            score = 0
            if l.get("email"): score += 25
            if l.get("phone"): score += 10
            if l.get("website"): score += 15
            r = l.get("rating") or 0
            if 3.5 <= r <= 4.7: score += 15
            rc = l.get("review_count") or l.get("reviews_count") or 0
            if rc >= 50: score += 20
            elif rc >= 20: score += 10
            score = min(score, 100)
            tier = "hot" if score >= 80 else "warm" if score >= 60 else "cold"
            out.append({"name": l.get("name", ""), "score": score, "tier": tier, "reason": "Rule-based"})
        return out

    def _merge_scores(self, leads: list, scores: list) -> list:
        score_map = {s.get("name", ""): s for s in scores}
        out = []
        for l in leads:
            s = score_map.get(l.get("name", ""), {})
            out.append({
                **l,
                "ai_score": s.get("score", 0),
                "tier": s.get("tier", "cold"),
                "ai_reason": s.get("reason", ""),
            })
        return out
