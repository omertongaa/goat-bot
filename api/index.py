"""Vercel serverless entry point.

NOTE on persistence: goat's control plane uses JSON file storage. The package
directory `/var/task` is read-only on Vercel; only `/tmp` is writable (and
ephemeral — cleared between cold starts). At boot we:

    1. Set GOAT_DATA_DIR=/tmp/goat-data and GOAT_OUTPUTS_DIR=/tmp/goat-outputs
       so all writes land in /tmp.
    2. Seed /tmp/goat-data once by copying the read-only ./data tree (which
       contains classroom content, MCP catalog, etc.) so reads still work.

For durable autonomous operation, self-host on a server where data/ persists,
or swap core/store.py for Postgres / Supabase / Turso.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    DATA_DST = Path("/tmp/goat-data")
    OUT_DST = Path("/tmp/goat-outputs")
    DATA_SRC = ROOT / "data"

    # Seed /tmp once per cold start
    if DATA_SRC.exists() and not DATA_DST.exists():
        try:
            shutil.copytree(DATA_SRC, DATA_DST, dirs_exist_ok=True)
        except Exception:
            DATA_DST.mkdir(parents=True, exist_ok=True)
    DATA_DST.mkdir(parents=True, exist_ok=True)
    OUT_DST.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("GOAT_DATA_DIR", str(DATA_DST))
    os.environ.setdefault("GOAT_OUTPUTS_DIR", str(OUT_DST))
    # Tell scheduler not to spin up BackgroundScheduler in serverless context
    os.environ.setdefault("GOAT_DISABLE_SCHEDULER", "1")

from app import app  # noqa: E402
