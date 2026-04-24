"""Ticket lifecycle wrapper for agent execution.

Every /api/agent/{id}/run call goes through `execute_in_ticket()` which:
    1. Creates a Ticket (status=pending)
    2. Checks budget — if exceeded, marks paused_budget and returns
    3. Enters cost tracking context + marks in_progress
    4. Calls the agent's run() with its params
    5. Writes result, artifacts, cost breakdown to the ticket
    6. If agent marks result['needs_approval'], ticket → needs_review
       Otherwise ticket → completed (or failed on exception)
    7. Logs every transition to the activity log
    8. Updates budget spend

The existing BaseAgent.run() interface is untouched — this wrapper sits
*around* it. Legacy callers (e.g. the current /api/agent/{id}/run route)
can opt in gradually.
"""

import os
import traceback
from typing import Callable, Optional

from core import activity_log, store, cost_tracker
from core.models import Ticket, now_iso, new_id, to_dict


# Agents whose run produces external side-effects (sending emails, posting to
# social, uploading videos, spending on ad platforms). Tickets for these are
# auto-flagged needs_approval=True — the user must approve in the board before
# side-effects fire. Individual agents may additionally set
# needs_approval via their returned dict for finer control.
MUTATION_AGENTS = {
    "outreach", "social", "admanager", "youtube", "videomaker", "videoproducer",
    "instagramdm",
}


def create_ticket(
    company_id: str,
    agent_id: str,
    title: str = "",
    description: str = "",
    params: Optional[dict] = None,
    goal_id: Optional[str] = None,
    parent_ticket_id: Optional[str] = None,
    needs_approval: bool = False,
) -> dict:
    """Create and persist a pending ticket. Returns the ticket dict."""
    t = to_dict(Ticket(
        id=new_id("t"),
        company_id=company_id,
        title=title or f"{agent_id} run",
        description=description,
        agent_id=agent_id,
        goal_id=goal_id,
        parent_ticket_id=parent_ticket_id,
        params=params or {},
        needs_approval=needs_approval or (agent_id in MUTATION_AGENTS),
    ))
    store.save_ticket(t)
    activity_log.append(
        company_id, "ticket_created", actor="user", subject=t["id"],
        details={"agent_id": agent_id, "title": t["title"]},
    )
    return t


def _transition(ticket: dict, status: str, actor: str = "system", **extra) -> dict:
    """Change ticket status + persist + log."""
    from_status = ticket.get("status")
    ticket["status"] = status
    if status == "in_progress" and not ticket.get("started_at"):
        ticket["started_at"] = now_iso()
    if status in ("completed", "failed", "cancelled") and not ticket.get("completed_at"):
        ticket["completed_at"] = now_iso()
    ticket.update(extra)
    store.save_ticket(ticket)
    activity_log.append(
        ticket["company_id"], f"ticket_{status}", actor=actor, subject=ticket["id"],
        details={"from": from_status, "agent_id": ticket.get("agent_id")},
    )
    return ticket


def execute_in_ticket(
    agent_id: str,
    run_fn: Callable[..., dict],
    params: Optional[dict] = None,
    company_id: Optional[str] = None,
    goal_id: Optional[str] = None,
    title: str = "",
) -> dict:
    """Create a ticket, run the agent, capture cost + artifacts, return the final ticket.

    `run_fn` receives **params and must return a dict (agent report).
    If the report contains key `needs_approval: True`, ticket → needs_review.
    Artifacts can be added by the agent via the `artifacts` key in its report.
    """
    company_id = company_id or store.active_company_id()
    params = params or {}
    ticket = create_ticket(
        company_id=company_id,
        agent_id=agent_id,
        title=title,
        params=params,
        goal_id=goal_id,
    )

    # Budget gate — check before we even start
    if store.is_over_budget(company_id, agent_id):
        budget = store.load_budgets(company_id).get(agent_id, {})
        _transition(
            ticket, "paused_budget",
            error=f"Budget exceeded: ${budget.get('spent_usd', 0):.2f} / ${budget.get('amount_usd', 0):.2f}",
        )
        activity_log.append(
            company_id, "budget_exceeded", actor="system", subject=ticket["id"],
            details={"agent_id": agent_id, "budget": budget},
        )
        return ticket

    _transition(ticket, "in_progress")

    try:
        with cost_tracker.track() as ctx:
            result = run_fn(**params) or {}

        ticket["result"] = {k: v for k, v in result.items() if k not in ("artifacts",)}
        ticket["artifacts"] = result.get("artifacts", [])
        ticket["cost_usd"] = ctx.total_usd()
        ticket["cost_breakdown"] = ctx.breakdown()

        # Update budget spend (if budget exists for this agent)
        if ctx.total_usd() > 0:
            updated = store.add_spend(company_id, agent_id, ctx.total_usd())
            if updated and updated.get("spent_usd", 0) >= updated.get("amount_usd", 0):
                activity_log.append(
                    company_id, "budget_exhausted", actor="system", subject=ticket["id"],
                    details={"agent_id": agent_id, "budget": updated},
                )

        # Approval gate or terminal success
        if ticket.get("needs_approval") or result.get("needs_approval"):
            ticket["needs_approval"] = True
            _transition(ticket, "needs_review")
        else:
            final_status = "completed" if result.get("status") != "error" else "failed"
            if final_status == "failed":
                ticket["error"] = result.get("summary", "Agent reported error status")
            _transition(ticket, final_status)

    except Exception as e:
        ticket["error"] = f"{type(e).__name__}: {e}"
        ticket["result"] = {"traceback": traceback.format_exc()[-2000:]}
        _transition(ticket, "failed")

    return ticket


def approve(company_id: str, ticket_id: str, approver: str = "user") -> Optional[dict]:
    """Mark a needs_review ticket as approved. If the agent attached an
    `approval_action` to its result, execute the corresponding side-effect
    (e.g. activate an Instantly.ai campaign)."""
    ticket = store.load_ticket(company_id, ticket_id)
    if not ticket:
        return None
    if ticket.get("status") != "needs_review":
        return ticket
    ticket["approved_by"] = approver
    ticket["approved_at"] = now_iso()
    _transition(ticket, "approved", actor=approver)
    activity_log.append(
        company_id, "approval_granted", actor=approver, subject=ticket_id,
    )

    action = (ticket.get("result") or {}).get("approval_action")
    if action:
        try:
            _execute_approval_action(company_id, ticket, action)
        except Exception as e:
            activity_log.append(
                company_id, "approval_action_failed", actor="system", subject=ticket_id,
                details={"error": f"{type(e).__name__}: {e}", "action": action},
            )
            ticket["error"] = f"Approval action failed: {e}"
            store.save_ticket(ticket)
    return ticket


def _execute_approval_action(company_id: str, ticket: dict, action: dict) -> None:
    """Dispatch a post-approval side-effect based on action.kind."""
    kind = action.get("kind")
    if kind == "activate_campaign":
        from services.email import activate_campaign, get_api_key
        campaign_id = action.get("campaign_id")
        config = store.load_company(company_id) or {}
        api_key = config.get("api_keys", {}).get("instantly_api_key") or get_api_key()
        if not (campaign_id and api_key):
            return
        ok = activate_campaign(campaign_id, api_key)
        activity_log.append(
            company_id,
            "campaign_activated" if ok else "campaign_activation_failed",
            actor="system", subject=ticket["id"],
            details={"campaign_id": campaign_id},
        )


def reject(company_id: str, ticket_id: str, approver: str = "user", reason: str = "") -> Optional[dict]:
    ticket = store.load_ticket(company_id, ticket_id)
    if not ticket:
        return None
    if ticket.get("status") != "needs_review":
        return ticket
    ticket["error"] = reason or "Rejected by user"
    _transition(ticket, "cancelled", actor=approver)
    activity_log.append(
        company_id, "approval_rejected", actor=approver, subject=ticket_id,
        details={"reason": reason},
    )
    return ticket
