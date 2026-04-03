"""Presentation service — slide generation and HTML export."""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"


# Slide layout templates
SLIDE_LAYOUTS = {
    "title": {"name": "Başlık Slaydı", "sections": ["title", "subtitle"]},
    "content": {"name": "İçerik", "sections": ["title", "bullets"]},
    "two_column": {"name": "İki Kolon", "sections": ["title", "left", "right"]},
    "image_text": {"name": "Görsel + Metin", "sections": ["title", "image", "text"]},
    "quote": {"name": "Alıntı", "sections": ["quote", "author"]},
    "stats": {"name": "İstatistikler", "sections": ["title", "stat1", "stat2", "stat3"]},
    "cta": {"name": "CTA", "sections": ["title", "subtitle", "button"]},
}

# Color themes for presentations
THEMES = {
    "dark": {"bg": "#0a0a0c", "surface": "#111114", "text": "#e8e8e8", "accent": "#e85d26", "secondary": "#00ff41"},
    "light": {"bg": "#ffffff", "surface": "#f5f7fa", "text": "#1a1a1a", "accent": "#e85d26", "secondary": "#3b82f6"},
    "corporate": {"bg": "#ffffff", "surface": "#f0f4f8", "text": "#2d3748", "accent": "#0066cc", "secondary": "#00cc66"},
    "creative": {"bg": "#1a1a2e", "surface": "#16213e", "text": "#e8e8e8", "accent": "#ff6b6b", "secondary": "#feca57"},
    "minimal": {"bg": "#fafafa", "surface": "#ffffff", "text": "#333333", "accent": "#333333", "secondary": "#999999"},
}


def generate_presentation_html(title, slides, theme_name="dark", business_name="", log=None):
    """Generate a full HTML presentation from slide data.

    slides: list of dicts with keys: title, content, layout, notes
    """
    theme = THEMES.get(theme_name, THEMES["dark"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    slides_html = ""
    for i, slide in enumerate(slides):
        slide_title = slide.get("title", f"Slayt {i + 1}")
        content = slide.get("content", "")
        layout = slide.get("layout", "content")

        if isinstance(content, list):
            content_html = "<ul>" + "".join(f"<li>{item}</li>" for item in content) + "</ul>"
        else:
            content_html = f"<p>{content}</p>"

        slides_html += f"""
<div class="slide" id="slide-{i}">
    <h2>{slide_title}</h2>
    <div class="slide-content">{content_html}</div>
    <div class="slide-number">{i + 1} / {len(slides)}</div>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: {theme['bg']}; color: {theme['text']}; overflow: hidden; }}
.slide {{ width: 100vw; height: 100vh; display: none; flex-direction: column; justify-content: center; padding: 80px; position: relative; }}
.slide.active {{ display: flex; }}
.slide h2 {{ font-size: 2.8em; color: {theme['accent']}; margin-bottom: 30px; }}
.slide-content {{ font-size: 1.4em; line-height: 2; }}
.slide-content ul {{ list-style: none; padding: 0; }}
.slide-content ul li {{ padding: 8px 0; }}
.slide-content ul li::before {{ content: "→ "; color: {theme['accent']}; }}
.slide-number {{ position: absolute; bottom: 30px; right: 40px; font-size: 0.9em; color: {theme['secondary']}; opacity: 0.6; }}
.controls {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); display: flex; gap: 15px; z-index: 100; }}
.controls button {{ padding: 10px 25px; background: {theme['accent']}; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 1em; }}
.controls button:hover {{ opacity: 0.85; }}
.progress {{ position: fixed; top: 0; left: 0; height: 3px; background: {theme['accent']}; transition: width 0.3s; }}
</style>
</head>
<body>

<div class="progress" id="progress"></div>
{slides_html}
<div class="controls">
    <button onclick="prevSlide()">← Önceki</button>
    <button onclick="nextSlide()">Sonraki →</button>
</div>

<script>
let current = 0;
const slides = document.querySelectorAll('.slide');
const progress = document.getElementById('progress');

function showSlide(n) {{
    slides.forEach(s => s.classList.remove('active'));
    current = Math.max(0, Math.min(n, slides.length - 1));
    slides[current].classList.add('active');
    progress.style.width = ((current + 1) / slides.length * 100) + '%';
}}

function nextSlide() {{ showSlide(current + 1); }}
function prevSlide() {{ showSlide(current - 1); }}

document.addEventListener('keydown', e => {{
    if (e.key === 'ArrowRight' || e.key === ' ') nextSlide();
    if (e.key === 'ArrowLeft') prevSlide();
    if (e.key === 'f') document.documentElement.requestFullscreen?.();
}});

showSlide(0);
</script>
</body>
</html>"""

    out_dir = OUTPUT_DIR / "presentations"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = title.lower().replace(" ", "_")[:30]
    path = out_dir / f"{timestamp}_{slug}.html"

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    if log:
        log(f"Presentation saved: {path}")

    return str(path)


def list_presentations(log=None):
    """List all generated presentations."""
    pres_dir = OUTPUT_DIR / "presentations"
    if not pres_dir.exists():
        return []

    files = sorted(pres_dir.glob("*.html"), reverse=True)
    result = []
    for f in files:
        result.append({
            "filename": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
        })
    return result
