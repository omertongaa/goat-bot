"""Append-only activity log per company (JSONL).

Every mutation in the control plane writes one line here: ticket creation,
approval, budget breach, config change, etc. The log is the source of truth
for the UI's activity stream and for audit/rollback.

One line per entry, newline-delimited JSON. Never rewrite — append only.
"""

import json
from pathlib import Path
from typing import Optional

from core.models import ActivityEntry, now_iso, to_dict
from core.store import company_dir


def log_path(company_id: str) -> Path:
    return company_dir(company_id) / "activity.jsonl"


def append(
    company_id: str,
    kind: str,
    actor: str = "system",
    subject: str = "",
    details: Optional[dict] = None,
) -> dict:
    """Append one entry. Returns the entry for convenience."""
    entry = to_dict(ActivityEntry(
        timestamp=now_iso(),
        company_id=company_id,
        kind=kind,
        actor=actor,
        subject=subject,
        details=details or {},
    ))
    p = log_path(company_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read(
    company_id: str,
    limit: int = 100,
    kind: Optional[str] = None,
    subject: Optional[str] = None,
) -> list:
    """Read most recent entries, newest first."""
    p = log_path(company_id)
    if not p.exists():
        return []

    # Read all lines — for 10K+ entries consider reverse-seeking, but JSONL
    # append-only stays small in practice.
    entries = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue

    if kind:
        entries = [e for e in entries if e.get("kind") == kind]
    if subject:
        entries = [e for e in entries if e.get("subject") == subject]

    return list(reversed(entries[-limit:]))
