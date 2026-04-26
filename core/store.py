"""Company-scoped persistence with two backends.

Backend selection (lazy via env):
    - If UPSTASH_REDIS_REST_URL+TOKEN are set → durable Redis KV (Vercel safe)
    - Otherwise → JSON files under GOAT_DATA_DIR (default ./data)

Local dev hits files; Vercel hits Redis. Same interface either way.

KV layout (when active):
    goat:active:{?}                  → "company_id"
    goat:companies                   → SET of company_ids
    goat:company:{cid}               → company profile JSON
    goat:tickets:{cid}               → SET of ticket_ids (for listing)
    goat:ticket:{cid}:{tid}          → ticket JSON
    goat:goals:{cid}                 → SET of goal_ids
    goat:goal:{cid}:{gid}            → goal JSON
    goat:budgets:{cid}               → budgets dict {agent_id: budget}
    goat:activity:{cid}              → LIST of activity entries (appended)
"""

import json
import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
# Allow override via GOAT_DATA_DIR (e.g. /tmp on Vercel, S3-mount, custom path)
DATA_ROOT = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))
COMPANIES_DIR = DATA_ROOT / "companies"
ACTIVE_COMPANY_FILE = DATA_ROOT / "active_company.json"

DEFAULT_COMPANY_ID = "default"


def _kv() -> bool:
    """True when Upstash KV is configured and should be used."""
    from core import kv as _kv_mod
    return _kv_mod.is_enabled()


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, data) -> None:
    """Atomic write via temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ── Active company ─────────────────────────────────────────────────

def active_company_id() -> str:
    if _kv():
        from core import kv as _kv_mod
        cid = _kv_mod.get_json("active_company")
        if isinstance(cid, str):
            return cid
        if isinstance(cid, dict):
            return cid.get("id", DEFAULT_COMPANY_ID)
        return DEFAULT_COMPANY_ID
    data = _read_json(ACTIVE_COMPANY_FILE, {})
    return (data or {}).get("id", DEFAULT_COMPANY_ID)


def set_active_company(company_id: str) -> None:
    if _kv():
        from core import kv as _kv_mod
        _kv_mod.set_json("active_company", company_id)
        return
    _write_json(ACTIVE_COMPANY_FILE, {"id": company_id})


# ── Company paths ──────────────────────────────────────────────────

def company_dir(company_id: str) -> Path:
    return _ensure(COMPANIES_DIR / company_id)


def tickets_dir(company_id: str) -> Path:
    return _ensure(company_dir(company_id) / "tickets")


def goals_dir(company_id: str) -> Path:
    return _ensure(company_dir(company_id) / "goals")


def artifacts_dir(company_id: str) -> Path:
    return _ensure(company_dir(company_id) / "artifacts")


# ── Companies ──────────────────────────────────────────────────────

def list_companies() -> list:
    if _kv():
        from core import kv as _kv_mod
        ids = _kv_mod.smembers("companies")
        if not ids:
            return []
        return [c for c in _kv_mod.mget_json([f"company:{i}" for i in ids]) if c]
    if not COMPANIES_DIR.exists():
        return []
    out = []
    for d in sorted(COMPANIES_DIR.iterdir()):
        if not d.is_dir():
            continue
        profile = _read_json(d / "profile.json")
        if profile:
            out.append(profile)
    return out


def load_company(company_id: str) -> Optional[dict]:
    if _kv():
        from core import kv as _kv_mod
        return _kv_mod.get_json(f"company:{company_id}")
    return _read_json(company_dir(company_id) / "profile.json")


def save_company(company: dict) -> None:
    if _kv():
        from core import kv as _kv_mod
        _kv_mod.set_json(f"company:{company['id']}", company)
        _kv_mod.sadd("companies", company["id"])
        return
    _write_json(company_dir(company["id"]) / "profile.json", company)


def ensure_company_exists(company_id: str, name: str = "", profile_extra: Optional[dict] = None) -> dict:
    """Get-or-create a company profile."""
    existing = load_company(company_id)
    if existing:
        return existing
    from core.models import Company, to_dict
    company = Company(id=company_id, name=name or company_id.title())
    data = to_dict(company)
    if profile_extra:
        data.update(profile_extra)
    save_company(data)
    return data


# ── Tickets ────────────────────────────────────────────────────────

def ticket_path(company_id: str, ticket_id: str) -> Path:
    return tickets_dir(company_id) / f"{ticket_id}.json"


def save_ticket(ticket: dict) -> None:
    if _kv():
        from core import kv as _kv_mod
        cid = ticket["company_id"]; tid = ticket["id"]
        _kv_mod.set_json(f"ticket:{cid}:{tid}", ticket)
        _kv_mod.sadd(f"tickets:{cid}", tid)
        return
    _write_json(ticket_path(ticket["company_id"], ticket["id"]), ticket)


def load_ticket(company_id: str, ticket_id: str) -> Optional[dict]:
    if _kv():
        from core import kv as _kv_mod
        return _kv_mod.get_json(f"ticket:{company_id}:{ticket_id}")
    return _read_json(ticket_path(company_id, ticket_id))


def list_tickets(
    company_id: str,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    goal_id: Optional[str] = None,
    limit: int = 500,
) -> list:
    if _kv():
        from core import kv as _kv_mod
        ids = _kv_mod.smembers(f"tickets:{company_id}")
        if not ids:
            return []
        items = [t for t in _kv_mod.mget_json([f"ticket:{company_id}:{i}" for i in ids]) if t]
    else:
        tdir = tickets_dir(company_id)
        items = []
        for f in tdir.glob("*.json"):
            t = _read_json(f)
            if t:
                items.append(t)

    out = []
    for t in items:
        if status and t.get("status") != status:
            continue
        if agent_id and t.get("agent_id") != agent_id:
            continue
        if goal_id and t.get("goal_id") != goal_id:
            continue
        out.append(t)
    out.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return out[:limit]


# ── Goals ──────────────────────────────────────────────────────────

def goal_path(company_id: str, goal_id: str) -> Path:
    return goals_dir(company_id) / f"{goal_id}.json"


def save_goal(goal: dict) -> None:
    if _kv():
        from core import kv as _kv_mod
        cid = goal["company_id"]; gid = goal["id"]
        _kv_mod.set_json(f"goal:{cid}:{gid}", goal)
        _kv_mod.sadd(f"goals:{cid}", gid)
        return
    _write_json(goal_path(goal["company_id"], goal["id"]), goal)


def load_goal(company_id: str, goal_id: str) -> Optional[dict]:
    if _kv():
        from core import kv as _kv_mod
        return _kv_mod.get_json(f"goal:{company_id}:{goal_id}")
    return _read_json(goal_path(company_id, goal_id))


def list_goals(company_id: str, status: Optional[str] = None) -> list:
    if _kv():
        from core import kv as _kv_mod
        ids = _kv_mod.smembers(f"goals:{company_id}")
        items = [g for g in _kv_mod.mget_json([f"goal:{company_id}:{i}" for i in ids]) if g] if ids else []
    else:
        gdir = goals_dir(company_id)
        items = []
        for f in gdir.glob("*.json"):
            g = _read_json(f)
            if g:
                items.append(g)
    out = []
    for g in items:
        if status and g.get("status") != status:
            continue
        out.append(g)
    out.sort(key=lambda g: g.get("created_at", ""), reverse=True)
    return out


# ── Budgets ────────────────────────────────────────────────────────

def budgets_path(company_id: str) -> Path:
    return company_dir(company_id) / "budgets.json"


def load_budgets(company_id: str) -> dict:
    """Returns {agent_id: Budget dict}. Empty if no budgets set."""
    if _kv():
        from core import kv as _kv_mod
        return _kv_mod.get_json(f"budgets:{company_id}", {}) or {}
    return _read_json(budgets_path(company_id), {}) or {}


def save_budgets(company_id: str, budgets: dict) -> None:
    if _kv():
        from core import kv as _kv_mod
        _kv_mod.set_json(f"budgets:{company_id}", budgets)
        return
    _write_json(budgets_path(company_id), budgets)


def set_budget(company_id: str, agent_id: str, amount_usd: float) -> dict:
    """Create or update an agent's monthly budget."""
    from core.models import Budget, to_dict
    budgets = load_budgets(company_id)
    existing = budgets.get(agent_id)
    if existing:
        existing["amount_usd"] = float(amount_usd)
        budgets[agent_id] = existing
    else:
        budgets[agent_id] = to_dict(
            Budget(company_id=company_id, agent_id=agent_id, amount_usd=float(amount_usd))
        )
    save_budgets(company_id, budgets)
    return budgets[agent_id]


def add_spend(company_id: str, agent_id: str, usd: float) -> Optional[dict]:
    """Record a cost event against the agent's budget. Returns updated budget or None
    if no budget is configured (no-op)."""
    if usd <= 0:
        return None
    budgets = load_budgets(company_id)
    if agent_id not in budgets:
        return None
    budgets[agent_id]["spent_usd"] = round(budgets[agent_id].get("spent_usd", 0.0) + usd, 4)
    save_budgets(company_id, budgets)
    return budgets[agent_id]


def is_over_budget(company_id: str, agent_id: str) -> bool:
    budgets = load_budgets(company_id)
    b = budgets.get(agent_id)
    if not b:
        return False
    return b.get("spent_usd", 0.0) >= b.get("amount_usd", 0.0)


# ── Legacy migration ───────────────────────────────────────────────

def migrate_legacy_profile_if_needed() -> Optional[dict]:
    """If data/companies/ is empty but data/config/user_profile.json exists,
    materialize a 'default' company from the legacy profile. Non-destructive —
    leaves legacy files in place."""
    default_profile_path = company_dir(DEFAULT_COMPANY_ID) / "profile.json"
    if default_profile_path.exists():
        return load_company(DEFAULT_COMPANY_ID)

    legacy = _read_json(DATA_ROOT / "config" / "user_profile.json")
    if legacy is None:
        # Fresh install — create empty default
        from core.models import Company, to_dict
        company = to_dict(Company(id=DEFAULT_COMPANY_ID, name="goat"))
        save_company(company)
        return company

    from core.models import Company, to_dict
    company = Company(
        id=DEFAULT_COMPANY_ID,
        name=legacy.get("agency_name") or legacy.get("name") or "goat",
        owner_name=legacy.get("owner_name", ""),
        niche=legacy.get("niche", ""),
        target_cities=legacy.get("target_cities", []) or [],
        target_industries=legacy.get("target_industries", []) or [],
        api_keys={
            k: legacy.get(k, "")
            for k in (
                "apify_token", "fal_key", "instantly_api_key",
                "leadmagic_api_key", "generect_api_key",
                "emailapi_key", "emailapi_domain",
            )
            if legacy.get(k)
        },
        settings={
            k: legacy.get(k)
            for k in ("scraper_actor", "email_finder_providers")
            if legacy.get(k)
        },
    )
    data = to_dict(company)
    save_company(data)
    return data
