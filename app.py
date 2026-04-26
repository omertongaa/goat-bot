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
from fastapi.responses import HTMLResponse, JSONResponse
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
}

AGENT_RESULTS = {}
CHAT_HISTORIES = {}  # {agent_id: [{"role": "user"|"assistant", "content": str}, ...]}
MAX_HISTORY = 20  # keep last 20 messages per agent


def get_agent_instance(agent_id: str):
    module_path, class_name = AGENT_MODULES[agent_id].rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def load_config():
    path = DATA_BASE / "config" / "user_profile.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


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


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Paperclip-style Board is now the primary interface."""
    return templates.TemplateResponse("board.html", {"request": request})


@app.get("/classic", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Legacy Dark Room dashboard — preserved for nostalgia + quick actions."""
    config = load_config()
    stats = load_pipeline_stats()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
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


# --- Chat ---

@app.post("/api/chat")
async def chat_with_agent(request: Request):
    """Chat with an agent. Mentor uses Claude CLI, others use context-based responses."""
    body = await request.json()
    message = body.get("message", "")
    agent_id = body.get("agent_id", "mentor")
    agent_info = AGENTS.get(agent_id, {})

    # Mentor has its own answer method
    if agent_id == "mentor":
        try:
            agent = get_agent_instance("mentor")
            response = agent.answer(message)
            return JSONResponse({"response": response, "agent": agent_id})
        except Exception as e:
            return JSONResponse({"response": f"Mentor error: {e}", "agent": agent_id})

    # For other agents, try Claude CLI with context
    agent_data = ""
    if agent_id in AGENT_RESULTS:
        r = AGENT_RESULTS[agent_id]["result"]
        agent_data = f"\nLatest data: {r.get('summary', '')}\nMetrics: {json.dumps(r.get('metrics', {}), default=str)}"

    config = load_config()
    agency_info = ""
    if config:
        agency_info = f"\nUser's agency: {config.get('agency_name', '')} | Niche: {config.get('niche', '')} | Location: {', '.join(config.get('target_cities', []))}"

    # goat orchestrator gets context about all agents
    goat_extra = ""
    if agent_id == "goat":
        agent_list = "\n".join([f"- {k}: {v['name']} ({v['role']})" for k, v in AGENTS.items()])
        available_results = "\n".join([f"- {k}: {v['result'].get('summary', 'done')}" for k, v in list(AGENT_RESULTS.items())[:10]])
        goat_extra = f"\n\nYou are the master orchestrator. Agents:\n{agent_list}\n\nResults:\n{available_results or 'No agents run yet.'}"

    # Build conversation history
    if agent_id not in CHAT_HISTORIES:
        CHAT_HISTORIES[agent_id] = []
    history = CHAT_HISTORIES[agent_id]

    # Add current message to history
    history.append({"role": "user", "content": message})

    # Format history for prompt
    history_text = ""
    if len(history) > 1:
        past = history[:-1][-MAX_HISTORY:]
        history_text = "\n\nConversation history:\n" + "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in past
        )

    prompt = f"""You are {agent_info.get('name', agent_id)}, an AI agent for goat (agency-in-a-box platform).
Your role: {agent_info.get('role', '')}
{agency_info}{goat_extra}{agent_data}{history_text}

Be concise, actionable, specific. Answer in the same language as the user's message.

User: {message}"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
        )
        response = result.stdout.strip() if result.stdout else f"[{agent_info.get('name', agent_id)}] Run the agent first to populate data."
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # No Claude CLI — return contextual fallback
        if agent_id in AGENT_RESULTS:
            r = AGENT_RESULTS[agent_id]["result"]
            response = (f"**{agent_info.get('name', agent_id)}** — {r.get('summary', 'Ready.')}\n\n"
                        + "\n".join(f"- {rec}" for rec in r.get("recommendations", [])))
        else:
            response = f"**{agent_info.get('name', agent_id)}** ready. Hit RUN first to generate data."

    # Save assistant response to history
    history.append({"role": "assistant", "content": response})
    # Trim history
    if len(history) > MAX_HISTORY * 2:
        CHAT_HISTORIES[agent_id] = history[-MAX_HISTORY * 2:]

    return JSONResponse({"response": response, "agent": agent_id})


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
async def core_approve_ticket(ticket_id: str):
    cid = core_store.active_company_id()
    t = core_runtime.approve(cid, ticket_id)
    if not t:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(t)


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


@app.post("/api/core/goals/{goal_id}/plan")
async def core_plan_goal(goal_id: str):
    from core import planner
    cid = core_store.active_company_id()
    goal = core_store.load_goal(cid, goal_id)
    if not goal:
        return JSONResponse({"error": "not found"}, status_code=404)
    plan = planner.plan_goal(cid, goal)
    tickets = planner.materialize_plan(cid, goal_id, plan)
    return JSONResponse({"goal_id": goal_id, "plan": plan,
                         "tickets": [{"id": t["id"], "agent_id": t["agent_id"], "title": t["title"]} for t in tickets]})


@app.get("/api/core/activity")
async def core_activity_stream(limit: int = 100, kind: str = "", subject: str = ""):
    cid = core_store.active_company_id()
    return JSONResponse({
        "company_id": cid,
        "entries": core_activity.read(cid, limit=limit, kind=kind or None, subject=subject or None),
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
        })
        c = float(t.get("cost_usd", 0.0) or 0.0)
        total_cost += c
        aid = t.get("agent_id", "unknown")
        cost_by_agent[aid] = round(cost_by_agent.get(aid, 0.0) + c, 4)
    return JSONResponse({
        "company_id": cid,
        "company": core_store.load_company(cid),
        "counts": {k: len(v) for k, v in by_status.items()},
        "tickets_by_status": by_status,
        "goals": core_store.list_goals(cid, status="active"),
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

    # Inject keys like the regular run endpoint
    cfg = load_config()
    for src, dst in [
        ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
        ("instantly_api_key", "INSTANTLY_API_KEY"),
    ]:
        if cfg.get(src):
            os.environ[dst] = cfg[src]

    import asyncio
    def _run():
        agent = get_agent_instance("ceo")
        return agent.run(message=message, history=history)
    result = await asyncio.to_thread(_run)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": result.get("response", "")})
    if len(history) > CEO_MAX_HISTORY * 2:
        CEO_HISTORIES[cid] = history[-CEO_MAX_HISTORY * 2:]

    return JSONResponse({
        "response": result.get("response", ""),
        "actions": result.get("actions", []),
        "executed": result.get("executed", []),
        "state": result.get("state_snapshot", {}),
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


@app.post("/api/core/heartbeat/tick")
async def core_heartbeat_tick():
    from core import heartbeat as core_heartbeat
    import asyncio
    summary = await asyncio.to_thread(core_heartbeat.tick)
    return JSONResponse(summary)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7778)
