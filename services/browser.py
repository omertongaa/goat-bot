"""Headless browser controller built on Playwright (optional dep).

Designed so the dependency is *opt-in*: if playwright isn't installed,
the agent falls back to plain `requests` for `extract_html` and returns
a clear error for actions that require a real browser (fill_form, click).

Install once on host:  pip install playwright && playwright install chromium
"""

import asyncio
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def _has_playwright() -> bool:
    try:
        import playwright  # noqa
        return True
    except Exception:
        return False


def extract_html(url: str, timeout: int = 15) -> dict:
    """Fetch a URL. Uses Playwright if available (executes JS), else requests."""
    if _has_playwright():
        return asyncio.run(_pw_extract(url, timeout))
    import requests
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 goat-bot"})
        return {"ok": True, "status": r.status_code, "html": r.text[:200_000], "engine": "requests"}
    except Exception as e:
        return {"ok": False, "error": str(e), "engine": "requests"}


def screenshot(url: str, full_page: bool = True, timeout: int = 30) -> dict:
    """Capture screenshot. Returns base64 PNG + saved file path."""
    if not _has_playwright():
        return {"ok": False, "error": "playwright not installed"}
    return asyncio.run(_pw_screenshot(url, full_page, timeout))


def fill_form(url: str, fields: dict, submit_selector: Optional[str] = None, timeout: int = 30) -> dict:
    """Open page, fill {selector: value} pairs, optionally click submit."""
    if not _has_playwright():
        return {"ok": False, "error": "playwright not installed"}
    return asyncio.run(_pw_fill(url, fields, submit_selector, timeout))


# ── Async Playwright helpers ──────────────────────────────────────────

async def _pw_extract(url: str, timeout: int) -> dict:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            content = await page.content()
            title = await page.title()
            return {"ok": True, "status": 200, "html": content[:200_000], "title": title, "engine": "playwright"}
        except Exception as e:
            return {"ok": False, "error": str(e), "engine": "playwright"}
        finally:
            await browser.close()


async def _pw_screenshot(url: str, full_page: bool, timeout: int) -> dict:
    from playwright.async_api import async_playwright
    out_dir = Path(os.getenv("GOAT_OUTPUTS_DIR") or "outputs") / "browser"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = out_dir / fname
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
            png = await page.screenshot(full_page=full_page)
            path.write_bytes(png)
            return {
                "ok": True,
                "path": str(path),
                "filename": fname,
                "base64_preview": base64.b64encode(png[:200_000]).decode(),
                "size_bytes": len(png),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            await browser.close()


async def _pw_fill(url: str, fields: dict, submit_selector: Optional[str], timeout: int) -> dict:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            filled = []
            for selector, value in fields.items():
                try:
                    await page.fill(selector, str(value), timeout=5000)
                    filled.append(selector)
                except Exception:
                    pass
            submitted = False
            if submit_selector:
                try:
                    await page.click(submit_selector, timeout=5000)
                    submitted = True
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
            return {
                "ok": True,
                "filled": filled,
                "submitted": submitted,
                "final_url": page.url,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            await browser.close()
