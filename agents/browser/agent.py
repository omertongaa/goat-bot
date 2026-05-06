"""Browser — Headless web automation agent.

Wraps services/browser.py for ticket-based runs. Three actions:
    extract → fetch HTML (cheap, JS-rendered if Playwright installed)
    screenshot → full-page PNG saved under outputs/browser/
    fill → fill form fields + optional submit (signup, contact form, demo)

Mutation agent — fill is mutation; auto-approval gate via core_runtime.
"""

from datetime import datetime

from agents.base import BaseAgent
from services import browser as browser_svc


class BrowserAgent(BaseAgent):
    agent_id = "browser"
    name = "Browser"
    role = "Headless tarayıcı — sayfa scrape, screenshot, form doldur"
    category = "system"

    def run(self, action: str = "extract", url: str = "", fields: dict = None, submit_selector: str = "") -> dict:
        if not url:
            return {
                "status": "error",
                "summary": "url parametresi zorunlu",
                "metrics": {},
                "recommendations": ["url= ile bir URL ver"],
            }
        action = (action or "extract").lower()
        self.log(f"Browser action={action} url={url}")

        if action == "extract":
            res = browser_svc.extract_html(url)
            html = (res.get("html") or "")[:5000]
            return {
                "status": "ok" if res.get("ok") else "error",
                "summary": f"Çekildi ({res.get('engine','?')}, {len(res.get('html') or '')} byte)",
                "metrics": {
                    "engine": res.get("engine"),
                    "bytes": len(res.get("html") or ""),
                },
                "result": {"html_preview": html, "title": res.get("title")},
                "recommendations": ["Auditor agent'a URL ver", "İçerikten lead bilgisi çıkart"],
            }

        if action == "screenshot":
            res = browser_svc.screenshot(url, full_page=True)
            return {
                "status": "ok" if res.get("ok") else "error",
                "summary": res.get("ok") and f"Screenshot: {res.get('filename')}" or res.get("error", "fail"),
                "metrics": {"size_bytes": res.get("size_bytes", 0)},
                "result": {"path": res.get("path"), "filename": res.get("filename")},
                "recommendations": ["Pitch agent'a görsel olarak ekle"],
            }

        if action == "fill":
            res = browser_svc.fill_form(url, fields or {}, submit_selector or None)
            return {
                "status": "ok" if res.get("ok") else "error",
                "summary": f"Doldurulan: {len(res.get('filled', []))}, submit={res.get('submitted')}",
                "metrics": {"filled": len(res.get("filled", [])), "submitted": bool(res.get("submitted"))},
                "result": res,
                "needs_approval": True,
                "recommendations": ["Çıktıyı outreach kampanyasına bağla"],
            }

        return {
            "status": "error",
            "summary": f"Bilinmeyen action: {action}",
            "metrics": {},
            "recommendations": ["action: extract|screenshot|fill"],
        }
