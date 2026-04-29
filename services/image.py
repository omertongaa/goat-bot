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
    """Get fal.ai key from env, active company schema, or legacy config."""
    # 1) Process env (FAL_KEY captured at module load) or current env
    key = FAL_KEY or os.getenv("FAL_KEY", "").strip()
    if key:
        return key
    # 2) Active company schema (preferred path on multi-company)
    try:
        from core import store
        company = store.load_company(store.active_company_id()) or {}
        api_keys = company.get("api_keys") or {}
        if api_keys.get("fal_key"):
            return api_keys["fal_key"]
    except Exception:
        pass
    # 3) Legacy config file
    config_path = DATA_BASE / "config" / "user_profile.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = json.load(f)
                return cfg.get("fal_key") or cfg.get("api_keys", {}).get("fal_key", "")
        except Exception:
            pass
    return ""


def _poll_image_queue(status_url, result_url, key, max_polls=30, interval=2):
    """Poll fal.ai queue for an image job using URLs from initial response."""
    import time
    for _ in range(max_polls):
        try:
            r = requests.get(status_url, headers={"Authorization": f"Key {key}"}, timeout=15)
            if r.status_code == 200:
                s = r.json().get("status", "")
                if s == "COMPLETED":
                    rr = requests.get(result_url, headers={"Authorization": f"Key {key}"}, timeout=20)
                    if rr.status_code == 200:
                        return rr.json()
                    return None
                if s in ("FAILED", "CANCELED", "ERROR"):
                    return None
        except Exception:
            pass
        time.sleep(interval)
    return None


def generate_image(prompt, size="landscape_16_9", model=None, filename=None):
    """Generate an image via fal.ai. Returns local file path or None.

    Default model is `fal-ai/nano-banana-2` (Google Gemini 2.5 Flash Image,
    queue-based, ~$0.04/image). FAL_IMAGE_MODEL env override edebilir.
    fal_client SDK kullanır — yeni modellerin sub-path mismatch sorunlarını
    otomatik çözer."""
    key = get_key()
    if not key:
        return None

    if not model:
        model = os.getenv("FAL_IMAGE_MODEL", "fal-ai/nano-banana-2")

    os.environ["FAL_KEY"] = key
    try:
        import fal_client
    except ImportError:
        return None

    # Build model-specific payload
    payload = {"prompt": prompt}
    if "schnell" in model or "flux" in model:
        payload.update({"image_size": size, "num_images": 1, "num_inference_steps": 4})
    elif "nano-banana" in model:
        ar = "16:9" if "landscape" in size else "9:16" if "portrait" in size else "1:1"
        payload.update({"aspect_ratio": ar, "num_images": 1})
    else:
        payload.update({"image_size": size, "num_images": 1})

    try:
        data = fal_client.subscribe(model, arguments=payload, with_logs=False)
        if not isinstance(data, dict):
            return None
        images = data.get("images") or []
        if not images or not isinstance(images[0], dict):
            return None
        image_url = images[0].get("url")
        if not image_url:
            return None

        # Cost attribution
        try:
            from core.cost_tracker import record
            if "nano-banana" in model:
                kind = "fal.image.nano_banana"
            elif "flux" in model:
                kind = "fal.image.flux"
            else:
                kind = "fal.image.other"
            record(kind, units=len(images), meta={"model": model, "size": size})
        except Exception:
            pass

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
    except Exception as e:
        # Silent fallback — caller decides what to do with None
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
