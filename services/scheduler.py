"""Scheduler Service — Automated agent runs via APScheduler.

Runs agents on configurable schedules (daily scout, auto-filter, etc).
No external services needed.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

BASE_DIR = Path(__file__).parent.parent
SCHEDULE_FILE = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data")) / "config" / "schedules.json"

scheduler = BackgroundScheduler()
_started = False


def _load_schedules():
    if SCHEDULE_FILE.exists():
        with open(SCHEDULE_FILE) as f:
            return json.load(f)
    return []


def _save_schedules(schedules):
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedules, f, indent=2, ensure_ascii=False, default=str)


def _run_agent(agent_id: str, params: dict = None):
    """Execute an agent run (called by scheduler)."""
    import importlib

    agent_modules = {
        "goat": "agents.goat.agent:GoatAgent",
        "scout": "agents.scout.agent:ScoutAgent",
        "filter": "agents.filter.agent:FilterAgent",
        "outreach": "agents.outreach.agent:OutreachAgent",
        "pitch": "agents.pitch.agent:PitchAgent",
        "mentor": "agents.mentor.agent:MentorAgent",
    }

    if agent_id not in agent_modules:
        return

    module_path, class_name = agent_modules[agent_id].rsplit(":", 1)
    module = importlib.import_module(module_path)
    agent = getattr(module, class_name)()

    try:
        if agent_id == "scout" and params:
            result = agent.run(
                query=params.get("query", ""),
                location=params.get("location", ""),
                limit=params.get("limit", 50),
            )
        else:
            result = agent.run()

        # Log the scheduled run
        from core.paths import data_path
        log_dir = data_path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "agent_id": agent_id,
            "ran_at": datetime.now().isoformat(),
            "status": result.get("status", "unknown"),
            "summary": result.get("summary", ""),
            "scheduled": True,
        }
        log_file = log_dir / "scheduled_runs.json"
        logs = []
        if log_file.exists():
            with open(log_file) as f:
                logs = json.load(f)
        logs.append(log_entry)
        # Keep last 100 logs
        logs = logs[-100:]
        with open(log_file, "w") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False, default=str)

    except Exception as e:
        print(f"Scheduled run error ({agent_id}): {e}")


def add_schedule(agent_id: str, cron_expr: str, params: dict = None, name: str = "") -> dict:
    """Add a scheduled agent run.

    Args:
        agent_id: Which agent to run
        cron_expr: Cron expression (e.g., "0 9 * * *" for daily at 9am)
                   Or shorthand: "daily", "hourly", "weekly"
        params: Optional params for the agent (e.g., query/location for Scout)
        name: Optional friendly name

    Returns:
        Schedule info dict
    """
    # Convert shorthands
    cron_map = {
        "daily": "0 9 * * *",
        "hourly": "0 * * * *",
        "weekly": "0 9 * * 1",
        "twice_daily": "0 9,18 * * *",
    }
    cron = cron_map.get(cron_expr, cron_expr)

    schedule_id = f"{agent_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if not name:
        name = f"{agent_id} — {cron_expr}"

    # Parse cron
    parts = cron.split()
    if len(parts) != 5:
        return {"error": "Invalid cron expression. Use: minute hour day month weekday"}

    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )

    scheduler.add_job(
        _run_agent,
        trigger=trigger,
        args=[agent_id],
        kwargs={"params": params or {}},
        id=schedule_id,
        name=name,
        replace_existing=True,
    )

    # Persist
    schedules = _load_schedules()
    schedules.append({
        "id": schedule_id,
        "agent_id": agent_id,
        "cron": cron,
        "cron_original": cron_expr,
        "params": params or {},
        "name": name,
        "created_at": datetime.now().isoformat(),
        "active": True,
    })
    _save_schedules(schedules)

    return {
        "id": schedule_id,
        "agent_id": agent_id,
        "cron": cron,
        "name": name,
        "status": "scheduled",
    }


def remove_schedule(schedule_id: str) -> bool:
    """Remove a scheduled job."""
    try:
        scheduler.remove_job(schedule_id)
    except Exception:
        pass

    schedules = _load_schedules()
    schedules = [s for s in schedules if s["id"] != schedule_id]
    _save_schedules(schedules)
    return True


def list_schedules():
    """List all schedules."""
    return _load_schedules()


def get_scheduled_run_logs(limit: int = 20):
    """Get recent scheduled run logs."""
    from core.paths import data_path
    log_file = data_path("logs", "scheduled_runs.json")
    if not log_file.exists():
        return []
    with open(log_file) as f:
        logs = json.load(f)
    return logs[-limit:]


def enable_cofounder_mode():
    """Enable Cofounder Mode — auto Scout daily at 9am, auto Filter at 9:30am."""
    # Remove existing cofounder schedules
    schedules = _load_schedules()
    schedules = [s for s in schedules if not s.get("id", "").startswith("cofounder_")]

    # Add Scout at 9am
    scout_id = "cofounder_scout_morning"
    schedules.append({
        "id": scout_id,
        "agent_id": "scout",
        "cron": "0 9 * * *",
        "cron_original": "daily",
        "params": {},
        "name": "Cofounder: Scout 09:00",
        "created_at": datetime.now().isoformat(),
        "active": True,
    })

    # Add Filter at 9:30am
    filter_id = "cofounder_filter_morning"
    schedules.append({
        "id": filter_id,
        "agent_id": "filter",
        "cron": "30 9 * * *",
        "cron_original": "daily",
        "params": {},
        "name": "Cofounder: Filter 09:30",
        "created_at": datetime.now().isoformat(),
        "active": True,
    })

    _save_schedules(schedules)

    # Register with running scheduler if started
    if _started:
        for sid, hour, minute, agent_id, name in [
            (scout_id, 9, 0, "scout", "Cofounder: Scout 09:00"),
            (filter_id, 9, 30, "filter", "Cofounder: Filter 09:30"),
        ]:
            try:
                scheduler.remove_job(sid)
            except Exception:
                pass
            scheduler.add_job(
                _run_agent,
                trigger=CronTrigger(minute=minute, hour=hour),
                args=[agent_id],
                id=sid,
                name=name,
                replace_existing=True,
            )

    return {"status": "enabled", "schedules": [scout_id, filter_id]}


def disable_cofounder_mode():
    """Disable Cofounder Mode."""
    schedules = _load_schedules()
    cofounder_ids = [s["id"] for s in schedules if s.get("id", "").startswith("cofounder_")]
    schedules = [s for s in schedules if not s.get("id", "").startswith("cofounder_")]
    _save_schedules(schedules)

    for sid in cofounder_ids:
        try:
            scheduler.remove_job(sid)
        except Exception:
            pass

    return {"status": "disabled"}


def is_cofounder_mode_active():
    """Check if cofounder mode is enabled."""
    schedules = _load_schedules()
    return any(s.get("id", "").startswith("cofounder_") for s in schedules)


def start_scheduler():
    """Start the background scheduler and restore saved schedules.

    No-op when GOAT_DISABLE_SCHEDULER=1 (Vercel serverless can't run a
    persistent background process)."""
    global _started
    if _started:
        return
    if os.getenv("GOAT_DISABLE_SCHEDULER") == "1":
        return

    # Restore saved schedules
    for sched in _load_schedules():
        if not sched.get("active", True):
            continue
        cron = sched["cron"]
        parts = cron.split()
        if len(parts) != 5:
            continue
        try:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
            scheduler.add_job(
                _run_agent,
                trigger=trigger,
                args=[sched["agent_id"]],
                kwargs={"params": sched.get("params", {})},
                id=sched["id"],
                name=sched.get("name", ""),
                replace_existing=True,
            )
        except Exception:
            pass

    # Register the autonomous heartbeat — fires every 2 minutes
    try:
        from core import heartbeat as core_heartbeat
        from apscheduler.triggers.interval import IntervalTrigger
        scheduler.add_job(
            core_heartbeat.tick,
            trigger=IntervalTrigger(minutes=2),
            id="goat_core_heartbeat",
            name="GOAT core heartbeat",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    except Exception as e:
        print(f"[scheduler] heartbeat registration failed: {e}")

    scheduler.start()
    _started = True
