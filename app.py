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

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

AGENT_MODULES = {
    "goat": "agents.goat.agent:GoatAgent",
    "scout": "agents.scout.agent:ScoutAgent",
    "filter": "agents.filter.agent:FilterAgent",
    "auditor": "agents.auditor.agent:AuditorAgent",
    "outreach": "agents.outreach.agent:OutreachAgent",
    "pitch": "agents.pitch.agent:PitchAgent",
    "mentor": "agents.mentor.agent:MentorAgent",
    "sitebuilder": "agents.sitebuilder.agent:SiteBuilderAgent",
    "designer": "agents.designer.agent:DesignerAgent",
    "videomaker": "agents.videomaker.agent:VideoMakerAgent",
    "content": "agents.content.agent:ContentAgent",
    "presenter": "agents.presenter.agent:PresenterAgent",
    "brandkit": "agents.brandkit.agent:BrandKitAgent",
    "admanager": "agents.admanager.agent:AdManagerAgent",
    "social": "agents.social.agent:SocialAgent",
    "analytics": "agents.analytics.agent:AnalyticsAgent",
}

AGENT_RESULTS = {}
CHAT_HISTORIES = {}  # {agent_id: [{"role": "user"|"assistant", "content": str}, ...]}
MAX_HISTORY = 20  # keep last 20 messages per agent


def get_agent_instance(agent_id: str):
    module_path, class_name = AGENT_MODULES[agent_id].rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def load_config():
    path = BASE_DIR / "data" / "config" / "user_profile.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def load_pipeline_stats():
    """Load stats from latest reports for the dashboard."""
    stats = {"leads_found": 0, "leads_qualified": 0, "hot": 0, "warm": 0, "cold": 0}
    reports_dir = BASE_DIR / "outputs" / "reports"

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
async def dashboard(request: Request):
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
    if cfg.get("instantly_api_key"):
        os.environ["INSTANTLY_API_KEY"] = cfg["instantly_api_key"]
    if cfg.get("apify_token"):
        os.environ["APIFY_TOKEN"] = cfg["apify_token"]
    if cfg.get("fal_key"):
        os.environ["FAL_KEY"] = cfg["fal_key"]

    try:
        agent = get_agent_instance(agent_id)
        if agent_id == "scout" and params:
            result = agent.run(
                query=params.get("query", ""),
                location=params.get("location", ""),
                limit=params.get("limit", 50),
            )
        elif agent_id == "auditor" and params:
            result = agent.run(
                url=params.get("url", ""),
                max_leads=params.get("max_leads", 10),
            )
        elif agent_id == "sitebuilder" and params:
            result = agent.run(
                site_type=params.get("site_type", "agency"),
                lead_index=params.get("lead_index", 0),
                manual_data=params.get("manual_data", None),
            )
        else:
            result = agent.run()

        AGENT_RESULTS[agent_id] = {
            "result": result,
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
        return JSONResponse({"status": "ok", "agent": agent_id, "result": result})
    except Exception as e:
        AGENT_RESULTS[agent_id] = {
            "result": {"error": str(e)},
            "timestamp": datetime.now().isoformat(),
            "status": "error",
        }
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/api/agents/run-pipeline")
async def run_pipeline():
    """Run the full pipeline: Scout → Filter."""
    agent = get_agent_instance("goat")
    result = agent.run()
    AGENT_RESULTS["goat"] = {
        "result": result,
        "timestamp": datetime.now().isoformat(),
        "status": "success",
    }
    return JSONResponse({"status": "ok", "result": result})


@app.get("/api/agent/{agent_id}/result")
async def get_agent_result(agent_id: str):
    if agent_id in AGENT_RESULTS:
        return JSONResponse(AGENT_RESULTS[agent_id])
    return JSONResponse({"status": "not_run"})


# --- Leads ---

@app.get("/api/leads")
async def get_leads():
    """Get all raw leads from latest scrape."""
    raw_dir = BASE_DIR / "data" / "leads" / "raw"
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
    qual_dir = BASE_DIR / "data" / "leads" / "qualified"
    if not qual_dir.exists():
        return JSONResponse([])
    files = sorted(qual_dir.glob("*.json"), reverse=True)
    if files:
        with open(files[0]) as f:
            data = json.load(f)
            return JSONResponse(data.get("leads", []))
    return JSONResponse([])


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

    # Conversation history
    if agent_id not in CHAT_HISTORIES:
        CHAT_HISTORIES[agent_id] = []
    history = CHAT_HISTORIES[agent_id]
    history.append({"role": "user", "content": message})

    history_text = ""
    if len(history) > 1:
        past = history[:-1][-MAX_HISTORY:]
        history_text = "\n\nConversation history:\n" + "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in past
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

    # Save to history
    history.append({"role": "assistant", "content": response})
    if len(history) > MAX_HISTORY * 2:
        CHAT_HISTORIES[agent_id] = history[-MAX_HISTORY * 2:]

    return JSONResponse({"response": response, "agent": agent_id, "actions": actions})


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
    config_dir = BASE_DIR / "data" / "config"
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
        p = BASE_DIR / "data" / sub
        if p.exists():
            shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)

    # Delete reports
    reports = BASE_DIR / "outputs" / "reports"
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
    qual_dir = BASE_DIR / "data" / "leads" / "qualified"
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


# ═══════════════════════════════════════════
# PIPELINE / CRM
# ═══════════════════════════════════════════

PIPELINE_DIR = BASE_DIR / "data" / "pipeline"
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
    qual_dir = BASE_DIR / "data" / "leads" / "qualified"
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
    sites_dir = BASE_DIR / "outputs" / "sites"
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
    filepath = BASE_DIR / "outputs" / "sites" / filename
    if not filepath.exists() or not filepath.suffix == ".html":
        return HTMLResponse("<h1>Site not found</h1>", status_code=404)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7778)
