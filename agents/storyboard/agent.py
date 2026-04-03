"""Storyboard Agent — Kling 3.0 video storyboard generator for fal.ai."""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class StoryboardAgent(BaseAgent):
    agent_id = "storyboard"
    name = "Storyboard"
    role = "Creates Kling 3.0 video storyboards with element plans and clip prompts for fal.ai"
    category = "creative"

    def run(self, project_type: str = "general", business_name: str = "",
            product_description: str = "", mood: str = "", duration: str = "15s",
            video_count: int = 1, orientation: str = "vertical",
            reference_notes: str = "") -> dict:
        self.log("Storyboard agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "Proje")

        from services.storyboard import PROJECT_PRESETS
        preset = PROJECT_PRESETS.get(project_type, PROJECT_PRESETS["general"])

        if not mood:
            mood = preset["mood_default"]

        self.log(f"Project: {project_type} | Business: {business_name} | Duration: {duration} | Videos: {video_count}")

        # ── Generate storyboard via Claude ──
        storyboard_data = self._generate_with_claude(
            project_type, preset, business_name, product_description,
            mood, duration, video_count, orientation, reference_notes
        )

        if not storyboard_data:
            self.log("Claude unavailable, using fallback template")
            storyboard_data = self._generate_fallback(
                project_type, preset, business_name, product_description,
                mood, duration, video_count, orientation
            )

        # ── Save JSON data ──
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = business_name.lower().replace(" ", "_")[:20]
        json_filename = f"{timestamp}_{slug}.json"
        self.save_data(f"storyboards/{json_filename}", storyboard_data)

        # ── Generate interactive HTML ──
        html_path = None
        try:
            from services.storyboard import save_storyboard_html
            html_filename = f"{slug}_{timestamp}_storyboard.html"
            html_path = save_storyboard_html(storyboard_data, html_filename)
            self.log(f"HTML storyboard generated: {html_path}")
        except Exception as e:
            self.log(f"HTML generation failed: {e}")

        results = {
            "status": "ok",
            "summary": f"Kling 3.0 storyboard oluşturuldu — {business_name} ({project_type})",
            "metrics": {
                "project_type": project_type,
                "business_name": business_name,
                "elements": len(storyboard_data.get("elements", [])),
                "clips": len(storyboard_data.get("clips", [])),
                "total_duration": duration,
                "video_count": video_count,
                "html_generated": bool(html_path),
                "timestamp": datetime.now().isoformat(),
            },
            "storyboard": storyboard_data,
            "html_path": html_path,
            "recommendations": [
                "Önce Görseller sekmesinden element görsellerini üret",
                "Her görseli isimlendirip kaydet",
                "Sonra Klipler sekmesinden fal.ai prompt'larını kopyala",
                "fal.ai'da Aspect Ratio ve Duration'ı elle ayarla",
                "Her klip 5sn üret, en iyi 1-3sn kullan",
            ],
        }

        self.save_output("storyboard_report.json", results)
        self.log("Storyboard agent completed")
        return results

    def _generate_with_claude(self, project_type, preset, business_name,
                               product_description, mood, duration, video_count,
                               orientation, reference_notes):
        """Generate structured storyboard data using Claude CLI."""

        element_hints = "\n".join(f"  - {tag}: {hint}" for tag, hint in preset["element_hints"].items())
        keywords = ", ".join(preset["prompt_keywords"])

        prompt = f"""Sen profesyonel bir AI video prodüksiyon danışmanısın. Kling 3.0 ile fal.ai üzerinden üretilecek bir video için detaylı storyboard oluştur.

## Proje Bilgileri
- Marka/İşletme: {business_name}
- Proje tipi: {preset["name"]}
- Ürün/Açıklama: {product_description or "Genel tanıtım"}
- Mood: {mood}
- Toplam süre: {duration}
- Video sayısı: {video_count}
- Yön: {"Dikey (9:16)" if orientation == "vertical" else "Yatay (16:9)"}
{"- Referans notları: " + reference_notes if reference_notes else ""}

## Element İpuçları
{element_hints}

## Prompt Anahtar Kelimeleri
{keywords}

## KRİTİK KURALLAR
1. Tüm prompt'lar İNGİLİZCE olmalı
2. Her klip prompt'unda kullanılan TÜM elementler @Element1, @Element2, @Element3 olarak GEÇMELİ
3. "shot on iPhone 15 Pro" veya "shot on iPhone 16 Pro" ifadesi ekle (insan sahnelerinde)
4. "realistic skin texture, natural pores visible, no retouching" ekle (insan sahnelerinde)
5. NEGATİF ifade KULLANMA ("no fire" yerine "dark gray stones" gibi pozitif tarif)
6. Her klip fal.ai'da 5 saniye olarak üretilir, videoda en iyi 1-3 saniye kullanılır
7. Ürün makro sahnelerinde insan olmamalı (face distortion riski)
8. Her prompt tek paragraf olmalı

## ÇIKTI FORMATI — SADECE JSON DÖNDÜR

```json
{{
  "business_name": "{business_name}",
  "project_type": "{project_type}",
  "description": "Kısa proje açıklaması (Türkçe)",
  "orientation": "{orientation}",
  "clip_duration": "5s",
  "accent_color": "{preset['accent']}",
  "accent_color2": "{preset['accent2']}",
  "elements": [
    {{
      "tag": "@E1",
      "label": "Element adı (Türkçe)",
      "icon": "emoji",
      "color": "#hex",
      "description": "Element açıklaması (Türkçe)",
      "note": "Önemli not (Türkçe, opsiyonel)",
      "images": [
        {{
          "type": "FRONTAL",
          "required": true,
          "desc": "Görsel açıklaması (Türkçe)",
          "prompt": "Full English prompt for image generation..."
        }},
        {{
          "type": "REF",
          "required": true,
          "desc": "Referans görsel açıklaması (Türkçe)",
          "prompt": "Full English prompt for reference image..."
        }}
      ]
    }}
  ],
  "clips": [
    {{
      "time": "0-3s",
      "duration_sec": 3,
      "title": "Sahne adı (Türkçe)",
      "desc": "Sahne açıklaması (Türkçe)",
      "camera": "Kamera hareketi",
      "color": "#hex",
      "elements": ["@E1", "@E2"],
      "start_image": "Hangi element görseli start image olacak",
      "prompt": "Full English cinematic prompt for fal.ai... must include @Element1 and @Element2 references in the text..."
    }}
  ],
  "post_production": {{
    "Renk Grade": ["Öneriler..."],
    "Geçişler": ["Öneriler..."],
    "Tipografi": ["Öneriler..."],
    "Müzik/SFX": ["Öneriler..."]
  }},
  "workflow": [
    {{"text": "Adım açıklaması", "done": false}}
  ]
}}
```

SADECE JSON döndür, başka açıklama yazma."""

        response = self.call_claude(prompt, timeout=180)
        if not response:
            return None

        # Parse JSON from response
        try:
            # Try to extract JSON block
            json_match = response
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_match = response.split("```")[1].split("```")[0]
            return json.loads(json_match.strip())
        except (json.JSONDecodeError, IndexError):
            self.log("Failed to parse Claude JSON response, trying raw")
            try:
                # Try parsing the raw response
                start = response.index("{")
                end = response.rindex("}") + 1
                return json.loads(response[start:end])
            except (ValueError, json.JSONDecodeError):
                self.log("JSON parse failed completely")
                return None

    def _generate_fallback(self, project_type, preset, business_name,
                           product_description, mood, duration, video_count, orientation):
        """Generate a template-based storyboard when Claude is unavailable."""

        total_sec = int(duration.replace("s", ""))
        num_clips = max(3, total_sec // 3)

        # Build elements from preset hints
        elements = []
        colors = [preset["accent"], preset["accent2"], "#7EB8D4", "#8FD48F", "#D4A574"]
        icons = ["👤", "📦", "🏠", "✨", "🎯"]

        for i, (tag, hint) in enumerate(preset["element_hints"].items()):
            el_color = colors[i % len(colors)]
            elements.append({
                "tag": tag,
                "label": hint.split("—")[0].strip() if "—" in hint else hint,
                "icon": icons[i % len(icons)],
                "color": el_color,
                "description": hint,
                "images": [
                    {
                        "type": "FRONTAL",
                        "required": True,
                        "desc": f"{tag} karşıdan görünüm",
                        "prompt": self._make_element_prompt(tag, hint, preset, "frontal"),
                    },
                    {
                        "type": "REF",
                        "required": True,
                        "desc": f"{tag} referans açı",
                        "prompt": self._make_element_prompt(tag, hint, preset, "reference"),
                    },
                ],
            })

        # Build clips
        clips = []
        clip_duration = total_sec / num_clips
        scene_titles = [
            ("Açılış", "Establishing shot — mekan veya ürün tanıtımı", "Dolly-in"),
            ("Detay", "Yakın çekim — doku, malzeme, detay", "Close-up"),
            ("Karakter", "İnsan sahne — doğal, candid hareket", "Medium shot"),
            ("Ürün Hero", "Ürün/mekan odaklı premium sahne", "Orbit"),
            ("Atmosfer", "Ortam, ışık, buhar, toz parçacıkları", "Wide shot"),
            ("Kapanış", "Final — geniş plan veya marka anı", "Pull-back"),
        ]

        current_time = 0
        element_tags = list(preset["element_hints"].keys())
        for i in range(num_clips):
            idx = i % len(scene_titles)
            title, desc, camera = scene_titles[idx]
            end_time = min(current_time + clip_duration, total_sec)
            dur = round(end_time - current_time)

            # Assign elements to this clip
            clip_elements = []
            if idx in (0, 4, 5) and len(element_tags) > 2:
                clip_elements = [element_tags[-1]]  # mekan
            elif idx == 2:
                clip_elements = [element_tags[0]]  # karakter
            elif idx == 3:
                clip_elements = [element_tags[1]] if len(element_tags) > 1 else [element_tags[0]]
            else:
                clip_elements = element_tags[:2]

            el_refs = " ".join(clip_elements)
            prompt = self._make_clip_prompt(
                business_name, title, desc, camera, clip_elements, preset, orientation
            )

            clips.append({
                "time": f"{int(current_time)}-{int(end_time)}s",
                "duration_sec": dur,
                "title": title,
                "desc": desc,
                "camera": camera,
                "color": colors[i % len(colors)],
                "elements": clip_elements,
                "start_image": f"{clip_elements[0]} frontal görseli" if clip_elements else "",
                "prompt": prompt,
            })
            current_time = end_time

        return {
            "business_name": business_name,
            "project_type": project_type,
            "description": f"{business_name} — {preset['name']} tanıtım filmi. {mood}.",
            "orientation": orientation,
            "clip_duration": "5s",
            "accent_color": preset["accent"],
            "accent_color2": preset["accent2"],
            "elements": elements,
            "clips": clips,
            "post_production": {
                "Renk Grade": [
                    "Warm amber/gold tonlar — tutarlılık için tüm kliplerde aynı LUT",
                    "Highlights yumuşak, shadows derinlikli",
                    "Satürasyon hafif düşürülmüş — doğal sinematik his",
                ],
                "Geçişler": [
                    "Hard cut (ana geçiş) — dinamik tempo",
                    "Dissolve (yavaş sahneler arası)",
                    "White flash (ürün reveal sahnelerinde)",
                ],
                "Tipografi": [
                    f"Font: Minimal sans-serif — marka ismi ({business_name})",
                    "Alt yazılar beyaz, ince, alt merkez",
                    "Logo kapanışta 2 saniye",
                ],
                "Müzik/SFX": [
                    "Ambient/cinematic — tempo sahne ritmine uyumlu",
                    "Doğal sesler: ayak sesi, kumaş, cam, su (ASMR his)",
                    "Müzik kısık başla, ürün reveal'da yüksel",
                ],
            },
            "workflow": [
                {"text": "Element görsellerini üret (karakter, ürün, mekan)", "done": False},
                {"text": "Görselleri isimlendirip kaydet", "done": False},
                {"text": "fal.ai'da Klip 1'i üret (Açılış)", "done": False},
                {"text": "Sonucu kontrol et — gerekirse prompt'u revize et", "done": False},
                {"text": "Kalan klipleri sırayla üret", "done": False},
                {"text": "En iyi kareleri seç ve timeline'a diz", "done": False},
                {"text": "Post-production: renk grade, geçişler, tipografi", "done": False},
                {"text": "Müzik/SFX ekle ve final render", "done": False},
            ],
        }

    def _make_element_prompt(self, tag, hint, preset, img_type):
        """Generate a fallback image prompt for an element."""
        keywords = " ".join(preset["prompt_keywords"][:3])
        if "karakter" in hint.lower() or "model" in hint.lower() or "insan" in hint.lower():
            if img_type == "frontal":
                return f"Portrait photograph shot on iPhone 15 Pro of a professional person, warm natural window light from the left side, clean minimal background, medium portrait framing from chest up. Realistic skin texture, natural pores visible, no retouching. {keywords}. Authentic photography."
            else:
                return f"Side profile portrait of the same person, same clothing and styling, soft window light illuminating the profile, clean background. Chest up framing. Same person same lighting from side angle. {keywords}."
        elif "ürün" in hint.lower() or "product" in hint.lower():
            if img_type == "frontal":
                return f"Professional product photography on a clean surface. Minimalist composition, soft studio lighting, premium commercial photography. High detail, sharp focus. {keywords}."
            else:
                return f"Same product from a different angle showing details and texture. Professional studio lighting, shallow depth of field. Premium product photography. {keywords}."
        else:
            if img_type == "frontal":
                return f"Professional interior/exterior photography. Warm ambient lighting, clean modern design, architectural photography. Wide angle showing full space. {keywords}."
            else:
                return f"Detail shot of the same space from a different angle. Focus on textures, materials, and lighting details. Warm ambient light. {keywords}."

    def _make_clip_prompt(self, business_name, title, desc, camera, elements, preset, orientation):
        """Generate a fallback clip prompt."""
        keywords = " ".join(preset["prompt_keywords"][:4])
        el_refs = " and ".join(elements)
        ratio = "9:16 vertical" if orientation == "vertical" else "16:9 horizontal"

        return (
            f"Cinematic promotional video. {keywords}. "
            f"Professional {ratio} composition. "
            f"{camera} shot inside/around {el_refs}. "
            f"{desc}. Warm natural lighting, shallow depth of field. "
            f"Smooth camera movement, premium atmosphere. "
            f"Natural and authentic feel."
        )
