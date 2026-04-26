"""Heartbeat loop — the autonomous brain.

Runs periodically (every N minutes). Each tick:
    1. For every active company, load pending tickets ordered by created_at
    2. Execute pending tickets IN PARALLEL via a thread pool
    3. Respect budgets (execute_in_ticket already handles hard-stop)
    4. For active goals with no open tickets, run the planner and materialize

Paperclip-style: multiple agents work simultaneously, not in a strict queue.
No parent_ticket_id blocking — tickets from the same goal fire concurrently.
"""

import importlib
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from core import store, activity_log, agent_runtime, planner

MAX_PARALLEL = 5             # concurrent tickets per tick (per company)
MAX_COMPANIES_PER_TICK = 10


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
    company_ids = (
        [company_id] if company_id
        else [c["id"] for c in store.list_companies()[:MAX_COMPANIES_PER_TICK]]
    )

    modules_map = _load_agent_modules_map()
    summary = {"companies_checked": 0, "tickets_run": 0, "plans_created": 0}

    for cid in company_ids:
        summary["companies_checked"] += 1

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

    activity_log.append(
        "default" if not company_ids else company_ids[0],
        "heartbeat_tick", actor="system", subject="",
        details=summary,
    )
    return summary


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

    except Exception as e:
        ticket["error"] = f"{type(e).__name__}: {e}"
        ticket["result"] = {"traceback": traceback.format_exc()[-2000:]}
        agent_runtime._transition(ticket, "failed", actor="heartbeat")
