"""CEO orchestrator — gerçek ajanlar arası iletişim.

Kullanıcı CEO'ya bir görev verdiğinde:
    1. CEO görevi ajan-listesi olarak parçalar (planlama adımı)
    2. Her ajanı **sırayla** çalıştırır
    3. Her ajanın çıktısı bir sonraki ajanın **bağlamına** girer
    4. CEO her step'te kullanıcıya canlı update yollar
       ("brandkit hazır → social agent'a marka stilini veriyorum...")
    5. Sonunda özet sunar

Bu modül stream_chat_events'a alternatif: "orchestrate" modu.
SSE event'leri:
    plan        — {steps: [{agent, params, why}]}
    step_start  — {step, agent, message}
    step_done   — {step, agent, summary, ticket_id}
    step_error  — {step, agent, error}
    text_delta  — {text}     CEO açıklaması
    done        — {summary}
"""

import json
import os
import re
import subprocess
import importlib
from pathlib import Path
from typing import Optional

from core import store, agent_runtime, activity_log
from core.models import Goal, new_id, to_dict

BASE_DIR = Path(__file__).resolve().parent.parent

ORCHESTRATOR_PROMPT = """Sen GOAT şirketinin CEO'susun. Kullanıcının görevini
ajanlara dağıtacaksın. Her ajan kendi görevini yapar, çıktısını sonraki ajana
context olarak veririm.

Mevcut ajanlar (sadece bunları kullan):
- scout      → Lead bulur (params: query, location, limit)
- filter     → Leadleri skorlar
- auditor    → Website denetler (params: url ya da max_leads)
- brandkit   → Marka kiti hazırlar (params: business_name, industry, style)
- designer   → Görsel üretir (params: design_type, business_name, theme)
- content    → Yazı/blog/email üretir (params: content_type, topic, language)
- social     → Sosyal medya stratejisi (params: action, platform, business_name)
- presenter  → Sunum oluşturur (params: template, topic, business_name)
- pitch      → Hot leadlere teklif PDF'i hazırlar
- outreach   → Email kampanyası hazırlar (3 adımlı dizi)
- admanager  → Reklam kampanyası planı (params: platform, campaign_type, budget)
- analytics  → Sektör/iç analiz (params: analysis_type)
- videomaker → Video script + storyboard (params: video_type, topic)
- sitebuilder→ Landing page (params: site_type)
- mcphub     → MCP araç katalog (params: action)

KURALLAR:
- Sadece geçerli JSON array dön, başka açıklama YOK.
- Her step'in `why` alanı 1 cümle: neden bu ajan şimdi.
- Adım sayısı 1-6 arası. Az iş için tek adım yeterli.
- Bağlamı önemse: brandkit önce gelirse content/social ona göre ayarlanır.

ÇIKTI ŞABLONU:
[
  {"agent":"brandkit","why":"...","params":{...}},
  {"agent":"social","why":"...","params":{...}}
]
"""

REFLECTION_PROMPT_TEMPLATE = """Sen GOAT şirketinin CEO'susun. Şu ajanın çıktısını
özetle ve bir sonraki ajan için **kısa context notu** üret (max 200 karakter).

Ajan: {agent}
Görev: {title}
Çıktı: {output}

Sadece tek paragraflık context döndür, action JSON yok.
"""


def _run_claude_cli(prompt: str, timeout: int = 60) -> str:
    """Run Claude CLI with subscription (no API key)."""
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        res = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(BASE_DIR), env=clean_env,
        )
        return (res.stdout or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _planning_with_claude(message: str, company: dict) -> Optional[list]:
    """Ask Claude to break the user's task into ordered agent steps."""
    company_brief = json.dumps({
        "name": company.get("name"),
        "niche": company.get("niche"),
        "target_cities": company.get("target_cities", []),
    }, ensure_ascii=False)
    full = f"{ORCHESTRATOR_PROMPT}\n\nŞİRKET:\n{company_brief}\n\nGÖREV:\n{message}"
    text = _run_claude_cli(full, timeout=90)
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return None
    try:
        plan = json.loads(m.group())
        if isinstance(plan, list) and all(isinstance(s, dict) and s.get("agent") for s in plan):
            return plan[:6]  # cap
    except Exception:
        return None
    return None


def _resolve_run_params(agent_id: str, params: dict, ctx_notes: list, company: dict) -> dict:
    """Map planner-emitted params to the agent's actual run() signature."""
    p = dict(params or {})
    biz = company.get("name") or "GOAT"
    niche = company.get("niche") or "dijital pazarlama"

    if agent_id == "scout":
        return {
            "query": p.get("query", niche),
            "location": p.get("location", (company.get("target_cities") or ["İstanbul"])[0]),
            "limit": int(p.get("limit", 30)),
        }
    if agent_id == "auditor":
        return {"url": p.get("url", ""), "max_leads": int(p.get("max_leads", 10))}
    if agent_id == "brandkit":
        return {"business_name": p.get("business_name", biz),
                "industry": p.get("industry", niche),
                "style": p.get("style", "modern"),
                "values": p.get("values", "")}
    if agent_id == "designer":
        return {"design_type": p.get("design_type", "social_post"),
                "business_name": p.get("business_name", biz),
                "platform": p.get("platform", "instagram"),
                "theme": p.get("theme", " ".join(ctx_notes)[:120]),
                "text": p.get("text", "")}
    if agent_id == "content":
        return {"content_type": p.get("content_type", "blog"),
                "topic": p.get("topic", niche),
                "tone": p.get("tone", "profesyonel"),
                "language": p.get("language", "tr"),
                "platform": p.get("platform", ""),
                "count": int(p.get("count", 1))}
    if agent_id == "social":
        return {"action": p.get("action", "strategy"),
                "platform": p.get("platform", "instagram"),
                "business_name": p.get("business_name", biz),
                "niche": p.get("niche", niche)}
    if agent_id == "presenter":
        return {"template": p.get("template", "pitch_deck"),
                "topic": p.get("topic", niche),
                "business_name": p.get("business_name", biz),
                "audience": p.get("audience", "")}
    if agent_id == "admanager":
        return {"platform": p.get("platform", "meta"),
                "campaign_type": p.get("campaign_type", "lead_gen"),
                "budget": str(p.get("budget", "1000")),
                "business_name": p.get("business_name", biz),
                "target_audience": p.get("target_audience", "")}
    if agent_id == "analytics":
        return {"analysis_type": p.get("analysis_type", "internal"),
                "target": p.get("target", ""),
                "industry": p.get("industry", niche),
                "location": p.get("location", "")}
    if agent_id == "videomaker":
        return {"video_type": p.get("video_type", "reels"),
                "business_name": p.get("business_name", biz),
                "topic": p.get("topic", niche),
                "target_audience": p.get("target_audience", ""),
                "count": int(p.get("count", 2)),
                "language": p.get("language", "tr")}
    if agent_id == "sitebuilder":
        return {"site_type": p.get("site_type", "agency"),
                "lead_index": int(p.get("lead_index", 0))}
    if agent_id == "mcphub":
        return {"action": p.get("action", "list"),
                "tool_id": p.get("tool_id", ""),
                "category": p.get("category", "")}
    return {}


def _agent_modules() -> dict:
    """Mirror app.AGENT_MODULES — kept here to avoid circular import."""
    try:
        return importlib.import_module("app").AGENT_MODULES
    except Exception:
        return {}


def _instantiate_agent(agent_id: str):
    spec = _agent_modules().get(agent_id)
    if not spec:
        return None
    mod, cls = spec.rsplit(":", 1)
    return getattr(importlib.import_module(mod), cls)()


def orchestrate(message: str, company_id: str):
    """Run the full orchestration as an SSE event generator."""
    company = store.load_company(company_id) or {}

    yield {"kind": "text_delta", "text": "🧠 Görevi anlıyorum, ajan planı çıkarıyorum...\n\n"}

    plan = _planning_with_claude(message, company)
    if not plan:
        yield {"kind": "text_delta",
               "text": "⚠ Plan oluşturulamadı. Tek ajanlı basit moda geçiyorum.\n"}
        # Fallback: try to map message intent to a single agent via fallback CEOAgent
        from agents.ceo.agent import CEOAgent
        agent = CEOAgent()
        result = agent.run(message=message, history=[])
        yield {"kind": "text_delta", "text": result.get("response", "")}
        yield {"kind": "done", "response": result.get("response", "")}
        return

    yield {"kind": "plan", "steps": [{"agent": s["agent"], "why": s.get("why", "")} for s in plan]}
    yield {"kind": "text_delta",
           "text": f"📋 **Plan**: {len(plan)} adım. Sırayla çalıştırıyorum.\n\n"}

    # Optional: anchor under a goal so progress shows in the sidebar
    goal = to_dict(Goal(
        id=new_id("g"),
        company_id=company_id,
        title=(message[:60] + "…") if len(message) > 60 else message,
        target_metric=f"{len(plan)} ajan adımı",
        description="CEO orkestrasyon",
    ))
    store.save_goal(goal)
    activity_log.append(company_id, "goal_created", actor="ceo", subject=goal["id"],
                        details={"title": goal["title"], "via": "orchestrator"})

    ctx_notes: list = []
    summaries: list = []

    for i, step in enumerate(plan, 1):
        agent_id = step["agent"]
        agent = _instantiate_agent(agent_id)
        if not agent:
            yield {"kind": "step_error", "step": i, "agent": agent_id,
                   "error": "agent bulunamadı"}
            continue

        why = step.get("why", "")
        yield {"kind": "step_start", "step": i, "total": len(plan),
               "agent": agent_id, "why": why}
        yield {"kind": "text_delta",
               "text": f"\n**Adım {i}/{len(plan)}** — `{agent_id}` çağırılıyor: {why}\n"}

        run_params = _resolve_run_params(agent_id, step.get("params", {}), ctx_notes, company)

        try:
            ticket = agent_runtime.execute_in_ticket(
                agent_id=agent_id,
                run_fn=agent.run,
                params=run_params,
                title=f"[Step {i}] {why[:50]}" if why else f"[Step {i}] {agent_id}",
                goal_id=goal["id"],
            )
        except Exception as e:
            yield {"kind": "step_error", "step": i, "agent": agent_id,
                   "error": f"{type(e).__name__}: {e}"}
            continue

        result = ticket.get("result") or {}
        summary = result.get("summary", ticket.get("status", "?"))
        ticket_id = ticket.get("id", "")
        summaries.append({"agent": agent_id, "summary": summary, "ticket_id": ticket_id,
                          "status": ticket["status"]})

        if ticket["status"] in ("failed", "paused_budget"):
            err = ticket.get("error", "")[:120]
            yield {"kind": "step_error", "step": i, "agent": agent_id,
                   "error": err, "ticket_id": ticket_id}
            yield {"kind": "text_delta",
                   "text": f"  ⚠ `{agent_id}` başarısız: {err}\n"}
            # Continue with remaining steps — they may still succeed
            continue

        yield {"kind": "step_done", "step": i, "agent": agent_id,
               "summary": summary, "ticket_id": ticket_id}
        yield {"kind": "text_delta",
               "text": f"  ✓ `{agent_id}` tamamlandı — {summary[:120]}\n"}

        # Distill output → context for next step (Claude reflection, optional)
        try:
            output_blob = json.dumps(result, ensure_ascii=False)[:1500]
            note_prompt = REFLECTION_PROMPT_TEMPLATE.format(
                agent=agent_id, title=ticket.get("title", ""), output=output_blob,
            )
            note = _run_claude_cli(note_prompt, timeout=30)
            if note:
                ctx_notes.append(f"[{agent_id}] {note[:300]}")
        except Exception:
            pass

    # Final summary
    yield {"kind": "text_delta", "text": "\n---\n## 📊 Özet\n\n"}
    for s in summaries:
        emoji = "✅" if s["status"] in ("completed", "approved", "needs_review") else "❌"
        yield {"kind": "text_delta",
               "text": f"- {emoji} **{s['agent']}** — {s['summary'][:140]}\n"}

    yield {"kind": "done",
           "summary": f"{len(plan)} adım çalıştırıldı, {sum(1 for s in summaries if s['status'] in ('completed','approved','needs_review'))} başarılı.",
           "goal_id": goal["id"],
           "summaries": summaries}
