"""goat — Agency-in-a-Box Command Center"""

import importlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from agents import AGENTS, CATEGORIES

app = FastAPI(title="goat — Agency-in-a-Box")
BASE_DIR = Path(__file__).parent
# Writable bases (overridden to /tmp on Vercel via GOAT_DATA_DIR / GOAT_OUTPUTS_DIR)
DATA_BASE = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))
OUTPUTS_BASE = Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
# Serve carousel PNG outputs so the board can preview them
_carousel_out = OUTPUTS_BASE / "carousel"
_carousel_out.mkdir(parents=True, exist_ok=True)
app.mount("/static/carousel", StaticFiles(directory=str(_carousel_out)), name="carousel_static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

AGENT_MODULES = {
    "ceo": "agents.ceo.agent:CEOAgent",
    "goat": "agents.goat.agent:GoatAgent",
    "scout": "agents.scout.agent:ScoutAgent",
    "filter": "agents.filter.agent:FilterAgent",
    "auditor": "agents.auditor.agent:AuditorAgent",
    "outreach": "agents.outreach.agent:OutreachAgent",
    "pitch": "agents.pitch.agent:PitchAgent",
    "mentor": "agents.mentor.agent:MentorAgent",
    "sitebuilder": "agents.sitebuilder.agent:SiteBuilderAgent",
    # --- New Agents ---
    "designer": "agents.designer.agent:DesignerAgent",
    "videomaker": "agents.videomaker.agent:VideoMakerAgent",
    "admanager": "agents.admanager.agent:AdManagerAgent",
    "analytics": "agents.analytics.agent:AnalyticsAgent",
    "content": "agents.content.agent:ContentAgent",
    "presenter": "agents.presenter.agent:PresenterAgent",
    "social": "agents.social.agent:SocialAgent",
    "brandkit": "agents.brandkit.agent:BrandKitAgent",
    "storyboard": "agents.storyboard.agent:StoryboardAgent",
    "mcphub": "agents.mcphub.agent:MCPHubAgent",
    "videoproducer": "agents.videoproducer.agent:VideoProducerAgent",
    "youtube": "agents.youtube.agent:YouTubeAgent",
    "leadscorer": "agents.leadscorer.agent:LeadScorerAgent",
    "browser": "agents.browser.agent:BrowserAgent",
    "carousel": "agents.carousel.agent:CarouselAgent",
    "improver": "agents.improver.agent:ImproverAgent",
    "automator": "agents.automator.agent:AutomatorAgent",
}

AGENT_RESULTS = {}
CHAT_HISTORIES = {}  # {agent_id: [{"role": "user"|"assistant", "content": str}, ...]}
MAX_HISTORY = 20  # keep last 20 messages per agent


def get_agent_instance(agent_id: str):
    module_path, class_name = AGENT_MODULES[agent_id].rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def load_config():
    """Merge legacy user_profile.json with the active company's profile,
    so callers see all api_keys and settings flattened to the top level."""
    legacy = {}
    path = DATA_BASE / "config" / "user_profile.json"
    if path.exists():
        try:
            with open(path) as f:
                legacy = json.load(f) or {}
        except Exception:
            legacy = {}
    # Merge in active company profile
    try:
        from core import store as _store
        cid = _store.active_company_id()
        company = _store.load_company(cid) or {}
        flat = dict(legacy)
        flat["id"] = cid
        for fld in ("name", "owner_name", "niche", "target_cities", "target_industries"):
            v = company.get(fld)
            if v:
                flat[fld] = v
        flat.setdefault("agency_name", company.get("name") or legacy.get("agency_name", ""))
        for k, v in (company.get("api_keys") or {}).items():
            if v:
                flat[k] = v
        for k, v in (company.get("settings") or {}).items():
            flat.setdefault(k, v)
        return flat
    except Exception:
        return legacy


def load_pipeline_stats():
    """Load stats from latest reports for the dashboard."""
    stats = {"leads_found": 0, "leads_qualified": 0, "hot": 0, "warm": 0, "cold": 0}
    reports_dir = OUTPUTS_BASE / "reports"

    scout_report = reports_dir / "scout_leads_report.json"
    if scout_report.exists():
        with open(scout_report) as f:
            data = json.load(f)
            stats["leads_found"] = data.get("metrics", {}).get("total_found", 0)

    filter_report = reports_dir / "filter_qualified_report.json"
    if filter_report.exists():
        with open(filter_report) as f:
            data = json.load(f)
            m = data.get("metrics", {})
            stats["leads_qualified"] = m.get("total_scored", 0)
            stats["hot"] = m.get("hot", 0)
            stats["warm"] = m.get("warm", 0)
            stats["cold"] = m.get("cold", 0)

    return stats


def load_hot_leads(limit=5):
    """Load top hot leads from latest qualified scrape, enriched with pipeline stage."""
    qual_dir = BASE_DIR / "data" / "leads" / "qualified"
    if not qual_dir.exists():
        return []
    files = sorted(qual_dir.glob("*.json"), reverse=True)
    if not files:
        return []
    try:
        with open(files[0]) as f:
            data = json.load(f)
    except Exception:
        return []

    # Load pipeline stages
    stages_path = BASE_DIR / "data" / "pipeline" / "stages.json"
    stages = {}
    if stages_path.exists():
        try:
            with open(stages_path) as f:
                stages = json.load(f)
        except Exception:
            pass

    hot = []
    for entry in data.get("leads", []):
        if entry.get("qualification") == "hot":
            lead = entry.get("lead", {})
            name = lead.get("name", "")
            slug = re.sub(r'[^a-z0-9-]', '-', name.lower().strip())
            slug = re.sub(r'-+', '-', slug).strip('-')
            hot.append({
                "name": name,
                "slug": slug,
                "score": entry.get("score", 0),
                "email": lead.get("email", ""),
                "phone": lead.get("phone", ""),
                "website": lead.get("website", ""),
                "stage": stages.get(slug, {}).get("stage", "new"),
            })
    hot.sort(key=lambda x: x["score"], reverse=True)
    return hot[:limit]


def load_pipeline_counts():
    """Get count of leads in each pipeline stage."""
    stages_path = BASE_DIR / "data" / "pipeline" / "stages.json"
    counts = {"new": 0, "contacted": 0, "meeting": 0, "proposal_sent": 0, "closed": 0, "lost": 0}
    if not stages_path.exists():
        return counts
    try:
        with open(stages_path) as f:
            stages = json.load(f)
        for slug, info in stages.items():
            stage = info.get("stage", "new")
            if stage in counts:
                counts[stage] += 1
    except Exception:
        pass
    return counts


def build_daily_brief():
    """Build a 'what happened since yesterday + what to do next' brief."""
    from datetime import timedelta

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    brief = {
        "date": today.isoformat(),
        "leads_today": 0,
        "leads_qualified_today": 0,
        "hot_added_today": 0,
        "agents_run_today": [],
        "pending_actions": [],
        "next_action": None,
    }

    # Count leads found today
    raw_dir = BASE_DIR / "data" / "leads" / "raw"
    if raw_dir.exists():
        for f in raw_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
                if mtime == today:
                    with open(f) as fh:
                        data = json.load(fh)
                    brief["leads_today"] += data.get("count", len(data.get("leads", [])))
            except Exception:
                pass

    # Count qualified
    qual_dir = BASE_DIR / "data" / "leads" / "qualified"
    if qual_dir.exists():
        for f in qual_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
                if mtime == today:
                    with open(f) as fh:
                        data = json.load(fh)
                    leads = data.get("leads", [])
                    brief["leads_qualified_today"] += len(leads)
                    brief["hot_added_today"] += sum(1 for l in leads if l.get("qualification") == "hot")
            except Exception:
                pass

    # Pending actions: hot leads not contacted
    hot_leads = load_hot_leads(limit=20)
    not_contacted = [l for l in hot_leads if l.get("stage") == "new"]
    if not_contacted:
        brief["pending_actions"].append({
            "type": "contact_hot",
            "count": len(not_contacted),
            "label": f"{len(not_contacted)} sıcak lead'in iletişime geçilmemiş",
        })
        top = not_contacted[0]
        brief["next_action"] = f"En sıcak lead: {top['name']} (puan: {top['score']}). Teklif gönder?"

    # Stale leads (contacted >7 days ago, no follow-up)
    pipeline_counts = load_pipeline_counts()
    if pipeline_counts.get("contacted", 0) > 0:
        brief["pending_actions"].append({
            "type": "stale_followup",
            "count": pipeline_counts["contacted"],
            "label": f"{pipeline_counts['contacted']} lead 'iletişime geçildi' aşamasında",
        })

    # Default next action
    if not brief["next_action"]:
        if brief["hot_added_today"] > 0:
            brief["next_action"] = f"Bugün {brief['hot_added_today']} yeni sıcak lead var. CRM'i kontrol et."
        elif brief["leads_today"] == 0:
            brief["next_action"] = "Bugün henüz lead taraması yapılmadı. Scout'u çalıştır?"
        else:
            brief["next_action"] = "Pipeline'daki lead'leri filtrele."

    return brief


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Paperclip-style Board is now the primary interface.

    First-run users (no onboarding completed yet) are redirected to /onboard."""
    cid = core_store.active_company_id()
    company = core_store.load_company(cid) or {}
    if not company.get("settings", {}).get("onboarded"):
        return HTMLResponse(content='<meta http-equiv="refresh" content="0; url=/onboard">')
    return templates.TemplateResponse("board.html", {"request": request})


@app.get("/onboard", response_class=HTMLResponse)
async def onboard_page(request: Request):
    return templates.TemplateResponse("onboarding.html", {"request": request})


@app.post("/api/core/onboarding/complete")
async def core_onboarding_complete(request: Request):
    body = await request.json()
    cid = core_store.active_company_id()
    company = core_store.load_company(cid) or {"id": cid}
    company["id"] = cid
    company["name"] = body.get("name") or company.get("name") or "goat"
    company["niche"] = body.get("niche") or ""
    company["target_cities"] = body.get("target_cities") or []
    company["target_industries"] = body.get("target_industries") or []
    keys = company.get("api_keys", {}) or {}
    for k in ("anthropic_api_key", "apify_token", "fal_key", "composio_api_key",
              "instantly_api_key"):
        v = body.get(k)
        if v:
            keys[k] = v
    company["api_keys"] = keys
    settings = company.get("settings", {}) or {}
    settings["onboarded"] = True
    settings.setdefault("work_mode", "auto")
    company["settings"] = settings
    core_store.save_company(company)

    # Sensible default budgets — protect user from runaway fal.ai/apify spend
    if keys.get("fal_key"):
        core_store.set_budget(cid, "videoproducer", 30.0)   # user-stated cap
        core_store.set_budget(cid, "designer", 5.0)
        core_store.set_budget(cid, "videomaker", 5.0)
    if keys.get("apify_token"):
        core_store.set_budget(cid, "scout", 10.0)

    core_activity.append(cid, "onboarding_completed", actor="user", subject=cid,
                         details={"name": company["name"]})
    return JSONResponse({"ok": True})


@app.get("/classic", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Legacy Dark Room dashboard — preserved for nostalgia + quick actions."""
    config = load_config()
    stats = load_pipeline_stats()
    daily_brief = build_daily_brief()
    hot_leads = load_hot_leads(limit=5)
    pipeline_counts = load_pipeline_counts()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "daily_brief": daily_brief,
        "hot_leads": hot_leads,
        "pipeline_counts": pipeline_counts,
        "agents": AGENTS,
        "categories": CATEGORIES,
        "config": config,
        "stats": stats,
        "results": AGENT_RESULTS,
    })


# --- Agent Execution ---

@app.post("/api/agent/{agent_id}/run")
async def run_agent(agent_id: str, request: Request):
    if agent_id not in AGENT_MODULES:
        return JSONResponse({"error": "Agent not found"}, status_code=404)

    # Parse optional body params for Scout
    params = {}
    try:
        body = await request.json()
        params = body if isinstance(body, dict) else {}
    except Exception:
        pass

    # Inject config API keys into env for agents
    cfg = load_config()
    for src, dst in [
        ("instantly_api_key", "INSTANTLY_API_KEY"),
        ("apify_token", "APIFY_TOKEN"),
        ("fal_key", "FAL_KEY"),
        ("scraper_actor", "SCRAPER_ACTOR"),
        ("email_finder_providers", "EMAIL_FINDER_PROVIDERS"),
        ("emailapi_key", "EMAILAPI_KEY"),
        ("emailapi_domain", "EMAILAPI_DOMAIN"),
        ("leadmagic_api_key", "LEADMAGIC_API_KEY"),
        ("generect_api_key", "GENERECT_API_KEY"),
    ]:
        if cfg.get(src):
            os.environ[dst] = cfg[src]

    # Resolve per-agent run() params from request body
    def _resolve_run_params(agent_id, params):
        if not params:
            return {}
        if agent_id == "scout":
            return {"query": params.get("query", ""), "location": params.get("location", ""), "limit": params.get("limit", 50)}
        if agent_id == "auditor":
            return {"url": params.get("url", ""), "max_leads": params.get("max_leads", 10)}
        if agent_id == "sitebuilder":
            return {"site_type": params.get("site_type", "agency"), "lead_index": params.get("lead_index", 0)}
        if agent_id == "designer":
            return {"design_type": params.get("design_type", "social_post"), "business_name": params.get("business_name", ""), "platform": params.get("platform", "instagram"), "theme": params.get("theme", ""), "text": params.get("text", "")}
        if agent_id in ("videomaker",):
            return {"video_type": params.get("video_type", "reels"), "business_name": params.get("business_name", ""), "topic": params.get("topic", ""), "target_audience": params.get("target_audience", ""), "count": params.get("count", 3), "language": params.get("language", "tr")}
        if agent_id == "admanager":
            return {"platform": params.get("platform", "meta"), "campaign_type": params.get("campaign_type", "lead_gen"), "budget": params.get("budget", "1000"), "business_name": params.get("business_name", ""), "target_audience": params.get("target_audience", "")}
        if agent_id == "analytics":
            return {"analysis_type": params.get("analysis_type", "competitor"), "target": params.get("target", ""), "industry": params.get("industry", ""), "location": params.get("location", "")}
        if agent_id == "content":
            return {"content_type": params.get("content_type", "blog"), "topic": params.get("topic", ""), "tone": params.get("tone", "profesyonel"), "language": params.get("language", "tr"), "platform": params.get("platform", ""), "count": params.get("count", 1)}
        if agent_id == "presenter":
            return {"template": params.get("template", "pitch_deck"), "topic": params.get("topic", ""), "business_name": params.get("business_name", ""), "audience": params.get("audience", "")}
        if agent_id == "social":
            return {"action": params.get("action", "strategy"), "platform": params.get("platform", "instagram"), "business_name": params.get("business_name", ""), "niche": params.get("niche", "")}
        if agent_id == "storyboard":
            return {"project_type": params.get("project_type", "general"), "business_name": params.get("business_name", ""), "product_description": params.get("product_description", ""), "mood": params.get("mood", ""), "duration": params.get("duration", "15s"), "video_count": params.get("video_count", 1), "orientation": params.get("orientation", "vertical"), "reference_notes": params.get("reference_notes", "")}
        if agent_id == "brandkit":
            return {"business_name": params.get("business_name", ""), "industry": params.get("industry", ""), "style": params.get("style", "modern"), "values": params.get("values", "")}
        if agent_id == "mcphub":
            return {"action": params.get("action", "list"), "tool_id": params.get("tool_id", ""), "category": params.get("category", "")}
        if agent_id == "videoproducer":
            return {"action": params.get("action", "plan"), "topic": params.get("topic", ""), "scenes": params.get("scenes"), "style": params.get("style", "cinematic"), "language": params.get("language", "tr"), "voice_id": params.get("voice_id", "")}
        if agent_id == "youtube":
            return {"action": params.get("action", "optimize"), "video_path": params.get("video_path", ""), "title": params.get("title", ""), "topic": params.get("topic", ""), "language": params.get("language", "tr"), "category": params.get("category", "education"), "schedule_time": params.get("schedule_time", "")}
        if agent_id == "taskplanner":
            return {"action": params.get("action", "plan"), "message": params.get("message", ""), "pipeline": params.get("pipeline", ""), "auto_execute": params.get("auto_execute", False)}
        if agent_id == "ceo":
            return {"message": params.get("message", ""), "history": params.get("history", [])}
        return {}

    try:
        from core import agent_runtime as _core_runtime
        agent = get_agent_instance(agent_id)
        run_params = _resolve_run_params(agent_id, params)
        ticket = _core_runtime.execute_in_ticket(
            agent_id=agent_id, run_fn=agent.run, params=run_params,
            title=(params or {}).get("title", ""),
            goal_id=(params or {}).get("goal_id"),
        )
        result = ticket.get("result", {})

        AGENT_RESULTS[agent_id] = {
            "result": result,
            "timestamp": datetime.now().isoformat(),
            "status": "success" if ticket.get("status") in ("completed", "approved", "needs_review") else "error",
            "ticket_id": ticket["id"],
        }
        return JSONResponse({
            "status": "ok", "agent": agent_id, "result": result,
            "ticket": {
                "id": ticket["id"], "status": ticket["status"],
                "cost_usd": ticket.get("cost_usd", 0.0),
                "needs_approval": ticket.get("needs_approval", False),
            },
        })
    except Exception as e:
        AGENT_RESULTS[agent_id] = {
            "result": {"error": str(e)},
            "timestamp": datetime.now().isoformat(),
            "status": "error",
        }
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# (legacy inline agent-run block removed — replaced by execute_in_ticket above)


@app.post("/api/agents/run-pipeline")
async def run_pipeline():
    """Run the full pipeline: Scout → Filter. Tracked as a goat-master ticket."""
    from core import agent_runtime as _core_runtime
    import asyncio
    def _run():
        agent = get_agent_instance("goat")
        return _core_runtime.execute_in_ticket(
            agent_id="goat", run_fn=agent.run, params={},
            title="Full pipeline: Scout → Filter",
        )
    ticket = await asyncio.to_thread(_run)
    result = ticket.get("result", {})
    AGENT_RESULTS["goat"] = {
        "result": result, "timestamp": datetime.now().isoformat(),
        "status": "success" if ticket.get("status") in ("completed", "approved") else "error",
        "ticket_id": ticket["id"],
    }
    return JSONResponse({
        "status": "ok", "result": result,
        "ticket": {"id": ticket["id"], "status": ticket["status"], "cost_usd": ticket.get("cost_usd", 0.0)},
    })


@app.get("/api/agent/{agent_id}/result")
async def get_agent_result(agent_id: str):
    if agent_id in AGENT_RESULTS:
        return JSONResponse(AGENT_RESULTS[agent_id])
    return JSONResponse({"status": "not_run"})


# --- Leads ---

@app.get("/api/leads")
async def get_leads():
    """Get all raw leads from latest scrape."""
    raw_dir = DATA_BASE / "leads" / "raw"
    if not raw_dir.exists():
        return JSONResponse([])
    files = sorted(raw_dir.glob("*.json"), reverse=True)
    if files:
        with open(files[0]) as f:
            data = json.load(f)
            return JSONResponse(data.get("leads", []))
    return JSONResponse([])


@app.get("/api/leads/qualified")
async def get_qualified_leads():
    """Get latest qualified/scored leads."""
    qual_dir = DATA_BASE / "leads" / "qualified"
    if not qual_dir.exists():
        return JSONResponse([])
    files = sorted(qual_dir.glob("*.json"), reverse=True)
    if files:
        with open(files[0]) as f:
            data = json.load(f)
            return JSONResponse(data.get("leads", []))
    return JSONResponse([])


# --- Cofounder Mode ---

@app.post("/api/cofounder/enable")
async def enable_cofounder():
    from services.scheduler import enable_cofounder_mode
    return JSONResponse(enable_cofounder_mode())


@app.post("/api/cofounder/disable")
async def disable_cofounder():
    from services.scheduler import disable_cofounder_mode
    return JSONResponse(disable_cofounder_mode())


@app.get("/api/cofounder/status")
async def cofounder_status():
    from services.scheduler import is_cofounder_mode_active
    return JSONResponse({"active": is_cofounder_mode_active()})


# --- Daily Brief & Hot Leads ---

@app.get("/api/daily-brief")
async def get_daily_brief():
    return JSONResponse(build_daily_brief())


@app.get("/api/leads/hot")
async def get_hot_leads():
    return JSONResponse(load_hot_leads(limit=10))


@app.get("/api/pipeline/counts")
async def get_pipeline_counts():
    return JSONResponse(load_pipeline_counts())


# --- Manual Lead Entry ---

@app.post("/api/leads/manual")
async def add_manual_lead(request: Request):
    """Add a lead manually (not from scraping)."""
    body = await request.json()
    name = body.get("name", "")
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)

    lead = {
        "name": name,
        "category": body.get("category", ""),
        "phone": body.get("phone", ""),
        "email": body.get("email", ""),
        "website": body.get("website", ""),
        "address": body.get("address", ""),
        "rating": body.get("rating", 0),
        "review_count": body.get("review_count", 0),
        "description": body.get("description", ""),
        "source": "manual",
        "added_at": datetime.now().isoformat(),
    }

    # Save to raw leads
    raw_dir = BASE_DIR / "data" / "leads" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Append to existing manual file or create new one
    manual_file = raw_dir / "manual_leads.json"
    if manual_file.exists():
        with open(manual_file) as f:
            data = json.load(f)
    else:
        data = {"query": "manual", "location": "", "scraped_at": datetime.now().isoformat(), "count": 0, "leads": []}

    data["leads"].append(lead)
    data["count"] = len(data["leads"])
    with open(manual_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Also auto-add to pipeline
    slug = slugify(name)
    stages_path = PIPELINE_DIR / "stages.json"
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    stages = _load_json(stages_path)
    if slug not in stages:
        stages[slug] = {"stage": "new", "updated_at": datetime.now().isoformat()}
        _save_json(stages_path, stages)

    return JSONResponse({"status": "ok", "lead": lead, "slug": slug})


# --- Chat ---

@app.post("/api/chat")
async def chat_with_agent(request: Request):
    """Smart chat — Claude CLI understands intents and returns actions."""
    body = await request.json()
    message = body.get("message", "")
    agent_id = body.get("agent_id", "goat")
    agent_info = AGENTS.get(agent_id, {})

    # Mentor has its own answer method
    if agent_id == "mentor":
        try:
            agent = get_agent_instance("mentor")
            response = agent.answer(message)
            return JSONResponse({"response": response, "agent": agent_id, "actions": []})
        except Exception as e:
            return JSONResponse({"response": f"Mentor error: {e}", "agent": agent_id, "actions": []})

    config = load_config()

    # Build rich context
    config_summary = ""
    if config:
        config_summary = f"""
Current config:
- Agency: {config.get('agency_name', 'not set')}
- Owner: {config.get('owner_name', 'not set')}
- Niche: {config.get('niche', 'not set')}
- Cities: {', '.join(config.get('target_cities', [])) or 'not set'}
- Apify token: {'set' if config.get('apify_token') else 'not set'}
- fal.ai key: {'set' if config.get('fal_key') else 'not set'}
- Instantly key: {'set' if config.get('instantly_api_key') else 'not set'}"""

    # Agent results summary
    results_summary = ""
    if AGENT_RESULTS:
        results_summary = "\nCompleted agent runs:"
        for k, v in list(AGENT_RESULTS.items())[:10]:
            results_summary += f"\n- {k}: {v['result'].get('summary', 'done')}"

    # Pipeline stats
    stats = load_pipeline_stats()
    stats_summary = f"\nPipeline: {stats['leads_found']} leads found, {stats['leads_qualified']} qualified, {stats['hot']} hot, {stats['warm']} warm"

    # Shared conversation history (all agents share one timeline)
    if "_shared" not in CHAT_HISTORIES:
        CHAT_HISTORIES["_shared"] = []
    history = CHAT_HISTORIES["_shared"]
    history.append({"role": "user", "content": f"[to {agent_id}] {message}"})

    history_text = ""
    if len(history) > 1:
        past = history[:-1][-MAX_HISTORY:]
        history_text = "\n\nIMPORTANT — Full conversation so far (you MUST use this context to understand what the user is referring to):\n" + "\n".join(
            f"{'User' if m['role'] == 'user' else 'You'}: {m['content']}" for m in past
        )

    available_actions = """
Available actions you can suggest (include as JSON at the END of your response, after <<<ACTIONS>>> marker):
- {"action": "scout", "params": {"query": "...", "location": "..."}} — search for leads
- {"action": "filter"} — score/qualify found leads
- {"action": "audit", "params": {"url": "..."}} — audit a website
- {"action": "pitch"} — generate proposals for hot leads
- {"action": "outreach"} — create email campaigns
- {"action": "site_agency"} — build agency landing page
- {"action": "site_client", "params": {"manual_data": {"name": "...", "category": "...", "phone": "...", "email": "...", "address": "..."}}} — build client site
- {"action": "save_config", "params": {"field": "value", ...}} — save config fields
- {"action": "add_lead", "params": {"name": "...", "category": "...", "phone": "...", "email": "...", "website": "...", "address": "..."}} — add manual lead
- {"action": "show_pipeline"} — show CRM pipeline
- {"action": "show_leads"} — show lead list
- {"action": "show_revenue"} — show revenue dashboard

CRITICAL: When the user asks you to DO something (add lead, build site, find leads, show pipeline, etc.), you MUST include the action JSON.
Format: Write your conversational response first, then on a NEW LINE write exactly:
<<<ACTIONS>>>[{"action": "...", "params": {...}}]

Examples:
- User: "Burhan'ı CRM'e ekle" → "Burhan'ı ekliyorum.\n<<<ACTIONS>>>[{\"action\": \"add_lead\", \"params\": {\"name\": \"Burhan\"}}]"
- User: "müşteri bul İstanbul'da restoran" → "bakıyorum.\n<<<ACTIONS>>>[{\"action\": \"scout\", \"params\": {\"query\": \"restoran\", \"location\": \"İstanbul\"}}]"
- User: "pipeline'ı göster" → "açıyorum.\n<<<ACTIONS>>>[{\"action\": \"show_pipeline\"}]"
- User: "Esad" (during onboarding) → "merhaba Esad!\n<<<ACTIONS>>>[{\"action\": \"save_config\", \"params\": {\"owner_name\": \"Esad\"}}]"

If no action needed (just chatting), do NOT include <<<ACTIONS>>>."""

    prompt = f"""You are GOAT, the AI command center for an agency-in-a-box platform. You help the user run their automation agency through a terminal-style interface.
{config_summary}{stats_summary}{results_summary}{history_text}

{available_actions}

Rules:
- Be concise, conversational, Turkish. Talk like a smart co-founder, not a bot.
- Short sentences, 1-3 lines max. No markdown headers. No bullet points unless listing data.
- ONBOARDING: If config fields are missing (owner_name, agency_name, niche, target_cities), guide the user through setup naturally. Ask ONE thing at a time. When the user gives you info, save it immediately via save_config action. Example flow:
  - User: "merhaba" → "selam! ben GOAT. adın ne?" (ask name)
  - User: "Esad" → save owner_name, then "merhaba Esad. ajansının adı ne olsun?" (ask agency name)
  - User: "sen seç" → pick a cool name for them, save it, move on to niche
  - User: "bilmiyorum" → suggest options, let them pick or pick for them
  - User: "bana site yap" during setup → acknowledge ("tamam yaparız"), but first finish setup, ask missing fields
- If the user says "sen seç", "bilmiyorum", "anlamadın" etc., UNDERSTAND the intent. Don't repeat the same question robotically. Adapt.
- When the user provides info during chat, ALWAYS extract and save via save_config action. For cities, parse comma-separated into a list.
- If the user asks to do something (build site, find leads, etc.), acknowledge and suggest the action.
- If info is missing for an action, ask for it naturally — don't block completely.
- When all config fields are set, stop asking setup questions and suggest next steps.
- Keep the vibe: dark room, hacker terminal, but friendly and smart.
- CRITICAL: Always read the conversation history carefully. When the user says "ok", "yap", "evet", "onaylıyorum", "olsun", "benim için", "tamam" — they are APPROVING or CONTINUING the previous topic. NEVER ask "what do you mean?" if the context is in the history. Just do it.
- NEVER say "bu yeni bir sohbet oturumu" or "daha önce söylemedim" — the history IS there, read it.
- When you proposed a plan and user says "ok yap" — execute it immediately via actions, don't ask again.

User: {message}"""

    actions = []
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
        )
        response = result.stdout.strip() if result.stdout else "hazırım. ne yapmak istersin?"

        # Parse actions from response
        if "<<<ACTIONS>>>" in response:
            parts = response.split("<<<ACTIONS>>>", 1)
            response = parts[0].strip()
            try:
                actions = json.loads(parts[1].strip())
                if not isinstance(actions, list):
                    actions = [actions]
            except (json.JSONDecodeError, IndexError):
                actions = []

    except (FileNotFoundError, subprocess.TimeoutExpired):
        # No Claude CLI — smart fallback based on intent
        response, actions = _smart_fallback(message, config, stats)

    # Execute save_config actions immediately
    for act in actions:
        if act.get("action") == "save_config" and act.get("params"):
            cfg = load_config()
            cfg.update(act["params"])
            config_dir = BASE_DIR / "data" / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            with open(config_dir / "user_profile.json", "w") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)

    # Save to shared history
    history.append({"role": "assistant", "content": f"[{agent_id}] {response}"})
    if len(history) > MAX_HISTORY * 2:
        CHAT_HISTORIES["_shared"] = history[-MAX_HISTORY * 2:]

    return JSONResponse({"response": response, "agent": agent_id, "actions": actions})


def _build_chat_prompt(message: str, agent_id: str):
    """Build the prompt used by both /api/chat and /api/chat/stream."""
    config = load_config()

    config_summary = ""
    if config:
        config_summary = f"""
Current config:
- Agency: {config.get('agency_name', 'not set')}
- Owner: {config.get('owner_name', 'not set')}
- Niche: {config.get('niche', 'not set')}
- Cities: {', '.join(config.get('target_cities', [])) or 'not set'}
- Apify token: {'set' if config.get('apify_token') else 'not set'}
- fal.ai key: {'set' if config.get('fal_key') else 'not set'}
- Instantly key: {'set' if config.get('instantly_api_key') else 'not set'}"""

    results_summary = ""
    if AGENT_RESULTS:
        results_summary = "\nCompleted agent runs:"
        for k, v in list(AGENT_RESULTS.items())[:10]:
            results_summary += f"\n- {k}: {v['result'].get('summary', 'done')}"

    stats = load_pipeline_stats()
    stats_summary = f"\nPipeline: {stats['leads_found']} leads found, {stats['leads_qualified']} qualified, {stats['hot']} hot, {stats['warm']} warm"

    if agent_id not in CHAT_HISTORIES:
        CHAT_HISTORIES[agent_id] = []
    history = CHAT_HISTORIES[agent_id]
    history.append({"role": "user", "content": message})

    history_text = ""
    if len(history) > 1:
        past = history[:-1][-MAX_HISTORY:]
        history_text = "\n\nIMPORTANT — Full conversation so far (you MUST use this context to understand what the user is referring to):\n" + "\n".join(
            f"{'User' if m['role'] == 'user' else 'You'}: {m['content']}" for m in past
        )

    available_actions = """
Available actions you can suggest (include as JSON at the END of your response, after <<<ACTIONS>>> marker):
- {"action": "scout", "params": {"query": "...", "location": "..."}} — search for leads
- {"action": "filter"} — score/qualify found leads
- {"action": "audit", "params": {"url": "..."}} — audit a website
- {"action": "pitch"} — generate proposals for hot leads
- {"action": "outreach"} — create email campaigns
- {"action": "site_agency"} — build agency landing page
- {"action": "site_client", "params": {"manual_data": {"name": "...", "category": "...", "phone": "...", "email": "...", "address": "..."}}} — build client site
- {"action": "save_config", "params": {"field": "value", ...}} — save config fields
- {"action": "add_lead", "params": {"name": "...", "category": "...", "phone": "...", "email": "...", "website": "...", "address": "..."}} — add manual lead
- {"action": "show_pipeline"} — show CRM pipeline
- {"action": "show_leads"} — show lead list
- {"action": "show_revenue"} — show revenue dashboard

CRITICAL: When the user asks you to DO something (add lead, build site, find leads, show pipeline, etc.), you MUST include the action JSON.
Format: Write your conversational response first, then on a NEW LINE write exactly:
<<<ACTIONS>>>[{"action": "...", "params": {...}}]

Examples:
- User: "Burhan'ı CRM'e ekle" → "Burhan'ı ekliyorum.\n<<<ACTIONS>>>[{\\"action\\": \\"add_lead\\", \\"params\\": {\\"name\\": \\"Burhan\\"}}]"
- User: "müşteri bul İstanbul'da restoran" → "bakıyorum.\n<<<ACTIONS>>>[{\\"action\\": \\"scout\\", \\"params\\": {\\"query\\": \\"restoran\\", \\"location\\": \\"İstanbul\\"}}]"
- User: "pipeline'ı göster" → "açıyorum.\n<<<ACTIONS>>>[{\\"action\\": \\"show_pipeline\\"}]"
- User: "Esad" (during onboarding) → "merhaba Esad!\n<<<ACTIONS>>>[{\\"action\\": \\"save_config\\", \\"params\\": {\\"owner_name\\": \\"Esad\\"}}]"

If no action needed (just chatting), do NOT include <<<ACTIONS>>>."""

    prompt = f"""You are GOAT, the AI command center for an agency-in-a-box platform. You help the user run their automation agency through a terminal-style interface.
{config_summary}{stats_summary}{results_summary}{history_text}

{available_actions}

Rules:
- Be concise, conversational, Turkish. Talk like a smart co-founder, not a bot.
- Short sentences, 1-3 lines max. No markdown headers. No bullet points unless listing data.
- ONBOARDING: If config fields are missing (owner_name, agency_name, niche, target_cities), guide the user through setup naturally. Ask ONE thing at a time. When the user gives you info, save it immediately via save_config action. Example flow:
  - User: "merhaba" → "selam! ben GOAT. adın ne?" (ask name)
  - User: "Esad" → save owner_name, then "merhaba Esad. ajansının adı ne olsun?" (ask agency name)
  - User: "sen seç" → pick a cool name for them, save it, move on to niche
  - User: "bilmiyorum" → suggest options, let them pick or pick for them
  - User: "bana site yap" during setup → acknowledge ("tamam yaparız"), but first finish setup, ask missing fields
- If the user says "sen seç", "bilmiyorum", "anlamadın" etc., UNDERSTAND the intent. Don't repeat the same question robotically. Adapt.
- When the user provides info during chat, ALWAYS extract and save via save_config action. For cities, parse comma-separated into a list.
- If the user asks to do something (build site, find leads, etc.), acknowledge and suggest the action.
- If info is missing for an action, ask for it naturally — don't block completely.
- When all config fields are set, stop asking setup questions and suggest next steps.
- Keep the vibe: dark room, hacker terminal, but friendly and smart.
- CRITICAL: Always read the conversation history carefully. When the user says "ok", "yap", "evet", "onaylıyorum", "olsun", "benim için", "tamam" — they are APPROVING or CONTINUING the previous topic. NEVER ask "what do you mean?" if the context is in the history. Just do it.
- NEVER say "bu yeni bir sohbet oturumu" or "daha önce söylemedim" — the history IS there, read it.
- When you proposed a plan and user says "ok yap" — execute it immediately via actions, don't ask again.

User: {message}"""

    return prompt, config, stats


@app.get("/api/chat/history")
async def get_chat_history():
    history = CHAT_HISTORIES.get("_shared", [])
    return JSONResponse(history[-50:])


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """Streaming chat — sends SSE events as Claude generates text."""
    body = await request.json()
    message = body.get("message", "")
    agent_id = body.get("agent_id", "goat")

    # Mentor has its own answer method — no streaming
    if agent_id == "mentor":
        try:
            agent = get_agent_instance("mentor")
            response = agent.answer(message)
            async def mentor_gen():
                yield f"data: {json.dumps({'text': response})}\n\n"
                yield f"data: {json.dumps({'done': True, 'actions': []})}\n\n"
            return StreamingResponse(mentor_gen(), media_type="text/event-stream")
        except Exception as e:
            async def err_gen():
                yield f"data: {json.dumps({'text': f'Mentor error: {e}'})}\n\n"
                yield f"data: {json.dumps({'done': True, 'actions': []})}\n\n"
            return StreamingResponse(err_gen(), media_type="text/event-stream")

    prompt, config, stats = _build_chat_prompt(message, agent_id)

    async def stream_generator():
        import asyncio
        full_response = ""
        try:
            proc = subprocess.Popen(
                ["claude", "-p", prompt, "--output-format", "text"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(BASE_DIR),
            )

            buffer = ""
            while True:
                chunk = proc.stdout.read(20)  # read small chunks
                if not chunk:
                    break
                buffer += chunk
                full_response += chunk

                # Don't stream the <<<ACTIONS>>> part
                if "<<<ACTIONS>>>" in buffer:
                    visible = buffer.split("<<<ACTIONS>>>")[0]
                    if visible:
                        yield f"data: {json.dumps({'text': visible})}\n\n"
                    buffer = ""
                    # Read the rest silently
                    rest = proc.stdout.read()
                    if rest:
                        full_response += rest
                    break
                else:
                    yield f"data: {json.dumps({'text': buffer})}\n\n"
                    buffer = ""

                await asyncio.sleep(0)

            # If there's remaining buffer (no ACTIONS marker hit)
            if buffer:
                yield f"data: {json.dumps({'text': buffer})}\n\n"

            proc.wait(timeout=5)

            # Parse actions
            actions = []
            if "<<<ACTIONS>>>" in full_response:
                parts = full_response.split("<<<ACTIONS>>>", 1)
                response_text = parts[0].strip()
                try:
                    actions = json.loads(parts[1].strip())
                    if not isinstance(actions, list):
                        actions = [actions]
                except (json.JSONDecodeError, IndexError):
                    actions = []
            else:
                response_text = full_response.strip()

            # Execute save_config actions immediately
            for act in actions:
                if act.get("action") == "save_config" and act.get("params"):
                    cfg = load_config()
                    cfg.update(act["params"])
                    config_dir = BASE_DIR / "data" / "config"
                    config_dir.mkdir(parents=True, exist_ok=True)
                    with open(config_dir / "user_profile.json", "w") as f_cfg:
                        json.dump(cfg, f_cfg, indent=2, ensure_ascii=False)

            # Save to history
            history = CHAT_HISTORIES.get(agent_id, [])
            history.append({"role": "assistant", "content": response_text})
            if len(history) > MAX_HISTORY * 2:
                CHAT_HISTORIES[agent_id] = history[-MAX_HISTORY * 2:]

            yield f"data: {json.dumps({'done': True, 'actions': actions})}\n\n"

        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
            # Fallback
            response, actions = _smart_fallback(message, config, stats)
            yield f"data: {json.dumps({'text': response})}\n\n"

            # Execute save_config actions
            for act in actions:
                if act.get("action") == "save_config" and act.get("params"):
                    cfg = load_config()
                    cfg.update(act["params"])
                    config_dir = BASE_DIR / "data" / "config"
                    config_dir.mkdir(parents=True, exist_ok=True)
                    with open(config_dir / "user_profile.json", "w") as f_cfg:
                        json.dump(cfg, f_cfg, indent=2, ensure_ascii=False)

            history = CHAT_HISTORIES.get(agent_id, [])
            history.append({"role": "assistant", "content": response})
            if len(history) > MAX_HISTORY * 2:
                CHAT_HISTORIES[agent_id] = history[-MAX_HISTORY * 2:]

            yield f"data: {json.dumps({'done': True, 'actions': actions})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# --- Activity Timeline ---

@app.get("/api/activity")
async def get_activity():
    """Return last 20 agent runs sorted by timestamp desc."""
    entries = []
    for agent_id, data in AGENT_RESULTS.items():
        result = data.get("result", {})
        entries.append({
            "agent_id": agent_id,
            "status": data.get("status", "unknown"),
            "summary": result.get("summary", str(result.get("error", "done")))[:120],
            "timestamp": data.get("timestamp", ""),
        })
    entries.sort(key=lambda x: x["timestamp"], reverse=True)
    return JSONResponse(entries[:20])


def _smart_fallback(message: str, config: dict, stats: dict):
    """Fallback intent detection when Claude CLI is not available."""
    msg = message.lower()
    actions = []
    response = ""

    # Onboarding
    if not config.get("agency_name"):
        if any(w in msg for w in ["merhaba", "selam", "hey", "başla"]):
            response = "hoş geldin! ajansını kuralım. adın ne?"
        else:
            response = f'"{message}" — güzel. devam edelim. ajansının adı ne olsun?'
        return response, actions

    # Intent detection
    if any(w in msg for w in ["müşteri bul", "lead", "scout", "ara", "tara"]):
        response = "lead taraması başlatıyorum."
        actions = [{"action": "scout", "params": {}}]
    elif any(w in msg for w in ["site yap", "site oluştur", "landing", "web"]):
        if "ajans" in msg:
            response = f"{config.get('agency_name', '')} için ajans sitesi oluşturuyorum."
            actions = [{"action": "site_agency"}]
        else:
            response = "ne tür bir site? ajans sitesi mi, müşteri sitesi mi?"
            actions = []
    elif any(w in msg for w in ["puanla", "filtre", "score"]):
        response = "leadleri puanlıyorum."
        actions = [{"action": "filter"}]
    elif any(w in msg for w in ["teklif", "pitch", "proposal"]):
        response = "teklif hazırlıyorum."
        actions = [{"action": "pitch"}]
    elif any(w in msg for w in ["pipeline", "crm", "süreç"]):
        response = "pipeline açılıyor."
        actions = [{"action": "show_pipeline"}]
    else:
        response = f"anladım. şu an {stats['leads_found']} lead var, {stats['hot']} tanesi sıcak. ne yapmak istersin?"

    return response, actions


# --- Config ---

@app.get("/api/config")
async def get_config():
    return JSONResponse(load_config())


@app.post("/api/config")
async def save_config(request: Request):
    body = await request.json()
    config_dir = DATA_BASE / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "user_profile.json"
    with open(config_path, "w") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
    return JSONResponse({"status": "saved"})


@app.post("/api/creative")
async def generate_creative(request: Request):
    """Generate an ad creative or social media image via fal.ai."""
    body = await request.json()
    business_type = body.get("business_type", "business")
    creative_type = body.get("type", "ad")

    # Inject fal key
    cfg = load_config()
    if cfg.get("fal_key"):
        os.environ["FAL_KEY"] = cfg["fal_key"]

    from services.image import generate_ad_creative, generate_social_example

    if creative_type == "social":
        path = generate_social_example(business_type)
    else:
        path = generate_ad_creative(business_type, business_type, "otomasyon")

    if path:
        return JSONResponse({"status": "ok", "path": path})
    return JSONResponse({"status": "error", "path": None})


@app.post("/api/reset")
async def reset_all():
    """Reset everything — delete config, leads, reports, campaigns."""
    import shutil
    global AGENT_RESULTS
    AGENT_RESULTS = {}

    # Delete data files
    for sub in ["config", "leads/raw", "leads/qualified", "campaigns", "proposals"]:
        p = DATA_BASE / sub
        if p.exists():
            shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)

    # Clear chat histories
    global CHAT_HISTORIES
    CHAT_HISTORIES = {}

    # Delete reports
    reports = OUTPUTS_BASE / "reports"
    if reports.exists():
        shutil.rmtree(reports)
        reports.mkdir(parents=True, exist_ok=True)

    return JSONResponse({"status": "reset"})


# --- Site Audit ---

@app.post("/api/audit")
async def audit_site(request: Request):
    """Run SEO, broken link, and tech stack audit on a URL."""
    body = await request.json()
    url = body.get("url", "")
    if not url:
        return JSONResponse({"error": "URL required"}, status_code=400)

    from services.site_auditor import full_audit
    report = full_audit(url)
    return JSONResponse({"status": "ok", "report": report})


@app.get("/api/audit/lead/{lead_name}")
async def audit_lead(lead_name: str):
    """Audit a specific lead's website by lead name."""
    from services.site_auditor import full_audit
    # Find the lead
    qual_dir = DATA_BASE / "leads" / "qualified"
    if not qual_dir.exists():
        return JSONResponse({"error": "No qualified leads"}, status_code=404)
    files = sorted(qual_dir.glob("*.json"), reverse=True)
    if not files:
        return JSONResponse({"error": "No qualified leads"}, status_code=404)
    with open(files[0]) as f:
        data = json.load(f)
    for entry in data.get("leads", []):
        lead = entry.get("lead", {})
        if lead.get("name", "").lower() == lead_name.lower() and lead.get("website"):
            report = full_audit(lead["website"])
            return JSONResponse({"status": "ok", "lead": lead["name"], "report": report})
    return JSONResponse({"error": "Lead not found or has no website"}, status_code=404)


# --- PDF Proposals ---

@app.post("/api/proposal/pdf")
async def generate_proposal_pdf(request: Request):
    """Convert a markdown proposal to PDF."""
    body = await request.json()
    md_path = body.get("path", "")
    md_text = body.get("markdown", "")

    from services.pdf_generator import markdown_to_pdf, proposal_file_to_pdf

    if md_path:
        pdf_path = proposal_file_to_pdf(md_path)
    elif md_text:
        pdf_path = markdown_to_pdf(md_text)
    else:
        return JSONResponse({"error": "Provide 'path' or 'markdown'"}, status_code=400)

    if pdf_path:
        return JSONResponse({"status": "ok", "pdf_path": pdf_path})
    return JSONResponse({"status": "error", "message": "PDF generation failed"}, status_code=500)


@app.post("/api/proposals/pdf/all")
async def convert_all_proposals_to_pdf():
    """Convert all existing markdown proposals to PDF."""
    from services.pdf_generator import convert_all_proposals
    paths = convert_all_proposals()
    return JSONResponse({"status": "ok", "converted": len(paths), "paths": paths})


# --- Google Search (Free Lead Discovery) ---

@app.post("/api/search/google")
async def google_search_leads(request: Request):
    """Search Google for businesses (no API key needed)."""
    body = await request.json()
    query = body.get("query", "")
    location = body.get("location", "")
    limit = body.get("limit", 15)

    if not query:
        return JSONResponse({"error": "Query required"}, status_code=400)

    from services.google_search import search_and_enrich
    leads = search_and_enrich(query, location, limit)
    return JSONResponse({"status": "ok", "count": len(leads), "leads": leads})


# --- Scheduler ---

@app.get("/api/schedules")
async def get_schedules():
    """List all scheduled agent runs."""
    from services.scheduler import list_schedules
    return JSONResponse(list_schedules())


@app.post("/api/schedules")
async def create_schedule(request: Request):
    """Create a scheduled agent run."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    cron = body.get("cron", "daily")
    params = body.get("params", {})
    name = body.get("name", "")

    if not agent_id:
        return JSONResponse({"error": "agent_id required"}, status_code=400)

    from services.scheduler import add_schedule
    result = add_schedule(agent_id, cron, params, name)
    return JSONResponse(result)


@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Remove a scheduled agent run."""
    from services.scheduler import remove_schedule
    remove_schedule(schedule_id)
    return JSONResponse({"status": "removed"})


@app.get("/api/schedules/logs")
async def get_schedule_logs():
    """Get recent scheduled run logs."""
    from services.scheduler import get_scheduled_run_logs
    return JSONResponse(get_scheduled_run_logs())


# --- Startup: start scheduler ---

@app.on_event("startup")
async def startup_event():
    from services.scheduler import start_scheduler
    start_scheduler()
    # Materialize default company from legacy user_profile.json on first run
    from core import store as _core_store
    _core_store.migrate_legacy_profile_if_needed()


# ═══════════════════════════════════════════
# CORE CONTROL PLANE (Paperclip-style)
# ═══════════════════════════════════════════

from core import store as core_store
from core import activity_log as core_activity
from core import agent_runtime as core_runtime


@app.get("/api/core/companies")
async def core_list_companies():
    return JSONResponse({
        "active": core_store.active_company_id(),
        "companies": core_store.list_companies(),
    })


@app.post("/api/core/companies/active")
async def core_set_active_company(request: Request):
    body = await request.json()
    cid = body.get("id", "").strip()
    if not cid:
        return JSONResponse({"error": "id required"}, status_code=400)
    core_store.ensure_company_exists(cid, name=body.get("name", ""))
    core_store.set_active_company(cid)
    return JSONResponse({"active": cid})


@app.get("/api/core/tickets")
async def core_list_tickets(status: str = "", agent_id: str = "", goal_id: str = "", limit: int = 200):
    cid = core_store.active_company_id()
    return JSONResponse({
        "company_id": cid,
        "tickets": core_store.list_tickets(cid, status=status or None, agent_id=agent_id or None,
                                           goal_id=goal_id or None, limit=limit),
    })


@app.get("/api/core/tickets/{ticket_id}")
async def core_get_ticket(ticket_id: str):
    cid = core_store.active_company_id()
    ticket = core_store.load_ticket(cid, ticket_id)
    if not ticket:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(ticket)


@app.post("/api/core/tickets/{ticket_id}/approve")
async def core_approve_ticket(ticket_id: str, request: Request):
    cid = core_store.active_company_id()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    channel = body.get("channel") if isinstance(body, dict) else None
    t = core_runtime.approve(cid, ticket_id)
    if not t:
        return JSONResponse({"error": "not found"}, status_code=404)
    # If user picked a delivery channel for an outreach campaign, route it now
    if channel:
        try:
            from core import outreach_dispatcher as _od
            _od.deliver(cid, t, channel)
        except Exception as e:
            core_activity.append(cid, "delivery_failed", actor="system",
                                 subject=ticket_id, details={"error": str(e)})
    import asyncio
    try:
        from core import heartbeat as _hb
        await asyncio.to_thread(_hb.tick, company_id=cid)
    except Exception:
        pass
    return JSONResponse(t)


@app.get("/api/core/tickets/{ticket_id}/export")
async def core_ticket_export(ticket_id: str, format: str = "csv"):
    """Export campaign leads as CSV or Markdown — tool-agnostic delivery."""
    cid = core_store.active_company_id()
    t = core_store.load_ticket(cid, ticket_id)
    if not t:
        return JSONResponse({"error": "not found"}, status_code=404)
    result = t.get("result") or {}
    leads = result.get("leads") or []
    sequence = result.get("sequence") or []

    from fastapi.responses import PlainTextResponse
    if format == "md":
        lines = [f"# {t.get('title')}\n"]
        for s in sequence:
            lines.append(f"## Email {s.get('step')} (gün {s.get('delay_days', 0)})")
            lines.append(f"**Subject:** {s.get('subject', '')}\n")
            lines.append(s.get("body", "") + "\n")
        return PlainTextResponse("\n".join(lines), media_type="text/markdown",
                                 headers={"Content-Disposition": f'attachment; filename="campaign-{ticket_id}.md"'})
    # CSV
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "first_name", "company", "city", "category"])
    for l in leads:
        w.writerow([l.get("email", ""), l.get("first_name", ""),
                    l.get("company_name", ""), l.get("city", ""), l.get("category", "")])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="leads-{ticket_id}.csv"'})


@app.post("/api/core/tickets/{ticket_id}/reject")
async def core_reject_ticket(ticket_id: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    cid = core_store.active_company_id()
    t = core_runtime.reject(cid, ticket_id, reason=body.get("reason", ""))
    if not t:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(t)


@app.get("/api/core/goals")
async def core_list_goals():
    cid = core_store.active_company_id()
    return JSONResponse({"company_id": cid, "goals": core_store.list_goals(cid)})


@app.post("/api/core/goals")
async def core_create_goal(request: Request):
    from core.models import Goal, new_id, to_dict
    body = await request.json()
    cid = core_store.active_company_id()
    goal = to_dict(Goal(
        id=new_id("g"),
        company_id=cid,
        title=body.get("title", "").strip() or "Untitled goal",
        description=body.get("description", ""),
        target_metric=body.get("target_metric", ""),
        deadline=body.get("deadline"),
    ))
    core_store.save_goal(goal)
    core_activity.append(cid, "goal_created", actor="user", subject=goal["id"],
                         details={"title": goal["title"]})
    return JSONResponse(goal)


@app.get("/api/core/goals/{goal_id}/progress")
async def core_goal_progress(goal_id: str):
    """Goal'un ticket'ları arasında ilerleme oranı."""
    cid = core_store.active_company_id()
    tickets = core_store.list_tickets(cid, goal_id=goal_id)
    if not tickets:
        return JSONResponse({"goal_id": goal_id, "total": 0, "completed": 0,
                             "in_progress": 0, "needs_review": 0, "failed": 0,
                             "percent": 0, "tickets": []})
    counts = {"completed": 0, "approved": 0, "in_progress": 0, "needs_review": 0,
              "failed": 0, "paused_budget": 0, "pending": 0}
    for t in tickets:
        s = t.get("status", "pending")
        counts[s] = counts.get(s, 0) + 1
    done = counts["completed"] + counts["approved"]
    total = len(tickets)
    return JSONResponse({
        "goal_id": goal_id,
        "total": total,
        "completed": done,
        "in_progress": counts["in_progress"],
        "needs_review": counts["needs_review"],
        "failed": counts["failed"] + counts["paused_budget"],
        "pending": counts["pending"],
        "percent": round(100 * done / total) if total else 0,
        "tickets": [{"id": t["id"], "status": t.get("status"), "agent_id": t.get("agent_id"),
                     "title": t.get("title", "")} for t in tickets],
    })


@app.post("/api/core/goals/{goal_id}/plan")
async def core_plan_goal(goal_id: str):
    from core import planner
    cid = core_store.active_company_id()
    goal = core_store.load_goal(cid, goal_id)
    if not goal:
        return JSONResponse({"error": "not found"}, status_code=404)
    plan = planner.plan_goal(cid, goal)
    tickets = planner.materialize_plan(cid, goal_id, plan)
    # Kick heartbeat so plan tickets start running immediately
    import asyncio
    try:
        from core import heartbeat as _hb
        await asyncio.to_thread(_hb.tick, company_id=cid)
    except Exception:
        pass
    return JSONResponse({"goal_id": goal_id, "plan": plan,
                         "tickets": [{"id": t["id"], "agent_id": t["agent_id"], "title": t["title"]} for t in tickets]})


@app.get("/api/core/activity")
async def core_activity_list(limit: int = 100, kind: str = "", subject: str = ""):
    cid = core_store.active_company_id()
    return JSONResponse({
        "company_id": cid,
        "entries": core_activity.read(cid, limit=limit, kind=kind or None, subject=subject or None),
    })


@app.get("/api/core/activity/stream")
async def core_activity_stream():
    """SSE stream — pushes new activity entries as they arrive.

    Polls activity_log every 1s server-side and emits SSE events for entries
    newer than the last seen timestamp. Connection lives ~5min then closes
    (Vercel function max). Browser EventSource auto-reconnects.
    """
    cid = core_store.active_company_id()

    async def gen():
        import asyncio
        seen = set()
        # Start by sending recent backlog so client paints history
        for e in reversed(core_activity.read(cid, limit=20)):
            seen.add(e.get("timestamp", "") + e.get("subject", ""))
            yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
        # Tail-poll
        for _ in range(290):  # ~290 * 1s = 4.8min, well under Vercel's 5min cap
            await asyncio.sleep(1)
            for e in reversed(core_activity.read(cid, limit=20)):
                key = e.get("timestamp", "") + e.get("subject", "")
                if key in seen:
                    continue
                seen.add(key)
                yield f"data: {json.dumps(e, ensure_ascii=False)}\n\n"
            yield ": ping\n\n"  # keep-alive comment

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@app.get("/api/core/budgets")
async def core_list_budgets():
    cid = core_store.active_company_id()
    return JSONResponse({"company_id": cid, "budgets": core_store.load_budgets(cid)})


@app.post("/api/core/budgets")
async def core_set_budget(request: Request):
    body = await request.json()
    agent_id = body.get("agent_id", "").strip()
    amount = float(body.get("amount_usd", 0))
    if not agent_id:
        return JSONResponse({"error": "agent_id required"}, status_code=400)
    cid = core_store.active_company_id()
    budget = core_store.set_budget(cid, agent_id, amount)
    core_activity.append(cid, "budget_set", actor="user", subject=f"budget:{agent_id}",
                         details={"amount_usd": amount})
    return JSONResponse(budget)


@app.post("/api/core/work_mode")
async def core_set_work_mode(request: Request):
    """Switch the active company's work mode: manual / auto / beast."""
    body = await request.json()
    mode = (body.get("mode") or "auto").lower()
    if mode not in ("manual", "auto", "beast"):
        return JSONResponse({"error": "mode must be manual|auto|beast"}, status_code=400)
    cid = core_store.active_company_id()
    company = core_store.load_company(cid) or {}
    settings = company.get("settings", {}) or {}
    settings["work_mode"] = mode
    company["settings"] = settings
    company["id"] = cid
    if not company.get("name"):
        company["name"] = cid.title()
    core_store.save_company(company)
    core_activity.append(cid, "work_mode_changed", actor="user", subject=f"mode:{mode}",
                         details={"mode": mode})
    return JSONResponse({"ok": True, "mode": mode})


@app.get("/api/core/system")
async def core_system_status():
    """Shows whether durable state, AI, Composio are configured + work mode."""
    from core import kv as _kv
    cid = core_store.active_company_id()
    company = core_store.load_company(cid) or {}
    settings = company.get("settings", {}) or {}
    return JSONResponse({
        "kv_enabled": _kv.is_enabled(),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "composio_configured": bool(os.getenv("COMPOSIO_API_KEY", "").strip()),
        "vercel": bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV")),
        "work_mode": settings.get("work_mode") or "auto",
    })


@app.get("/api/core/dashboard")
async def core_dashboard_summary():
    cid = core_store.active_company_id()
    tickets = core_store.list_tickets(cid, limit=500)
    by_status: dict = {}
    total_cost = 0.0
    cost_by_agent: dict = {}
    for t in tickets:
        s = t.get("status", "pending")
        by_status.setdefault(s, []).append({
            "id": t["id"], "title": t.get("title", ""), "agent_id": t.get("agent_id", ""),
            "cost_usd": t.get("cost_usd", 0.0), "created_at": t.get("created_at", ""),
            "needs_approval": t.get("needs_approval", False),
            "goal_id": t.get("goal_id"),
            "error": (t.get("error") or "")[:160] if s in ("failed", "paused_budget") else "",
        })
        c = float(t.get("cost_usd", 0.0) or 0.0)
        total_cost += c
        aid = t.get("agent_id", "unknown")
        cost_by_agent[aid] = round(cost_by_agent.get(aid, 0.0) + c, 4)
    # Add per-goal progress so sidebar can render bars without N+1 calls
    active_goals = core_store.list_goals(cid, status="active")
    for g in active_goals:
        gtickets = [t for t in tickets if t.get("goal_id") == g["id"]]
        if not gtickets:
            g["progress"] = {"total": 0, "completed": 0, "percent": 0}
            continue
        done = sum(1 for t in gtickets if t.get("status") in ("completed", "approved"))
        g["progress"] = {
            "total": len(gtickets), "completed": done,
            "percent": round(100 * done / len(gtickets)) if gtickets else 0,
        }

    return JSONResponse({
        "company_id": cid,
        "company": core_store.load_company(cid),
        "counts": {k: len(v) for k, v in by_status.items()},
        "tickets_by_status": by_status,
        "goals": active_goals,
        "budgets": core_store.load_budgets(cid),
        "activity": core_activity.read(cid, limit=40),
        "totals": {"cost_usd": round(total_cost, 4), "cost_by_agent": cost_by_agent,
                   "tickets": len(tickets)},
    })


@app.get("/board", response_class=HTMLResponse)
async def board_page(request: Request):
    return templates.TemplateResponse("board.html", {"request": request})


@app.get("/apps", response_class=HTMLResponse)
async def apps_page(request: Request):
    return templates.TemplateResponse("apps.html", {"request": request})


@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    return templates.TemplateResponse("files.html", {"request": request})


@app.get("/api/core/files")
async def core_list_files(limit: int = 200, include_raw: bool = False):
    from core import files as _files
    return JSONResponse({"files": _files.list_files(limit=limit, include_raw=include_raw)})


@app.get("/api/core/files/raw")
async def core_files_raw(path: str):
    from core import files as _files
    from fastapi.responses import FileResponse, PlainTextResponse
    target = _files.safe_read_file(path)
    if not target:
        return JSONResponse({"error": "not allowed"}, status_code=403)
    # Render markdown / json inline; force download otherwise depends on content-type
    return FileResponse(str(target), filename=target.name)


@app.get("/api/core/agents")
async def core_list_agents():
    """List every agent the orchestrator can dispatch, with role + category."""
    out = []
    for agent_id in AGENT_MODULES.keys():
        try:
            agent = get_agent_instance(agent_id)
            out.append({
                "id": agent.agent_id,
                "name": agent.name,
                "role": agent.role,
                "category": agent.category,
                "needs_approval": agent.agent_id in (
                    "outreach", "social", "admanager", "youtube",
                    "videomaker", "videoproducer", "instagramdm",
                ),
            })
        except Exception:
            pass
    return JSONResponse({"agents": out})


@app.get("/api/core/apps")
async def core_list_apps():
    from services import apps as _apps_svc
    cfg = load_config()
    if cfg.get("composio_api_key"):
        os.environ["COMPOSIO_API_KEY"] = cfg["composio_api_key"]
    cid = core_store.active_company_id()
    # Refresh status from Composio if any connections exist
    connections = _apps_svc.refresh_connection_status(cid)
    return JSONResponse({
        "company_id": cid,
        "catalog": _apps_svc.APPS_CATALOG,
        "connections": connections,
        "composio_configured": bool(os.getenv("COMPOSIO_API_KEY", "").strip()),
    })


@app.post("/api/core/apps/{slug}/connect")
async def core_connect_app(slug: str):
    from services import apps as _apps_svc
    cfg = load_config()
    if cfg.get("composio_api_key"):
        os.environ["COMPOSIO_API_KEY"] = cfg["composio_api_key"]
    return JSONResponse(_apps_svc.initiate_connection(slug))


@app.post("/api/core/apps/{slug}/disconnect")
async def core_disconnect_app(slug: str):
    from services import apps as _apps_svc
    return JSONResponse(_apps_svc.disconnect(slug))


@app.post("/api/core/agents/{agent_id}/quick-run")
async def core_agent_quick_run(agent_id: str, request: Request):
    """Quick-run any agent with custom params from the Board's agent panel."""
    if agent_id not in AGENT_MODULES:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    params = body.get("params", {}) if isinstance(body, dict) else {}
    title = body.get("title", f"{agent_id} run") if isinstance(body, dict) else f"{agent_id} run"

    cfg = load_config()
    for src, dst in [
        ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
        ("instantly_api_key", "INSTANTLY_API_KEY"),
        ("anthropic_api_key", "ANTHROPIC_API_KEY"),
        ("composio_api_key", "COMPOSIO_API_KEY"),
    ]:
        if cfg.get(src):
            os.environ[dst] = cfg[src]

    import asyncio
    def _run():
        agent = get_agent_instance(agent_id)
        return core_runtime.execute_in_ticket(
            agent_id=agent_id, run_fn=agent.run, params=params, title=title,
        )
    ticket = await asyncio.to_thread(_run)
    return JSONResponse({
        "ticket_id": ticket["id"],
        "status": ticket["status"],
        "cost_usd": ticket.get("cost_usd", 0.0),
        "needs_approval": ticket.get("needs_approval", False),
    })


# ── CEO chat ───────────────────────────────────────────────────────
CEO_HISTORIES: dict = {}
CEO_MAX_HISTORY = 24


@app.post("/api/core/ceo/chat")
async def core_ceo_chat(request: Request):
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    cid = core_store.active_company_id()
    history = CEO_HISTORIES.setdefault(cid, [])

    # Inject keys from the active company's profile (works on Vercel where
    # /data/config/user_profile.json doesn't exist) plus legacy single-file config
    company = core_store.load_company(cid) or {}
    company_keys = company.get("api_keys", {}) or {}
    cfg = load_config()
    for src, dst in [
        ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
        ("instantly_api_key", "INSTANTLY_API_KEY"),
        ("anthropic_api_key", "ANTHROPIC_API_KEY"),
        ("composio_api_key", "COMPOSIO_API_KEY"),
        ("scraper_actor", "SCRAPER_ACTOR"),
        ("email_finder_providers", "EMAIL_FINDER_PROVIDERS"),
    ]:
        v = company_keys.get(src) or cfg.get(src)
        if v:
            os.environ[dst] = v

    import asyncio
    def _run():
        agent = get_agent_instance("ceo")
        return agent.run(message=message, history=history)
    result = await asyncio.to_thread(_run)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": result.get("response", "")})
    if len(history) > CEO_MAX_HISTORY * 2:
        CEO_HISTORIES[cid] = history[-CEO_MAX_HISTORY * 2:]

    # Auto-execution: if CEO created any tickets, kick the heartbeat
    # immediately so user sees agents starting work right away (not waiting
    # for the hourly cron).
    created_ticket = any(
        e.get("ok") and e.get("kind") in ("create_ticket", "plan_goal")
        for e in (result.get("executed") or [])
    )
    if created_ticket:
        try:
            from core import heartbeat as _hb
            await asyncio.to_thread(_hb.tick, company_id=cid)
        except Exception:
            pass

    return JSONResponse({
        "response": result.get("response", ""),
        "actions": result.get("actions", []),
        "executed": result.get("executed", []),
        "tool_calls": result.get("tool_calls", []),
        "state": result.get("state_snapshot", {}),
    })


@app.post("/api/core/ceo/orchestrate")
async def core_ceo_orchestrate(request: Request):
    """CEO multi-agent orchestration: tek mesaj → plan → ajanlar zinciri.

    Her ajan bir öncekinin çıktısı bağlamında çalışır. Live SSE stream:
        plan / step_start / step_done / step_error / text_delta / done
    """
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    cid = core_store.active_company_id()

    company = core_store.load_company(cid) or {}
    company_keys = company.get("api_keys", {}) or {}
    cfg = load_config()
    for src, dst in [
        ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
        ("instantly_api_key", "INSTANTLY_API_KEY"),
        ("anthropic_api_key", "ANTHROPIC_API_KEY"),
        ("composio_api_key", "COMPOSIO_API_KEY"),
        ("scraper_actor", "SCRAPER_ACTOR"),
        ("email_finder_providers", "EMAIL_FINDER_PROVIDERS"),
    ]:
        v = company_keys.get(src) or cfg.get(src)
        if v:
            os.environ[dst] = v

    from core import orchestrator as _orc

    def event_gen():
        try:
            for evt in _orc.orchestrate(message, cid):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'kind':'error','message':str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@app.post("/api/core/ceo/chat/stream")
async def core_ceo_chat_stream(request: Request):
    """SSE streaming endpoint — emits text deltas, tool starts/ends, action
    results as the CEO works. Connection ends on 'done' event."""
    body = await request.json()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)
    cid = core_store.active_company_id()
    history = CEO_HISTORIES.setdefault(cid, [])

    company = core_store.load_company(cid) or {}
    company_keys = company.get("api_keys", {}) or {}
    cfg = load_config()
    for src, dst in [
        ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
        ("instantly_api_key", "INSTANTLY_API_KEY"),
        ("anthropic_api_key", "ANTHROPIC_API_KEY"),
        ("composio_api_key", "COMPOSIO_API_KEY"),
        ("scraper_actor", "SCRAPER_ACTOR"),
        ("email_finder_providers", "EMAIL_FINDER_PROVIDERS"),
    ]:
        v = company_keys.get(src) or cfg.get(src)
        if v:
            os.environ[dst] = v

    from agents.ceo.agent import stream_chat_events

    def event_gen():
        final_response = ""
        final_actions = []
        any_create = False
        try:
            for evt in stream_chat_events(message, history, cid):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                if evt.get("kind") == "done":
                    final_response = evt.get("response", "") or ""
                    final_actions = evt.get("executed", []) or []
                    any_create = any(
                        e.get("ok") and e.get("kind") in ("create_ticket", "plan_goal")
                        for e in final_actions
                    )
        except Exception as e:
            yield f"data: {json.dumps({'kind':'error','message':str(e)}, ensure_ascii=False)}\n\n"

        # Persist history once stream completes
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": final_response})
        if len(history) > CEO_MAX_HISTORY * 2:
            CEO_HISTORIES[cid] = history[-CEO_MAX_HISTORY * 2:]

        # Auto-execute downstream agents if CEO created tickets
        if any_create:
            try:
                from core import heartbeat as _hb
                _hb.tick(company_id=cid)
            except Exception:
                pass

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@app.get("/api/core/ceo/history")
async def core_ceo_history():
    cid = core_store.active_company_id()
    return JSONResponse({"company_id": cid, "messages": CEO_HISTORIES.get(cid, [])})


@app.post("/api/core/ceo/history/clear")
async def core_ceo_clear():
    cid = core_store.active_company_id()
    CEO_HISTORIES[cid] = []
    return JSONResponse({"ok": True})


@app.get("/api/core/memory")
async def core_list_memory(limit: int = 30):
    """Şirketin biriktirdiği gözlemler."""
    from core import memory as _mem
    cid = core_store.active_company_id()
    return JSONResponse({"company_id": cid, "facts": _mem.list_facts(cid, limit=limit)})


@app.post("/api/core/heartbeat/tick")
async def core_heartbeat_tick():
    from core import heartbeat as core_heartbeat
    import asyncio
    summary = await asyncio.to_thread(core_heartbeat.tick)
    return JSONResponse(summary)


@app.get("/api/cron/heartbeat")
async def cron_heartbeat(request: Request):
    """Triggered by Vercel Cron every 2 minutes. Vercel adds an
    Authorization: Bearer ${CRON_SECRET} header automatically when
    CRON_SECRET env is set on the project."""
    secret = os.getenv("CRON_SECRET", "").strip()
    if secret:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {secret}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    # Inject company API keys into env per-company before each tick so
    # agents that depend on Apify/fal/etc. can run autonomously
    from core import heartbeat as core_heartbeat, store as _store
    import asyncio

    def _tick_all():
        results = []
        for company in _store.list_companies():
            cid = company.get("id")
            keys = company.get("api_keys", {}) or {}
            for src, dst in [
                ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
                ("instantly_api_key", "INSTANTLY_API_KEY"),
                ("anthropic_api_key", "ANTHROPIC_API_KEY"),
                ("composio_api_key", "COMPOSIO_API_KEY"),
                ("scraper_actor", "SCRAPER_ACTOR"),
                ("email_finder_providers", "EMAIL_FINDER_PROVIDERS"),
            ]:
                v = keys.get(src) if isinstance(keys, dict) else None
                if v:
                    os.environ[dst] = v
            results.append({"company": cid, **core_heartbeat.tick(company_id=cid)})
        return results

    summary = await asyncio.to_thread(_tick_all)
    return JSONResponse({"ok": True, "ticks": summary, "at": datetime.now().isoformat()})


# ═══════════════════════════════════════════
# PIPELINE / CRM
# ═══════════════════════════════════════════

PIPELINE_DIR = DATA_BASE / "pipeline"
VALID_STAGES = ["new", "contacted", "meeting", "proposal_sent", "closed", "lost"]


def slugify(name):
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s-]+', '-', s)
    return s


def _load_json(path, default=None):
    if default is None:
        default = {}
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.post("/api/leads/{lead_id}/stage")
async def set_lead_stage(lead_id: str, request: Request):
    body = await request.json()
    stage = body.get("stage", "")
    if stage not in VALID_STAGES:
        return JSONResponse({"error": "Invalid stage. Valid: " + ", ".join(VALID_STAGES)}, status_code=400)
    path = PIPELINE_DIR / "stages.json"
    stages = _load_json(path)
    stages[lead_id] = {"stage": stage, "updated_at": datetime.now().isoformat()}
    _save_json(path, stages)
    return JSONResponse({"status": "ok", "lead_id": lead_id, "stage": stage})


@app.post("/api/leads/{lead_id}/note")
async def add_lead_note(lead_id: str, request: Request):
    body = await request.json()
    text = body.get("text", "")
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    path = PIPELINE_DIR / "notes.json"
    notes = _load_json(path)
    if lead_id not in notes:
        notes[lead_id] = []
    note = {"text": text, "created_at": datetime.now().isoformat(), "id": "note_" + uuid.uuid4().hex[:8]}
    notes[lead_id].append(note)
    _save_json(path, notes)
    return JSONResponse({"status": "ok", "note": note})


@app.get("/api/leads/{lead_id}/notes")
async def get_lead_notes(lead_id: str):
    path = PIPELINE_DIR / "notes.json"
    notes = _load_json(path)
    return JSONResponse(notes.get(lead_id, []))


@app.get("/api/pipeline")
async def get_pipeline():
    stages_path = PIPELINE_DIR / "stages.json"
    stages = _load_json(stages_path)

    # Get qualified leads for enrichment
    qual_dir = DATA_BASE / "leads" / "qualified"
    leads_by_name = {}
    if qual_dir.exists():
        files = sorted(qual_dir.glob("*.json"), reverse=True)
        if files:
            with open(files[0]) as f:
                data = json.load(f)
            for entry in data.get("leads", []):
                lead = entry if "name" in entry else entry.get("lead", entry)
                name = lead.get("name", lead.get("title", ""))
                slug = slugify(name)
                leads_by_name[slug] = {
                    "name": name,
                    "score": entry.get("score", lead.get("score", 0)),
                    "qualification": entry.get("qualification", lead.get("qualification", "")),
                    "email": lead.get("email", ""),
                    "phone": lead.get("phone", ""),
                    "website": lead.get("website", ""),
                }
                # Auto-create stage entry for leads not yet in pipeline
                if slug not in stages:
                    stages[slug] = {"stage": "new", "updated_at": datetime.now().isoformat()}

    # Save auto-created entries
    _save_json(stages_path, stages)

    # Group by stage
    grouped = {s: [] for s in VALID_STAGES}
    for slug, info in stages.items():
        stage = info.get("stage", "new")
        lead_info = leads_by_name.get(slug, {"name": slug})
        lead_info["slug"] = slug
        lead_info["updated_at"] = info.get("updated_at", "")
        grouped[stage].append(lead_info)

    counts = {s: len(v) for s, v in grouped.items()}
    return JSONResponse({"stages": grouped, "counts": counts})


@app.post("/api/leads/{lead_id}/reminder")
async def add_reminder(lead_id: str, request: Request):
    body = await request.json()
    text = body.get("text", "")
    due_date = body.get("due_date", "")
    if not text or not due_date:
        return JSONResponse({"error": "text and due_date required"}, status_code=400)

    path = PIPELINE_DIR / "reminders.json"
    reminders = _load_json(path, [])
    reminder = {
        "lead_id": lead_id,
        "lead_name": body.get("lead_name", lead_id),
        "text": text,
        "due_date": due_date,
        "done": False,
        "created_at": datetime.now().isoformat(),
    }
    reminders.append(reminder)
    _save_json(path, reminders)
    return JSONResponse({"status": "ok", "reminder": reminder})


@app.get("/api/reminders")
async def get_reminders():
    path = PIPELINE_DIR / "reminders.json"
    reminders = _load_json(path, [])
    # Sort by due_date, filter out done
    active = [r for r in reminders if not r.get("done", False)]
    active.sort(key=lambda r: r.get("due_date", ""))
    return JSONResponse(active)


# ═══════════════════════════════════════════
# DEALS / REVENUE
# ═══════════════════════════════════════════

VALID_DEAL_STATUS = ["proposal", "negotiation", "won", "lost"]


@app.post("/api/deals")
async def create_deal(request: Request):
    body = await request.json()
    lead_name = body.get("lead_name", "")
    if not lead_name:
        return JSONResponse({"error": "lead_name required"}, status_code=400)
    deal = {
        "id": "deal_" + uuid.uuid4().hex[:8],
        "lead_name": lead_name,
        "value": body.get("value", 0),
        "currency": body.get("currency", "USD"),
        "service": body.get("service", ""),
        "status": body.get("status", "proposal"),
        "created_at": datetime.now().isoformat(),
        "closed_at": None,
        "notes": body.get("notes", ""),
    }
    path = PIPELINE_DIR / "deals.json"
    deals = _load_json(path, [])
    deals.append(deal)
    _save_json(path, deals)
    return JSONResponse({"status": "ok", "deal": deal})


@app.get("/api/deals")
async def get_deals():
    path = PIPELINE_DIR / "deals.json"
    deals = _load_json(path, [])
    return JSONResponse(deals)


@app.put("/api/deals/{deal_id}")
async def update_deal(deal_id: str, request: Request):
    body = await request.json()
    path = PIPELINE_DIR / "deals.json"
    deals = _load_json(path, [])
    for deal in deals:
        if deal["id"] == deal_id:
            for k in ["value", "currency", "service", "status", "notes", "lead_name"]:
                if k in body:
                    deal[k] = body[k]
            if body.get("status") in ("won", "lost") and not deal.get("closed_at"):
                deal["closed_at"] = datetime.now().isoformat()
            _save_json(path, deals)
            return JSONResponse({"status": "ok", "deal": deal})
    return JSONResponse({"error": "Deal not found"}, status_code=404)


@app.delete("/api/deals/{deal_id}")
async def delete_deal(deal_id: str):
    path = PIPELINE_DIR / "deals.json"
    deals = _load_json(path, [])
    deals = [d for d in deals if d["id"] != deal_id]
    _save_json(path, deals)
    return JSONResponse({"status": "ok"})


@app.get("/api/revenue/summary")
async def revenue_summary():
    path = PIPELINE_DIR / "deals.json"
    deals = _load_json(path, [])
    total_won = sum(d.get("value", 0) for d in deals if d.get("status") == "won")
    total_pipeline = sum(d.get("value", 0) for d in deals if d.get("status") in ("proposal", "negotiation"))
    total_closed = len([d for d in deals if d.get("status") in ("won", "lost")])
    total_won_count = len([d for d in deals if d.get("status") == "won"])
    win_rate = round(total_won_count / total_closed * 100) if total_closed > 0 else 0
    open_deals = len([d for d in deals if d.get("status") in ("proposal", "negotiation")])

    # Monthly breakdown
    monthly = {}
    for d in deals:
        if d.get("status") == "won" and d.get("closed_at"):
            month = d["closed_at"][:7]
            monthly[month] = monthly.get(month, 0) + d.get("value", 0)

    return JSONResponse({
        "total_won": total_won,
        "total_pipeline": total_pipeline,
        "win_rate": win_rate,
        "open_deals": open_deals,
        "total_deals": len(deals),
        "monthly": monthly,
        "currency": "USD",
    })


# ═══════════════════════════════════════════
# GENERATED SITES
# ═══════════════════════════════════════════

@app.get("/api/sites")
async def list_sites():
    """List all generated site HTML files."""
    sites_dir = OUTPUTS_BASE / "sites"
    if not sites_dir.exists():
        return JSONResponse([])
    files = sorted(sites_dir.glob("*.html"), reverse=True)
    result = []
    for f in files:
        result.append({
            "filename": f.name,
            "preview_url": "/site/" + f.name,
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
        })
    return JSONResponse(result)


@app.get("/site/{filename}")
async def serve_site(filename: str):
    """Serve a generated site HTML file for preview."""
    # Sanitize filename
    if ".." in filename or "/" in filename:
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = OUTPUTS_BASE / "sites" / filename
    if not filepath.exists() or not filepath.suffix == ".html":
        return HTMLResponse("<h1>Site not found</h1>", status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


# ═══════════════════════════════════════════
# PRESENTATIONS
# ═══════════════════════════════════════════

@app.get("/api/presentations")
async def list_presentations():
    """List all generated presentations."""
    pres_dir = OUTPUTS_BASE / "presentations"
    if not pres_dir.exists():
        return JSONResponse([])
    files = sorted(pres_dir.glob("*.html"), reverse=True)
    result = []
    for f in files:
        result.append({
            "filename": f.name,
            "preview_url": "/presentation/" + f.name,
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
        })
    return JSONResponse(result)


@app.get("/presentation/{filename}")
async def serve_presentation(filename: str):
    """Serve a generated presentation HTML file."""
    if ".." in filename or "/" in filename:
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = OUTPUTS_BASE / "presentations" / filename
    if not filepath.exists() or not filepath.suffix == ".html":
        return HTMLResponse("<h1>Presentation not found</h1>", status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


# ═══════════════════════════════════════════
# BRAND KIT
# ═══════════════════════════════════════════

@app.get("/api/brandkit")
async def get_brand_kit():
    """Get the latest brand kit."""
    kit_dir = DATA_BASE / "brandkit"
    if not kit_dir.exists():
        return JSONResponse({"status": "empty"})
    files = sorted(kit_dir.glob("*.json"), reverse=True)
    if files:
        with open(files[0]) as f:
            return JSONResponse(json.load(f))
    return JSONResponse({"status": "empty"})


@app.get("/brandkit/{filename}")
async def serve_brand_board(filename: str):
    """Serve a generated brand board HTML file."""
    if ".." in filename or "/" in filename:
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = OUTPUTS_BASE / "brandkit" / filename
    if not filepath.exists() or not filepath.suffix == ".html":
        return HTMLResponse("<h1>Brand board not found</h1>", status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


# ═══════════════════════════════════════════
# STORYBOARD
# ═══════════════════════════════════════════

@app.get("/api/storyboards")
async def list_storyboards_api():
    """List all generated storyboard HTML files."""
    from services.storyboard import list_storyboards
    return JSONResponse(list_storyboards())


@app.get("/storyboard/{filename}")
async def serve_storyboard(filename: str):
    """Serve a generated storyboard HTML file for preview."""
    if ".." in filename or "/" in filename:
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = OUTPUTS_BASE / "storyboards" / filename
    if not filepath.exists() or not filepath.suffix == ".html":
        return HTMLResponse("<h1>Storyboard not found</h1>", status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


# ═══════════════════════════════════════════
# MCP HUB
# ═══════════════════════════════════════════

@app.get("/api/mcp/tools")
async def list_mcp_tools(category: str = ""):
    """List available MCP tools."""
    from services.mcp_registry import list_tools
    tools = list_tools(category or None)
    return JSONResponse({"status": "ok", "tools": tools, "count": len(tools)})


@app.get("/api/mcp/tools/{tool_id}")
async def get_mcp_tool(tool_id: str):
    """Get MCP tool details and config."""
    from services.mcp_registry import get_tool_config, MCP_CATALOG
    tool = MCP_CATALOG.get(tool_id)
    if not tool:
        return JSONResponse({"error": "Tool not found"}, status_code=404)
    config = get_tool_config(tool_id)
    return JSONResponse({"status": "ok", "tool": tool, "config": config})


@app.post("/api/mcp/install")
async def install_mcp_tool(request: Request):
    """Install (save config for) an MCP tool."""
    body = await request.json()
    tool_ids = body.get("tool_ids", [])
    if not tool_ids:
        return JSONResponse({"error": "tool_ids required"}, status_code=400)
    from services.mcp_registry import save_installed_tools
    installed = save_installed_tools(tool_ids)
    return JSONResponse({"status": "ok", "installed": len(installed)})


@app.get("/api/mcp/installed")
async def get_installed_mcp():
    """Get installed MCP tools."""
    path = DATA_BASE / "mcp" / "installed.json"
    if path.exists():
        with open(path) as f:
            return JSONResponse(json.load(f))
    return JSONResponse({})


@app.get("/api/mcp/config")
async def generate_mcp_config():
    """Generate full MCP config from installed tools."""
    from services.mcp_registry import generate_full_config
    path = DATA_BASE / "mcp" / "installed.json"
    if not path.exists():
        return JSONResponse({"mcpServers": {}})
    with open(path) as f:
        installed = json.load(f)
    config = generate_full_config(list(installed.keys()))
    return JSONResponse(config)


@app.post("/api/mcp/search")
async def search_mcp_tools(request: Request):
    """Search MCP tools by keyword."""
    body = await request.json()
    query = body.get("query", "")
    if not query:
        return JSONResponse({"error": "query required"}, status_code=400)
    from services.mcp_registry import search_tools
    results = search_tools(query)
    return JSONResponse({"status": "ok", "results": results, "count": len(results)})


# ═══════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════

@app.get("/api/analytics/dashboard")
async def analytics_dashboard():
    """Get full analytics dashboard data."""
    from services.analytics_engine import gather_pipeline_metrics, calculate_conversion_funnel
    metrics = gather_pipeline_metrics()
    funnel = calculate_conversion_funnel()
    return JSONResponse({"metrics": metrics, "funnel": funnel})


@app.get("/api/analytics/funnel")
async def analytics_funnel():
    """Get conversion funnel data."""
    from services.analytics_engine import calculate_conversion_funnel
    return JSONResponse(calculate_conversion_funnel())


@app.get("/api/analytics/summary")
async def analytics_summary():
    """Get weekly performance summary."""
    from services.analytics_engine import generate_weekly_summary
    return JSONResponse(generate_weekly_summary())


# ═══════════════════════════════════════════
# CONTENT
# ═══════════════════════════════════════════

@app.get("/api/content")
async def list_content():
    """List generated content files."""
    content_dir = OUTPUTS_BASE / "content"
    if not content_dir.exists():
        return JSONResponse([])
    files = sorted(content_dir.glob("*.md"), reverse=True)
    result = []
    for f in files:
        result.append({
            "filename": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
        })
    return JSONResponse(result)


# ═══════════════════════════════════════════
# DESIGNS
# ═══════════════════════════════════════════

@app.get("/api/designs")
async def list_designs():
    """List generated design briefs."""
    designs_dir = DATA_BASE / "designs"
    if not designs_dir.exists():
        return JSONResponse([])
    files = sorted(designs_dir.glob("*.json"), reverse=True)
    result = []
    for f in files[:20]:
        with open(f) as fh:
            data = json.load(fh)
            result.append({
                "filename": f.name,
                "design_type": data.get("design_type", ""),
                "platform": data.get("platform", ""),
                "business_name": data.get("business_name", ""),
                "created_at": data.get("created_at", ""),
            })
    return JSONResponse(result)


# ═══════════════════════════════════════════
# VIDEO
# ═══════════════════════════════════════════

@app.get("/api/videos")
async def list_videos():
    """List generated video projects."""
    videos_dir = DATA_BASE / "videos"
    if not videos_dir.exists():
        return JSONResponse([])
    files = sorted(videos_dir.glob("*.json"), reverse=True)
    result = []
    for f in files[:20]:
        with open(f) as fh:
            data = json.load(fh)
            result.append({
                "filename": f.name,
                "video_type": data.get("video_type", ""),
                "business_name": data.get("business_name", ""),
                "created_at": data.get("created_at", ""),
            })
    return JSONResponse(result)


# ═══════════════════════════════════════════
# COST DASHBOARD
# ═══════════════════════════════════════════

@app.get("/api/cost/summary")
async def cost_summary(days: int = 30):
    from services import cost_dashboard
    from core import store as _store
    cid = _store.active_company_id()
    return JSONResponse(cost_dashboard.summary(cid, days=days))


@app.post("/api/cost/alerts")
async def cost_set_alerts(req: Request):
    from services import cost_dashboard
    from core import store as _store
    body = await req.json()
    cid = _store.active_company_id()
    alerts = cost_dashboard.set_alerts(
        cid,
        daily=body.get("daily_total"),
        monthly=body.get("monthly_total"),
    )
    return JSONResponse({"ok": True, "alerts": alerts})


# ═══════════════════════════════════════════
# TELEGRAM APPROVAL BOT
# ═══════════════════════════════════════════

@app.post("/api/telegram/setup")
async def telegram_setup(req: Request):
    from services import telegram_bot
    from core import store as _store
    body = await req.json()
    cid = _store.active_company_id()
    base_url = body.get("base_url") or str(req.base_url).rstrip("/")
    return JSONResponse(telegram_bot.setup_webhook(cid, base_url))


@app.post("/api/telegram/test")
async def telegram_test():
    from services import telegram_bot
    from core import store as _store
    cid = _store.active_company_id()
    return JSONResponse(telegram_bot.push_text(cid, "🤖 *goat-bot bağlı.* Onay mesajları buraya düşecek."))


@app.post("/api/webhooks/telegram")
async def telegram_webhook(req: Request):
    from services import telegram_bot
    from core import agent_runtime, store as _store
    payload = await req.json()
    decision = telegram_bot.handle_callback(payload)
    if decision.get("action") in ("approve", "reject") and decision.get("ticket_id"):
        cid = _store.active_company_id()
        if decision["action"] == "approve":
            agent_runtime.approve(cid, decision["ticket_id"], approver="telegram")
        else:
            agent_runtime.reject(cid, decision["ticket_id"], approver="telegram", reason="Telegram'dan reddedildi")
    return JSONResponse({"ok": True, "decision": decision})


# ═══════════════════════════════════════════
# EMAIL STATS (Instantly warmup tracker)
# ═══════════════════════════════════════════

@app.get("/api/email/stats")
async def email_stats():
    from services import instantly_stats
    return JSONResponse(instantly_stats.aggregate())


@app.get("/api/email/stats/{campaign_id}")
async def email_stats_one(campaign_id: str):
    from services import instantly_stats
    return JSONResponse(instantly_stats.fetch_campaign_stats(campaign_id))


# ═══════════════════════════════════════════
# WEBHOOKS (external integrations)
# ═══════════════════════════════════════════

@app.post("/api/webhooks/stripe")
async def webhook_stripe(req: Request):
    from services import webhooks
    from core import store as _store
    body = await req.json()
    sig = req.headers.get("stripe-signature")
    cid = _store.active_company_id()
    return JSONResponse(webhooks.stripe_event(cid, body, signature=sig))


@app.post("/api/webhooks/calendly")
async def webhook_calendly(req: Request):
    from services import webhooks
    from core import store as _store
    body = await req.json()
    cid = _store.active_company_id()
    return JSONResponse(webhooks.calendly_event(cid, body))


@app.post("/api/webhooks/instantly")
async def webhook_instantly(req: Request):
    from services import webhooks
    from core import store as _store
    body = await req.json()
    cid = _store.active_company_id()
    return JSONResponse(webhooks.instantly_event(cid, body))


# ═══════════════════════════════════════════
# VOICE (CEO mic input)
# ═══════════════════════════════════════════

@app.post("/api/ceo/voice")
async def ceo_voice(req: Request):
    from services import voice
    raw = await req.body()
    mime = req.headers.get("content-type") or "audio/webm"
    return JSONResponse(voice.transcribe(raw, mime=mime))


# ═══════════════════════════════════════════
# COMPANY TEMPLATES (.goat)
# ═══════════════════════════════════════════

@app.get("/api/templates")
async def list_company_templates():
    from core import templates as _tmpl
    return JSONResponse(_tmpl.list_templates())


@app.get("/api/templates/{template_id}")
async def get_company_template(template_id: str):
    from core import templates as _tmpl
    data = _tmpl.load_template(template_id)
    if not data:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(data)


@app.post("/api/templates/import")
async def import_company_template(req: Request):
    from core import templates as _tmpl
    body = await req.json()
    template_id = body.get("template_id") or ""
    return JSONResponse(_tmpl.import_template(template_id, company_id=body.get("company_id")))


# ═══════════════════════════════════════════
# FAL.AI DYNAMIC MODELS
# ═══════════════════════════════════════════

@app.get("/api/fal/models")
async def fal_models(category: str = "", refresh: bool = False):
    from services import fal_mcp
    return JSONResponse(fal_mcp.list_models(category=category or None, force_refresh=refresh))


@app.get("/api/fal/search")
async def fal_search(q: str = ""):
    from services import fal_mcp
    return JSONResponse(fal_mcp.search(q))


@app.get("/api/fal/recommend")
async def fal_recommend(use_case: str = ""):
    from services import fal_mcp
    return JSONResponse(fal_mcp.recommend_for(use_case))


# ═══════════════════════════════════════════
# LLM ROUTER + OLLAMA
# ═══════════════════════════════════════════

@app.get("/api/llm/providers")
async def llm_providers():
    from services import llm
    return JSONResponse(llm.available_providers())


@app.post("/api/llm/complete")
async def llm_complete(req: Request):
    from services import llm
    body = await req.json()
    return JSONResponse(llm.complete(
        messages=body.get("messages") or [],
        task=body.get("task", "default"),
        system=body.get("system", ""),
        max_tokens=int(body.get("max_tokens") or 1500),
        force_provider=body.get("provider"),
    ))


@app.get("/api/ollama/status")
async def ollama_status():
    from services import ollama
    return JSONResponse(ollama.status())


@app.get("/api/ollama/models")
async def ollama_models():
    from services import ollama
    return JSONResponse(ollama.list_models())


@app.post("/api/ollama/pull")
async def ollama_pull(req: Request):
    from services import ollama
    body = await req.json()
    return JSONResponse(ollama.pull(body.get("model", "llama3.1:8b")))


# ═══════════════════════════════════════════
# SELF-IMPROVEMENT
# ═══════════════════════════════════════════

@app.get("/api/improver/records")
async def improver_records():
    from core import improver
    return JSONResponse(improver.all_records())


@app.get("/api/improver/{agent_id}")
async def improver_record(agent_id: str):
    from core import improver
    rec = improver.latest_record(agent_id)
    if not rec:
        return JSONResponse({"error": "no record yet"}, status_code=404)
    return JSONResponse(rec)


@app.post("/api/improver/run")
async def improver_run(req: Request):
    from core import improver, store
    body = await req.json() if req.headers.get("content-type", "").startswith("application/json") else {}
    company_id = body.get("company_id") or store.active_company_id()
    agent_id = body.get("agent_id")
    if agent_id:
        return JSONResponse(improver.improve_agent(company_id, agent_id))
    return JSONResponse(improver.improve_all(company_id))


# ═══════════════════════════════════════════
# APIFY CATALOG
# ═══════════════════════════════════════════

@app.get("/api/apify/actors")
async def apify_actors(category: str = "", refresh: bool = False):
    from services import apify_catalog
    return JSONResponse(apify_catalog.list_actors(category=category, refresh=refresh))


@app.get("/api/apify/health")
async def apify_health():
    from services import apify_catalog
    return JSONResponse(apify_catalog.actor_health())


@app.get("/api/apify/runs")
async def apify_runs():
    from services import apify_catalog
    return JSONResponse(apify_catalog.actor_runs_summary())


@app.get("/api/apify/recommend")
async def apify_recommend(niche: str = ""):
    from services import apify_catalog
    return JSONResponse({"niche": niche, "recommended": apify_catalog.recommend_for_niche(niche)})


# ═══════════════════════════════════════════
# AUTOMATIONS (n8n-flavored)
# ═══════════════════════════════════════════

@app.get("/api/automations/templates")
async def automations_list_templates():
    from core import automations
    return JSONResponse({"templates": automations.list_templates()})


@app.get("/api/automations/templates/{template_id}")
async def automations_template_detail(template_id: str):
    from core import automations
    data = automations.load_template(template_id)
    if not data:
        return JSONResponse({"error": "not found"}, status_code=404)
    nodes = data.get("nodes", [])
    types = sorted({n.get("type", "").replace("n8n-nodes-base.", "") for n in nodes})
    return JSONResponse({
        "id": template_id,
        "name": data.get("name", template_id),
        "trigger": automations._detect_trigger(nodes),
        "node_count": len(nodes),
        "node_types": types,
        "workflow": data,
    })


@app.get("/api/automations/installed")
async def automations_installed(req: Request):
    from core import automations, store
    cid = store.active_company_id()
    return JSONResponse({"installed": automations.list_installed(cid)})


@app.post("/api/automations/install")
async def automations_install(req: Request):
    from core import automations, store
    body = await req.json()
    cid = store.active_company_id()
    res = automations.install_template(cid, body.get("template_id", ""))
    return JSONResponse(res)


@app.post("/api/automations/{automation_id}/trigger")
async def automations_trigger(automation_id: str, req: Request):
    from core import automations, store
    cid = store.active_company_id()
    payload = {}
    try:
        if req.headers.get("content-type", "").startswith("application/json"):
            payload = await req.json()
    except Exception:
        payload = {}
    return JSONResponse(automations.trigger(cid, automation_id, payload=payload))


@app.delete("/api/automations/{automation_id}")
async def automations_delete(automation_id: str):
    from core import automations, store
    cid = store.active_company_id()
    return JSONResponse({"deleted": automations.delete_installed(cid, automation_id)})


# ═══════════════════════════════════════════
# UI PAGES (workflows + apify)
# ═══════════════════════════════════════════

@app.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    return templates.TemplateResponse("workflows.html", {"request": request})


@app.get("/apify", response_class=HTMLResponse)
async def apify_page(request: Request):
    return templates.TemplateResponse("apify.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7778)
