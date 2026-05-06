"""Improver — looks at every agent's run history and suggests upgrades.

Wraps core/improver.py for ticket-based execution. Run nightly via the
heartbeat, or manually from the board ("Self-improve" button).
"""

from agents.base import BaseAgent
from core import improver, store


class ImproverAgent(BaseAgent):
    agent_id = "improver"
    name = "Improver"
    role = "Tüm agent'ların geçmişini inceler, somut iyileştirme önerileri çıkarır"
    category = "system"

    def run(self, agent_id: str = "", lookback_runs: int = 25) -> dict:
        company_id = store.active_company_id()
        if agent_id:
            self.log(f"{agent_id} için improver çalışıyor (son {lookback_runs} koşu)")
            rec = improver.improve_agent(company_id, agent_id, lookback_runs=lookback_runs)
            return {
                "status": "ok",
                "summary": f"{agent_id}: {rec.get('summary','')}",
                "metrics": {"agent": agent_id, **rec.get("stats", {})},
                "result": rec,
                "recommendations": [imp.get("change", "") for imp in rec.get("improvements", [])],
            }

        self.log("Tüm agent'lar için improver çalışıyor")
        records = improver.improve_all(company_id)
        improved = [r for r in records if r.get("improvements")]
        return {
            "status": "ok",
            "summary": f"{len(improved)}/{len(records)} agent için iyileştirme önerisi üretildi",
            "metrics": {
                "total_agents": len(records),
                "with_suggestions": len(improved),
            },
            "result": {"records": records},
            "recommendations": [
                f"{r['agent_id']}: {r.get('summary','')[:80]}" for r in improved[:5]
            ],
        }
