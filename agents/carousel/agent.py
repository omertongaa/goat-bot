"""Carousel — Instagram kaydırmalı içerik agent.

Pipeline:
    1. LLM (Haiku/Ollama) konudan slide planı üretir (8 slide JSON)
    2. JSON `services/carousel/generate.py` ile HTML'e çevrilir
    3. `services/carousel/export_slides.py` Playwright ile PNG'ye render eder
    4. PNG'ler `outputs/carousel/{slug}/slide_*.png` olarak kaydedilir,
       ticket artifact olarak döner

Tema: terminal-dark | editorial-cream | vibrant-gradient | minimal-mono | data-viz

Vendored: github.com/Arif-Ata-Kosker/carousel-template (services/carousel/)
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, OUTPUT_DIR
from services import llm


CAROUSEL_DIR = Path(__file__).resolve().parent.parent.parent / "services" / "carousel"


SYSTEM_PROMPT = """Sen Instagram carousel uzmanısın. Konu verince 8 slide'lık plan yapacaksın.
Şablon JSON formatı:
{"defaults": {"handle": "@marka", "theme": "terminal-dark"}, "slides": [...]}

Slide tipleri: cover, inner_text, inner_list, inner_comparison, inner_stats, inner_quote, cta
Plan: 1× cover → 5-6 inner (mix tipler) → 1× cta. Türkçe, kısa, hook'lu yaz.

ÖNEMLİ: Sadece geçerli JSON dön, başka hiçbir şey yazma. cover ve cta zorunlu.
Her slide için title/heading <br> yerine \\n kullan. body içinde <strong> tag'i serbest.

Tema seçimi:
- terminal-dark: dev/teknik
- editorial-cream: rehber/eğitim
- vibrant-gradient: viral/karşılaştırma
- minimal-mono: alıntı/fikir
- data-viz: istatistik/rakam"""


class CarouselAgent(BaseAgent):
    agent_id = "carousel"
    name = "Carousel"
    role = "Instagram kaydırmalı içerik (8 slide PNG, 1080×1350)"
    category = "creative"

    def run(
        self,
        topic: str = "",
        theme: str = "",
        handle: str = "",
        slides: int = 8,
    ) -> dict:
        if not topic:
            return {"status": "error", "summary": "topic parametresi zorunlu", "metrics": {}, "recommendations": ["topic= ile konu ver"]}

        config = self.load_config()
        handle = handle or config.get("instagram_handle") or f"@{(config.get('agency_name','marka').lower().replace(' ','_'))[:20]}"
        theme = theme or config.get("default_carousel_theme") or "terminal-dark"

        self.log(f"Carousel planı üretiliyor: {topic} (tema={theme})")
        plan = self._generate_plan(topic, theme, handle, slides)
        if not plan:
            return {"status": "error", "summary": "Slide planı üretilemedi (LLM provider yok mu?)", "metrics": {}, "recommendations": ["Anthropic key veya Ollama kur"]}

        slug = self._slug(topic)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = OUTPUT_DIR / "carousel" / f"{ts}_{slug}"
        out_dir.mkdir(parents=True, exist_ok=True)
        plan_path = out_dir / "plan.json"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

        self.log("HTML render ediliyor")
        html_path = self._render_html(plan_path, out_dir)
        if not html_path:
            return {
                "status": "warning",
                "summary": "Plan üretildi ama HTML render başarısız (Playwright yok mu?)",
                "metrics": {"slides": len(plan.get("slides", []))},
                "result": {"plan": plan, "plan_path": str(plan_path)},
                "recommendations": ["pip install playwright && playwright install chromium"],
            }

        self.log("PNG export ediliyor")
        pngs = self._export_pngs(html_path)

        return {
            "status": "ok" if pngs else "warning",
            "summary": f"{len(pngs)} slide üretildi: {topic} (tema={theme})",
            "metrics": {
                "slides": len(plan.get("slides", [])),
                "pngs": len(pngs),
                "theme": theme,
            },
            "result": {
                "plan_path": str(plan_path),
                "html_path": str(html_path),
                "png_paths": [str(p) for p in pngs],
                "preview": [f"/static/carousel/{out_dir.name}/{p.name}" for p in pngs[:3]],
            },
            "artifacts": [{"type": "image", "path": str(p), "name": p.name} for p in pngs],
            "recommendations": [
                f"Instagram'a yükle (en üst slide kapak)",
                "Caption + hashtag üret: Content agent çağır",
            ],
        }

    def _generate_plan(self, topic: str, theme: str, handle: str, n: int) -> dict:
        hint = self.improvement_hint()
        system = SYSTEM_PROMPT + (f"\n\n[ÖNERI]: {hint}" if hint else "")
        result = llm.complete(
            messages=[{"role": "user", "content": f"Konu: {topic}\nTema: {theme}\nHandle: {handle}\nToplam slide: {n}\n\nJSON dön."}],
            task="cheap",
            system=system,
            max_tokens=3000,
        )
        text = (result.get("text") or "").strip()
        self.log(f"LLM: {result.get('provider')} ({len(text)} char)")
        if not text:
            return {}
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            plan = json.loads(text)
        except Exception as e:
            self.log(f"JSON parse hata: {e}")
            return {}
        plan.setdefault("defaults", {})["handle"] = handle
        plan["defaults"]["theme"] = theme
        return plan

    def _render_html(self, plan_path: Path, out_dir: Path) -> Path:
        try:
            result = subprocess.run(
                [sys.executable, str(CAROUSEL_DIR / "generate.py"), str(plan_path)],
                capture_output=True,
                cwd=str(CAROUSEL_DIR),
                timeout=60,
            )
            if result.returncode != 0:
                self.log(f"generate.py hata: {result.stderr.decode()[:300]}")
                return None
            html_files = list(plan_path.parent.glob("*.html"))
            if html_files:
                return html_files[0]
            for fname in ("output.html", "carousel.html", plan_path.with_suffix(".html").name):
                src = plan_path.parent / fname
                if src.exists():
                    return src
            siblings = list((CAROUSEL_DIR / "content").glob("*.html"))
            if siblings:
                target = out_dir / "carousel.html"
                shutil.copy(siblings[-1], target)
                return target
            return None
        except Exception as e:
            self.log(f"HTML render exception: {e}")
            return None

    def _export_pngs(self, html_path: Path) -> list:
        try:
            result = subprocess.run(
                [sys.executable, str(CAROUSEL_DIR / "export_slides.py"), str(html_path)],
                capture_output=True,
                cwd=str(CAROUSEL_DIR),
                timeout=180,
            )
            if result.returncode != 0:
                self.log(f"export_slides hata: {result.stderr.decode()[:300]}")
                return []
            return sorted(html_path.parent.glob("slide_*.png"))
        except FileNotFoundError:
            self.log("Playwright kurulu değil")
            return []
        except Exception as e:
            self.log(f"Export exception: {e}")
            return []

    @staticmethod
    def _slug(text: str) -> str:
        s = text.lower().strip()
        s = re.sub(r"[^a-z0-9\s-]", "", s)
        s = re.sub(r"[\s-]+", "-", s)
        return s[:40] or "carousel"
