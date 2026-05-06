"""
Carousel Generator — Dinamik Template Sistemi
Kullanım: python content/carousel/generate.py content/carousel/content/icerik.json
"""

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
SLIDE_TYPES = BASE / "slide_types"
EXPORT_SCRIPT = BASE / "export_slides.py"

sys.path.insert(0, str(BASE))
from components.icon_badge import render_icon_row
from components.shape_decoration import render_decorations

_BRAND_DEFAULTS = {
    "handle": "",
    "lang": "tr",
    "default_theme": "terminal-dark",
    "ui": {
        "swipe_text": "Kaydır",
        "swipe_arrow": "›",
        "cta_default_button": "Takip et",
        "cta_icon": "📌",
    },
}


def load_brand() -> dict:
    brand_path = BASE / "brand.json"
    if brand_path.exists():
        return json.loads(brand_path.read_text(encoding="utf-8"))
    return _BRAND_DEFAULTS


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fill(tmpl: str, vars: dict) -> str:
    for k, v in vars.items():
        tmpl = tmpl.replace(f"{{{{{k}}}}}", str(v))
    return tmpl


def br(text: str) -> str:
    return text.replace("\n", "<br>")


def render_terminal_block(terminal: dict) -> str:
    if not terminal:
        return ""
    title = terminal.get("title", "")
    lines_html = ""
    for line in terminal.get("lines", []):
        line_type = line.get("type", "output")
        text = line.get("text", "")
        lines_html += f'<div class="terminal-line {line_type}">{text}</div>\n'
    return (
        '<div class="terminal-block">'
        '<div class="terminal-header">'
        '<span class="dot red"></span>'
        '<span class="dot yellow"></span>'
        '<span class="dot green"></span>'
        f'<span class="terminal-title">{title}</span>'
        '</div>'
        f'<div class="terminal-body">{lines_html}</div>'
        '</div>'
    )


def render_slide_decoration(slide: dict) -> str:
    deco = slide.get("decoration", {})
    if not deco:
        return ""
    icons = deco.get("icons", [])
    shapes = deco.get("shapes", [])
    parts = []
    if icons:
        parts.append(render_icon_row(icons))
    if shapes:
        parts.append(render_decorations(shapes))
    return "".join(parts)


def render_cover(slide: dict, defaults: dict, brand: dict, _pos: int, _total: int) -> str:
    ui = brand.get("ui", _BRAND_DEFAULTS["ui"])
    return fill(load(SLIDE_TYPES / "cover.html"), {
        "category":        slide.get("category", ""),
        "handle":          defaults.get("handle") or brand.get("handle", ""),
        "cover_eyebrow":   slide.get("eyebrow", ""),
        "cover_title":     br(slide.get("title", "")),
        "cover_subtitle":  slide.get("subtitle", ""),
        "terminal_block":  render_terminal_block(slide.get("terminal", {})),
        "decoration_html": render_slide_decoration(slide),
        "swipe_text":      ui.get("swipe_text", "Kaydır"),
        "swipe_arrow":     ui.get("swipe_arrow", "›"),
    })


def render_inner_text(slide: dict, _defaults: dict, _brand: dict, pos: int, total: int) -> str:
    return fill(load(SLIDE_TYPES / "inner_text.html"), {
        "progress":        round(pos / (total - 1) * 100),
        "slide_num":       f"{pos + 1:02d}",
        "slide_total":     f"{total:02d}",
        "label":           slide.get("label", ""),
        "heading":         br(slide.get("heading", "")),
        "body":            br(slide.get("body", "")),
        "terminal_block":  render_terminal_block(slide.get("terminal", {})),
        "decoration_html": render_slide_decoration(slide),
    })


def render_inner_list(slide: dict, _defaults: dict, _brand: dict, pos: int, total: int) -> str:
    items_html = "".join(
        f'<li><span class="num">{i:02d}</span>'
        f'<span class="text"><strong>{it.get("title", "")}</strong>{it.get("body", "")}</span></li>'
        for i, it in enumerate(slide.get("items", []), 1)
    )
    return fill(load(SLIDE_TYPES / "inner_list.html"), {
        "progress":        round(pos / (total - 1) * 100),
        "slide_num":       f"{pos + 1:02d}",
        "slide_total":     f"{total:02d}",
        "label":           slide.get("label", ""),
        "heading":         br(slide.get("heading", "")),
        "list_items_html": items_html,
        "terminal_block":  render_terminal_block(slide.get("terminal", {})),
        "decoration_html": render_slide_decoration(slide),
    })


def render_inner_quote(slide: dict, _defaults: dict, _brand: dict, pos: int, total: int) -> str:
    return fill(load(SLIDE_TYPES / "inner_quote.html"), {
        "progress":        round(pos / (total - 1) * 100),
        "slide_num":       f"{pos + 1:02d}",
        "slide_total":     f"{total:02d}",
        "label":           slide.get("label", ""),
        "heading":         br(slide.get("heading", "")),
        "quote_text":      slide.get("quote", ""),
        "quote_attr":      slide.get("attr", ""),
        "body":            br(slide.get("body", "")),
        "decoration_html": render_slide_decoration(slide),
    })


def render_inner_stats(slide: dict, _defaults: dict, _brand: dict, pos: int, total: int) -> str:
    stats_html = "".join(
        f'<div class="stat-item">'
        f'<span class="stat-number">{s.get("number", "")}</span>'
        f'<span class="stat-label">{s.get("label", "")}</span>'
        f'</div>'
        for s in slide.get("stats", [])
    )
    return fill(load(SLIDE_TYPES / "inner_stats.html"), {
        "progress":        round(pos / (total - 1) * 100),
        "slide_num":       f"{pos + 1:02d}",
        "slide_total":     f"{total:02d}",
        "label":           slide.get("label", ""),
        "heading":         br(slide.get("heading", "")),
        "stats_html":      stats_html,
        "body":            br(slide.get("body", "")),
        "terminal_block":  render_terminal_block(slide.get("terminal", {})),
        "decoration_html": render_slide_decoration(slide),
    })


def render_inner_comparison(slide: dict, _defaults: dict, _brand: dict, pos: int, total: int) -> str:
    left = slide.get("left", {})
    right = slide.get("right", {})
    left_items = "".join(f"<li>{item}</li>" for item in left.get("items", []))
    right_items = "".join(f"<li>{item}</li>" for item in right.get("items", []))
    return fill(load(SLIDE_TYPES / "inner_comparison.html"), {
        "progress":        round(pos / (total - 1) * 100),
        "slide_num":       f"{pos + 1:02d}",
        "slide_total":     f"{total:02d}",
        "label":           slide.get("label", ""),
        "heading":         br(slide.get("heading", "")),
        "left_title":      left.get("title", ""),
        "left_items":      left_items,
        "right_title":     right.get("title", ""),
        "right_items":     right_items,
        "terminal_block":  render_terminal_block(slide.get("terminal", {})),
        "decoration_html": render_slide_decoration(slide),
    })


def render_cta(slide: dict, defaults: dict, brand: dict, _pos: int, _total: int) -> str:
    ui = brand.get("ui", _BRAND_DEFAULTS["ui"])
    return fill(load(SLIDE_TYPES / "cta.html"), {
        "heading":         br(slide.get("heading", "")),
        "body":            slide.get("body", ""),
        "button_text":     slide.get("button_text") or ui.get("cta_default_button", "Takip et"),
        "handle":          defaults.get("handle") or brand.get("handle", ""),
        "decoration_html": render_slide_decoration(slide),
        "cta_icon":        ui.get("cta_icon", "📌"),
    })


RENDERERS = {
    "cover":            render_cover,
    "inner_text":       render_inner_text,
    "inner_list":       render_inner_list,
    "inner_quote":      render_inner_quote,
    "inner_stats":      render_inner_stats,
    "inner_comparison": render_inner_comparison,
    "cta":              render_cta,
}


def resolve_base(theme: str) -> Path:
    theme_path = BASE / "themes" / theme / "base.html"
    if theme_path.exists():
        return theme_path
    fallback = BASE / "base.html"
    print(f"   Uyari: tema '{theme}' bulunamadi, varsayilan kullaniliyor")
    return fallback


def generate(content_path: str) -> Path:
    brand = load_brand()
    path = Path(content_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    slides = data.get("slides", [])
    total = len(slides)
    theme = defaults.get("theme") or brand.get("default_theme", "terminal-dark")
    lang = brand.get("lang", "tr")

    slide_htmls = []
    for pos, slide in enumerate(slides):
        stype = slide.get("type", "")
        renderer = RENDERERS.get(stype)
        if renderer is None:
            print(f"   Uyari: bilinmeyen slide tipi '{stype}', atlaniyor")
            continue
        slide_htmls.append(renderer(slide, defaults, brand, pos, total))

    base_html = resolve_base(theme).read_text(encoding="utf-8")
    full_html = base_html.replace("{{slides}}", "\n\n".join(slide_htmls))
    full_html = full_html.replace('lang="tr"', f'lang="{lang}"')
    print(f"Tema: {theme}")

    out_dir = BASE / "output" / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "carousel.html"
    out_path.write_text(full_html, encoding="utf-8")
    print(f"HTML olusturuldu: {out_path}")
    print(f"Toplam {len(slide_htmls)} slide")
    return out_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Kullanim: python content/carousel/generate.py content/carousel/content/icerik.json")
        sys.exit(1)

    out_html = generate(sys.argv[1])

    print("PNG export basliyor...")
    result = subprocess.run(
        [sys.executable, str(EXPORT_SCRIPT), str(out_html)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("Export hatasi:")
        print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
