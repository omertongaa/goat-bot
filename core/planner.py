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

# Cache the agents brief — built once from app.AGENT_MODULES at first call
_AGENTS_BRIEF_CACHE: Optional[str] = None


def _build_agents_brief() -> str:
    """Walk app.AGENT_MODULES, instantiate each agent class, pull
    agent_id / name / role / category. Build a Turkish-friendly brief
    grouped by category. Cached after first build."""
    global _AGENTS_BRIEF_CACHE
    if _AGENTS_BRIEF_CACHE is not None:
        return _AGENTS_BRIEF_CACHE

    try:
        import importlib
        app_mod = importlib.import_module("app")
        modules_map = getattr(app_mod, "AGENT_MODULES", {}) or {}
    except Exception:
        modules_map = {}

    if not modules_map:
        # Last-resort static fallback covering common agents
        _AGENTS_BRIEF_CACHE = _STATIC_AGENTS_BRIEF
        return _AGENTS_BRIEF_CACHE

    agents = []
    for agent_id, spec in modules_map.items():
        if agent_id in ("ceo", "goat"):
            # CEO is the orchestrator itself; goat is the legacy meta-runner
            continue
        try:
            import importlib
            module_path, class_name = spec.rsplit(":", 1)
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            agents.append({
                "id": getattr(cls, "agent_id", agent_id),
                "name": getattr(cls, "name", agent_id.title()),
                "role": getattr(cls, "role", "—"),
                "category": getattr(cls, "category", "other"),
            })
        except Exception:
            continue

    # Group by category — gives Claude semantic structure
    by_cat = {}
    for a in agents:
        by_cat.setdefault(a["category"], []).append(a)

    cat_labels = {
        "acquisition": "Lead bulma & filtreleme",
        "intelligence": "Analiz & istihbarat",
        "creative": "Tasarım & içerik & sunum",
        "marketing": "Pazarlama & reklam & sosyal",
        "delivery": "Teslimat (web sitesi, kampanya)",
        "education": "Eğitim & danışmanlık",
        "production": "Üretim (video / YouTube)",
        "system": "Sistem (MCP, automation, improver)",
        "sales": "Satış (teklif, outreach)",
        "master": "Master orchestrator",
        "other": "Diğer",
    }

    lines = ["AVAILABLE AGENTS — kategori bazlı liste:"]
    for cat in ("acquisition", "sales", "intelligence", "creative",
                "marketing", "delivery", "production", "education", "system", "other"):
        items = by_cat.get(cat) or []
        if not items:
            continue
        lines.append(f"\n## {cat_labels.get(cat, cat).upper()}")
        for a in items:
            lines.append(f"  - {a['id']}: {a['role']}")

    _AGENTS_BRIEF_CACHE = "\n".join(lines)
    return _AGENTS_BRIEF_CACHE


# Static fallback if app.AGENT_MODULES introspection fails
_STATIC_AGENTS_BRIEF = """AVAILABLE AGENTS:
- scout, filter, auditor, leadscorer, pitch, outreach, sitebuilder
- designer, content, presenter, brandkit, videomaker, videoproducer, carousel
- admanager, social, youtube
- analytics, browser, automator
- mentor, mcphub, improver, storyboard
"""

PLANNER_PROMPT = """Sen GOAT şirketinin CEO'susun. Hedefi gerçekleştirmek için
şirketin tüm agentlarından oluşan zengin bir iş planı hazırla.

HEDEF:
  Başlık: {title}
  Açıklama: {description}
  Metrik: {metric}

ŞİRKET BAĞLAMI:
  İsim: {company_name}
  Niş: {niche}
  Hedef şehirler: {cities}

{agents_brief}

PLAN KURALLARI:
1. Hedefin **tüm aşamalarını** çıkar — sadece scout→outreach değil. Hedefe uygunsa
   marka, içerik, sunum, tasarım, web sitesi, sosyal medya, otomasyon adımlarını da ekle.
2. Plan en az **5**, en fazla **15** adım olsun. Büyük hedef için fazla, küçük için az.
3. Her adım gerçek bir agent'a verilsin. Aynı agent birden fazla adımda kullanılabilir
   (örn: content agent hem blog hem social caption üretebilir).
4. Hedefin doğasına uygun **paralel akışlar** kur:
   - Lead-odaklı hedef: scout → filter → auditor → leadscorer → pitch → presenter → outreach
   - Marka/lansman hedefi: brandkit → designer → sitebuilder → content → carousel → social → admanager
   - Büyüme hedefi: analytics → improver → content → social → admanager
5. Mutation eden agent'lar (outreach, social, admanager, youtube, videoproducer, videomaker,
   instagramdm) — params kısmında "needs_approval": true olsun.
6. Her step'in `params`'ını sektöre özel doldur. Boş `{{}}` mümkünse verme.

ÇIKTI — sadece geçerli JSON array ver, açıklama yazma:
[
  {{"agent_id": "scout", "title": "İzmir restoranlarını tara",
    "description": "50 lead, contact details ile",
    "params": {{"query":"restoran", "location":"İzmir", "limit":50}} }},
  {{"agent_id": "leadscorer", "title": "Leadleri AI ile sırala",
    "description": "0-100 puan + hot/warm/cold tier",
    "params": {{}} }},
  ...
]
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
        agents_brief=_build_agents_brief().strip(),
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
    """Rule-based plan when Claude isn't available. Picks one of two
    templates based on goal text: lead-acquisition vs brand-launch.
    Both produce 7-9 steps using a wider range of agents.
    """
    niche = (company.get("niche") or "").lower()
    cities = company.get("target_cities") or []
    target_industries = company.get("target_industries") or []
    company_name = company.get("name") or "goat"

    text = (
        f"{goal.get('title', '')} {goal.get('description', '')} "
        f"{goal.get('target_metric', '')}"
    ).lower()

    is_brand_goal = any(kw in text for kw in (
        "marka", "lansman", "launch", "brand", "kimlik", "rebrand",
        "yeni ürün", "yeni urun", "açılış", "acilis",
    ))

    if is_brand_goal:
        return _brand_launch_plan(company_name, niche)

    # Default: lead-acquisition flow (richer than the old 5-step version)
    query = _infer_query(goal, niche, target_industries)
    location = cities[0] if cities else ""
    limit = _infer_limit(goal)

    return [
        {
            "agent_id": "scout",
            "title": f"Scout: {query} {location}".strip(),
            "description": f"{limit} lead bul (Google Maps + B2B)",
            "params": {"query": query, "location": location, "limit": limit},
        },
        {
            "agent_id": "filter",
            "title": "Leadleri kural-bazlı skorla",
            "description": "Email/website/rating'e göre hot/warm/cold",
            "params": {},
        },
        {
            "agent_id": "leadscorer",
            "title": "Leadleri AI ile derinlemesine skorla",
            "description": "Claude Haiku ile 0-100 puan + tier",
            "params": {},
        },
        {
            "agent_id": "auditor",
            "title": "Hot leadlerin sitelerini denetle",
            "description": "SEO + broken links + tech stack",
            "params": {"max_leads": 10},
        },
        {
            "agent_id": "pitch",
            "title": "Hot leadler için Türkçe teklif PDF'i",
            "description": "Audit-aware proposal + cover image",
            "params": {},
        },
        {
            "agent_id": "presenter",
            "title": "Genel pitch deck hazırla",
            "description": f"{niche} sektörü için sunum, hot leadlerle paylaşılabilir",
            "params": {"template": "pitch_deck", "topic": f"{company_name} — {niche}"},
        },
        {
            "agent_id": "content",
            "title": "Outreach için email + LinkedIn copy",
            "description": "Sektöre özel 3 hook variant",
            "params": {"content_type": "email", "topic": niche, "count": 3},
        },
        {
            "agent_id": "outreach",
            "title": "3 adımlı email kampanyası",
            "description": "Intro → Value → Last call (Instantly.ai)",
            "params": {},
            "needs_approval": True,
        },
    ]


def _brand_launch_plan(company_name: str, niche: str) -> list:
    """Plan for brand/launch goals — uses creative & marketing agents."""
    return [
        {
            "agent_id": "brandkit",
            "title": f"{company_name} marka kimliği oluştur",
            "description": "Renkler, fontlar, ses tonu, logo briefi",
            "params": {"business_name": company_name, "industry": niche, "style": "modern"},
        },
        {
            "agent_id": "designer",
            "title": "Sosyal medya görsel seti",
            "description": "Instagram + LinkedIn + Twitter banner ve post",
            "params": {"design_type": "social_post", "business_name": company_name, "platform": "instagram"},
        },
        {
            "agent_id": "sitebuilder",
            "title": "Lansman landing page",
            "description": "Tek sayfa, CTA odaklı, marka kit ile",
            "params": {"site_type": "agency"},
        },
        {
            "agent_id": "content",
            "title": "Lansman blog yazısı + 10 sosyal post",
            "description": "Türkçe, sektöre özel, SEO odaklı",
            "params": {"content_type": "blog", "topic": f"{company_name} lansman", "count": 1},
        },
        {
            "agent_id": "carousel",
            "title": "Instagram lansman carousel",
            "description": "5-7 slayt, marka renkleri",
            "params": {"topic": f"{company_name} hakkında 5 şey"},
        },
        {
            "agent_id": "presenter",
            "title": "Şirket tanıtım sunumu",
            "description": "Yatırımcı / partner için pitch deck",
            "params": {"template": "company", "topic": f"{company_name} tanıtım"},
        },
        {
            "agent_id": "social",
            "title": "30 günlük sosyal medya planı",
            "description": "Hashtag + posting takvimi + bio",
            "params": {"action": "strategy", "platform": "instagram", "business_name": company_name},
            "needs_approval": True,
        },
        {
            "agent_id": "admanager",
            "title": "Lansman reklam kampanyası",
            "description": "Meta + Google için 5 ad copy varianti",
            "params": {"platform": "meta", "campaign_type": "awareness", "business_name": company_name},
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
