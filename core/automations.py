"""n8n-flavored automation runtime — minimal native executor.

Reads n8n workflow JSON (export format), walks node graph in
connection order, runs supported nodes natively in Python. Unsupported
nodes log a "skipped" event but the run keeps going.

Supported node types (n8n-nodes-base.*):
    webhook         → triggered by /api/automations/{id}/trigger
    scheduleTrigger → registered with services/scheduler.py
    set             → field assignment, expression eval ({{ ... }})
    code            → JS not run; falls back to passthrough or LLM-generated Python (off by default)
    if              → comparator (equal/notEqual/greater/contains)
    httpRequest     → requests.request
    telegram        → services/telegram_bot.push_text
    gmail           → SMTP fallback if SMTP_HOST set, else skipped
    slack           → webhook URL post if SLACK_WEBHOOK_URL set
    googleSheets    → skipped (logs warning)
    notion          → skipped (logs warning)
    postgres        → skipped (logs warning)
    @langchain.openAi → llm.complete (provider-agnostic)
    merge           → input merger (passthrough)

Why "native" instead of running n8n? — One process, one ticket model,
one cost dashboard. User runs Docker `goat-bot` once; doesn't have to
also manage an n8n server.
"""

import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core import store


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data" / "automations" / "templates"
INSTALLED_DIR_NAME = "automations"  # under each company dir


# ─────────────────────────── Storage ───────────────────────────

def _installed_dir(company_id: str) -> Path:
    p = store.company_dir(company_id) / INSTALLED_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_templates() -> list:
    if not TEMPLATES_DIR.exists():
        return []
    out = []
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            nodes = data.get("nodes", [])
            types = sorted({n.get("type", "").replace("n8n-nodes-base.", "") for n in nodes})
            out.append({
                "id": f.stem,
                "name": data.get("name", f.stem),
                "node_count": len(nodes),
                "node_types": types,
                "trigger": _detect_trigger(nodes),
                "supported_pct": _support_pct(types),
            })
        except Exception:
            continue
    return out


def load_template(template_id: str) -> Optional[dict]:
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_installed(company_id: str) -> list:
    d = _installed_dir(company_id)
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": data.get("id"),
                "template_id": data.get("template_id"),
                "name": data.get("name"),
                "active": data.get("active", True),
                "trigger": data.get("trigger"),
                "runs": data.get("runs", []),
                "installed_at": data.get("installed_at"),
            })
        except Exception:
            continue
    return out


def install_template(company_id: str, template_id: str) -> dict:
    tmpl = load_template(template_id)
    if not tmpl:
        return {"error": "template not found"}
    nodes = tmpl.get("nodes", [])
    record = {
        "id": f"a_{template_id}_{int(time.time())}",
        "template_id": template_id,
        "name": tmpl.get("name", template_id),
        "active": True,
        "trigger": _detect_trigger(nodes),
        "workflow": tmpl,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }
    path = _installed_dir(company_id) / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def delete_installed(company_id: str, automation_id: str) -> bool:
    path = _installed_dir(company_id) / f"{automation_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def get_installed(company_id: str, automation_id: str) -> Optional[dict]:
    path = _installed_dir(company_id) / f"{automation_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─────────────────────────── Execution ───────────────────────────

def trigger(company_id: str, automation_id: str, payload: Optional[dict] = None) -> dict:
    """Run an installed automation. Returns {ok, log[], output, error?}."""
    record = get_installed(company_id, automation_id)
    if not record:
        return {"ok": False, "error": "not found"}
    workflow = record.get("workflow") or {}
    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", {})
    if not record.get("active", True):
        return {"ok": False, "error": "automation disabled"}

    nodes_by_name = {n.get("name"): n for n in nodes}
    start = _start_node(nodes, payload is not None)
    if not start:
        return {"ok": False, "error": "no executable trigger"}

    log: list = []
    ctx: dict = {
        "trigger_payload": payload or {},
        "node_outputs": {start.get("name"): {"json": {"body": payload or {}}}},
    }

    visited = set()
    queue = [start.get("name")]
    while queue:
        name = queue.pop(0)
        if name in visited:
            continue
        visited.add(name)
        node = nodes_by_name.get(name)
        if not node:
            continue
        try:
            output = _run_node(node, ctx, log, company_id)
        except Exception as e:
            log.append({"node": name, "status": "error", "error": f"{type(e).__name__}: {e}"})
            output = None

        if output is not None:
            ctx["node_outputs"][name] = output

        # Walk to next nodes via "main" connection
        nexts = (connections.get(name) or {}).get("main") or []
        for branch in nexts:
            for c in branch:
                next_name = c.get("node")
                if next_name and next_name not in visited:
                    queue.append(next_name)

    # Persist run
    run_record = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "payload_keys": list((payload or {}).keys()),
        "log": log,
        "ok": all(e.get("status") != "error" for e in log) if log else True,
    }
    record["runs"] = (record.get("runs") or [])[-19:] + [run_record]
    path = _installed_dir(company_id) / f"{automation_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": run_record["ok"], "log": log, "output": ctx["node_outputs"]}


# ─────────────────────────── Node executors ───────────────────────────

def _run_node(node: dict, ctx: dict, log: list, company_id: str) -> Optional[dict]:
    """Returns the node's output dict or None on no-op."""
    raw_type = node.get("type", "")
    ntype = raw_type.replace("n8n-nodes-base.", "").split(".")[-1]
    name = node.get("name", "")
    params = node.get("parameters") or {}

    if ntype in ("webhook", "scheduleTrigger", "manualTrigger"):
        log.append({"node": name, "status": "ok", "kind": ntype, "msg": "trigger pass-through"})
        return ctx["node_outputs"].get(name) or {"json": ctx["trigger_payload"]}

    if ntype == "set":
        out = _exec_set(params, ctx)
        log.append({"node": name, "status": "ok", "kind": "set", "fields": list(out.keys())})
        return {"json": out}

    if ntype == "if":
        passed = _exec_if(params, ctx)
        log.append({"node": name, "status": "ok", "kind": "if", "branch": "true" if passed else "false"})
        return {"json": ctx["trigger_payload"], "branch": passed}

    if ntype == "httpRequest":
        result = _exec_http(params, ctx)
        log.append({"node": name, "status": "ok" if result.get("ok") else "error",
                    "kind": "http", "status_code": result.get("status_code"), "url": result.get("url")})
        return {"json": result}

    if ntype == "telegram":
        from services import telegram_bot
        text = _resolve(params.get("text") or params.get("message") or "(boş)", ctx)
        res = telegram_bot.push_text(company_id, str(text))
        log.append({"node": name, "status": "ok" if res.get("ok") else "skipped", "kind": "telegram"})
        return {"json": res}

    if ntype in ("gmail", "emailSend"):
        out = _exec_gmail(params, ctx)
        log.append({"node": name, "status": out.get("status", "skipped"), "kind": "gmail",
                    "msg": out.get("msg", "")})
        return {"json": out}

    if ntype == "slack":
        out = _exec_slack(params, ctx)
        log.append({"node": name, "status": out.get("status", "skipped"), "kind": "slack"})
        return {"json": out}

    if "openAi" in raw_type or "openai" in raw_type.lower():
        out = _exec_llm(params, ctx)
        log.append({"node": name, "status": "ok" if out.get("text") else "skipped", "kind": "llm",
                    "provider": out.get("provider")})
        return {"json": out}

    if ntype == "code":
        log.append({"node": name, "status": "skipped", "kind": "code", "msg": "JS not executed; passthrough"})
        return {"json": ctx["trigger_payload"]}

    if ntype == "merge":
        log.append({"node": name, "status": "ok", "kind": "merge"})
        return {"json": ctx["trigger_payload"]}

    if ntype in ("googleSheets", "notion", "postgres", "mysql"):
        log.append({"node": name, "status": "skipped", "kind": ntype,
                    "msg": f"{ntype} integration requires credentials"})
        return None

    log.append({"node": name, "status": "skipped", "kind": ntype, "msg": "unsupported node"})
    return None


def _exec_set(params: dict, ctx: dict) -> dict:
    out: dict = {}
    assignments = (params.get("assignments") or {}).get("assignments") or []
    for a in assignments:
        key = a.get("name")
        val = _resolve(a.get("value"), ctx)
        if key:
            out[key] = val
    # Some n8n versions store as `values`
    for kind in ("string", "number", "boolean"):
        for v in ((params.get("values") or {}).get(kind) or []):
            out[v.get("name")] = _resolve(v.get("value"), ctx)
    return out


def _exec_if(params: dict, ctx: dict) -> bool:
    conds = (params.get("conditions") or {}).get("conditions") or []
    if not conds:
        # n8n v1 syntax with `boolean`/`number`/`string`
        for kind in ("boolean", "number", "string"):
            for c in ((params.get("conditions") or {}).get(kind) or []):
                conds.append({"value1": c.get("value1"), "value2": c.get("value2"),
                              "operation": c.get("operation", "equal")})
    for c in conds:
        v1 = _resolve(c.get("value1") or c.get("leftValue"), ctx)
        v2 = _resolve(c.get("value2") or c.get("rightValue"), ctx)
        op = c.get("operation") or (c.get("operator") or {}).get("operation") or "equal"
        if not _compare(v1, v2, op):
            return False
    return True


def _compare(v1, v2, op: str) -> bool:
    op = (op or "equal").lower()
    if op in ("equal", "equals", "eq"): return v1 == v2
    if op in ("notequal", "neq"): return v1 != v2
    if op in ("greater", "gt"):
        try: return float(v1) > float(v2)
        except: return False
    if op in ("smaller", "lt"):
        try: return float(v1) < float(v2)
        except: return False
    if op == "contains":
        try: return str(v2) in str(v1)
        except: return False
    return v1 == v2


def _exec_http(params: dict, ctx: dict) -> dict:
    import requests
    url = _resolve(params.get("url"), ctx) or ""
    method = (params.get("method") or "GET").upper()
    body = params.get("jsonParameters") and (params.get("bodyParametersJson") or "")
    headers = {}
    for h in ((params.get("headerParametersUi") or {}).get("parameter") or []):
        k = _resolve(h.get("name"), ctx); v = _resolve(h.get("value"), ctx)
        if k: headers[str(k)] = str(v)
    try:
        r = requests.request(method, str(url), headers=headers, data=str(body) if body else None, timeout=15)
        return {"ok": r.status_code < 400, "status_code": r.status_code, "url": str(url),
                "body": r.text[:2000]}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": str(url)}


def _exec_gmail(params: dict, ctx: dict) -> dict:
    import smtplib
    from email.message import EmailMessage
    host = os.getenv("SMTP_HOST")
    if not host:
        return {"status": "skipped", "msg": "SMTP_HOST not set; gmail node skipped"}
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    to = _resolve(params.get("toEmail") or params.get("toRecipients"), ctx) or ""
    subject = _resolve(params.get("subject"), ctx) or "goat-bot automation"
    body = _resolve(params.get("message") or params.get("emailBody") or params.get("text"), ctx) or ""
    try:
        msg = EmailMessage()
        msg["From"] = user; msg["To"] = str(to); msg["Subject"] = str(subject)
        msg.set_content(str(body))
        with smtplib.SMTP(host, port, timeout=10) as s:
            s.starttls(); s.login(user, pwd); s.send_message(msg)
        return {"status": "ok", "msg": f"sent to {to}"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


def _exec_slack(params: dict, ctx: dict) -> dict:
    import requests
    hook = os.getenv("SLACK_WEBHOOK_URL", "")
    if not hook:
        return {"status": "skipped", "msg": "SLACK_WEBHOOK_URL not set"}
    text = _resolve(params.get("text") or params.get("message"), ctx) or "(boş)"
    try:
        r = requests.post(hook, json={"text": str(text)}, timeout=8)
        return {"status": "ok" if r.status_code == 200 else "error", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


def _exec_llm(params: dict, ctx: dict) -> dict:
    from services import llm
    prompt = _resolve(params.get("prompt") or params.get("text") or params.get("message"), ctx) or ""
    if not prompt:
        return {"text": "", "skipped": True}
    return llm.complete(messages=[{"role": "user", "content": str(prompt)}], task="cheap")


# ─────────────────────────── Helpers ───────────────────────────

EXPR_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def _resolve(expr: Any, ctx: dict) -> Any:
    """Substitute {{ $json.body.foo }} style expressions with ctx values.
    Returns string for safety. None passthrough."""
    if expr is None:
        return None
    if not isinstance(expr, str):
        return expr
    if "{{" not in expr:
        return expr

    def repl(m):
        path = m.group(1).strip()
        path = re.sub(r"^\$json\.", "", path)
        path = re.sub(r"^body\.", "", path)
        try:
            val = ctx["trigger_payload"]
            for part in re.split(r"\.|\[\"?|\"?\]", path):
                if part == "":
                    continue
                if isinstance(val, dict):
                    val = val.get(part, "")
                elif isinstance(val, list):
                    try: val = val[int(part)]
                    except: val = ""
                else:
                    val = ""
            return str(val)
        except Exception:
            return ""
    return EXPR_RE.sub(repl, expr)


def _detect_trigger(nodes: list) -> str:
    for n in nodes:
        t = (n.get("type") or "").replace("n8n-nodes-base.", "")
        if t == "webhook": return "webhook"
        if t == "scheduleTrigger": return "schedule"
        if t == "manualTrigger": return "manual"
    return "manual"


def _start_node(nodes: list, with_payload: bool) -> Optional[dict]:
    for n in nodes:
        t = (n.get("type") or "").replace("n8n-nodes-base.", "")
        if t in ("webhook", "manualTrigger", "scheduleTrigger"):
            return n
    return nodes[0] if nodes else None


def _support_pct(types: list) -> int:
    supported = {"webhook", "scheduleTrigger", "manualTrigger", "set", "if", "httpRequest",
                 "telegram", "gmail", "slack", "merge", "code"}
    if not types: return 0
    hits = sum(1 for t in types if t in supported or "openAi" in t or "openai" in t.lower())
    return int(round(hits / len(types) * 100))
