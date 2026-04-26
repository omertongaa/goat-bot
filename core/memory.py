"""Knowledge memory — what the company has learned from past tickets.

Every time a ticket completes successfully, a Claude Haiku call extracts
1-3 short facts (insights, found leads, decisions, learned constraints)
and appends them to a per-company KV list. The CEO snapshots `recent_facts`
on every chat so it can reference past work without the user re-explaining.

Backend: KV when configured, JSON file under data/companies/{cid}/memory.json
otherwise. Read/write through the same dual-backend pattern as core/store.
"""

import json
import os
from pathlib import Path
from typing import Optional

from core.store import company_dir, _kv
from core.models import now_iso, new_id

EXTRACTOR_MODEL = "claude-haiku-4-5-20251001"  # cheap, fast


def _file_path(company_id: str) -> Path:
    return company_dir(company_id) / "memory.json"


def list_facts(company_id: str, limit: int = 50) -> list:
    if _kv():
        from core import kv as _kv_mod
        items = _kv_mod.lrange_json(f"memory:{company_id}", -limit, -1)
        return list(reversed(items))
    p = _file_path(company_id)
    if not p.exists():
        return []
    try:
        all_facts = json.loads(p.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    return list(reversed(all_facts[-limit:]))


def add_fact(company_id: str, kind: str, content: str,
             source_ticket_id: Optional[str] = None) -> dict:
    """Append one fact and return it."""
    fact = {
        "id": new_id("f"),
        "kind": kind,
        "content": content,
        "source_ticket_id": source_ticket_id,
        "created_at": now_iso(),
    }
    if _kv():
        from core import kv as _kv_mod
        _kv_mod.rpush_json(f"memory:{company_id}", fact)
        n = _kv_mod.llen(f"memory:{company_id}")
        if n > 500:
            _kv_mod.ltrim(f"memory:{company_id}", n - 500, -1)
        return fact
    p = _file_path(company_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8")) or []
        except Exception:
            existing = []
    existing.append(fact)
    if len(existing) > 500:
        existing = existing[-500:]
    p.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return fact


def extract_facts_from_ticket(ticket: dict) -> list:
    """Use Claude Haiku to extract 1-3 short facts from a completed ticket.
    Returns list of {kind, content}. No-op when API key missing."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return []
    try:
        import anthropic
    except ImportError:
        return []

    summary_blob = json.dumps({
        "agent": ticket.get("agent_id"),
        "title": ticket.get("title"),
        "params": ticket.get("params"),
        "result": ticket.get("result"),
    }, ensure_ascii=False)[:6000]

    prompt = f"""Bu agent çıktısından şirketin ileride kullanabileceği 1-3 kısa
gözlem çıkar. Her gözlem 1 cümleyi geçmesin. JSON array dön:
[{{"kind":"insight|lead|decision|constraint","content":"..."}}, ...]

Boş bilgi varsa boş array dön. Sadece JSON döndür.

TİCKET:
{summary_blob}"""

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=EXTRACTOR_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        # Track cost
        try:
            from core.cost_tracker import record
            u = resp.usage
            record("claude.token_in", units=getattr(u, "input_tokens", 0))
            record("claude.token_out", units=getattr(u, "output_tokens", 0))
        except Exception:
            pass
        # Parse JSON
        import re
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        parsed = json.loads(m.group())
        out = []
        for f in parsed[:3]:
            if isinstance(f, dict) and f.get("content"):
                out.append({
                    "kind": (f.get("kind") or "insight")[:32],
                    "content": str(f["content"])[:500],
                })
        return out
    except Exception:
        return []
