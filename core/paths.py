"""Centralized writable-path helpers.

On Vercel serverless functions the package directory (`/var/task`) is
read-only. We can only write to `/tmp`. Setting `GOAT_DATA_DIR` and
`GOAT_OUTPUTS_DIR` at boot redirects all data writes there.

Use these helpers everywhere instead of computing `BASE_DIR / "data"`
inline so a single env tweak relocates the entire writable surface.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))


def outputs_dir() -> Path:
    return Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))


def data_path(*parts) -> Path:
    return data_dir().joinpath(*parts)


def outputs_path(*parts) -> Path:
    return outputs_dir().joinpath(*parts)
