"""Files — agent çıktılarını tek noktadan tarayan registry.

Agentlar farklı yerlere yazıyor:
    outputs/proposals/*.pdf|md   — Pitch
    outputs/creatives/*.png      — Designer / Pitch cover
    outputs/sites/*.html         — SiteBuilder
    outputs/presentations/*.html — Presenter
    outputs/brandkit/*.html      — BrandKit board
    outputs/storyboards/...      — Storyboard
    outputs/content/*.md         — Content
    outputs/reports/*.json       — Tüm agent raporları
    data/designs/*.json          — Designer briefs
    data/videos/*.json           — VideoMaker
    data/brandkit/*.json         — BrandKit raw
    data/content/*.md|json       — Content
    data/proposals/*.md          — Pitch markdown
    data/audits/*.json           — Auditor

Bu modül hepsini tarayıp tek liste olarak sunuyor: kind, agent, path, name,
size, created_at, ticket_id (varsa).
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.paths import data_dir, outputs_dir, BASE_DIR


# Path → (kind, agent) mapping. Used to label files by their location.
LOCATION_MAP = [
    # outputs/
    ("outputs/proposals",    "Teklif",       "pitch"),
    ("outputs/creatives",    "Görsel",       "designer"),
    ("outputs/sites",        "Web Sitesi",   "sitebuilder"),
    ("outputs/presentations","Sunum",        "presenter"),
    ("outputs/brandkit",     "Marka Board",  "brandkit"),
    ("outputs/storyboards",  "Storyboard",   "storyboard"),
    ("outputs/content",      "İçerik",       "content"),
    ("outputs/reports",      "Rapor",        "system"),
    ("outputs/videos",       "Video",        "videoproducer"),
    # data/
    ("data/designs",         "Tasarım",      "designer"),
    ("data/videos",          "Video Plan",   "videomaker"),
    ("data/brandkit",        "Marka Kiti",   "brandkit"),
    ("data/content",         "İçerik",       "content"),
    ("data/proposals",       "Teklif",       "pitch"),
    ("data/audits",          "Site Denetim", "auditor"),
    ("data/social",          "Sosyal Plan",  "social"),
    ("data/analytics",       "Analiz",       "analytics"),
    ("data/ads",             "Reklam Plan",  "admanager"),
    ("data/presentations",   "Sunum",        "presenter"),
    ("data/storyboards",     "Storyboard",   "storyboard"),
    ("data/leads/raw",       "Ham Lead",     "scout"),
    ("data/leads/qualified", "Skorlu Lead",  "filter"),
    ("data/campaigns",       "Kampanya",     "outreach"),
]

# Skip these — internal state, not user-visible artifacts
SKIP_PATTERNS = (
    "tickets/", "goals/", "active_company.json", "profile.json",
    "budgets.json", "activity.jsonl", "memory.json", "apps.json",
    "config/", "logs/", ".gitkeep",
)

EXT_KIND = {
    ".pdf": "PDF", ".md": "Markdown", ".html": "Web sayfası",
    ".png": "Görsel", ".jpg": "Görsel", ".jpeg": "Görsel", ".gif": "GIF",
    ".webp": "Görsel", ".mp4": "Video", ".mov": "Video", ".webm": "Video",
    ".mp3": "Ses", ".wav": "Ses", ".json": "JSON", ".txt": "Metin",
    ".csv": "CSV",
}


def _ext_kind(path: Path) -> str:
    return EXT_KIND.get(path.suffix.lower(), "Dosya")


def _classify(rel_path: str) -> tuple:
    """Return (kind, agent) for a relative path."""
    for prefix, kind, agent in LOCATION_MAP:
        if rel_path.startswith(prefix):
            return (kind, agent)
    return ("Dosya", "system")


def _should_skip(rel_path: str) -> bool:
    return any(p in rel_path for p in SKIP_PATTERNS)


def list_files(company_id: Optional[str] = None, limit: int = 200) -> list:
    """Tüm artifact'ları topla, en yeniden eskiye sırala."""
    out = []
    bases = [outputs_dir(), data_dir()]
    base_root = BASE_DIR
    for base in bases:
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            try:
                rel = str(f.relative_to(base_root)) if str(base).startswith(str(base_root)) \
                      else str(f).replace(str(base.parent) + "/", "")
            except ValueError:
                rel = str(f)
            if _should_skip(rel):
                continue
            try:
                stat = f.stat()
            except OSError:
                continue
            kind, agent = _classify(rel)
            out.append({
                "name": f.name,
                "path": rel,
                "kind": kind,
                "agent": agent,
                "type": _ext_kind(f),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "url": f"/api/core/files/raw?path={rel}",
            })
    out.sort(key=lambda x: x["modified"], reverse=True)
    return out[:limit]


def safe_read_file(rel_path: str) -> Optional[Path]:
    """Path traversal safety — only allow files inside data/ or outputs/."""
    target = (BASE_DIR / rel_path).resolve()
    allowed_roots = [data_dir().resolve(), outputs_dir().resolve(),
                     (BASE_DIR / "data").resolve(), (BASE_DIR / "outputs").resolve()]
    if not any(str(target).startswith(str(root)) for root in allowed_roots):
        return None
    if not target.exists() or not target.is_file():
        return None
    if any(p in rel_path for p in SKIP_PATTERNS):
        return None
    return target
