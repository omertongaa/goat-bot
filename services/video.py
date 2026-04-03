"""Video content service — script templates, storyboard generation, format presets."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"


# Video format specifications for different platforms
FORMAT_SPECS = {
    "instagram_reel": {"width": 1080, "height": 1920, "fps": 30, "max_duration": 90, "ratio": "9:16"},
    "instagram_feed": {"width": 1080, "height": 1080, "fps": 30, "max_duration": 60, "ratio": "1:1"},
    "instagram_story": {"width": 1080, "height": 1920, "fps": 30, "max_duration": 15, "ratio": "9:16"},
    "tiktok": {"width": 1080, "height": 1920, "fps": 30, "max_duration": 180, "ratio": "9:16"},
    "youtube": {"width": 1920, "height": 1080, "fps": 30, "max_duration": 7200, "ratio": "16:9"},
    "youtube_short": {"width": 1080, "height": 1920, "fps": 30, "max_duration": 60, "ratio": "9:16"},
    "facebook_feed": {"width": 1280, "height": 720, "fps": 30, "max_duration": 240, "ratio": "16:9"},
    "linkedin": {"width": 1920, "height": 1080, "fps": 30, "max_duration": 600, "ratio": "16:9"},
    "twitter": {"width": 1280, "height": 720, "fps": 30, "max_duration": 140, "ratio": "16:9"},
    "ad_horizontal": {"width": 1920, "height": 1080, "fps": 30, "max_duration": 30, "ratio": "16:9"},
    "ad_vertical": {"width": 1080, "height": 1920, "fps": 30, "max_duration": 30, "ratio": "9:16"},
    "ad_square": {"width": 1080, "height": 1080, "fps": 30, "max_duration": 30, "ratio": "1:1"},
}


# Script templates for common video types
SCRIPT_TEMPLATES = {
    "hook_story_cta": {
        "name": "Hook → Story → CTA",
        "structure": [
            {"section": "hook", "duration": "0-3s", "purpose": "Dikkat çek — soru veya şok edici bilgi"},
            {"section": "problem", "duration": "3-8s", "purpose": "İzleyicinin acı noktasını anlat"},
            {"section": "solution", "duration": "8-18s", "purpose": "Çözümü göster — nasıl yardım ediyorsun"},
            {"section": "proof", "duration": "18-25s", "purpose": "Sosyal kanıt — sonuçlar, sayılar"},
            {"section": "cta", "duration": "25-30s", "purpose": "Harekete geç — takip et, link, DM"},
        ],
    },
    "listicle": {
        "name": "Listicle (Numara + İpucu)",
        "structure": [
            {"section": "intro", "duration": "0-3s", "purpose": "X şeyi bilmelisiniz..."},
            {"section": "tip_1", "duration": "3-10s", "purpose": "1. ipucu + açıklama"},
            {"section": "tip_2", "duration": "10-17s", "purpose": "2. ipucu + açıklama"},
            {"section": "tip_3", "duration": "17-24s", "purpose": "3. ipucu + açıklama"},
            {"section": "cta", "duration": "24-30s", "purpose": "Kaydet + takip et"},
        ],
    },
    "before_after": {
        "name": "Before / After",
        "structure": [
            {"section": "before", "duration": "0-5s", "purpose": "Önceki durum — problem"},
            {"section": "transition", "duration": "5-8s", "purpose": "Geçiş efekti"},
            {"section": "after", "duration": "8-15s", "purpose": "Sonraki durum — çözüm"},
            {"section": "how", "duration": "15-25s", "purpose": "Nasıl yapıldı — kısa açıklama"},
            {"section": "cta", "duration": "25-30s", "purpose": "Sen de istiyorsan..."},
        ],
    },
    "tutorial": {
        "name": "Hızlı Tutorial",
        "structure": [
            {"section": "intro", "duration": "0-3s", "purpose": "Bugün X yapmayı öğreneceksiniz"},
            {"section": "step_1", "duration": "3-10s", "purpose": "Adım 1 — ekran kaydı/demo"},
            {"section": "step_2", "duration": "10-17s", "purpose": "Adım 2"},
            {"section": "step_3", "duration": "17-24s", "purpose": "Adım 3"},
            {"section": "result", "duration": "24-30s", "purpose": "Sonuç + CTA"},
        ],
    },
    "testimonial": {
        "name": "Müşteri Testimonial",
        "structure": [
            {"section": "intro", "duration": "0-5s", "purpose": "Müşteri tanıtım"},
            {"section": "problem", "duration": "5-15s", "purpose": "Yaşadığı problem"},
            {"section": "solution", "duration": "15-25s", "purpose": "Nasıl çözüldü"},
            {"section": "result", "duration": "25-35s", "purpose": "Sonuçlar + tavsiye"},
        ],
    },
}


def get_format_spec(platform_format):
    """Get video format specifications."""
    return FORMAT_SPECS.get(platform_format, FORMAT_SPECS["instagram_reel"])


def get_script_template(template_name):
    """Get a script template structure."""
    return SCRIPT_TEMPLATES.get(template_name, SCRIPT_TEMPLATES["hook_story_cta"])


def list_formats():
    """List all available video formats."""
    return FORMAT_SPECS


def list_templates():
    """List all available script templates."""
    return {k: v["name"] for k, v in SCRIPT_TEMPLATES.items()}


def generate_shot_list(scenes, business_name="", log=None):
    """Generate a detailed shot list from scene descriptions."""
    shots = []
    for i, scene in enumerate(scenes, 1):
        shot = {
            "shot_number": i,
            "scene": scene.get("section", f"Sahne {i}"),
            "duration": scene.get("duration", "3-5s"),
            "description": scene.get("purpose", ""),
            "camera": "Medium shot" if i % 2 == 0 else "Close up",
            "audio": "Voiceover" if i < len(scenes) else "Music + voiceover",
            "text_overlay": scene.get("purpose", "")[:50],
        }
        shots.append(shot)

    if log:
        log(f"Generated {len(shots)} shots")
    return shots


def save_video_project(project_data, log=None):
    """Save a video project to disk."""
    out_dir = DATA_DIR / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = project_data.get("title", "untitled").lower().replace(" ", "_")[:30]
    path = out_dir / f"{timestamp}_{slug}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False, default=str)

    if log:
        log(f"Video project saved: {path}")
    return str(path)
