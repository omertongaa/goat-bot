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

ÇALIŞMA STİLİ:
- Paperclip gibi çalış — paralel, akıcı, sıralı DEĞİL.
- Kullanıcı "X yap" derse, direkt create_ticket ile o agent'ı çağır. "Önce şunu yap,
  sonra bunu yap" diye sıralama yapma. Birden fazla iş eşzamanlı koşabilir.
- "teklif yap" → create_ticket(agent_id=pitch). Scout'u çağırma.
- "email gönder" → create_ticket(agent_id=outreach). Pitch'i önce çağırma.
- "50 lead bul" → create_ticket(agent_id=scout, params={query, location, limit}).
- Kullanıcı sadece hedef anlatıyorsa ("bu ay 50 hot lead hedef") create_goal + plan_goal
  çağır, böylece plan otomatik oluşur.
- Kısa ve net Türkçe konuş.

KURALLAR:
- Her cevap sonunda <<<ACTIONS>>> etiketinden SONRA geçerli JSON array ver. Yoksa [].
- Geçerli agent_id'ler: scout, filter, auditor, pitch, outreach, designer, videomaker,
  videoproducer, content, presenter, brandkit, admanager, social, analytics, sitebuilder,
  youtube, storyboard, mcphub, ceo, goat.
- Aynı anda birden çok create_ticket ekleyebilirsin; hepsi paralel çalışır.
- Email/video/sosyal/ad gibi dışarıya etki eden agent'lar otomatik onay gate'ine takılır —
  kullanıcıya "hazır olunca onay için board'a düşecek" de.

AKSIYON FORMATLARI:
[
  {"action":"create_ticket","agent_id":"scout","title":"...","params":{"query":"...","location":"...","limit":50}},
  {"action":"create_ticket","agent_id":"pitch","title":"Hot lead için teklif hazırla","params":{}},
  {"action":"create_ticket","agent_id":"designer","title":"Logo taslağı","params":{"design_type":"logo","business_name":"X"}},
  {"action":"create_goal","title":"Bu ay 50 hot lead","target_metric":"50 hot leads"},
  {"action":"plan_goal","goal_id":"g_xxxx"},
  {"action":"approve_ticket","ticket_id":"t_xxxx"},
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
        """Template-based reply for when Claude CLI isn't available.

        Intent: parse the user's sentence, extract the TARGET AGENT, fire a
        create_ticket directly. No sequential planning unless user explicitly
        asks for a goal/plan.
        """
        m = (message or "").lower()
        default_location = (company.get("target_cities") or ["İstanbul"])[0]
        limit = _extract_num(m) or 50

        # ── Direct agent dispatch (single action, paralel uyumlu) ──
        if _matches(m, ["teklif", "proposal", "pitch"]):
            return ("Pitch agent'ı ticket açtım — hot leadler için teklif hazırlıyor. Board'da görebilirsin.",
                    [{"action": "create_ticket", "agent_id": "pitch", "title": "Teklif hazırla", "params": {}}])

        if _matches(m, ["email", "mail gönder", "kampanya", "outreach"]):
            return ("Outreach ticket açtım — 3 adımlı email kampanyası hazırlanıyor (gönderim öncesi onay soracak).",
                    [{"action": "create_ticket", "agent_id": "outreach", "title": "Email kampanyası", "params": {}}])

        if _matches(m, ["lead bul", "müşteri bul", "scout", "ara", "bulsun", "bul scout"]):
            query = _extract_first(m, ["restoran", "kafe", "klinik", "otel", "kuaför", "emlak", "spor", "kebapçı", "market", "bakkal"]) or (company.get("niche") or "küçük işletme")
            return (f"Scout ticket açtım — {default_location} için {query} ({limit} lead).",
                    [{"action": "create_ticket", "agent_id": "scout", "title": f"Scout {query}",
                      "params": {"query": query, "location": default_location, "limit": limit}}])

        if _matches(m, ["site denetle", "site analiz", "audit", "seo"]):
            return ("Auditor ticket açtım — hot lead websitelerini denetliyor.",
                    [{"action": "create_ticket", "agent_id": "auditor", "title": "Website audit", "params": {"max_leads": 10}}])

        if _matches(m, ["filtrele", "skorla", "filter", "puanla"]):
            return ("Filter ticket açtım — leadler skorlanıyor.",
                    [{"action": "create_ticket", "agent_id": "filter", "title": "Filter & score", "params": {}}])

        if _matches(m, ["logo", "brand kit", "marka", "brandkit"]):
            name = company.get("name") or "goat"
            return (f"BrandKit ticket açtım — {name} için marka kiti hazırlanıyor.",
                    [{"action": "create_ticket", "agent_id": "brandkit", "title": "Brand kit",
                      "params": {"business_name": name, "industry": company.get("niche", ""), "style": "modern"}}])

        if _matches(m, ["reklam", "ad", "ads", "admanager"]):
            name = company.get("name") or "goat"
            return ("AdManager ticket açtım — reklam kampanyası taslağı hazırlanıyor (yayın için onay soracak).",
                    [{"action": "create_ticket", "agent_id": "admanager", "title": "Reklam kampanyası",
                      "params": {"platform": "meta", "campaign_type": "lead_gen", "budget": "1000", "business_name": name}}])

        if _matches(m, ["sosyal", "social", "instagram", "linkedin"]):
            name = company.get("name") or "goat"
            return ("Social ticket açtım — sosyal medya stratejisi hazırlanıyor.",
                    [{"action": "create_ticket", "agent_id": "social", "title": "Sosyal medya strateji",
                      "params": {"action": "strategy", "platform": "instagram", "business_name": name, "niche": company.get("niche", "")}}])

        if _matches(m, ["video", "youtube", "tiktok", "reels"]):
            name = company.get("name") or "goat"
            return ("VideoMaker ticket açtım — video içerik planı hazırlanıyor (render için onay soracak).",
                    [{"action": "create_ticket", "agent_id": "videomaker", "title": "Video content",
                      "params": {"video_type": "reels", "business_name": name, "topic": company.get("niche", "")}}])

        if _matches(m, ["blog", "içerik", "yaz", "content"]):
            return ("Content ticket açtım — blog/sosyal içerik taslağı hazırlanıyor.",
                    [{"action": "create_ticket", "agent_id": "content", "title": "İçerik taslağı",
                      "params": {"content_type": "blog", "topic": company.get("niche", ""), "language": "tr"}}])

        if _matches(m, ["site yap", "website", "landing", "sitebuilder"]):
            return ("SiteBuilder ticket açtım — landing page hazırlanıyor.",
                    [{"action": "create_ticket", "agent_id": "sitebuilder", "title": "Landing page",
                      "params": {"site_type": "agency"}}])

        if _matches(m, ["analiz", "rapor", "analytics"]):
            return ("Analytics ticket açtım — performans raporu çıkarılıyor.",
                    [{"action": "create_ticket", "agent_id": "analytics", "title": "Performans raporu",
                      "params": {"analysis_type": "internal"}}])

        # ── Bütçe ──
        if "bütçe" in m or "budget" in m:
            agent = _extract_first(m, ["scout", "outreach", "videomaker", "pitch", "designer", "content", "social", "admanager"]) or "scout"
            amt = _extract_num(m) or 20
            return (f"{agent} agent'ına ${amt} aylık bütçe ayarladım.",
                    [{"action": "set_budget", "agent_id": agent, "amount_usd": float(amt)}])

        # ── Onay ──
        if _matches(m, ["onay", "approve", "reddet", "reject"]):
            needs = [t for t in state.get("recent_tickets", []) if t["status"] == "needs_review"]
            if not needs:
                return ("Onay bekleyen ticket yok.", [])
            names = ", ".join(f"{t['title']} ({t['id']})" for t in needs[:3])
            return (f"Onay bekleyen: {names}. Board'dan tek tek onaylayabilirsin, ya da bana 't_xxx onayla' yaz.", [])

        # ── Hedef (sıralı planlama) ──
        if _matches(m, ["hedef", "goal", "bu ay", "bu hafta", "plan yap"]):
            title = message.strip()
            return (f"'{title}' hedefini oluşturuyorum ve planı hazırlıyorum — ticketlar paralel çalışacak.",
                    [{"action": "create_goal", "title": title, "description": "", "target_metric": ""}])

        # ── Durum ──
        if _matches(m, ["durum", "status", "nerede", "ne oluyor"]):
            counts = state.get("counts_by_status", {})
            summary = ", ".join(f"{k}: {v}" for k, v in counts.items()) or "hiç ticket yok"
            return (f"Durum: {summary}. Aktif hedef: {len(state.get('active_goals', []))}.", [])

        # ── Default: don't force a plan, just ask ──
        return (
            "Tam anlamadım. Direkt söyle: 'teklif oluştur', 'email kampanyası başlat', "
            "'İstanbul'da 50 restoran lead'i bul', 'logo hazırla', 'bütçe ver scout 20$'.",
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


def _matches(text: str, keywords: list) -> bool:
    return any(k in text for k in keywords)
