"""Storyboard Service — Kling 3.0 storyboard templates, prompt rules, and HTML generation."""

import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


# ── Kling 3.0 Prompt Rules (from project-instructions.md) ──────────────

PROMPT_RULES = """
## Kling 3.0 Prompt Kuralları

### Genel
- Prompt dili her zaman İNGİLİZCE
- UI ve açıklamalar TÜRKÇE
- Her prompt tek paragraf, satır atlama yok
- Element referansları (@E1, @E2, @E3) prompt METNİNDE geçmeli — sadece listede yetmez

### Model/Karakter
- "shot on iPhone 15 Pro" veya "shot on iPhone 16 Pro" ekle — AI look'u kırar
- "realistic skin texture, natural pores visible, no retouching" ekle
- "candid", "natural handheld feel", "authentic" kullan
- Hasselblad, editorial, fashion film gibi kalite referanslarından KAÇIN
- Gözler kapalı sahneler yüz bozulma riskini düşürür
- Backlit/silüet sahneler Kling için kolay ve sinematik

### Ürün
- Gerçek ürün fotoğrafı varsa → Frontal Image olarak kullan
- Stüdyo kalitesinde profesyonel ürün fotoğrafçılığı dili
- Reflektif koyu yüzey premium his verir
- Ürün makro sahnelerinde insan olmamalı → face distortion riski sıfır

### Sahne Süresi
- Her klip fal.ai'da 5 saniye olarak üretilir
- Videoda sadece en iyi 1-3 saniye kullanılır
- Kısa sahneler (1-2sn) AI artifact'lerini gizler
- Model ↔ Ürün "ping-pong" ritmi

### Negatif İfade Yasak
- "no" veya "don't" gibi negatif ifadeler Kling'de genelde işe yaramaz
- İstediğin şeyi POZİTİF olarak tarif et
- Örnek: "no fire" yerine → "dark gray stones, cold-colored"

### fal.ai Ayarları
- Aspect Ratio: Elle seçilmeli (16:9 yatay veya 9:16 dikey)
- Duration: 5s veya 10s
- Multi Prompt: Boş bırakılmalı
- Start Image: Her klip için belirtilen görseli yükle
- Elements: Frontal + Reference görseller doğru slotlara yüklenmeli
"""

# ── Project Type Presets ────────────────────────────────────────────────

PROJECT_PRESETS = {
    "cosmetic": {
        "name": "Kozmetik / Güzellik",
        "accent": "#E88DA0",
        "accent2": "#D4A574",
        "mood_default": "Doğal, editorial, minimal",
        "camera_style": "Medium shot, soft window light, shallow DOF",
        "element_hints": {
            "@E1": "Model/Karakter — doğal güzellik, dewy skin",
            "@E2": "Ürün — minimalist ambalaj, stüdyo çekim",
        },
        "prompt_keywords": ["shot on iPhone 15 Pro", "realistic skin texture", "natural pores visible",
                            "no retouching", "candid", "editorial beauty"],
    },
    "restaurant": {
        "name": "Restoran / Yeme-İçme",
        "accent": "#D4A574",
        "accent2": "#8B6F47",
        "mood_default": "Sıcak, sinematik, food cinematography",
        "camera_style": "Warm golden lighting, shallow DOF, close-ups",
        "element_hints": {
            "@E1": "Şef/İnsan — uzaktan, çevrenin parçası",
            "@E2": "Yemek/İçecek — makro, buhar, doku",
            "@E3": "Mekan — iç/dış cephe, atmosfer",
        },
        "prompt_keywords": ["cinematic food cinematography", "warm golden lighting",
                            "shallow depth of field", "natural and authentic"],
    },
    "jewelry": {
        "name": "Mücevher / Aksesuar",
        "accent": "#C9A87C",
        "accent2": "#E8E8E8",
        "mood_default": "Lüks, B&W, editorial",
        "camera_style": "Macro, orbit, reflektif yüzey, dramatic lighting",
        "element_hints": {
            "@E1": "Model — doğal güzellik, mücevher taşıyıcı",
            "@E2": "Ana ürün — makro, detay, ışık kırılmaları",
        },
        "prompt_keywords": ["shot on iPhone 16 Pro", "black and white monochrome",
                            "realistic skin texture", "candid"],
    },
    "clinic": {
        "name": "Klinik / Sağlık",
        "accent": "#5DAFA0",
        "accent2": "#C4A265",
        "mood_default": "Sıcak, güven veren, premium",
        "camera_style": "Warm amber lighting, window light, professional",
        "element_hints": {
            "@E1": "Doktor/Uzman — beyaz önlük, sıcak gülümseme",
            "@E2": "Hasta/Model — mutlu, rahat ifade",
            "@E3": "Mekan — lüks, modern, sıcak aydınlatma",
        },
        "prompt_keywords": ["shot on iPhone 15 Pro", "warm amber lighting",
                            "realistic skin texture", "candid photograph", "authentic"],
    },
    "wellness": {
        "name": "Wellness / Spa / Sauna",
        "accent": "#A0C4B8",
        "accent2": "#D4A574",
        "mood_default": "Meditatif, huzurlu, warm amber",
        "camera_style": "Warm LED, clear air, silhouettes",
        "element_hints": {
            "@E1": "Mekan A — ana alan, genel görünüm",
            "@E2": "Mekan B — detay alan, farklı açı",
        },
        "prompt_keywords": ["cinematic luxury", "warm amber lighting",
                            "calm meditative atmosphere", "shallow depth of field"],
    },
    "general": {
        "name": "Genel / Özel Proje",
        "accent": "#7EB8D4",
        "accent2": "#D4A574",
        "mood_default": "Profesyonel, sinematik",
        "camera_style": "Cinematic, warm natural light",
        "element_hints": {
            "@E1": "Ana karakter veya obje",
            "@E2": "İkincil karakter veya ürün",
            "@E3": "Mekan veya ortam",
        },
        "prompt_keywords": ["cinematic", "professional cinematography",
                            "shallow depth of field", "natural light"],
    },
}


# ── Scene Template Library ──────────────────────────────────────────────

CAMERA_MOVEMENTS = [
    "Dolly-in", "Pull-back", "Tracking", "Close-up", "Extreme close-up",
    "Wide shot", "Medium shot", "Low angle", "Top-down", "Orbit",
    "Slow-motion macro", "POV dolly", "Eye-level", "Pan", "Tilt-up",
    "Macro slide", "Walk-in", "Handheld", "Silhouette backlit",
]

TRANSITION_TYPES = [
    "Hard cut", "Dissolve", "White flash", "Whip pan",
    "Match cut", "J-cut (ses önce)", "Fade to black",
]


# ── HTML Storyboard Generator ──────────────────────────────────────────

def generate_storyboard_html(storyboard_data: dict) -> str:
    """Generate an interactive HTML storyboard from structured data."""

    project = storyboard_data
    preset = PROJECT_PRESETS.get(project.get("project_type", "general"), PROJECT_PRESETS["general"])
    accent = project.get("accent_color", preset["accent"])
    accent2 = project.get("accent_color2", preset["accent2"])
    biz = project.get("business_name", "Proje")
    elements = project.get("elements", [])
    clips = project.get("clips", [])
    post_production = project.get("post_production", {})
    workflow = project.get("workflow", [])

    # ── Build Elements HTML ──
    elements_html = ""
    for el in elements:
        images_html = ""
        for img in el.get("images", []):
            req_badge = '<span style="background:rgba(212,80,80,0.2);color:#D45050;padding:2px 6px;border-radius:3px;font-size:9px;font-family:monospace">ZORUNLU</span>' if img.get("required") else '<span style="background:rgba(255,255,255,0.06);color:#666;padding:2px 6px;border-radius:3px;font-size:9px;font-family:monospace">OPSİYONEL</span>'
            images_html += f'''
            <div style="background:rgba(0,0,0,0.3);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px;margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <div style="display:flex;gap:6px;align-items:center">
                  <span style="font-size:8px;font-family:monospace;background:{el["color"]}25;color:{el["color"]};padding:2px 6px;border-radius:3px;font-weight:700">{img.get("type","FRONTAL")}</span>
                  {req_badge}
                </div>
                <button onclick="navigator.clipboard.writeText(this.dataset.prompt).then(()=>{{this.textContent='✓ Kopyalandı!';setTimeout(()=>this.textContent='📋 Kopyala',2000)}})" data-prompt="{_escape_html(img.get('prompt',''))}" style="background:rgba(212,165,116,0.1);border:1px solid rgba(212,165,116,0.2);border-radius:6px;padding:6px 14px;font-size:11px;color:#D4A574;cursor:pointer;font-family:monospace;font-weight:700">📋 Kopyala</button>
              </div>
              <div style="font-size:11px;color:#aaa;margin-bottom:6px">{_escape_html(img.get("desc",""))}</div>
              <div style="background:rgba(0,0,0,0.4);border-radius:6px;padding:10px;font-size:10.5px;line-height:1.8;color:#999;font-family:'Courier New',monospace;white-space:pre-wrap;word-break:break-word;max-height:200px;overflow-y:auto">{_highlight_prompt(img.get("prompt",""))}</div>
            </div>'''

        elements_html += f'''
        <div style="background:{el["color"]}08;border:1px solid {el["color"]}20;border-radius:10px;margin-bottom:12px;overflow:hidden">
          <div style="padding:12px 14px;border-bottom:1px solid {el["color"]}15;display:flex;justify-content:space-between;align-items:center">
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-size:18px">{el.get("icon","📦")}</span>
              <div>
                <span style="font-size:9px;font-family:monospace;background:{el["color"]}20;color:{el["color"]};padding:2px 8px;border-radius:3px;font-weight:700">{el["tag"]}</span>
                <span style="font-size:13px;color:#F0EDE8;margin-left:8px">{_escape_html(el.get("label",""))}</span>
              </div>
            </div>
          </div>
          <div style="padding:10px 14px;font-size:11px;color:#888;border-bottom:1px solid rgba(255,255,255,0.04)">{_escape_html(el.get("description",""))}</div>
          <div style="padding:12px 14px">{images_html}</div>
          {"<div style='padding:8px 14px 12px;background:rgba(212,165,116,0.04);font-size:10px;color:#D4A574'>⚠️ " + _escape_html(el.get("note","")) + "</div>" if el.get("note") else ""}
        </div>'''

    # ── Build Clips HTML ──
    clips_html = ""
    # Timeline bar
    total_duration = sum(c.get("duration_sec", 3) for c in clips) or 15
    timeline_html = '<div style="display:flex;gap:2px;margin-bottom:12px">'
    for c in clips:
        dur = c.get("duration_sec", 3)
        pct = (dur / total_duration) * 100
        ccolor = c.get("color", accent)
        timeline_html += f'<div style="width:{pct}%;background:linear-gradient(135deg,{ccolor}50,{ccolor}20);border-radius:4px;padding:4px 2px;text-align:center;border:1px solid {ccolor}30"><div style="font-size:7px;color:{ccolor};font-family:monospace;font-weight:700">{dur}s</div></div>'
    timeline_html += '</div>'

    for i, c in enumerate(clips):
        ccolor = c.get("color", accent)
        el_badges = "".join(f'<span style="background:rgba(126,184,212,0.15);border:1px solid rgba(126,184,212,0.3);padding:1px 6px;border-radius:3px;color:#7EB8D4;font-weight:700;font-size:9px;font-family:monospace">{e}</span> ' for e in c.get("elements", []))
        el_check = ""
        for e in c.get("elements", []):
            in_prompt = e in c.get("prompt", "")
            icon = "✓" if in_prompt else "✗"
            color = "#8FD48F" if in_prompt else "#D45050"
            el_check += f'<span style="color:{color};font-size:9px;font-family:monospace">{e} {icon}</span> '

        clips_html += f'''
        <div style="background:{ccolor}06;border:1px solid {ccolor}15;border-radius:10px;margin-bottom:10px;overflow:hidden">
          <div style="padding:12px 14px;border-bottom:1px solid {ccolor}10;display:flex;justify-content:space-between;align-items:center">
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-size:9px;font-family:monospace;font-weight:700;color:{ccolor};background:{ccolor}15;padding:3px 8px;border-radius:4px;min-width:36px;text-align:center">{c.get("time","")}</span>
              <span style="font-size:13px;color:#F0EDE8">{_escape_html(c.get("title",""))}</span>
            </div>
            <span style="font-size:8px;color:#666;font-family:monospace;background:rgba(255,255,255,0.03);padding:2px 6px;border-radius:3px">{_escape_html(c.get("camera",""))}</span>
          </div>
          <div style="padding:8px 14px;font-size:11px;color:#888">{_escape_html(c.get("desc",""))}</div>
          <div style="padding:4px 14px 8px;display:flex;gap:4px;flex-wrap:wrap;align-items:center">
            <span style="font-size:9px;color:#555;font-family:monospace">Elements:</span> {el_badges}
            <span style="margin-left:8px;font-size:9px;color:#555">Prompt check:</span> {el_check}
          </div>
          <div style="padding:0 14px 12px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <span style="font-size:9px;letter-spacing:2px;color:#7EB8D4;font-family:monospace;font-weight:700">fal.ai PROMPT</span>
              <button onclick="navigator.clipboard.writeText(this.dataset.prompt).then(()=>{{this.textContent='✓ Kopyalandı!';setTimeout(()=>this.textContent='📋 Kopyala',2000)}})" data-prompt="{_escape_html(c.get('prompt',''))}" style="background:rgba(212,165,116,0.1);border:1px solid rgba(212,165,116,0.2);border-radius:6px;padding:6px 14px;font-size:11px;color:#D4A574;cursor:pointer;font-family:monospace;font-weight:700">📋 Kopyala</button>
            </div>
            <div style="background:rgba(0,0,0,0.4);border-radius:6px;padding:10px;font-size:10.5px;line-height:1.8;color:#999;font-family:'Courier New',monospace;white-space:pre-wrap;word-break:break-word;max-height:300px;overflow-y:auto">{_highlight_prompt(c.get("prompt",""))}</div>
          </div>
        </div>'''

    # ── Post-Production HTML ──
    post_html = ""
    if post_production:
        items = []
        for key, val in post_production.items():
            if isinstance(val, list):
                items.append(f'<div style="margin-bottom:10px"><div style="font-size:11px;font-weight:600;color:{accent};margin-bottom:4px">{_escape_html(key)}</div>' + "".join(f'<div style="font-size:11px;color:#888;padding-left:12px">• {_escape_html(v)}</div>' for v in val) + '</div>')
            else:
                items.append(f'<div style="font-size:11px;color:#888;margin-bottom:4px"><strong style="color:#aaa">{_escape_html(key)}:</strong> {_escape_html(str(val))}</div>')
        post_html = "".join(items)

    # ── Workflow HTML ──
    workflow_html = ""
    for step in workflow:
        done = step.get("done", False)
        icon = "✅" if done else "⏳"
        workflow_html += f'<div style="display:flex;gap:8px;align-items:start;margin-bottom:6px"><span>{icon}</span><span style="font-size:11px;color:{"#8FD48F" if done else "#888"};{"text-decoration:line-through;opacity:0.6" if done else ""}">{_escape_html(step.get("text",""))}</span></div>'

    # ── fal.ai Reminder ──
    fal_ratio = "9:16 (dikey)" if project.get("orientation") == "vertical" else "16:9 (yatay)"
    fal_duration = project.get("clip_duration", "5s")

    # ── Full HTML ──
    html = f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape_html(biz)} — Kling 3.0 Storyboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0A0A0C; color:#E0DDD8; font-family:'Georgia','Noto Serif',serif; min-height:100vh; }}
  .tabs {{ display:flex; border-bottom:1px solid {accent}15; position:sticky; top:0; background:#0A0A0C; z-index:10; }}
  .tab {{ flex:1; padding:13px 4px; background:transparent; border:none; border-bottom:2px solid transparent; color:#5A5550; font-size:12px; font-family:inherit; cursor:pointer; transition:all 0.2s; }}
  .tab.active {{ border-bottom-color:{accent}; color:{accent}; }}
  .tab:hover {{ color:{accent}99; }}
  .panel {{ display:none; padding:16px; }}
  .panel.active {{ display:block; }}
</style>
</head>
<body>

<!-- Header -->
<div style="padding:24px 20px 16px;border-bottom:1px solid {accent}15;background:linear-gradient(180deg,{accent}08,transparent)">
  <div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap">
    <span style="background:linear-gradient(135deg,{accent},{accent2});padding:3px 8px;border-radius:4px;font-size:9px;font-weight:700;color:#0A0A0C;letter-spacing:1.5px;font-family:monospace">{_escape_html(preset["name"].upper())}</span>
    <span style="background:rgba(100,200,100,0.1);border:1px solid rgba(100,200,100,0.25);padding:3px 8px;border-radius:4px;font-size:9px;color:#8FD48F;letter-spacing:1px;font-family:monospace">KLING 3.0</span>
    <span style="background:rgba(126,184,212,0.1);border:1px solid rgba(126,184,212,0.2);padding:3px 8px;border-radius:4px;font-size:9px;color:#7EB8D4;letter-spacing:1px;font-family:monospace">{len(clips)} KLİP</span>
  </div>
  <h1 style="font-size:22px;font-weight:400;margin:0 0 4px;color:#F0EDE8">{_escape_html(biz)} — Video Storyboard</h1>
  <p style="font-size:12px;color:#5A5550;margin:0">{_escape_html(project.get("description",""))}</p>
</div>

<!-- Tabs -->
<div class="tabs">
  <button class="tab active" onclick="switchTab('elements',this)">🎨 Görseller</button>
  <button class="tab" onclick="switchTab('clips',this)">🎬 Klipler</button>
  <button class="tab" onclick="switchTab('post',this)">🎨 Post</button>
  <button class="tab" onclick="switchTab('workflow',this)">📋 Plan</button>
</div>

<!-- Elements Panel -->
<div id="panel-elements" class="panel active">
  <div style="background:rgba(126,184,212,0.05);border:1px solid rgba(126,184,212,0.15);border-radius:10px;padding:14px;margin-bottom:16px">
    <div style="font-size:12px;color:#7EB8D4;line-height:1.6">
      Toplam <strong>{len(elements)} element</strong> — her birinin görsellerini üret, isim ver ve kaydet. Klipler sekmesinde fal.ai'ya yükleyeceksin.
    </div>
  </div>
  {elements_html}
</div>

<!-- Clips Panel -->
<div id="panel-clips" class="panel">
  {timeline_html}
  {clips_html}

  <!-- fal.ai Reminder -->
  <div style="margin-top:14px;background:rgba(212,165,116,0.04);border:1px solid rgba(212,165,116,0.12);border-radius:10px;padding:14px">
    <div style="font-size:11px;font-weight:600;color:#D4A574;margin-bottom:6px">⚙️ fal.ai Hatırlatma</div>
    <div style="font-size:11px;color:#888;line-height:1.7">
      • Aspect Ratio → elle <strong>{fal_ratio}</strong> seç<br>
      • Duration → <strong>{fal_duration}</strong> seç<br>
      • Multi Prompt → boş bırak<br>
      • Elements → Frontal + Reference görselleri doğru slotlara yükle<br>
      • Start Image → her klip için belirtilen görseli yükle
    </div>
  </div>
</div>

<!-- Post-Production Panel -->
<div id="panel-post" class="panel">
  <div style="background:{accent}06;border:1px solid {accent}15;border-radius:10px;padding:16px">
    <div style="font-size:13px;font-weight:600;color:{accent};margin-bottom:12px">Post-Production Rehberi</div>
    {post_html if post_html else '<div style="font-size:11px;color:#666">Post-production bilgisi henüz eklenmedi.</div>'}
  </div>
</div>

<!-- Workflow Panel -->
<div id="panel-workflow" class="panel">
  <div style="background:rgba(100,200,100,0.04);border:1px solid rgba(100,200,100,0.15);border-radius:10px;padding:16px">
    <div style="font-size:13px;font-weight:600;color:#8FD48F;margin-bottom:12px">Üretim Planı</div>
    {workflow_html if workflow_html else '<div style="font-size:11px;color:#666">Workflow henüz eklenmedi.</div>'}
  </div>
</div>

<script>
function switchTab(name, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  btn.classList.add('active');
}}
</script>

</body>
</html>'''
    return html


def save_storyboard_html(storyboard_data: dict, filename: str) -> str:
    """Generate and save storyboard HTML. Returns the file path."""
    html = generate_storyboard_html(storyboard_data)
    out_dir = OUTPUT_DIR / "storyboards"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return str(path)


def list_storyboards() -> list:
    """List all generated storyboard HTML files."""
    out_dir = OUTPUT_DIR / "storyboards"
    if not out_dir.exists():
        return []
    files = sorted(out_dir.glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"filename": f.name, "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat()} for f in files]


# ── Helpers ─────────────────────────────────────────────────────────────

def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def _highlight_prompt(prompt: str) -> str:
    """Add color highlights to @Element refs, timestamps, and keywords in prompt HTML."""
    import re
    text = _escape_html(prompt)
    # @Element refs → blue
    text = re.sub(
        r'(@Element\d)',
        r'<span style="background:rgba(126,184,212,0.15);border:1px solid rgba(126,184,212,0.3);padding:1px 6px;border-radius:3px;color:#7EB8D4;font-weight:700">\1</span>',
        text
    )
    # Timestamps [0s-3s] → gold
    text = re.sub(
        r'(\[[\ds\-]+\])',
        r'<span style="background:rgba(212,165,116,0.15);border:1px solid rgba(212,165,116,0.25);padding:1px 6px;border-radius:3px;color:#D4A574;font-weight:700">\1</span>',
        text
    )
    return text
