"""Voice → text transcription for CEO chat.

Two paths:
    1. fal.ai whisper-large-v3 (preferred — falls under existing FAL_KEY)
    2. OpenAI whisper-1 if OPENAI_API_KEY set
    3. Local ffmpeg+whisper.cpp (only if explicitly enabled, off by default)

Front-end records WebM/Opus from MediaRecorder, POSTs blob to
/api/ceo/voice, we forward upstream and return {text, provider}.
"""

import io
import os
from typing import Optional

import requests

from core import cost_tracker


def _fal_token() -> Optional[str]:
    return os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")


def _openai_token() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def transcribe(audio_bytes: bytes, mime: str = "audio/webm") -> dict:
    """Returns {text, provider, error?}. Tries providers in order."""
    if not audio_bytes or len(audio_bytes) < 200:
        return {"text": "", "error": "audio too small"}

    if _fal_token():
        result = _via_fal(audio_bytes, mime)
        if result.get("text"):
            return result

    if _openai_token():
        result = _via_openai(audio_bytes, mime)
        if result.get("text"):
            return result

    return {"text": "", "error": "no transcription provider configured (set FAL_KEY or OPENAI_API_KEY)"}


def _via_fal(audio_bytes: bytes, mime: str) -> dict:
    """fal.ai whisper-large-v3 — uploads to fal storage then runs model."""
    token = _fal_token()
    try:
        up = requests.post(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            headers={"Authorization": f"Key {token}", "Content-Type": "application/json"},
            json={"file_name": "voice.webm", "content_type": mime},
            timeout=15,
        )
        if up.status_code >= 400:
            return {"error": f"fal upload init {up.status_code}"}
        upload_meta = up.json()
        put_url = upload_meta["upload_url"]
        file_url = upload_meta["file_url"]
        put = requests.put(put_url, data=audio_bytes, headers={"Content-Type": mime}, timeout=30)
        if put.status_code >= 400:
            return {"error": f"fal put {put.status_code}"}
        run = requests.post(
            "https://fal.run/fal-ai/whisper",
            headers={"Authorization": f"Key {token}", "Content-Type": "application/json"},
            json={"audio_url": file_url, "task": "transcribe", "language": "tr"},
            timeout=60,
        )
        if run.status_code >= 400:
            return {"error": f"fal whisper {run.status_code}"}
        data = run.json() or {}
        cost_tracker.record("fal.whisper.run", units=1.0)
        return {"text": data.get("text", "").strip(), "provider": "fal/whisper"}
    except Exception as e:
        return {"error": str(e)}


def _via_openai(audio_bytes: bytes, mime: str) -> dict:
    token = _openai_token()
    try:
        files = {"file": ("voice.webm", io.BytesIO(audio_bytes), mime)}
        data = {"model": "whisper-1", "language": "tr"}
        r = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
            timeout=60,
        )
        if r.status_code >= 400:
            return {"error": f"openai {r.status_code}: {r.text[:200]}"}
        cost_tracker.record("openai.whisper.minute", units=1.0)
        return {"text": (r.json() or {}).get("text", "").strip(), "provider": "openai/whisper-1"}
    except Exception as e:
        return {"error": str(e)}
