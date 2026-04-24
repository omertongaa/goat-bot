"""Planner — turns a Goal into an ordered list of Tickets.

Uses Claude CLI for rich plans; falls back to a rule-based Turkish-SMB
template when Claude isn't available.

Plan output shape:
    [
      {"agent_id": "scout", "title": "...", "params": {...}, "needs_approval": False},
      {"agent_id": "filter", ...},
      {"agent_id": "auditor", ...},
      {"agent_id": "pitch", ..., "needs_approval": True},
      {"agent_id": "outreach", ..., "needs_approval": True},
    ]

After planning, the caller invokes `materialize_plan()` to turn each plan step
into an actual Ticket in the store (status=pending).
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from core import store, activity_log, agent_runtime

BASE_DIR = Path(__file__).resolve().parent.parent

# Agents that mutate external state — always require approval
MUTATION_AGENTS = {"outreach", "youtube", "social", "videoproducer", "admanager", "instagramdm"}


def plan_goal(company_id: str, goal: dict) -> list:
    """Return a list of plan steps for achieving the goal."""
    company = store.load_company(company_id) or {}

    plan = _plan_with_claude(company, goal)
    if not plan:
        plan = _plan_fallback(company, goal)

    for step in plan:
        if step.get("agent_id") in MUTATION_AGENTS:
            step["needs_approval"] = True
        step.setdefault("needs_approval", False)
        step.setdefault("params", {})
        step.setdefault("title", f"{step.get('agent_id', '?')} step")

    return plan


def materialize_plan(company_id: str, goal_id: str, plan: list) -> list:
    """Create pending tickets for each plan step — all independent, no chaining.

    Tickets are intentionally NOT linked via parent_ticket_id so they can
    execute in parallel. The user wants Paperclip-style concurrent execution,
    not a strict pipeline. Agents that truly need upstream data will no-op
    gracefully (e.g. Pitch with no hot leads).
    """
    created = []
    for step in plan:
        t = agent_runtime.create_ticket(
            company_id=company_id,
            agent_id=step["agent_id"],
            title=step["title"],
            description=step.get("description", ""),
            params=step.get("params", {}),
            goal_id=goal_id,
            needs_approval=step.get("needs_approval", False),
        )
        created.append(t)

    activity_log.append(
        company_id, "plan_created", actor="planner", subject=goal_id,
        details={"steps": len(created), "agents": [t["agent_id"] for t in created]},
    )
    return created


# ── Claude-backed planner ──────────────────────────────────────────

AVAILABLE_AGENTS_BRIEF = """
Available agents and what they do:
- scout:      Find business leads from Google Maps / B2B sources. Params: query (str), location (str), limit (int).
- filter:     Score and classify leads (hot/warm/cold). No params.
- auditor:    Audit a website for SEO, broken links, tech stack. Params: url (str) OR max_leads (int) to batch.
- pitch:      Generate a Turkish proposal PDF for hot leads. No params.
- outreach:   Create a 3-step email campaign via Instantly.ai. Requires APPROVAL before send. No params.
- designer:   Generate visual design assets. Params: type (str), brand (dict).
- videomaker: Generate an AI video via Kie.ai + Remotion. Requires APPROVAL.
- content:    Generate blog/social content drafts.
- brandkit:   Build a brand kit (colors, logo, voice). Params: brand_name (str).
- admanager:  Generate paid ad campaigns. Requires APPROVAL.
- social:     Schedule social media posts. Requires APPROVAL.
- analytics:  Compute metrics from past runs.
- sitebuilder: Build a landing page for a lead. Params: lead_index (int).
- presenter:  Build a presentation deck.
"""

PLANNER_PROMPT = """Sen GOAT şirketinin CEO'susun. Aşağıdaki hedefi gerçekleştirmek için
agentlardan oluşan bir iş planı hazırla. Sadece geçerli agent_id'leri kullan.

HEDEF:
  Başlık: {title}
  Açıklama: {description}
  Metrik: {metric}

ŞİRKET BAĞLAMI:
  İsim: {company_name}
  Niş: {niche}
  Hedef şehirler: {cities}

{agents_brief}

ÇIKTI — sadece geçerli JSON array ver, başka açıklama yazma:
[
  {{"agent_id": "scout",  "title": "...", "description": "...", "params": {{"query":"...", "location":"...", "limit":50}} }},
  {{"agent_id": "filter", "title": "...", "description": "...", "params": {{}} }},
  ...
]
Adım sayısı 3-8 arası. Sıra önemli (önceki adıma bağımlı olabilir).
"""


def _plan_with_claude(company: dict, goal: dict) -> Optional[list]:
    """Try to plan via Claude CLI. Returns None on failure/unavailable."""
    prompt = PLANNER_PROMPT.format(
        title=goal.get("title", ""),
        description=goal.get("description", ""),
        metric=goal.get("target_metric", ""),
        company_name=company.get("name", "goat"),
        niche=company.get("niche", "—"),
        cities=", ".join(company.get("target_cities", []) or []) or "—",
        agents_brief=AVAILABLE_AGENTS_BRIEF.strip(),
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=90,
            cwd=str(BASE_DIR),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    text = (result.stdout or "").strip()
    if not text:
        return None
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group())
        if isinstance(parsed, list) and all(isinstance(s, dict) and s.get("agent_id") for s in parsed):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


# ── Rule-based fallback ────────────────────────────────────────────

def _plan_fallback(company: dict, goal: dict) -> list:
    """Sensible Turkish-SMB default when Claude is unavailable.

    The default flow: Scout → Filter → Auditor → Pitch → Outreach.
    Query/location pulled from company profile with goal-specific overrides.
    """
    niche = (company.get("niche") or "").lower()
    cities = company.get("target_cities") or []
    target_industries = company.get("target_industries") or []

    query = _infer_query(goal, niche, target_industries)
    location = cities[0] if cities else ""

    limit = _infer_limit(goal)

    return [
        {
            "agent_id": "scout",
            "title": f"Scout {query} {location}".strip(),
            "description": f"{limit} lead bul: {query} / {location}",
            "params": {"query": query, "location": location, "limit": limit},
        },
        {
            "agent_id": "filter",
            "title": "Leadleri skorla ve sınıflandır",
            "description": "Hot / warm / cold ayrımı",
            "params": {},
        },
        {
            "agent_id": "auditor",
            "title": "Hot leadlerin websitelerini denetle",
            "description": "SEO + broken links + tech stack",
            "params": {"max_leads": 10},
        },
        {
            "agent_id": "pitch",
            "title": "Hot leadler için Türkçe teklif hazırla",
            "description": "PDF proposal + cover image",
            "params": {},
        },
        {
            "agent_id": "outreach",
            "title": "3 adımlı email kampanyası (ONAY GEREKLİ)",
            "description": "Intro → Value → Last call",
            "params": {},
            "needs_approval": True,
        },
    ]


def _infer_query(goal: dict, niche: str, industries: list) -> str:
    text = " ".join(filter(None, [goal.get("title", ""), goal.get("description", ""), goal.get("target_metric", "")])).lower()

    hints = {
        "restoran": "restoran", "kafe": "kafe", "cafe": "kafe",
        "klinik": "klinik", "diş": "diş kliniği", "dis": "diş kliniği",
        "otel": "otel", "hotel": "otel",
        "kuaför": "kuaför", "kuafor": "kuaför", "salon": "güzellik salonu",
        "emlak": "emlak ofisi",
        "spor": "spor salonu",
        "butik": "butik", "mağaza": "mağaza",
        "market": "market", "bakkal": "bakkal",
    }
    for k, v in hints.items():
        if k in text:
            return v
    if industries:
        return industries[0]
    if "kebap" in niche:
        return "kebapçı"
    return "küçük işletme"


def _infer_limit(goal: dict) -> int:
    text = f"{goal.get('title', '')} {goal.get('target_metric', '')} {goal.get('description', '')}"
    nums = re.findall(r"\b(\d{1,4})\b", text)
    if nums:
        try:
            n = int(nums[0])
            # target_metric might say "50 hot leads" — we need more raw leads to get that many hot
            return min(200, max(20, n * 2))
        except ValueError:
            pass
    return 50
