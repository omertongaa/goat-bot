"""CEO — Master Orchestrator Agent.

The CEO is goat's public-facing orchestrator. It:
    - Interprets natural-language user input
    - Creates goals, schedules tickets, delegates to specialists
    - Answers questions about board state (tickets, budgets, goals)
    - Guides the user through what to do next
    - NEVER mutates external systems directly — always goes through a ticket
      with an approval gate for side-effects

Design choice: the CEO is pure orchestration. It returns ACTIONS (as a list
of structured directives) that the caller executes. This keeps the agent
stateless and testable.

Actions the CEO can emit:
    { "action": "create_goal", "title": str, "description": str, "target_metric": str }
    { "action": "create_ticket", "agent_id": str, "params": dict, "title": str }
    { "action": "plan_goal", "goal_id": str }
    { "action": "approve_ticket", "ticket_id": str }
    { "action": "reject_ticket", "ticket_id": str, "reason": str }
    { "action": "set_budget", "agent_id": str, "amount_usd": float }
    { "action": "chat", "text": str }    # fallback — just talk back
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from agents.base import BaseAgent
from core import store, activity_log

BASE_DIR = Path(__file__).resolve().parent.parent.parent

CEO_SYSTEM_PROMPT = """Sen GOAT şirketinin CEO'susun. Kullanıcıyı dinle, şirketi yönet.

KURALLAR:
- Kullanıcıya Türkçe konuş, kısa ve net.
- Her konuşma sonunda <<<ACTIONS>>> etiketinden SONRA geçerli JSON array olarak
  yapılacak işleri listele. Yoksa boş array [].
- Sadece geçerli agent_id'ler kullan: scout, filter, auditor, pitch, outreach,
  designer, videomaker, content, presenter, brandkit, admanager, social, analytics,
  sitebuilder.
- Kalıcı aksiyon gerekmiyorsa (sadece bilgi sorusu) aksiyon boş kalabilir, ama
  yanıtın kullanıcının sorusuna mutlaka değinmeli.
- Email/video/sosyal gibi dışarıya etki eden işler onay ister. Bunu kullanıcıya
  söyle; sistem zaten approval gate uygulayacak.

AKSIYON FORMATLARI:
[
  {"action":"create_goal","title":"...","description":"...","target_metric":"..."},
  {"action":"create_ticket","agent_id":"scout","title":"...","params":{"query":"...", "location":"...", "limit": 50}},
  {"action":"plan_goal","goal_id":"g_xxxx"},
  {"action":"approve_ticket","ticket_id":"t_xxxx"},
  {"action":"reject_ticket","ticket_id":"t_xxxx","reason":"..."},
  {"action":"set_budget","agent_id":"scout","amount_usd": 20.0}
]
"""


class CEOAgent(BaseAgent):
    agent_id = "ceo"
    name = "CEO"
    role = "Master orchestrator — talks to user, delegates to specialists, manages goals and budgets"
    category = "master"

    def run(self, message: str = "", history: Optional[list] = None) -> dict:
        """Process a single user message. Returns {response, actions, metrics}."""
        history = history or []
        company_id = store.active_company_id()
        company = store.load_company(company_id) or {}
        state = self._snapshot(company_id)

        reply_text, actions = self._chat_with_claude(message, history, company, state)
        if reply_text is None:
            reply_text, actions = self._fallback_reply(message, company, state)

        # Execute actions locally so the user sees effect immediately
        executed = [self._execute_action(a, company_id) for a in actions]

        return {
            "status": "ok",
            "summary": reply_text[:160],
            "response": reply_text,
            "actions": actions,
            "executed": executed,
            "state_snapshot": state,
        }

    # ── Internals ─────────────────────────────────────────────────────

    def _snapshot(self, company_id: str) -> dict:
        tickets = store.list_tickets(company_id, limit=50)
        goals = store.list_goals(company_id, status="active")
        budgets = store.load_budgets(company_id)
        by_status: dict = {}
        for t in tickets:
            by_status.setdefault(t["status"], 0)
            by_status[t["status"]] += 1
        return {
            "active_goals": [{"id": g["id"], "title": g["title"], "metric": g.get("target_metric", "")} for g in goals],
            "recent_tickets": [
                {"id": t["id"], "agent_id": t["agent_id"], "status": t["status"], "title": t.get("title", ""), "cost": t.get("cost_usd", 0)}
                for t in tickets[:10]
            ],
            "counts_by_status": by_status,
            "budgets": budgets,
        }

    def _chat_with_claude(self, message: str, history: list, company: dict, state: dict):
        convo = [{"role": "system", "content": CEO_SYSTEM_PROMPT}]
        convo.append({"role": "system", "content": json.dumps({
            "company": {
                "name": company.get("name"),
                "niche": company.get("niche"),
                "target_cities": company.get("target_cities", []),
                "target_industries": company.get("target_industries", []),
            },
            "state": state,
        }, ensure_ascii=False)})
        for h in history[-12:]:
            convo.append(h)
        convo.append({"role": "user", "content": message})

        prompt = self._format_for_cli(convo)
        try:
            res = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=120,
                cwd=str(BASE_DIR),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None, []

        full = (res.stdout or "").strip()
        if not full:
            return None, []
        return self._parse_response(full)

    def _format_for_cli(self, convo: list) -> str:
        lines = []
        for m in convo:
            role = m["role"].upper()
            lines.append(f"[{role}]\n{m['content']}")
        return "\n\n".join(lines)

    def _parse_response(self, text: str):
        actions: list = []
        response = text
        if "<<<ACTIONS>>>" in text:
            head, tail = text.split("<<<ACTIONS>>>", 1)
            response = head.strip()
            match = re.search(r"\[.*\]", tail, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                    if isinstance(parsed, list):
                        actions = parsed
                except json.JSONDecodeError:
                    pass
        return response, actions

    def _fallback_reply(self, message: str, company: dict, state: dict):
        """Template-based reply for when Claude CLI isn't available."""
        m = (message or "").lower()

        # Simple intent heuristics
        if any(w in m for w in ("lead bul", "müşteri bul", "scout", "ara")):
            query = _extract_first(m, ["restoran", "kafe", "klinik", "otel", "kuaför", "emlak", "spor"]) or "küçük işletme"
            location = (company.get("target_cities") or ["İstanbul"])[0]
            limit = _extract_num(m) or 50
            return (
                f"Hemen {location} için {query} arayacak bir Scout ticket açıyorum (limit {limit}). "
                "Tamamlandığında board'dan görebileceksin.",
                [{"action": "create_ticket", "agent_id": "scout", "title": f"Scout {query} {location}",
                  "params": {"query": query, "location": location, "limit": limit}}],
            )
        if any(w in m for w in ("hedef", "goal", "bu ay", "bu hafta")):
            title = message.strip() or "Yeni hedef"
            return (
                f"Hedefi oluşturuyorum: '{title}'. Hemen planlamaya başlıyorum — heartbeat sıraya alacak.",
                [{"action": "create_goal", "title": title, "description": "", "target_metric": ""}],
            )
        if "durum" in m or "status" in m or "nerede" in m:
            counts = state.get("counts_by_status", {})
            summary = ", ".join(f"{k}: {v}" for k, v in counts.items()) or "hiç ticket yok"
            return (f"Durum: {summary}. Aktif hedef: {len(state.get('active_goals', []))}.", [])
        if "onay" in m or "approve" in m:
            needs = [t for t in state.get("recent_tickets", []) if t["status"] == "needs_review"]
            if not needs:
                return ("Onay bekleyen ticket yok.", [])
            names = ", ".join(f"{t['title']} ({t['id']})" for t in needs[:3])
            return (f"Onay bekleyen: {names}. Board'dan tek tek onaylayabilirsin.", [])

        return (
            "Anladım. Sana daha iyi yardımcı olabilmek için şunlardan birini söyle: "
            "'bu ay için hedef koy', 'X şehrinde Y tipi lead bul', 'durum raporu', 'onay bekleyenleri göster'.",
            [],
        )

    def _execute_action(self, action: dict, company_id: str) -> dict:
        from core import planner, agent_runtime

        kind = action.get("action")
        try:
            if kind == "create_goal":
                from core.models import Goal, new_id, to_dict
                g = to_dict(Goal(
                    id=new_id("g"),
                    company_id=company_id,
                    title=action.get("title", "Untitled"),
                    description=action.get("description", ""),
                    target_metric=action.get("target_metric", ""),
                ))
                store.save_goal(g)
                activity_log.append(company_id, "goal_created", actor="ceo", subject=g["id"],
                                    details={"title": g["title"]})
                return {"ok": True, "kind": kind, "id": g["id"]}

            if kind == "plan_goal":
                gid = action.get("goal_id")
                goal = store.load_goal(company_id, gid) if gid else None
                if not goal:
                    return {"ok": False, "kind": kind, "error": "goal not found"}
                plan = planner.plan_goal(company_id, goal)
                tickets = planner.materialize_plan(company_id, gid, plan)
                return {"ok": True, "kind": kind, "tickets": [t["id"] for t in tickets]}

            if kind == "create_ticket":
                t = agent_runtime.create_ticket(
                    company_id=company_id,
                    agent_id=action.get("agent_id", ""),
                    title=action.get("title", ""),
                    params=action.get("params", {}),
                    needs_approval=bool(action.get("needs_approval", False)),
                )
                return {"ok": True, "kind": kind, "id": t["id"]}

            if kind == "approve_ticket":
                t = agent_runtime.approve(company_id, action.get("ticket_id"), approver="ceo")
                return {"ok": bool(t), "kind": kind, "id": action.get("ticket_id")}

            if kind == "reject_ticket":
                t = agent_runtime.reject(company_id, action.get("ticket_id"),
                                         approver="ceo", reason=action.get("reason", ""))
                return {"ok": bool(t), "kind": kind, "id": action.get("ticket_id")}

            if kind == "set_budget":
                b = store.set_budget(company_id, action.get("agent_id", ""),
                                     float(action.get("amount_usd", 0)))
                return {"ok": True, "kind": kind, "budget": b}

            if kind == "chat":
                return {"ok": True, "kind": kind}

            return {"ok": False, "kind": kind, "error": "unknown action"}
        except Exception as e:
            return {"ok": False, "kind": kind, "error": f"{type(e).__name__}: {e}"}


def _extract_first(text: str, words: list) -> Optional[str]:
    for w in words:
        if w in text:
            return w
    return None


def _extract_num(text: str) -> Optional[int]:
    m = re.search(r"\b(\d{1,4})\b", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None
