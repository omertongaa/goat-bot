"""Heartbeat loop — the autonomous brain.

Runs periodically (every N minutes). Each tick:
    0. For every active company, retry failed tickets (up to MAX_RETRIES)
    1. For active goals with no open tickets, run the planner and materialize
    2. Execute pending tickets IN PARALLEL via a thread pool
    3. Respect budgets (execute_in_ticket already handles hard-stop)
    4. After execution, mark goals whose tickets are all terminal as completed

Paperclip-style: multiple agents work simultaneously, not in a strict queue.
No parent_ticket_id blocking — tickets from the same goal fire concurrently.
"""

import importlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from core import store, activity_log, agent_runtime, planner

MAX_PARALLEL = 5             # concurrent tickets per tick (per company)
MAX_COMPANIES_PER_TICK = 10
MAX_RETRIES = 2              # failed ticket → up to 2 auto-retries
TERMINAL_STATES = {"completed", "failed", "cancelled", "paused_budget"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_agent_modules_map() -> dict:
    """Lazy import of app.AGENT_MODULES to avoid circular deps."""
    try:
        app_mod = importlib.import_module("app")
        return getattr(app_mod, "AGENT_MODULES", {}) or {}
    except Exception:
        return {}


def _get_agent_instance(agent_id: str, modules_map: dict):
    """Instantiate an agent by id using the app-level module registry."""
    spec = modules_map.get(agent_id)
    if not spec:
        return None
    module_path, class_name = spec.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def _resolve_run_params(agent_id: str, params: dict) -> dict:
    """Match stored params to the known agent signature."""
    p = params or {}
    if agent_id == "scout":
        return {"query": p.get("query", ""), "location": p.get("location", ""), "limit": int(p.get("limit", 50) or 50)}
    if agent_id == "auditor":
        return {"url": p.get("url", ""), "max_leads": int(p.get("max_leads", 10) or 10)}
    if agent_id == "sitebuilder":
        return {"site_type": p.get("site_type", "agency"), "lead_index": int(p.get("lead_index", 0) or 0), "manual_data": p.get("manual_data")}
    return {}


def tick(company_id: Optional[str] = None) -> dict:
    """Run one heartbeat. If company_id is None, iterates all companies."""
    import os as _os
    company_ids = (
        [company_id] if company_id
        else [c["id"] for c in store.list_companies()[:MAX_COMPANIES_PER_TICK]]
    )

    modules_map = _load_agent_modules_map()
    summary = {
        "companies_checked": 0, "tickets_run": 0, "plans_created": 0,
        "retries": 0, "goals_completed": 0,
    }

    for cid in company_ids:
        summary["companies_checked"] += 1

        # Inject company API keys into env so agents can reach Apify, fal.ai, etc.
        company = store.load_company(cid) or {}
        for src, dst in [
            ("apify_token", "APIFY_TOKEN"), ("fal_key", "FAL_KEY"),
            ("instantly_api_key", "INSTANTLY_API_KEY"),
            ("anthropic_api_key", "ANTHROPIC_API_KEY"),
            ("composio_api_key", "COMPOSIO_API_KEY"),
            ("scraper_actor", "SCRAPER_ACTOR"),
            ("email_finder_providers", "EMAIL_FINDER_PROVIDERS"),
        ]:
            v = (company.get("api_keys") or {}).get(src) or (company.get("settings") or {}).get(src)
            if v:
                _os.environ[dst] = v

        # 0) Retry failed tickets (auto, up to MAX_RETRIES)
        summary["retries"] += _retry_failed_tickets(cid)

        # 1) Plan any goal that has no tickets yet
        goals = store.list_goals(cid, status="active")
        for goal in goals:
            existing = store.list_tickets(cid, goal_id=goal["id"])
            if existing:
                continue
            try:
                plan = planner.plan_goal(cid, goal)
                if plan:
                    planner.materialize_plan(cid, goal["id"], plan)
                    summary["plans_created"] += 1
            except Exception as e:
                activity_log.append(
                    cid, "plan_failed", actor="heartbeat", subject=goal["id"],
                    details={"error": f"{type(e).__name__}: {e}"},
                )

        # 2) Execute pending tickets IN PARALLEL
        pending = store.list_tickets(cid, status="pending")
        pending.sort(key=lambda t: t.get("created_at", ""))
        runnable = []
        for t in pending[:MAX_PARALLEL]:
            agent = _get_agent_instance(t["agent_id"], modules_map)
            if not agent:
                activity_log.append(
                    cid, "ticket_missing_agent", actor="heartbeat", subject=t["id"],
                    details={"agent_id": t["agent_id"]},
                )
                continue
            run_params = _resolve_run_params(t["agent_id"], t.get("params", {}))
            runnable.append((t, agent, run_params))

        if runnable:
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
                futures = [pool.submit(_execute_existing_ticket, cid, t, agent, p)
                           for (t, agent, p) in runnable]
                for f in futures:
                    try:
                        f.result(timeout=900)  # 15 min safety cap per ticket
                        summary["tickets_run"] += 1
                    except Exception:
                        pass

        # 3) Goal completion check — mark goals whose tickets all reached terminal
        summary["goals_completed"] += _check_goal_completion(cid)

    activity_log.append(
        "default" if not company_ids else company_ids[0],
        "heartbeat_tick", actor="system", subject="",
        details=summary,
    )
    return summary


def _retry_failed_tickets(cid: str) -> int:
    """Reset failed tickets back to pending, up to MAX_RETRIES per ticket.
    Skip tickets that needed approval (those failed for human reasons, not transient).
    Returns number of tickets requeued."""
    failed = store.list_tickets(cid, status="failed")
    requeued = 0
    for t in failed:
        if t.get("retry_count", 0) >= MAX_RETRIES:
            continue
        if t.get("needs_approval"):
            # Approval-gated failures aren't transient — skip auto-retry
            continue
        t["retry_count"] = t.get("retry_count", 0) + 1
        t["last_retry_at"] = _utcnow_iso()
        # Clear prior error so next run starts fresh
        t.pop("error", None)
        agent_runtime._transition(t, "pending", actor="heartbeat-retry")
        activity_log.append(
            cid, "ticket_retry", actor="heartbeat", subject=t["id"],
            details={"attempt": t["retry_count"], "agent_id": t.get("agent_id")},
        )
        requeued += 1
    return requeued


def _check_goal_completion(cid: str) -> int:
    """For each active goal, if all its tickets are in a terminal state,
    promote the goal to completed (or completed_with_errors). Returns count."""
    completed = 0
    for goal in store.list_goals(cid, status="active"):
        tickets = store.list_tickets(cid, goal_id=goal["id"])
        if not tickets:
            continue
        if not all(t.get("status") in TERMINAL_STATES for t in tickets):
            continue
        any_failed = any(t.get("status") == "failed" for t in tickets)
        completed_n = sum(1 for t in tickets if t.get("status") == "completed")
        failed_n = sum(1 for t in tickets if t.get("status") == "failed")
        paused_n = sum(1 for t in tickets if t.get("status") == "paused_budget")
        cancelled_n = sum(1 for t in tickets if t.get("status") == "cancelled")

        goal["status"] = "completed_with_errors" if any_failed else "completed"
        goal["completed_at"] = _utcnow_iso()
        goal["completion_stats"] = {
            "total": len(tickets), "completed": completed_n,
            "failed": failed_n, "paused_budget": paused_n, "cancelled": cancelled_n,
        }
        store.save_goal(goal)
        activity_log.append(
            cid, "goal_completed", actor="heartbeat", subject=goal["id"],
            details={"status": goal["status"], **goal["completion_stats"]},
        )
        completed += 1
    return completed


def _execute_existing_ticket(company_id: str, ticket: dict, agent, run_params: dict) -> None:
    """Like execute_in_ticket but against an already-created pending ticket.
    Mirrors the logic in agent_runtime.execute_in_ticket without creating a new one.
    """
    from core import cost_tracker
    import traceback

    if store.is_over_budget(company_id, ticket["agent_id"]):
        budget = store.load_budgets(company_id).get(ticket["agent_id"], {})
        agent_runtime._transition(
            ticket, "paused_budget",
            error=f"Budget exceeded: ${budget.get('spent_usd', 0):.2f} / ${budget.get('amount_usd', 0):.2f}",
        )
        activity_log.append(
            company_id, "budget_exceeded", actor="heartbeat", subject=ticket["id"],
            details={"agent_id": ticket["agent_id"]},
        )
        return

    agent_runtime._transition(ticket, "in_progress", actor="heartbeat")

    try:
        with cost_tracker.track() as ctx:
            result = agent.run(**run_params) or {}

        ticket["result"] = {k: v for k, v in result.items() if k != "artifacts"}
        ticket["artifacts"] = result.get("artifacts", [])
        ticket["cost_usd"] = ctx.total_usd()
        ticket["cost_breakdown"] = ctx.breakdown()
        if hasattr(agent, "run_log"):
            ticket["run_log"] = list(agent.run_log)

        if ctx.total_usd() > 0:
            store.add_spend(company_id, ticket["agent_id"], ctx.total_usd())

        agent_says_review = bool(result.get("needs_approval"))
        require_review = agent_runtime._should_require_approval(
            company_id, ticket["agent_id"], agent_says_review
        ) and (ticket.get("needs_approval") or agent_says_review)
        if require_review:
            ticket["needs_approval"] = True
            agent_runtime._transition(ticket, "needs_review", actor="heartbeat")
        else:
            ticket["needs_approval"] = False
            status = "completed" if result.get("status") != "error" else "failed"
            if status == "failed":
                ticket["error"] = result.get("summary", "Agent reported error")
            agent_runtime._transition(ticket, status, actor="heartbeat")
            action = (ticket.get("result") or {}).get("approval_action")
            if action and status == "completed":
                try:
                    agent_runtime._execute_approval_action(company_id, ticket, action)
                except Exception:
                    pass
            if status == "completed":
                agent_runtime._extract_facts_async(company_id, ticket)

    except Exception as e:
        ticket["error"] = f"{type(e).__name__}: {e}"
        ticket["result"] = {"traceback": traceback.format_exc()[-2000:]}
        agent_runtime._transition(ticket, "failed", actor="heartbeat")
