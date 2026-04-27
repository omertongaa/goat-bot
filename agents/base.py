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
        """Load the user's agency profile.

        Order of resolution:
            1. Active company profile (data/companies/{id}/profile.json)
               — flattened so legacy keys like agency_name still work
            2. Legacy data/config/user_profile.json
        Both are merged with company taking precedence.
        """
        # Legacy file
        legacy = {}
        config_path = DATA_DIR / "config" / "user_profile.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    legacy = json.load(f) or {}
            except Exception:
                legacy = {}
        # Company schema → flatten to legacy-shaped dict
        try:
            from core import store as _store
            cid = _store.active_company_id()
            company = _store.load_company(cid) or {}
            flat = {
                "id": cid,
                "agency_name": company.get("name") or legacy.get("agency_name", ""),
                "name": company.get("name") or legacy.get("name", ""),
                "owner_name": company.get("owner_name") or legacy.get("owner_name", ""),
                "niche": company.get("niche") or legacy.get("niche", ""),
                "target_cities": company.get("target_cities") or legacy.get("target_cities", []),
                "target_industries": company.get("target_industries") or legacy.get("target_industries", []),
            }
            # Mix in api_keys at flat top-level (legacy callers expect that)
            for k, v in (company.get("api_keys") or {}).items():
                flat.setdefault(k, v)
            for k, v in (company.get("settings") or {}).items():
                flat.setdefault(k, v)
            # Final merge: legacy fills any gaps
            merged = {**legacy, **{k: v for k, v in flat.items() if v}}
            return merged
        except Exception:
            return legacy

    def ensure_leads(self, min_count: int = 5, with_email: bool = False) -> list:
        """Lead havuzu boşsa otomatik Scout çalıştır + email enrichment.

        Pitch, Filter, Outreach gibi downstream agent'lar bunu çağırır:
            leads = self.ensure_leads(min_count=10)
        Hiç fail etmez — Scout başarısız olsa bile boş list döner."""
        # 1. Mevcut qualified leads'a bak
        try:
            qual = sorted((DATA_DIR / "leads" / "qualified").glob("*.json"),
                          reverse=True)
            if qual:
                with open(qual[0]) as f:
                    data = json.load(f)
                leads = data.get("leads", [])
                if with_email:
                    leads = [l for l in leads if l.get("lead", {}).get("email")
                             or l.get("email")]
                if len(leads) >= min_count:
                    return leads
        except Exception:
            pass

        # 2. Raw leads — varsa filter'a girmeden de döndürebiliriz
        try:
            raw = sorted((DATA_DIR / "leads" / "raw").glob("*.json"), reverse=True)
            if raw:
                with open(raw[0]) as f:
                    data = json.load(f)
                cached = data.get("leads", [])
                if cached and len(cached) >= min_count:
                    if with_email:
                        cached = [l for l in cached if l.get("email")]
                        if not cached:
                            return []
                    self.log(f"Cache'ten {len(cached)} lead kullanıyorum")
                    return cached
        except Exception:
            pass

        # 3. Boş — otomatik Scout tetikle
        if not os.environ.get("APIFY_TOKEN", "").strip():
            self.log("APIFY_TOKEN yok — auto-fetch atlandı")
            return []

        cfg = self.load_config()
        niche = cfg.get("niche") or (cfg.get("target_industries") or ["restoran"])[0]
        city = (cfg.get("target_cities") or [""])[0]

        self.log(f"Hot lead yok, Scout otomatik çalıştırıyor: {niche} / {city}")
        try:
            from services.scraper import scrape_b2b_leads
            new_leads = scrape_b2b_leads(query=niche, location=city,
                                         max_results=max(min_count * 2, 20),
                                         log=self.log)
            if not new_leads:
                self.log("Scout sonuç dönmedi")
                return []

            # Email enrichment for downstream
            if with_email:
                without_email = [l for l in new_leads if not l.get("email")]
                if without_email and os.environ.get("EMAIL_FINDER_PROVIDERS", "").strip():
                    try:
                        from services.email_finder import enrich_leads
                        enrich_leads(without_email, log=self.log)
                    except Exception:
                        pass

            # Persist as raw so other agents can use it too
            try:
                from datetime import datetime as _dt
                slug = niche.lower().replace(" ", "_")[:30]
                fname = f"leads/raw/auto_{_dt.now().strftime('%Y%m%d_%H%M%S')}_{slug}.json"
                self.save_data(fname, {
                    "query": niche, "location": city,
                    "scraped_at": _dt.now().isoformat(),
                    "auto_fetched_by": self.agent_id,
                    "count": len(new_leads), "leads": new_leads,
                })
            except Exception:
                pass

            self.log(f"Scout {len(new_leads)} lead getirdi")
            if with_email:
                new_leads = [l for l in new_leads if l.get("email")]
            return new_leads
        except Exception as e:
            self.log(f"Auto-fetch hatası: {e}")
            return []

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
