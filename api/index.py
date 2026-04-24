"""Vercel serverless entry point.

NOTE on persistence: goat's control plane uses JSON file storage under data/
and /tmp. Vercel serverless functions only have a writable /tmp and it is
ephemeral (cleared between cold starts). This deployment is for UI preview
and demo only — for real autonomous operation, self-host on a box where
data/ persists (or swap store.py for Postgres / Supabase / Turso).
"""

import os
import sys
from pathlib import Path

# Make the repo root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Redirect data writes to /tmp on Vercel so the function can boot even without
# a writable repo directory.
if os.getenv("VERCEL") or os.getenv("VERCEL_ENV"):
    os.environ.setdefault("GOAT_DATA_DIR", "/tmp/goat-data")

from app import app  # noqa: E402  — re-exports FastAPI instance for Vercel
