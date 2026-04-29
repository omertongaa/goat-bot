"""HTML → PDF dönüştürücü.

Öncelik sırası:
1. Playwright (Chromium) — pixel-perfect, slayt için ideal
2. weasyprint (eğer kuruluysa) — CSS render, Chromium gerektirmez
3. Fallback: None (caller .pdf üretmeyebilir)
"""

import os
from pathlib import Path
from typing import Optional


def html_to_pdf(html_path: str, pdf_path: str, landscape: bool = True,
                width_px: int = 1920, height_px: int = 1080,
                full_page: bool = False, log=None) -> Optional[str]:
    """HTML dosyasını PDF'e dönüştür. Başarısız olursa None döner.

    landscape=True + width/height → slayt sunum boyutları.
    full_page=True → tek sayfa A4 (uzun blog için)."""
    html_p = Path(html_path).resolve()
    pdf_p = Path(pdf_path).resolve()
    pdf_p.parent.mkdir(parents=True, exist_ok=True)

    # 1) Playwright (Chromium) — preferred
    result = _try_playwright(html_p, pdf_p, landscape, width_px, height_px, full_page, log)
    if result:
        return result

    # 2) weasyprint
    result = _try_weasyprint(html_p, pdf_p, log)
    if result:
        return result

    if log:
        log("HTML→PDF: ne Playwright ne weasyprint kullanılabilir")
    return None


def _try_playwright(html_p, pdf_p, landscape, w, h, full_page, log):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if log:
            log("Playwright import edilemedi")
        return None

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                if log:
                    log(f"Chromium launch başarısız ({e}) — Mac Chrome.app deneniyor")
                # Try macOS bundled Chrome
                chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                if not Path(chrome_path).exists():
                    if log:
                        log("Chrome.app yok — Playwright atlandı")
                    return None
                browser = p.chromium.launch(headless=True, executable_path=chrome_path)

            context = browser.new_context(
                viewport={"width": w if landscape else 794, "height": h if landscape else 1123},
                device_scale_factor=2,
            )
            page = context.new_page()
            page.goto(f"file://{html_p}", wait_until="networkidle", timeout=30000)

            # Wait for fonts / images to settle
            page.wait_for_timeout(1500)

            if full_page:
                # Single tall page (blogs / articles)
                page.pdf(
                    path=str(pdf_p),
                    format="A4",
                    print_background=True,
                    margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
                )
            else:
                # Slayt başına 1 sayfa: kullanıcı CSS'inde @media print → page-break-after kuralları lazım
                page.pdf(
                    path=str(pdf_p),
                    width=f"{w}px", height=f"{h}px",
                    landscape=landscape,
                    print_background=True,
                    prefer_css_page_size=False,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
            browser.close()
        if pdf_p.exists() and pdf_p.stat().st_size > 0:
            if log:
                log(f"PDF (Playwright): {pdf_p.name} ({round(pdf_p.stat().st_size / 1024)}KB)")
            return str(pdf_p)
    except Exception as e:
        if log:
            log(f"Playwright PDF hatası: {e}")
    return None


def _try_weasyprint(html_p, pdf_p, log):
    try:
        from weasyprint import HTML
    except ImportError:
        return None

    try:
        HTML(filename=str(html_p)).write_pdf(str(pdf_p))
        if pdf_p.exists():
            if log:
                log(f"PDF (weasyprint): {pdf_p.name}")
            return str(pdf_p)
    except Exception as e:
        if log:
            log(f"weasyprint hatası: {e}")
    return None
