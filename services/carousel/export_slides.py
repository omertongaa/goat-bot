import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

INPUT_HTML = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "claude_code_carousel.html"
OUTPUT_DIR = INPUT_HTML.parent
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIEW_W   = 1680
VIEW_H   = 3200   # tüm slaytların render edilmesi için yeterince yüksek
SCALE    = 1080 / 420
SLIDE_W  = 420    # CSS piksel — çıktı: 1080px
SLIDE_H  = 525    # CSS piksel — çıktı: 1350px (4:5)


async def export_slides() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": VIEW_W, "height": VIEW_H},
            device_scale_factor=SCALE,
        )

        html_content = INPUT_HTML.read_text(encoding="utf-8")
        await page.set_content(html_content, wait_until="networkidle")
        await page.wait_for_timeout(3500)

        slides = await page.query_selector_all(".slide")
        total  = len(slides)

        for old in OUTPUT_DIR.glob("slide_*.png"):
            old.unlink()

        for i, slide in enumerate(slides):
            box = await slide.bounding_box()
            out_path = OUTPUT_DIR / f"slide_{i + 1:02d}.png"
            await page.screenshot(
                path=str(out_path),
                clip={"x": box["x"], "y": box["y"], "width": SLIDE_W, "height": SLIDE_H},
            )
            print(f"[OK] Slide {i + 1}/{total} -> {out_path.name}")

        await browser.close()
        print(f"\nTum slaytlar hazir: {OUTPUT_DIR}")


asyncio.run(export_slides())
