"""fal.ai dynamic model discovery.

fal.ai has 600+ models. Hardcoding model IDs ages badly. This service
hits fal's catalog API + caches the result, exposes search by category
(image, video, audio, transcribe), and returns the curated set of
"production-ready" models the goat-bot agents pre-select from.

Cache lives in data/fal_models.json with a 24h TTL.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests


CACHE_PATH = Path(os.getenv("GOAT_DATA_DIR") or (Path(__file__).resolve().parent.parent / "data")) / "fal_models.json"
CACHE_TTL = 24 * 3600

# Curated short-list — agents default to these unless user overrides
CURATED = {
    "image": [
        "fal-ai/flux/schnell",
        "fal-ai/flux/dev",
        "fal-ai/fast-sdxl",
        "fal-ai/recraft-v3",
        "fal-ai/nano-banana-2",
    ],
    "video": [
        "fal-ai/kling-video/v2/master/text-to-video",
        "fal-ai/seedance/v2/pro/text-to-video",
        "fal-ai/runway-gen3/turbo/image-to-video",
    ],
    "audio": [
        "fal-ai/elevenlabs/tts/multilingual-v2",
        "fal-ai/playht/v3",
    ],
    "transcribe": [
        "fal-ai/whisper",
    ],
    "upscale": [
        "fal-ai/topaz/upscale/video",
        "fal-ai/aura-sr",
    ],
}


def _read_cache() -> Optional[dict]:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text())
        if time.time() - data.get("_cached_at", 0) > CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _write_cache(data: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data["_cached_at"] = int(time.time())
        CACHE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        pass


def list_models(category: Optional[str] = None, force_refresh: bool = False) -> dict:
    """Return curated + (where possible) live discovery.

    fal.ai doesn't have a stable public catalog endpoint, so we ship a
    curated list and let the user inspect cached results. force_refresh
    re-pings their docs feed to surface new models.
    """
    if not force_refresh:
        cached = _read_cache()
        if cached:
            if category:
                return {"category": category, "models": cached.get(category, [])}
            return cached

    data = {k: list(v) for k, v in CURATED.items()}
    token = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if token:
        try:
            r = requests.get(
                "https://fal.ai/api/models",
                headers={"Authorization": f"Key {token}"},
                timeout=8,
            )
            if r.status_code == 200:
                live = r.json()
                if isinstance(live, list):
                    data["_live_count"] = len(live)
                    for m in live[:300]:
                        cat = (m.get("category") or "").lower()
                        slug = m.get("slug") or m.get("id") or ""
                        if not slug:
                            continue
                        bucket = data.setdefault(cat or "other", [])
                        if slug not in bucket:
                            bucket.append(slug)
        except Exception:
            pass

    _write_cache(data)
    if category:
        return {"category": category, "models": data.get(category, [])}
    return data


def search(query: str) -> list:
    """Substring match across cached models."""
    data = list_models()
    q = query.lower()
    out = []
    for cat, models in data.items():
        if cat.startswith("_"):
            continue
        for m in models or []:
            if q in m.lower():
                out.append({"category": cat, "model": m})
    return out[:50]


def recommend_for(use_case: str) -> dict:
    """Pick the best curated model for a use case."""
    rules = {
        "social_post": "fal-ai/flux/schnell",
        "ad_creative": "fal-ai/flux/dev",
        "product_render": "fal-ai/recraft-v3",
        "tts_turkish": "fal-ai/elevenlabs/tts/multilingual-v2",
        "voice_input": "fal-ai/whisper",
        "ad_video": "fal-ai/kling-video/v2/master/text-to-video",
        "product_video": "fal-ai/seedance/v2/pro/text-to-video",
        "image_animation": "fal-ai/runway-gen3/turbo/image-to-video",
        "video_upscale": "fal-ai/topaz/upscale/video",
    }
    return {"use_case": use_case, "model": rules.get(use_case, "")}
