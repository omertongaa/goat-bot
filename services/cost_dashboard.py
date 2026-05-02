"""Cost dashboard — aggregate ticket cost_breakdowns into daily/monthly totals.

Reads tickets from store, sums by `cost_breakdown` kind across time windows,
flags spend over user-configurable thresholds, and exposes panel-ready JSON
for the board UI.

No DB — works on top of existing ticket records.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from core import store
from core.cost_tracker import DEFAULT_PRICES


# Default monthly threshold per kind (USD). User overrides via company.settings.cost_alerts.
DEFAULT_ALERTS = {
    "daily_total": 5.0,
    "monthly_total": 75.0,
}


def _ticket_ts(t: dict) -> Optional[datetime]:
    raw = t.get("completed_at") or t.get("created_at") or ""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def summary(company_id: str, days: int = 30) -> dict:
    """Return totals by kind, by agent, by day, and over the rolling window."""
    tickets = store.list_tickets(company_id, limit=2000)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=days)

    by_kind: dict = defaultdict(float)
    by_agent: dict = defaultdict(float)
    by_day: dict = defaultdict(float)
    total = 0.0
    today_total = 0.0
    month_total = 0.0
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for t in tickets:
        ts = _ticket_ts(t)
        if not ts or ts < window_start:
            continue
        breakdown = t.get("cost_breakdown") or {}
        cost = float(t.get("cost_usd") or 0.0)
        agent_id = t.get("agent_id", "?")
        day_key = ts.date().isoformat()

        total += cost
        by_agent[agent_id] += cost
        by_day[day_key] += cost
        if ts >= today_start:
            today_total += cost
        if ts >= month_start:
            month_total += cost
        for k, v in breakdown.items():
            by_kind[k] += float(v or 0.0)

    settings = (store.load_company(company_id) or {}).get("settings", {}) or {}
    alerts_cfg = {**DEFAULT_ALERTS, **(settings.get("cost_alerts") or {})}
    alerts: list = []
    if today_total > alerts_cfg["daily_total"]:
        alerts.append({"level": "warn", "msg": f"Bugün ${today_total:.2f} harcadın (limit ${alerts_cfg['daily_total']:.2f})"})
    if month_total > alerts_cfg["monthly_total"]:
        alerts.append({"level": "warn", "msg": f"Bu ay ${month_total:.2f} harcadın (limit ${alerts_cfg['monthly_total']:.2f})"})

    return {
        "window_days": days,
        "total_usd": round(total, 4),
        "today_usd": round(today_total, 4),
        "month_usd": round(month_total, 4),
        "by_kind": {k: round(v, 4) for k, v in sorted(by_kind.items(), key=lambda x: -x[1])},
        "by_agent": {k: round(v, 4) for k, v in sorted(by_agent.items(), key=lambda x: -x[1])},
        "by_day": {k: round(v, 4) for k, v in sorted(by_day.items())},
        "alerts": alerts,
        "alert_thresholds": alerts_cfg,
        "known_kinds": sorted(DEFAULT_PRICES.keys()),
    }


def set_alerts(company_id: str, daily: Optional[float] = None, monthly: Optional[float] = None) -> dict:
    """Update cost alert thresholds for a company."""
    company = store.load_company(company_id) or {}
    settings = company.get("settings") or {}
    alerts = settings.get("cost_alerts") or {}
    if daily is not None:
        alerts["daily_total"] = float(daily)
    if monthly is not None:
        alerts["monthly_total"] = float(monthly)
    settings["cost_alerts"] = alerts
    company["settings"] = settings
    store.save_company(company)
    return alerts
