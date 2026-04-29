"""fal.ai Kling video service — gerçek MP4 üretimi.

Bir sahne listesinden:
1. Her sahne için 5s/10s Kling 2 master text-to-video çağırır
2. Tüm clip'leri imageio-ffmpeg ile concat eder
3. outputs/videos/ altına final MP4 yazar

Maliyet kontrolü: HARD_CAP_CLIPS varsayılanı 4 → max ~$2/run.
"""

import os
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional

import requests

BASE_DIR = Path(__file__).parent.parent
OUTPUTS_BASE = Path(os.getenv("GOAT_OUTPUTS_DIR") or (BASE_DIR / "outputs"))
VIDEOS_DIR = OUTPUTS_BASE / "videos"

# Seedance 2.0 (ByteDance) — kullanıcı tercihi. ~2-3dk/clip, ~$0.30-0.50/5s.
# Path: NO `fal-ai/` prefix → `bytedance/seedance-2.0/text-to-video`.
FAL_VIDEO_MODEL = os.getenv("FAL_VIDEO_MODEL", "bytedance/seedance-2.0/text-to-video")
FAL_QUEUE_BASE = "https://queue.fal.run"
FAL_POLL_INTERVAL = 6
FAL_MAX_POLLS = 50   # ~5 dk — Seedance için yeterli
HARD_CAP_CLIPS = 3   # Maliyet limiti — her clip ~$0.30-0.50


def _get_key() -> str:
    key = os.getenv("FAL_KEY", "").strip()
    if key:
        return key
    # Fallback: read from active company config if available
    try:
        from core import store
        company = store.load_company(store.active_company_id()) or {}
        return (company.get("api_keys") or {}).get("fal_key", "")
    except Exception:
        return ""


def _get_ffmpeg() -> Optional[str]:
    """Return path to a usable ffmpeg binary, or None if unavailable."""
    # System ffmpeg
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    # imageio-ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _build_payload(prompt: str, ratio: str, duration: str) -> dict:
    """Model-specific payload."""
    payload = {"prompt": prompt[:1500], "aspect_ratio": ratio}
    if "seedance" in FAL_VIDEO_MODEL:
        payload["duration"] = str(duration)
        payload["resolution"] = os.getenv("SEEDANCE_RESOLUTION", "1080p")
    elif "kling" in FAL_VIDEO_MODEL:
        payload["duration"] = str(duration)
    elif "minimax" in FAL_VIDEO_MODEL:
        payload["prompt_optimizer"] = True
    return payload


def _run_clip_via_sdk(prompt: str, ratio: str, duration: str, key: str, log=None) -> Optional[str]:
    """fal_client SDK ile submit + poll + result al — sub-path'leri otomatik handle eder.
    Returns video URL or None."""
    try:
        import fal_client
    except ImportError:
        if log:
            log("fal_client kurulu değil — pip install fal-client")
        return None

    # Set FAL_KEY in env (fal_client expects it)
    os.environ["FAL_KEY"] = key

    payload = _build_payload(prompt, ratio, duration)
    try:
        if log:
            log(f"  → fal.ai {FAL_VIDEO_MODEL} (subscribe)")

        # Use submit + status_handler for log streaming
        result = fal_client.subscribe(
            FAL_VIDEO_MODEL,
            arguments=payload,
            with_logs=False,
        )
        if not isinstance(result, dict):
            return None
        video = result.get("video")
        if isinstance(video, dict):
            return video.get("url")
        # Some models return video as direct URL string or videos array
        if isinstance(video, str):
            return video
        videos = result.get("videos")
        if isinstance(videos, list) and videos:
            v0 = videos[0]
            if isinstance(v0, dict):
                return v0.get("url")
            if isinstance(v0, str):
                return v0
        if log:
            log(f"  fal.ai response: video URL bulunamadı → keys: {list(result.keys())}")
    except Exception as e:
        if log:
            log(f"  fal.ai subscribe hatası: {str(e)[:200]}")
    return None


def _download(url: str, dest: Path, log=None) -> bool:
    try:
        r = requests.get(url, timeout=120, stream=True)
        if r.status_code != 200:
            if log:
                log(f"  download failed {r.status_code} for {url[:80]}")
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as e:
        if log:
            log(f"  download exception: {e}")
        return False


def _concat_clips(clip_paths: List[Path], output: Path, ffmpeg: str, log=None) -> bool:
    """Concat clips with re-encoding (Kling outputs may differ in codec/fps)."""
    if not clip_paths:
        return False
    if len(clip_paths) == 1:
        # Single clip — just copy
        try:
            shutil.copy2(str(clip_paths[0]), str(output))
            return True
        except Exception as e:
            if log:
                log(f"copy failed: {e}")
            return False

    # Use concat demuxer with re-encode for safety
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_file = f.name
        for p in clip_paths:
            f.write(f"file '{p.absolute()}'\n")

    try:
        cmd = [
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output),
        ]
        if log:
            log(f"ffmpeg concat: {len(clip_paths)} clip → {output.name}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            if log:
                log(f"ffmpeg failed: {result.stderr[-400:]}")
            return False
        return output.exists() and output.stat().st_size > 0
    finally:
        try:
            os.unlink(list_file)
        except Exception:
            pass


def make_video_from_scenes(scenes: list, topic: str, slug: str, timestamp: str,
                            ratio: str = "16:9", duration: str = "5",
                            max_clips: int = HARD_CAP_CLIPS, log=None) -> Optional[dict]:
    """Ana giriş noktası.
    Sahne listesinden gerçek MP4 üret.

    Returns: {"mp4_path": "...", "clips": [...], "total_seconds": N} or None.
    """
    key = _get_key()
    if not key:
        if log:
            log("fal.ai key bulunamadı — gerçek video üretimi atlandı")
        return None

    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        if log:
            log("ffmpeg bulunamadı — concat yapılamaz")
        return None

    # Pick scenes that have a videoPrompt and aren't title/end cards
    candidate = [s for s in scenes
                 if s.get("videoPrompt") and s.get("type") not in ("titleCard", "endCard")]
    if not candidate:
        if log:
            log("Video üretimi için uygun sahne yok (videoPrompt boş)")
        return None

    # Cost cap — cap clips to keep budget under control
    chosen = candidate[:max(1, min(max_clips, HARD_CAP_CLIPS))]
    if log:
        log(f"fal.ai Kling: {len(chosen)} clip üretilecek (~${len(chosen) * 0.5:.2f})")

    # 1+2) Submit each scene via fal_client SDK (handles sub-paths correctly)
    #      Run in parallel via threads to keep total wall-time low.
    clip_dir = VIDEOS_DIR / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _produce_one(idx, scene):
        url = _run_clip_via_sdk(scene["videoPrompt"], ratio, duration, key, log)
        if not url:
            return None
        clip_path = clip_dir / f"{timestamp}_{slug}_clip{idx + 1}.mp4"
        if _download(url, clip_path, log):
            try:
                from core.cost_tracker import record
                kind = ("fal.video.seedance" if "seedance" in FAL_VIDEO_MODEL
                        else "fal.video.kling" if "kling" in FAL_VIDEO_MODEL
                        else "fal.video")
                record(kind, units=1, meta={"scene_idx": idx, "duration": duration})
            except Exception:
                pass
            return (idx, clip_path)
        return None

    downloaded_pairs = []
    with ThreadPoolExecutor(max_workers=len(chosen)) as pool:
        futures = [pool.submit(_produce_one, i, sc) for i, sc in enumerate(chosen)]
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                downloaded_pairs.append(res)

    # Order by scene index so concat is deterministic
    downloaded_pairs.sort(key=lambda x: x[0])
    downloaded = [p for _, p in downloaded_pairs]

    if not downloaded:
        if log:
            log("Hiçbir clip indirilemedi")
        return None

    # 3) Concat
    final = VIDEOS_DIR / f"{timestamp}_{slug}.mp4"
    ok = _concat_clips(downloaded, final, ffmpeg, log)
    if not ok:
        return None

    return {
        "mp4_path": str(final),
        "clip_paths": [str(p) for p in downloaded],
        "clips_count": len(downloaded),
        "total_seconds": int(duration) * len(downloaded) if duration.isdigit() else len(downloaded) * 5,
    }
