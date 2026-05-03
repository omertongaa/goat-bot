from pathlib import Path

_ICONS_DIR = Path(__file__).parent.parent / "assets" / "icons"


def render_icon_badge(icon_name: str, color: str = "currentColor", size: int = 20) -> str:
    """Return inline SVG for a named icon, styled as a small accent badge."""
    svg_path = _ICONS_DIR / f"{icon_name}.svg"
    if not svg_path.exists():
        return ""
    raw = svg_path.read_text(encoding="utf-8").strip()
    # Inject size and color overrides into the root <svg> tag
    raw = raw.replace('width="24"', f'width="{size}"').replace('height="24"', f'height="{size}"')
    raw = raw.replace('stroke="currentColor"', f'stroke="{color}"')
    return f'<span class="icon-badge" style="display:inline-flex;align-items:center;vertical-align:middle;">{raw}</span>'


def render_icon_row(icons: list[str], color: str = "currentColor", size: int = 18) -> str:
    """Render a horizontal row of icon badges (max 2)."""
    badges = [render_icon_badge(name, color, size) for name in icons[:2] if name]
    if not badges:
        return ""
    inner = "".join(badges)
    return (
        f'<div class="icon-row" style="display:flex;gap:8px;align-items:center;margin-bottom:8px;">'
        f'{inner}'
        f'</div>'
    )
