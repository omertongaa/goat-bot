"""Brand service — color palette generation, typography, brand guidelines."""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"


# Industry-specific color palettes
INDUSTRY_PALETTES = {
    "teknoloji": {"primary": "#6c5ce7", "secondary": "#00cec9", "accent": "#fd79a8", "bg": "#0a0a0c", "text": "#dfe6e9"},
    "sağlık": {"primary": "#00b894", "secondary": "#0984e3", "accent": "#6c5ce7", "bg": "#ffffff", "text": "#2d3436"},
    "eğitim": {"primary": "#0984e3", "secondary": "#00cec9", "accent": "#fdcb6e", "bg": "#f5f7fa", "text": "#2d3436"},
    "finans": {"primary": "#0066cc", "secondary": "#003366", "accent": "#00cc66", "bg": "#f5f7fa", "text": "#1a1a1a"},
    "restoran": {"primary": "#e85d26", "secondary": "#ff7a45", "accent": "#ffeaa7", "bg": "#fdf6f0", "text": "#2c3e50"},
    "moda": {"primary": "#2d2d2d", "secondary": "#666666", "accent": "#e85d26", "bg": "#ffffff", "text": "#1a1a1a"},
    "emlak": {"primary": "#0066cc", "secondary": "#003366", "accent": "#ffa500", "bg": "#f8f9fa", "text": "#1a1a1a"},
    "hukuk": {"primary": "#1a237e", "secondary": "#283593", "accent": "#c5cae9", "bg": "#fafafa", "text": "#212121"},
    "spor": {"primary": "#e74c3c", "secondary": "#2c3e50", "accent": "#f1c40f", "bg": "#ecf0f1", "text": "#2c3e50"},
    "güzellik": {"primary": "#e84393", "secondary": "#fd79a8", "accent": "#ffeaa7", "bg": "#fff5f5", "text": "#2c3e50"},
    "dijital pazarlama": {"primary": "#e85d26", "secondary": "#1a1a2e", "accent": "#00ff41", "bg": "#fafafa", "text": "#1a1a1a"},
}

# Font pairings
FONT_PAIRINGS = {
    "modern": {"heading": "Poppins", "body": "Inter", "accent": "Space Grotesk"},
    "classic": {"heading": "Playfair Display", "body": "Lora", "accent": "Source Serif Pro"},
    "minimal": {"heading": "DM Sans", "body": "IBM Plex Sans", "accent": "JetBrains Mono"},
    "bold": {"heading": "Montserrat", "body": "Open Sans", "accent": "Raleway"},
    "tech": {"heading": "Space Grotesk", "body": "Inter", "accent": "JetBrains Mono"},
    "friendly": {"heading": "Nunito", "body": "Quicksand", "accent": "Comfortaa"},
    "corporate": {"heading": "Roboto Slab", "body": "Roboto", "accent": "Roboto Condensed"},
}


def get_palette_for_industry(industry, log=None):
    """Get a recommended color palette for an industry."""
    industry_lower = industry.lower()
    for key, palette in INDUSTRY_PALETTES.items():
        if key in industry_lower:
            if log:
                log(f"Found palette for: {key}")
            return palette

    # Default palette
    if log:
        log("Using default palette")
    return INDUSTRY_PALETTES["dijital pazarlama"]


def get_font_pairing(style="modern", log=None):
    """Get a recommended font pairing for a style."""
    pairing = FONT_PAIRINGS.get(style, FONT_PAIRINGS["modern"])
    if log:
        log(f"Font pairing: {pairing['heading']} / {pairing['body']}")
    return pairing


def generate_brand_colors(base_color, log=None):
    """Generate a full color palette from a base color."""
    # Simple color derivation (in production, use colormath)
    # For now return a preset based on the base
    return {
        "primary": base_color,
        "primary_light": base_color + "33",
        "primary_dark": base_color,
        "secondary": "#1a1a2e",
        "accent": "#00ff41",
        "success": "#34d399",
        "warning": "#fbbf24",
        "error": "#ef4444",
        "background": "#fafafa",
        "surface": "#ffffff",
        "text": "#1a1a1a",
        "text_muted": "#8a8a98",
    }


def generate_css_variables(colors, fonts=None, log=None):
    """Generate CSS custom properties from brand colors and fonts."""
    if fonts is None:
        fonts = FONT_PAIRINGS["modern"]

    css = ":root {\n"
    for key, value in colors.items():
        css += f"  --brand-{key.replace('_', '-')}: {value};\n"
    css += f"  --font-heading: '{fonts['heading']}', sans-serif;\n"
    css += f"  --font-body: '{fonts['body']}', sans-serif;\n"
    css += f"  --font-accent: '{fonts['accent']}', monospace;\n"
    css += "}\n"

    if log:
        log("CSS variables generated")
    return css


def save_brand_kit(brand_data, log=None):
    """Save brand kit to disk."""
    out_dir = DATA_DIR / "brandkit"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{timestamp}_brand_kit.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(brand_data, f, indent=2, ensure_ascii=False, default=str)

    if log:
        log(f"Brand kit saved: {path}")
    return str(path)
