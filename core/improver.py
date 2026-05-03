"""Self-improvement loop.

Reads the last N tickets per agent, computes:
    - success_rate, avg_cost, p95_cost, common_errors, slow_runs

Then asks the LLM (cheap path: Haiku/Ollama) for *concrete prompt or
parameter changes* the agent should adopt. The output is persisted to
data/agent_improvements/{agent_id}.json so a future run can read it
and the user can review them.

Daily heartbeat calls `improve_all()`. The agents themselves can opt in
by calling `latest_hint(agent_id)` — only the BaseAgent needs to know.
"""

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core import store
from services import llm


IMPROVEMENTS_DIR = Path(os.getenv("GOAT_DATA_DIR") or (Path(__file__).resolve().parent.parent / "data")) / "agent_improvements"


SYSTEM_PROMPT = """Sen bir agent gözlemcisisin. Sana bir agent'ın son N koşusunun özetini veriyorum.
Görevin: 3 maddelik *somut* iyileştirme önerisi yaz. Her madde:
1. Hangi davranışı değiştir (prompt, parametre, retry)
2. Neden (gözlemden veri)
3. Beklenen etki (kısa)

ÇIKTI: sadece geçerli JSON dön, başka hiçbir şey yazma:
{
  "agent_id": "...",
  "summary": "tek cümlelik genel durum",
  "improvements": [
    {"change": "...", "reason": "...", "expected": "..."},
    ...
  ],
  "prompt_hint": "agent prompt'una eklenecek 1-2 cümlelik somut yönerge"
}
"""


def _stats(tickets: list) -> dict:
    if not tickets:
        return {"runs": 0}
    statuses = Counter(t.get("status") for t in tickets)
    costs = [float(t.get("cost_usd") or 0.0) for t in tickets if t.get("cost_usd")]
    durations = []
    for t in tickets:
        s = t.get("started_at"); e = t.get("completed_at")
        if s and e:
            try:
                ds = datetime.fromisoformat(s.replace("Z", "+00:00"))
                de = datetime.fromisoformat(e.replace("Z", "+00:00"))
                durations.append((de - ds).total_seconds())
            except Exception:
                pass
    errors = [t.get("error", "") for t in tickets if t.get("error")]
    completed = statuses.get("completed", 0)
    failed = statuses.get("failed", 0)
    total = completed + failed + statuses.get("cancelled", 0) + statuses.get("paused_budget", 0)
    return {
        "runs": len(tickets),
        "completed": completed,
        "failed": failed,
        "success_rate": round(completed / max(total, 1) * 100, 1),
        "avg_cost_usd": round(sum(costs) / max(len(costs), 1), 4),
        "max_cost_usd": round(max(costs), 4) if costs else 0.0,
        "avg_duration_s": round(sum(durations) / max(len(durations), 1), 1),
        "common_errors": [e for e, _ in Counter(errors).most_common(3) if e],
    }


def improve_agent(company_id: str, agent_id: str, lookback_runs: int = 25) -> dict:
    """Generate improvement hints for one agent. Returns persisted record."""
    tickets = store.list_tickets(company_id, agent_id=agent_id, limit=lookback_runs)
    stats = _stats(tickets)
    if stats.get("runs", 0) < 3:
        record = {
            "agent_id": agent_id,
            "company_id": company_id,
            "stats": stats,
            "summary": "Yeterli koşu verisi yok (en az 3 koşu gerek).",
            "improvements": [],
            "prompt_hint": "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": "skipped",
        }
        _persist(agent_id, record)
        return record

    sample = []
    for t in tickets[:8]:
        sample.append({
            "status": t.get("status"),
            "cost_usd": t.get("cost_usd"),
            "summary": ((t.get("result") or {}).get("summary") or "")[:200],
            "error": (t.get("error") or "")[:200],
            "params": {k: str(v)[:80] for k, v in (t.get("params") or {}).items()},
        })
    user_prompt = (
        f"Agent: {agent_id}\nİstatistik: {json.dumps(stats, ensure_ascii=False)}\n"
        f"Son {len(sample)} koşu: {json.dumps(sample, ensure_ascii=False)[:8000]}"
    )
    response = llm.complete(
        messages=[{"role": "user", "content": user_prompt}],
        task="cheap",
        system=SYSTEM_PROMPT,
        max_tokens=1200,
    )
    text = (response.get("text") or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    parsed = {}
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {"summary": text[:300] or "Parse failed", "improvements": []}

    record = {
        "agent_id": agent_id,
        "company_id": company_id,
        "stats": stats,
        "summary": parsed.get("summary", ""),
        "improvements": parsed.get("improvements", []),
        "prompt_hint": parsed.get("prompt_hint", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": response.get("provider", "?"),
    }
    _persist(agent_id, record)
    return record


def improve_all(company_id: Optional[str] = None) -> list:
    """Run improver across every agent that has tickets in the company."""
    company_id = company_id or store.active_company_id()
    tickets = store.list_tickets(company_id, limit=2000)
    agent_ids = sorted({t.get("agent_id") for t in tickets if t.get("agent_id")})
    out = []
    for aid in agent_ids:
        try:
            out.append(improve_agent(company_id, aid))
        except Exception as e:
            out.append({"agent_id": aid, "error": str(e)})
    return out


def latest_hint(agent_id: str) -> str:
    """Return the latest prompt_hint for an agent (used by BaseAgent at run time)."""
    rec = _load(agent_id)
    return (rec or {}).get("prompt_hint") or ""


def latest_record(agent_id: str) -> dict:
    return _load(agent_id) or {}


def all_records() -> list:
    if not IMPROVEMENTS_DIR.exists():
        return []
    out = []
    for f in IMPROVEMENTS_DIR.glob("*.json"):
        try:
            out.append(json.loads(f.read_text()))
        except Exception:
            continue
    out.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
    return out


def _persist(agent_id: str, record: dict) -> None:
    IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = IMPROVEMENTS_DIR / f"{agent_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))


def _load(agent_id: str) -> Optional[dict]:
    path = IMPROVEMENTS_DIR / f"{agent_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None
