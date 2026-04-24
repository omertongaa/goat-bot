"""Scheduler Service — Automated agent runs via APScheduler.

Runs agents on configurable schedules (daily scout, auto-filter, etc).
No external services needed.
"""

import json
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

BASE_DIR = Path(__file__).parent.parent
SCHEDULE_FILE = BASE_DIR / "data" / "config" / "schedules.json"

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
        log_dir = BASE_DIR / "data" / "logs"
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
    log_file = BASE_DIR / "data" / "logs" / "scheduled_runs.json"
    if not log_file.exists():
        return []
    with open(log_file) as f:
        logs = json.load(f)
    return logs[-limit:]


def start_scheduler():
    """Start the background scheduler and restore saved schedules."""
    global _started
    if _started:
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
