from pathlib import Path

_SHAPES_DIR = Path(__file__).parent.parent / "assets" / "shapes"

_SHAPE_STYLES: dict[str, str] = {
    "dot-grid-corner":  "position:absolute;top:0;right:0;width:120px;height:120px;pointer-events:none;z-index:0;",
    "circle-glow":      "position:absolute;top:-40px;right:-40px;width:200px;height:200px;pointer-events:none;z-index:0;",
    "diagonal-lines":   "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;",
    "hexagon-cluster":  "position:absolute;bottom:-20px;right:-20px;width:160px;height:160px;pointer-events:none;z-index:0;",
    "arrow-curved":     "position:absolute;bottom:60px;right:36px;width:80px;height:80px;pointer-events:none;z-index:0;",
    "wave-bottom":      "position:absolute;bottom:0;left:0;width:100%;height:60px;pointer-events:none;z-index:0;",
}


def render_shape(shape_name: str, color: str = "currentColor") -> str:
    """Return an absolutely-positioned inline SVG decoration."""
    svg_path = _SHAPES_DIR / f"{shape_name}.svg"
    if not svg_path.exists():
        return ""
    raw = svg_path.read_text(encoding="utf-8").strip()
    style = _SHAPE_STYLES.get(shape_name, "position:absolute;pointer-events:none;z-index:0;")
    raw = raw.replace('stroke="currentColor"', f'stroke="{color}"')
    raw = raw.replace('fill="currentColor"', f'fill="{color}"')
    return f'<div style="{style}">{raw}</div>'


def render_decorations(shapes: list[str], color: str = "currentColor") -> str:
    """Render up to 1 shape decoration (enforce limit)."""
    parts = [render_shape(name, color) for name in shapes[:1] if name]
    return "".join(parts)
