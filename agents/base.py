"""Base agent class for goat agents."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
# On Vercel/serverless the package directory is read-only. GOAT_DATA_DIR
# (set in api/index.py to /tmp/goat-data on Vercel) overrides the default.
DATA_DIR = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))
OUTPUT_DIR = Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))


class BaseAgent:
    """Base class for all goat agents."""

    agent_id: str = ""
    name: str = ""
    role: str = ""
    category: str = ""

    def __init__(self):
        self.run_log = []

    def log(self, message: str):
        entry = {"time": datetime.now().isoformat(), "message": message}
        self.run_log.append(entry)

    def load_data(self, path: str):
        full_path = DATA_DIR / path
        if full_path.exists():
            with open(full_path) as f:
                return json.load(f)
        return {}

    def save_output(self, filename: str, data):
        out_dir = OUTPUT_DIR / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        self.log(f"Saved output to {path}")

    def save_data(self, path: str, data):
        """Save data to the data directory."""
        full_path = DATA_DIR / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def load_config(self) -> dict:
        """Load the user's agency profile."""
        config_path = DATA_DIR / "config" / "user_profile.json"
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        return {}

    def call_claude(self, prompt: str, timeout: int = 120):
        """Call Claude CLI if available. Returns response text or None."""
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(BASE_DIR),
            )
            if result.stdout and result.stdout.strip():
                return result.stdout.strip()
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def run(self) -> dict:
        raise NotImplementedError

    def get_status(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "category": self.category,
            "last_run": self.run_log[-1] if self.run_log else None,
            "total_runs": len(self.run_log),
        }
