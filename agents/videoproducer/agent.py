"""VideoProducer Agent — AI video production pipeline using Kie.ai + ElevenLabs + Remotion."""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

from agents.base import BaseAgent, BASE_DIR, DATA_DIR, OUTPUT_DIR


class VideoProducerAgent(BaseAgent):
    agent_id = "videoproducer"
    name = "VideoProducer"
    role = "AI video production — generates scenes, TTS narration, and renders MP4 via Remotion"
    category = "production"

    # Remotion project path
    REMOTION_DIR = BASE_DIR / "Remotion-Video-main 2" / "my-video"
    SCRIPTS_DIR = BASE_DIR / "Remotion-Video-main 2" / "scripts"
    VIDEOS_DIR = REMOTION_DIR / "public" / "videos"
    AUDIO_DIR = REMOTION_DIR / "public" / "audio"

    # Kie.ai config
    KIE_API_URL = "https://api.kie.ai/api/v1/jobs"
    KIE_MODEL = "grok-imagine/text-to-video"
    KIE_POLL_INTERVAL = 10  # seconds
    KIE_MAX_POLLS = 60  # 10 minutes max

    # ElevenLabs config
    TTS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
    TTS_MODEL = "eleven_multilingual_v2"
    TTS_VOICE_SETTINGS = {"stability": 0.75, "similarity_boost": 0.85, "use_speaker_boost": True}

    # Scene types
    SCENE_TYPES = ["intro", "image", "titleCard", "endCard", "quote", "montage", "chapterDivider"]

    def run(self, action: str = "plan", topic: str = "", scenes: list = None,
            style: str = "cinematic", language: str = "tr", voice_id: str = "") -> dict:
        self.log("VideoProducer agent started")
        config = self.load_config()

        if not voice_id:
            voice_id = os.environ.get("ELEVENLABS_VOICE_ID", config.get("elevenlabs_voice_id", "MF3mGyEYCl7XYWbV9V6O"))

        business_name = config.get("agency_name", "My Agency")

        if action == "plan":
            return self._plan_video(topic, style, language, business_name)
        elif action == "generate":
            return self._generate_assets(scenes or [], voice_id)
        elif action == "render":
            return self._render_video()
        elif action == "full":
            return self._full_pipeline(topic, style, language, business_name, voice_id)
        elif action == "status":
            return self._check_status()
        else:
            return self._plan_video(topic, style, language, business_name)

    # ═══════════════════════════════════════
    # ACTION: plan — Create video storyboard
    # ═══════════════════════════════════════

    def _plan_video(self, topic, style, language, business_name):
        self.log(f"Planning video: {topic} | Style: {style}")

        lang = "Türkçe" if language == "tr" else "English"
        prompt = f"""Sen profesyonel bir video prodüktörüsün. AI video üretim pipeline'ı için storyboard oluştur.

Konu: {topic}
Stil: {style}
Dil: {lang}
İşletme: {business_name}

Her sahne için JSON formatında yaz:

```json
[
  {{
    "id": "1",
    "type": "intro",
    "videoPrompt": "Cinematic aerial drone shot of [detailed visual description], golden hour lighting, 4K quality",
    "narration": "{lang} anlatım metni (max 2 cümle, 6 saniyeye sığmalı)",
    "title": "Sahne başlığı",
    "needsVideo": true
  }},
  {{
    "id": "2",
    "type": "titleCard",
    "videoPrompt": "",
    "narration": "",
    "titleCardText": "ANA BAŞLIK",
    "needsVideo": false
  }},
  ...
]
```

Kurallar:
- 8-12 sahne oluştur
- İlk sahne "intro" türünde olmalı
- Son sahne "endCard" türünde olmalı
- Her sahne max 6 saniye video (Kie.ai limiti)
- Eğer narration 6 saniyeden uzunsa, continuation sahne (3b, 3c) ekle
- videoPrompt: İngilizce, çok detaylı, sinematik
- narration: {lang}, kısa ve etkili
- Scene types: intro, image, titleCard, endCard, quote, montage

Sadece JSON array döndür, başka metin yazma."""

        plan = self.call_claude(prompt)

        # Try to parse JSON from response
        scenes = self._extract_scenes_from_response(plan, topic, style)

        # Calculate estimated duration
        total_duration = len(scenes) * 6  # 6 sec per scene
        estimated_cost = self._estimate_cost(scenes)

        # Save plan
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = topic.lower().replace(" ", "_")[:30] if topic else "untitled"
        plan_data = {
            "topic": topic,
            "style": style,
            "language": language,
            "scenes": scenes,
            "total_scenes": len(scenes),
            "estimated_duration_sec": total_duration,
            "estimated_cost": estimated_cost,
            "raw_plan": plan,
            "created_at": timestamp,
        }

        self.save_data(f"video_productions/{timestamp}_{slug}_plan.json", plan_data)

        results = {
            "status": "ok",
            "summary": f"Video planı oluşturuldu: {topic} — {len(scenes)} sahne, ~{total_duration}s, ~${estimated_cost:.2f}",
            "metrics": {
                "scenes": len(scenes),
                "estimated_duration": f"{total_duration}s",
                "estimated_cost": f"${estimated_cost:.2f}",
                "style": style,
                "timestamp": datetime.now().isoformat(),
            },
            "plan": plan_data,
            "recommendations": [
                "Planı kontrol edin — sahne sırasını ve narration'ları gözden geçirin",
                "Narration 6 saniyeden uzunsa continuation sahne (3b, 3c) ekleyin",
                "videoPrompt'lar İngilizce ve detaylı olmalı",
                f"Tahmini maliyet: ${estimated_cost:.2f} (video + TTS)",
                "'generate' action ile video/ses üretimini başlatın",
            ],
        }

        self.save_output("videoproducer_report.json", results)
        self.log(f"Plan created: {len(scenes)} scenes, ~{total_duration}s")
        return results

    # ═══════════════════════════════════════
    # ACTION: generate — Create video + TTS assets
    # ═══════════════════════════════════════

    def _generate_assets(self, scenes, voice_id):
        if not scenes:
            # Load latest plan
            plans_dir = DATA_DIR / "video_productions"
            if plans_dir.exists():
                plan_files = sorted(plans_dir.glob("*_plan.json"), reverse=True)
                if plan_files:
                    with open(plan_files[0]) as f:
                        plan = json.load(f)
                        scenes = plan.get("scenes", [])

        if not scenes:
            return {"status": "error", "summary": "Sahne bulunamadı — önce 'plan' çalıştırın", "metrics": {}, "recommendations": []}

        kie_key = os.environ.get("KIE_AI_API_KEY", "")
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")

        if not kie_key:
            cfg = self.load_config()
            kie_key = cfg.get("kie_ai_api_key", "")
        if not elevenlabs_key:
            cfg = self.load_config()
            elevenlabs_key = cfg.get("elevenlabs_api_key", "")

        self.log(f"Generating assets for {len(scenes)} scenes")

        # Ensure output dirs exist
        self.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        self.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        videos_generated = 0
        videos_failed = 0
        tts_generated = 0
        tts_failed = 0

        # Step 1: Generate videos via Kie.ai
        if kie_key:
            video_scenes = [s for s in scenes if s.get("needsVideo", False) and s.get("videoPrompt")]
            self.log(f"Generating {len(video_scenes)} videos via Kie.ai...")

            # Batch in groups of 5
            for i in range(0, len(video_scenes), 5):
                batch = video_scenes[i:i+5]
                task_ids = []

                for scene in batch:
                    scene_id = scene.get("id", "x")
                    video_path = self.VIDEOS_DIR / f"v{scene_id}.mp4"

                    if video_path.exists():
                        self.log(f"Video v{scene_id}.mp4 already exists — skipping")
                        videos_generated += 1
                        continue

                    task_id = self._create_kie_task(kie_key, scene["videoPrompt"])
                    if task_id:
                        task_ids.append({"task_id": task_id, "scene_id": scene_id})
                        self.log(f"Scene {scene_id}: Kie.ai task created → {task_id}")
                    else:
                        videos_failed += 1
                        self.log(f"Scene {scene_id}: Kie.ai task creation failed")

                # Poll and download batch
                for task in task_ids:
                    video_url = self._poll_kie_task(kie_key, task["task_id"])
                    if video_url:
                        success = self._download_file(video_url, self.VIDEOS_DIR / f"v{task['scene_id']}.mp4")
                        if success:
                            videos_generated += 1
                            self.log(f"Scene {task['scene_id']}: Video downloaded ✓")
                        else:
                            videos_failed += 1
                    else:
                        videos_failed += 1
                        self.log(f"Scene {task['scene_id']}: Video generation timed out")
        else:
            self.log("⚠ KIE_AI_API_KEY not set — skipping video generation")

        # Step 2: Generate TTS via ElevenLabs
        if elevenlabs_key:
            tts_scenes = [s for s in scenes if s.get("narration")]
            self.log(f"Generating {len(tts_scenes)} TTS audio files via ElevenLabs...")

            for scene in tts_scenes:
                scene_id = scene.get("id", "x")
                audio_path = self.AUDIO_DIR / f"s{scene_id}.mp3"

                if audio_path.exists():
                    self.log(f"Audio s{scene_id}.mp3 already exists — skipping")
                    tts_generated += 1
                    continue

                success = self._generate_tts(elevenlabs_key, voice_id, scene["narration"], audio_path)
                if success:
                    tts_generated += 1
                    self.log(f"Scene {scene_id}: TTS generated ✓")
                else:
                    tts_failed += 1
                    self.log(f"Scene {scene_id}: TTS failed")
        else:
            self.log("⚠ ELEVENLABS_API_KEY not set — skipping TTS generation")

        # Step 3: Measure audio durations
        durations = self._measure_audio_durations()

        # Save generation report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gen_data = {
            "scenes_total": len(scenes),
            "videos_generated": videos_generated,
            "videos_failed": videos_failed,
            "tts_generated": tts_generated,
            "tts_failed": tts_failed,
            "audio_durations": durations,
            "created_at": timestamp,
        }

        self.save_data(f"video_productions/{timestamp}_generation.json", gen_data)

        results = {
            "status": "ok" if videos_failed == 0 and tts_failed == 0 else "partial",
            "summary": f"Video: {videos_generated} ✓ {videos_failed} ✗ | TTS: {tts_generated} ✓ {tts_failed} ✗",
            "metrics": gen_data,
            "recommendations": self._generation_recommendations(durations, videos_failed, tts_failed),
        }

        self.save_output("videoproducer_report.json", results)
        self.log("Asset generation completed")
        return results

    # ═══════════════════════════════════════
    # ACTION: render — Render final MP4 via Remotion
    # ═══════════════════════════════════════

    def _render_video(self):
        self.log("Starting Remotion render...")

        if not self.REMOTION_DIR.exists():
            return {
                "status": "error",
                "summary": "Remotion project not found — 'Remotion-Video-main 2/my-video' dizini gerekli",
                "metrics": {}, "recommendations": ["Remotion projesinin doğru konumda olduğundan emin olun"],
            }

        try:
            # Run remotion render
            result = subprocess.run(
                ["npx", "remotion", "render", "src/index.ts", "--codec", "h264"],
                capture_output=True, text=True, timeout=600,
                cwd=str(self.REMOTION_DIR),
            )

            output_path = self.REMOTION_DIR / "out" / "video.mp4"

            if result.returncode == 0 and output_path.exists():
                # Copy to goat outputs
                goat_output = OUTPUT_DIR / "videos"
                goat_output.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                import shutil
                final_path = goat_output / f"{timestamp}_rendered.mp4"
                shutil.copy2(str(output_path), str(final_path))

                self.log(f"Render complete: {final_path}")
                return {
                    "status": "ok",
                    "summary": f"Video renderlanlandı: {final_path}",
                    "metrics": {"output_path": str(final_path), "size_mb": round(final_path.stat().st_size / 1024 / 1024, 1)},
                    "recommendations": ["Video hazır — YouTube'a yükleyebilirsiniz"],
                }
            else:
                self.log(f"Render failed: {result.stderr[:500]}")
                return {
                    "status": "error",
                    "summary": f"Render başarısız: {result.stderr[:200]}",
                    "metrics": {"stderr": result.stderr[:500]},
                    "recommendations": ["Remotion projesini kontrol edin", "'npx remotion studio' ile preview yapın"],
                }

        except subprocess.TimeoutExpired:
            return {"status": "error", "summary": "Render timeout (10 dk)", "metrics": {}, "recommendations": ["Sahne sayısını azaltın"]}
        except FileNotFoundError:
            return {"status": "error", "summary": "npx/remotion bulunamadı — Node.js kurulu mu?", "metrics": {}, "recommendations": ["npm install -g remotion"]}

    # ═══════════════════════════════════════
    # ACTION: full — Complete pipeline
    # ═══════════════════════════════════════

    def _full_pipeline(self, topic, style, language, business_name, voice_id):
        self.log(f"Full pipeline: {topic}")

        # Step 1: Plan
        plan_result = self._plan_video(topic, style, language, business_name)
        if plan_result["status"] == "error":
            return plan_result

        scenes = plan_result.get("plan", {}).get("scenes", [])
        if not scenes:
            return {"status": "error", "summary": "Plan boş — sahne oluşturulamadı", "metrics": {}, "recommendations": []}

        # Step 2: Generate assets
        gen_result = self._generate_assets(scenes, voice_id)

        # Step 3: Render (if assets generated)
        render_result = None
        if gen_result["status"] in ("ok", "partial"):
            render_result = self._render_video()

        return {
            "status": render_result["status"] if render_result else gen_result["status"],
            "summary": f"Pipeline: Plan ✓ | Assets: {gen_result['summary']} | Render: {render_result['summary'] if render_result else 'skipped'}",
            "metrics": {
                "plan": plan_result.get("metrics", {}),
                "generation": gen_result.get("metrics", {}),
                "render": render_result.get("metrics", {}) if render_result else {},
            },
            "recommendations": [
                "YouTube agent ile video yükleyebilirsiniz",
                "Farklı stil ve konu ile yeni videolar oluşturun",
            ],
        }

    # ═══════════════════════════════════════
    # ACTION: status — Check current assets
    # ═══════════════════════════════════════

    def _check_status(self):
        videos = list(self.VIDEOS_DIR.glob("*.mp4")) if self.VIDEOS_DIR.exists() else []
        audios = list(self.AUDIO_DIR.glob("*.mp3")) if self.AUDIO_DIR.exists() else []
        rendered = self.REMOTION_DIR / "out" / "video.mp4"

        return {
            "status": "ok",
            "summary": f"Videos: {len(videos)} | Audio: {len(audios)} | Rendered: {'✓' if rendered.exists() else '✗'}",
            "metrics": {
                "videos": [v.name for v in videos],
                "audios": [a.name for a in audios],
                "rendered": rendered.exists(),
                "rendered_path": str(rendered) if rendered.exists() else None,
            },
            "recommendations": [],
        }

    # ═══════════════════════════════════════
    # HELPERS: Kie.ai
    # ═══════════════════════════════════════

    def _create_kie_task(self, api_key, prompt):
        try:
            resp = requests.post(
                f"{self.KIE_API_URL}/createTask",
                headers={"Content-Type": "application/json", "api-key": api_key},
                json={
                    "modelName": self.KIE_MODEL,
                    "input": {"prompt": prompt, "aspect_ratio": "16:9", "duration": 6},
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("taskId") or data.get("taskId")
            self.log(f"Kie.ai error: {resp.status_code} — {resp.text[:200]}")
            return None
        except Exception as e:
            self.log(f"Kie.ai request failed: {e}")
            return None

    def _poll_kie_task(self, api_key, task_id):
        for i in range(self.KIE_MAX_POLLS):
            try:
                resp = requests.get(
                    f"{self.KIE_API_URL}/recordInfo",
                    params={"taskId": task_id},
                    headers={"api-key": api_key},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", resp.json())
                    status = data.get("status", "")

                    if status in ("completed", "SUCCESS", "success"):
                        # Multiple response formats
                        url = data.get("videoUrl") or data.get("output", {}).get("videoUrl")
                        if not url:
                            urls = data.get("resultUrls", data.get("output", {}).get("resultUrls", []))
                            if urls:
                                url = urls[0] if isinstance(urls[0], str) else urls[0].get("url", "")
                        return url

                    if status in ("failed", "FAILED", "error"):
                        self.log(f"Kie.ai task {task_id} failed")
                        return None

            except Exception as e:
                self.log(f"Kie.ai poll error: {e}")

            time.sleep(self.KIE_POLL_INTERVAL)

        return None

    # ═══════════════════════════════════════
    # HELPERS: ElevenLabs TTS
    # ═══════════════════════════════════════

    def _generate_tts(self, api_key, voice_id, text, output_path):
        try:
            resp = requests.post(
                f"{self.TTS_API_URL}/{voice_id}",
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": self.TTS_MODEL,
                    "voice_settings": self.TTS_VOICE_SETTINGS,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                return True
            self.log(f"ElevenLabs error: {resp.status_code} — {resp.text[:200]}")
            return False
        except Exception as e:
            self.log(f"ElevenLabs request failed: {e}")
            return False

    # ═══════════════════════════════════════
    # HELPERS: Audio duration + download
    # ═══════════════════════════════════════

    def _measure_audio_durations(self):
        durations = {}
        if not self.AUDIO_DIR.exists():
            return durations

        try:
            from mutagen.mp3 import MP3
            for mp3 in self.AUDIO_DIR.glob("*.mp3"):
                audio = MP3(str(mp3))
                durations[mp3.stem] = round(audio.info.length, 2)
        except ImportError:
            # Fallback: try subprocess ffprobe
            for mp3 in self.AUDIO_DIR.glob("*.mp3"):
                try:
                    result = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3)],
                        capture_output=True, text=True, timeout=10,
                    )
                    if result.stdout.strip():
                        durations[mp3.stem] = round(float(result.stdout.strip()), 2)
                except Exception:
                    pass

        # Save durations
        dur_path = self.REMOTION_DIR / "src" / "data" / "audio-durations.json"
        if dur_path.parent.exists():
            with open(dur_path, "w") as f:
                json.dump(durations, f, indent=2)
            self.log(f"Audio durations saved: {len(durations)} files")

        return durations

    def _download_file(self, url, output_path):
        try:
            resp = requests.get(url, timeout=120, stream=True)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            return False
        except Exception as e:
            self.log(f"Download failed: {e}")
            return False

    # ═══════════════════════════════════════
    # HELPERS: Misc
    # ═══════════════════════════════════════

    def _extract_scenes_from_response(self, response, topic, style):
        """Try to extract JSON scenes from Claude response."""
        if not response:
            return self._fallback_scenes(topic, style)

        # Try to find JSON array in response
        import re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            try:
                scenes = json.loads(json_match.group())
                if isinstance(scenes, list) and len(scenes) > 0:
                    return scenes
            except json.JSONDecodeError:
                pass

        return self._fallback_scenes(topic, style)

    def _fallback_scenes(self, topic, style):
        title = topic or "Video"
        return [
            {"id": "1", "type": "intro", "videoPrompt": f"Cinematic aerial establishing shot, {style} style, dramatic lighting, 4K", "narration": f"{title} hakkında bilmeniz gerekenler.", "needsVideo": True},
            {"id": "2", "type": "titleCard", "videoPrompt": "", "narration": "", "titleCardText": title.upper(), "needsVideo": False},
            {"id": "3", "type": "image", "videoPrompt": f"Professional {style} shot related to {topic}, detailed scene, high quality", "narration": f"{title} konusunda en önemli nokta şudur.", "needsVideo": True},
            {"id": "4", "type": "image", "videoPrompt": f"Dynamic {style} scene showing progress and development, inspiring imagery", "narration": "Detaylara birlikte bakalım.", "needsVideo": True},
            {"id": "5", "type": "image", "videoPrompt": f"Close-up detailed shot, {style} lighting, revealing key information", "narration": "İşte dikkat etmeniz gereken noktalar.", "needsVideo": True},
            {"id": "6", "type": "endCard", "videoPrompt": "", "narration": "", "endCardMessage": "Beğendiyseniz abone olun!", "endCardTag": title, "needsVideo": False},
        ]

    def _estimate_cost(self, scenes):
        video_count = sum(1 for s in scenes if s.get("needsVideo", False))
        narration_chars = sum(len(s.get("narration", "")) for s in scenes)
        video_cost = video_count * 0.08  # $0.08 per Kie.ai video
        tts_cost = (narration_chars / 1000) * 0.015  # $0.015 per 1K chars
        return round(video_cost + tts_cost, 2)

    def _generation_recommendations(self, durations, video_fails, tts_fails):
        recs = []
        if video_fails > 0:
            recs.append(f"{video_fails} video başarısız — Kie.ai API key ve bakiyesini kontrol edin")
        if tts_fails > 0:
            recs.append(f"{tts_fails} TTS başarısız — ElevenLabs API key ve bakiyesini kontrol edin")

        # Check for long narrations needing continuation scenes
        for name, dur in durations.items():
            if dur > 6.5:
                recs.append(f"⚠ {name}: {dur}s — 6s'den uzun, continuation sahne ({name}b, {name}c) ekleyin")

        if not recs:
            recs.append("Tüm assetler hazır — 'render' ile MP4 oluşturun")
        return recs
