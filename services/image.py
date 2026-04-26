"""fal.ai image service — generates images for proposals, ads, and content."""

import os
import json
import requests
from pathlib import Path

FAL_KEY = os.getenv("FAL_KEY", "")
BASE_DIR = Path(__file__).parent.parent
DATA_BASE = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))
OUTPUTS_BASE = Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))
OUTPUT_DIR = OUTPUTS_BASE / "creatives"


def get_key():
    """Get fal.ai key from env or config."""
    if FAL_KEY:
        return FAL_KEY
    config_path = DATA_BASE / "config" / "user_profile.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
            return cfg.get("fal_key", "")
    return ""


def generate_image(prompt, size="landscape_16_9", model="fal-ai/nano-banana-2", filename=None):
    """Generate an image via fal.ai. Returns local file path or None."""
    key = get_key()
    if not key:
        return None

    try:
        resp = requests.post(
            f"https://queue.fal.run/{model}",
            headers={
                "Authorization": f"Key {key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "image_size": size,
                "num_images": 1,
                "num_inference_steps": 25,
                "guidance_scale": 7.5,
                "enable_safety_checker": True,
            },
            timeout=60,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        images = data.get("images", [])
        if not images:
            return None

        # Cost attribution — record against active ticket's cost context
        try:
            from core.cost_tracker import record
            kind = "fal.image.flux" if "flux" in (model or "").lower() else "fal.image.sdxl"
            record(kind, units=len(images), meta={"model": model, "size": size})
        except Exception:
            pass

        image_url = images[0].get("url")
        if not image_url:
            return None

        # Download image
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        fname = filename or f"generated_{hash(prompt) % 100000}.png"
        out_path = OUTPUT_DIR / fname

        img_resp = requests.get(image_url, timeout=30)
        if img_resp.status_code == 200:
            with open(out_path, "wb") as f:
                f.write(img_resp.content)
            return str(out_path)

        return None
    except Exception:
        return None


def generate_ad_creative(business_name, business_type, service, style="modern"):
    """Generate an ad creative for a specific business/service."""
    prompt = (
        f"Professional digital marketing ad creative for {business_type} business. "
        f"Clean, modern design. Service: {service}. "
        f"Minimalist style, dark background, orange and white accent colors. "
        f"No text, no letters, no words. Abstract business automation concept. "
        f"Professional, premium feel. {style} aesthetic."
    )
    fname = f"ad_{business_type}_{hash(business_name) % 10000}.png"
    return generate_image(prompt, filename=fname)


def generate_proposal_cover(agency_name, client_name, business_type):
    """Generate a proposal cover image."""
    prompt = (
        f"Professional business proposal cover design. Abstract geometric shapes. "
        f"Dark elegant background with orange and gold accents. "
        f"Corporate, premium, trustworthy feel. "
        f"No text, no letters, no words. "
        f"Industry: {business_type}. Modern minimalist style."
    )
    fname = f"proposal_{hash(client_name) % 10000}.png"
    return generate_image(prompt, filename=fname)


def generate_social_example(business_type, platform="instagram"):
    """Generate example social media content for a business type."""
    prompt = (
        f"Professional {platform} post design for {business_type}. "
        f"Eye-catching, scroll-stopping visual. "
        f"Modern, clean layout. Warm colors. Food photography style if restaurant. "
        f"No text, no letters, no words. Visual content only. "
        f"High quality, professional photography feel."
    )
    fname = f"social_{business_type}_{platform}_{hash(prompt) % 10000}.png"
    return generate_image(prompt, size="square", filename=fname)
