"""goat CLI — command-line interface for the goat control plane.

Two modes:
  • **Local** (default): operates directly on the local data/ store. Runs
    agents in-process. Good for scripted / power-user flows.
  • **Remote** (`--remote URL` or env GOAT_REMOTE): hits a deployed Vercel
    instance via HTTP. State, agents, and CEO chat all run server-side.

Usage:
    python cli.py status
    python cli.py --remote https://goat-bot-tau.vercel.app status
    GOAT_REMOTE=https://goat-bot-tau.vercel.app python cli.py chat "selam"
"""

import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core import store, activity_log, agent_runtime, heartbeat, planner
from core.models import Goal, Company, new_id, to_dict


# ── Remote mode helper ─────────────────────────────────────────────

REMOTE_URL = None  # set by main() if --remote or GOAT_REMOTE present


def _remote() -> bool:
    return bool(REMOTE_URL)


def _http(method: str, path: str, **kwargs):
    import requests
    url = REMOTE_URL.rstrip("/") + path
    r = requests.request(method, url, timeout=60, **kwargs)
    return r

# ANSI colors for prettier output
RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
BLUE = "\033[34m"; DIM = "\033[2m"; BOLD = "\033[1m"; END = "\033[0m"


def _color_status(s: str) -> str:
    return {
        "completed": GREEN, "approved": GREEN,
        "needs_review": YELLOW, "paused_budget": RED, "failed": RED,
        "in_progress": BLUE, "pending": DIM,
    }.get(s, "") + s + END


def cmd_status(args):
    if _remote():
        d = _http("GET", "/api/core/dashboard").json()
        company = d.get("company") or {}
        tickets_total = d.get("totals", {}).get("tickets", 0)
        cost = d.get("totals", {}).get("cost_usd", 0)
        counts = d.get("counts", {})
        goals = d.get("goals", [])
        budgets = d.get("budgets", {})
        print(f"\n{BOLD}== goat status (remote) =={END}")
        print(f"URL: {DIM}{REMOTE_URL}{END}")
        print(f"Active company: {BOLD}{company.get('name','?')}{END}")
        print(f"\n{BOLD}Tickets ({tickets_total} total, ${cost:.4f} spent){END}")
        for s, n in sorted(counts.items()):
            print(f"  {_color_status(s):20} {n}")
        print(f"\n{BOLD}Active goals ({len(goals)}){END}")
        for g in goals[:10]:
            p = g.get("progress", {})
            pct = p.get("percent", 0)
            print(f"  · {g['title']}  {DIM}[{p.get('completed',0)}/{p.get('total',0)} %{pct}]{END}")
        print(f"\n{BOLD}Budgets ({len(budgets)}){END}")
        for aid, b in budgets.items():
            spent = b.get("spent_usd", 0)
            amt = b.get("amount_usd", 1)
            pct = 100 * spent / amt if amt else 0
            col = RED if pct >= 100 else (YELLOW if pct >= 80 else GREEN)
            print(f"  {aid:15} {col}${spent:.2f} / ${amt:.2f}{END}")
        print()
        return
    cid = store.active_company_id()
    company = store.load_company(cid) or {}
    tickets = store.list_tickets(cid, limit=500)
    goals = store.list_goals(cid, status="active")
    budgets = store.load_budgets(cid)

    by_status: dict = {}
    total_cost = 0.0
    for t in tickets:
        by_status.setdefault(t["status"], 0)
        by_status[t["status"]] += 1
        total_cost += float(t.get("cost_usd", 0) or 0)

    print(f"\n{BOLD}== goat status =={END}")
    print(f"Active company: {BOLD}{company.get('name', cid)}{END} ({cid})")
    print(f"Niche: {company.get('niche') or '—'}")
    print(f"Target cities: {', '.join(company.get('target_cities') or []) or '—'}")
    print(f"\n{BOLD}Tickets ({len(tickets)} total, ${total_cost:.4f} spent){END}")
    for s, n in sorted(by_status.items()):
        print(f"  {_color_status(s):20} {n}")
    print(f"\n{BOLD}Active goals ({len(goals)}){END}")
    for g in goals[:10]:
        print(f"  · {g['title']}  {DIM}[{g['id']}]{END}")
    print(f"\n{BOLD}Budgets ({len(budgets)}){END}")
    for aid, b in budgets.items():
        pct = 100 * b.get("spent_usd", 0) / b["amount_usd"] if b.get("amount_usd") else 0
        col = RED if pct >= 100 else (YELLOW if pct >= 80 else GREEN)
        print(f"  {aid:15} {col}${b['spent_usd']:.2f} / ${b['amount_usd']:.2f}{END}  ({pct:.0f}%)")
    print()


def cmd_companies(args):
    companies = store.list_companies()
    active = store.active_company_id()
    print(f"\n{BOLD}Companies{END}")
    for c in companies:
        mark = GREEN + "●" + END if c["id"] == active else DIM + "○" + END
        print(f"  {mark} {c['name']:25} {DIM}{c['id']}{END}")
    print()


def cmd_switch(args):
    store.ensure_company_exists(args.company_id, name=args.name or args.company_id)
    store.set_active_company(args.company_id)
    print(f"Active company → {GREEN}{args.company_id}{END}")


def cmd_goal(args):
    cid = store.active_company_id()
    g = to_dict(Goal(
        id=new_id("g"),
        company_id=cid,
        title=args.title,
        description=args.description or "",
        target_metric=args.metric or "",
    ))
    store.save_goal(g)
    activity_log.append(cid, "goal_created", actor="cli", subject=g["id"],
                        details={"title": g["title"]})
    print(f"Goal created: {GREEN}{g['id']}{END}  {g['title']}")
    if args.plan:
        cmd_plan(argparse.Namespace(goal_id=g["id"]))


def cmd_plan(args):
    cid = store.active_company_id()
    goal = store.load_goal(cid, args.goal_id)
    if not goal:
        print(f"{RED}Goal not found{END}")
        return
    plan = planner.plan_goal(cid, goal)
    tickets = planner.materialize_plan(cid, args.goal_id, plan)
    print(f"\n{BOLD}Plan for:{END} {goal['title']}")
    for t in tickets:
        print(f"  · {t['agent_id']:12} {DIM}{t['id']}{END}  {t['title']}")
    print()


def cmd_run(args):
    """Run an agent immediately (creates and executes ticket)."""
    import importlib, app as app_mod
    spec = app_mod.AGENT_MODULES.get(args.agent_id)
    if not spec:
        print(f"{RED}Unknown agent: {args.agent_id}{END}")
        return
    mod_path, cls_name = spec.rsplit(":", 1)
    agent = getattr(importlib.import_module(mod_path), cls_name)()

    params: dict = {}
    if args.agent_id == "scout":
        params = {"query": args.query or "", "location": args.location or "", "limit": int(args.limit or 50)}
    elif args.agent_id == "auditor":
        params = {"url": args.url or "", "max_leads": int(args.limit or 10)}

    ticket = agent_runtime.execute_in_ticket(
        agent_id=args.agent_id, run_fn=agent.run, params=params, title=args.title or f"{args.agent_id} run",
    )
    print(f"Ticket {ticket['id']} → {_color_status(ticket['status'])}  cost ${ticket.get('cost_usd', 0):.4f}")


def cmd_tickets(args):
    cid = store.active_company_id()
    tickets = store.list_tickets(cid, status=args.status or None, limit=args.limit)
    print(f"\n{BOLD}Tickets ({len(tickets)}){END}")
    for t in tickets[:args.limit]:
        cost = f"${t.get('cost_usd', 0):.3f}" if t.get("cost_usd") else ""
        print(f"  {_color_status(t['status']):25} {t['agent_id']:12} {t.get('title', '')[:50]:50} {DIM}{t['id']} {cost}{END}")
    print()


def cmd_show(args):
    cid = store.active_company_id()
    t = store.load_ticket(cid, args.ticket_id)
    if not t:
        print(f"{RED}Ticket not found{END}")
        return
    print(json.dumps(t, indent=2, ensure_ascii=False))


def cmd_approve(args):
    cid = store.active_company_id()
    t = agent_runtime.approve(cid, args.ticket_id, approver="cli")
    if not t:
        print(f"{RED}Not found{END}")
        return
    print(f"{GREEN}Approved{END} {args.ticket_id}  → {_color_status(t['status'])}")


def cmd_reject(args):
    cid = store.active_company_id()
    t = agent_runtime.reject(cid, args.ticket_id, approver="cli", reason=args.reason or "")
    if not t:
        print(f"{RED}Not found{END}")
        return
    print(f"{YELLOW}Rejected{END} {args.ticket_id}")


def cmd_budget(args):
    cid = store.active_company_id()
    b = store.set_budget(cid, args.agent_id, float(args.amount))
    activity_log.append(cid, "budget_set", actor="cli", subject=f"budget:{args.agent_id}",
                        details={"amount_usd": args.amount})
    print(f"Budget for {GREEN}{args.agent_id}{END} → ${b['amount_usd']:.2f}/month")


def cmd_heartbeat(args):
    summary = heartbeat.tick(company_id=args.company or None)
    print(f"Heartbeat: {json.dumps(summary, indent=2)}")


def cmd_chat(args):
    """Single-shot CEO conversation."""
    if _remote():
        # Stream from /api/core/ceo/chat/stream — print text deltas live
        import requests
        marker = "<<<ACTIONS>>>"
        accumulated = ""
        printed_len = 0
        blocked = False
        with requests.post(REMOTE_URL.rstrip("/") + "/api/core/ceo/chat/stream",
                           json={"message": args.message}, stream=True, timeout=180) as r:
            print(f"\n{BOLD}CEO:{END} ", end="", flush=True)
            buf = ""
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                buf += chunk
                while "\n\n" in buf:
                    part, buf = buf.split("\n\n", 1)
                    line = next((l for l in part.split("\n") if l.startswith("data: ")), None)
                    if not line:
                        continue
                    try:
                        evt = json.loads(line[6:])
                    except Exception:
                        continue
                    k = evt.get("kind")
                    if k == "text_delta":
                        if blocked:
                            continue
                        accumulated += evt.get("text", "")
                        if marker in accumulated:
                            visible = accumulated.split(marker)[0]
                            sys.stdout.write(visible[printed_len:])
                            sys.stdout.flush()
                            blocked = True
                            continue
                        # Hold back partial-marker tails
                        safe = accumulated
                        for n in range(len(marker)-1, 0, -1):
                            if accumulated.endswith(marker[:n]):
                                safe = accumulated[:-n]
                                break
                        if len(safe) > printed_len:
                            sys.stdout.write(safe[printed_len:])
                            sys.stdout.flush()
                            printed_len = len(safe)
                    elif k == "tool_start":
                        print(f"\n{BLUE}[{evt.get('name')} çağrılıyor…]{END}", flush=True)
                    elif k == "tool_end":
                        mark_ok = GREEN+"✓"+END if evt.get("ok") else RED+"✗"+END
                        print(f" {mark_ok}", flush=True)
                    elif k == "action":
                        print(f"\n{DIM}[{evt.get('kind')} {evt.get('id','')[:14]}]{END}", flush=True)
            print()
        return
    import importlib, app as app_mod
    spec = app_mod.AGENT_MODULES.get("ceo")
    mod_path, cls_name = spec.rsplit(":", 1)
    agent = getattr(importlib.import_module(mod_path), cls_name)()
    result = agent.run(message=args.message)
    print(f"\n{BOLD}CEO:{END} {result.get('response', '')}\n")
    if result.get("executed"):
        print(f"{DIM}Executed:{END}")
        for e in result["executed"]:
            mark = GREEN + "✓" + END if e.get("ok") else RED + "✗" + END
            print(f"  {mark} {e.get('kind')}  {e.get('id', e.get('error', ''))}")


def cmd_activity(args):
    cid = store.active_company_id()
    entries = activity_log.read(cid, limit=args.limit)
    for e in entries:
        kind_col = {
            "ticket_completed": GREEN, "ticket_failed": RED,
            "ticket_needs_review": YELLOW, "budget_exceeded": RED,
            "approval_granted": GREEN,
        }.get(e["kind"], "")
        print(f"{DIM}{e['timestamp']}{END}  {kind_col}{e['kind']:25}{END} {e.get('subject', ''):20} {DIM}[{e.get('actor', '')}]{END}")


def main():
    ap = argparse.ArgumentParser(prog="goat", description="goat CLI")
    ap.add_argument("--remote", default=os.getenv("GOAT_REMOTE", ""),
                    help="Drive a deployed instance via HTTP (e.g. https://goat-bot-tau.vercel.app)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show company + tickets + budgets overview").set_defaults(func=cmd_status)
    sub.add_parser("companies", help="List companies").set_defaults(func=cmd_companies)

    p = sub.add_parser("switch", help="Switch active company"); p.add_argument("company_id"); p.add_argument("--name", default=""); p.set_defaults(func=cmd_switch)

    p = sub.add_parser("goal", help="Create a goal"); p.add_argument("title"); p.add_argument("--description", default=""); p.add_argument("--metric", default=""); p.add_argument("--plan", action="store_true"); p.set_defaults(func=cmd_goal)

    p = sub.add_parser("plan", help="Plan tickets for a goal"); p.add_argument("goal_id"); p.set_defaults(func=cmd_plan)

    p = sub.add_parser("run", help="Run an agent immediately"); p.add_argument("agent_id"); p.add_argument("--query", default=""); p.add_argument("--location", default=""); p.add_argument("--url", default=""); p.add_argument("--limit", type=int, default=None); p.add_argument("--title", default=""); p.set_defaults(func=cmd_run)

    p = sub.add_parser("tickets", help="List tickets"); p.add_argument("--status", default=""); p.add_argument("--limit", type=int, default=40); p.set_defaults(func=cmd_tickets)

    p = sub.add_parser("show", help="Show a ticket in detail"); p.add_argument("ticket_id"); p.set_defaults(func=cmd_show)

    p = sub.add_parser("approve", help="Approve a needs_review ticket"); p.add_argument("ticket_id"); p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="Reject a needs_review ticket"); p.add_argument("ticket_id"); p.add_argument("--reason", default=""); p.set_defaults(func=cmd_reject)

    p = sub.add_parser("budget", help="Set monthly USD budget for an agent"); p.add_argument("agent_id"); p.add_argument("amount", type=float); p.set_defaults(func=cmd_budget)

    p = sub.add_parser("heartbeat", help="Run one heartbeat tick"); p.add_argument("--company", default=""); p.set_defaults(func=cmd_heartbeat)

    p = sub.add_parser("chat", help="Talk to the CEO"); p.add_argument("message"); p.set_defaults(func=cmd_chat)

    p = sub.add_parser("activity", help="Show recent activity log"); p.add_argument("--limit", type=int, default=30); p.set_defaults(func=cmd_activity)

    args = ap.parse_args()
    global REMOTE_URL
    if args.remote:
        REMOTE_URL = args.remote.rstrip("/")
    args.func(args)


if __name__ == "__main__":
    main()
