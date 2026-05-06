"""Company template loader/importer.

Templates live in data/company_templates/*.goat.json. import_template()
creates a fresh company, applies settings, seeds budgets, and creates
starter goals so the user lands on a board that already has tickets.
"""

import json
from pathlib import Path
from typing import Optional

from core import activity_log, store
from core.models import Company, Goal, new_id, now_iso, to_dict


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data" / "company_templates"


def list_templates() -> list:
    if not TEMPLATES_DIR.exists():
        return []
    out = []
    for f in sorted(TEMPLATES_DIR.glob("*.goat.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": data.get("id") or f.stem,
                "label": data.get("label", ""),
                "description": data.get("description", ""),
                "industries": (data.get("company") or {}).get("target_industries", []),
                "cities": (data.get("company") or {}).get("target_cities", []),
            })
        except Exception:
            continue
    return out


def load_template(template_id: str) -> Optional[dict]:
    path = TEMPLATES_DIR / f"{template_id}.goat.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def import_template(template_id: str, company_id: Optional[str] = None) -> dict:
    """Materialize a template into a new company. Returns {company_id, goals}."""
    tmpl = load_template(template_id)
    if not tmpl:
        return {"error": "template not found", "template_id": template_id}

    cdef = tmpl.get("company") or {}
    cid = company_id or new_id("c")[:10]
    company = to_dict(Company(
        id=cid,
        name=cdef.get("name") or template_id.title(),
        owner_name=cdef.get("owner_name", ""),
        niche=cdef.get("niche", ""),
        target_cities=list(cdef.get("target_cities") or []),
        target_industries=list(cdef.get("target_industries") or []),
    ))
    company["api_keys"] = dict(cdef.get("api_keys") or {})
    company["settings"] = dict(cdef.get("settings") or {})
    company["from_template"] = template_id
    store.save_company(company)

    budgets = {a: {"agent_id": a, "monthly_usd": float(v), "spent_usd": 0.0}
               for a, v in (tmpl.get("starter_budgets") or {}).items()}
    if budgets:
        store.save_budgets(cid, budgets)

    goals = []
    for g in (tmpl.get("starter_goals") or []):
        goal = to_dict(Goal(
            id=new_id("g"),
            company_id=cid,
            title=g.get("title", "Goal"),
            description=g.get("description", ""),
        ))
        store.save_goal(goal)
        goals.append({"id": goal["id"], "title": goal["title"]})

    activity_log.append(
        cid, "company_template_imported", actor="system",
        subject=cid, details={"template": template_id, "goals": len(goals)},
    )
    return {
        "company_id": cid,
        "company_name": company["name"],
        "template": template_id,
        "goals": goals,
        "budgets": list(budgets.keys()),
    }
