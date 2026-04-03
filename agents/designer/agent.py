"""Designer Agent — Visual content creation for agencies and clients."""

import json
from datetime import datetime
from pathlib import Path

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class DesignerAgent(BaseAgent):
    agent_id = "designer"
    name = "Designer"
    role = "Creates visual content — social media posts, banners, ad creatives, logos"
    category = "creative"

    def run(self, design_type: str = "social_post", business_name: str = "",
            platform: str = "instagram", theme: str = "", text: str = "") -> dict:
        self.log("Designer agent started")
        config = self.load_config()

        if not business_name:
            business_name = config.get("agency_name", "My Agency")
        if not theme:
            theme = config.get("niche", "digital marketing")

        # Design type presets
        presets = {
            "social_post": {
                "sizes": {"instagram": "1080x1080", "facebook": "1200x630", "twitter": "1600x900", "linkedin": "1200x627"},
                "description": "Sosyal medya paylaşımı",
            },
            "story": {
                "sizes": {"instagram": "1080x1920", "facebook": "1080x1920", "tiktok": "1080x1920"},
                "description": "Hikaye/Story görseli",
            },
            "banner": {
                "sizes": {"website": "1920x600", "email": "600x200", "youtube": "2560x1440"},
                "description": "Banner görseli",
            },
            "ad_creative": {
                "sizes": {"google": "1200x628", "facebook": "1080x1080", "instagram": "1080x1080"},
                "description": "Reklam görseli",
            },
            "logo": {
                "sizes": {"default": "1024x1024"},
                "description": "Logo tasarımı",
            },
            "thumbnail": {
                "sizes": {"youtube": "1280x720", "blog": "800x450"},
                "description": "Küçük resim / Thumbnail",
            },
            "infographic": {
                "sizes": {"default": "800x2000"},
                "description": "Infografik tasarımı",
            },
            "carousel": {
                "sizes": {"instagram": "1080x1080", "linkedin": "1080x1080"},
                "description": "Carousel / Çoklu görsel seti",
            },
        }

        preset = presets.get(design_type, presets["social_post"])
        size = preset["sizes"].get(platform, list(preset["sizes"].values())[0])

        self.log(f"Design type: {preset['description']} | Platform: {platform} | Size: {size}")

        # Build creative prompt
        prompt_text = text or f"{business_name} için profesyonel {preset['description']}"
        fal_prompt = (
            f"Professional {design_type.replace('_', ' ')} design for {business_name}. "
            f"Theme: {theme}. Clean, modern, high-quality. "
            f"Text overlay: '{prompt_text}'. Platform: {platform}."
        )

        # Try generating via fal.ai
        image_path = None
        try:
            from services.image import generate_image
            w, h = size.split("x")
            ratio = int(w) / int(h)
            if ratio > 1.2:
                fal_size = "landscape_16_9"
            elif ratio < 0.8:
                fal_size = "portrait_9_16"
            else:
                fal_size = "square"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{design_type}_{platform}_{timestamp}.png"
            image_path = generate_image(fal_prompt, size=fal_size, filename=filename)
            if image_path:
                self.log(f"Image generated: {image_path}")
        except Exception as e:
            self.log(f"Image generation failed: {e}")

        # Generate design brief via Claude
        brief = None
        brief_prompt = f"""Sen profesyonel bir grafik tasarımcısın. Aşağıdaki brief'i hazırla:

İşletme: {business_name}
Tasarım türü: {preset['description']}
Platform: {platform}
Boyut: {size}
Tema: {theme}
Metin: {prompt_text}

Şunları içeren bir tasarım brief'i oluştur:
1. Renk paleti (hex kodlarıyla)
2. Tipografi önerileri
3. Layout/kompozisyon
4. Görsel elementler
5. CTA (call-to-action) önerisi
6. Tasarım notları

Kısa ve actionable yaz."""

        brief = self.call_claude(brief_prompt)
        if not brief:
            brief = self._generate_fallback_brief(business_name, design_type, platform, theme, size)

        # Save design brief
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brief_data = {
            "business_name": business_name,
            "design_type": design_type,
            "platform": platform,
            "size": size,
            "theme": theme,
            "prompt": prompt_text,
            "brief": brief,
            "image_path": image_path,
            "created_at": timestamp,
        }

        briefs_dir = DATA_DIR / "designs"
        briefs_dir.mkdir(parents=True, exist_ok=True)
        self.save_data(f"designs/{timestamp}_{design_type}.json", brief_data)

        results = {
            "status": "ok",
            "summary": f"{preset['description']} oluşturuldu — {business_name} ({platform}, {size})",
            "metrics": {
                "design_type": design_type,
                "platform": platform,
                "size": size,
                "image_generated": bool(image_path),
                "brief_generated": bool(brief),
                "timestamp": datetime.now().isoformat(),
            },
            "design": brief_data,
            "recommendations": [
                f"Boyut: {size} — {platform} için optimize edildi",
                "Canva veya Figma'da brief'e göre finalize edin",
                "A/B test için farklı varyasyonlar deneyin",
                "Brand kit'inize uygun renkleri kullanın",
            ],
        }

        self.save_output("designer_report.json", results)
        self.log("Designer agent completed")
        return results

    def _generate_fallback_brief(self, business_name, design_type, platform, theme, size):
        return f"""# Tasarım Brief — {business_name}

## Genel Bilgi
- Tür: {design_type}
- Platform: {platform}
- Boyut: {size}
- Tema: {theme}

## Renk Paleti
- Ana renk: #e85d26 (Turuncu)
- İkincil: #1a1a2e (Koyu Lacivert)
- Accent: #00ff41 (Yeşil)
- Arka plan: #f8f9fa (Açık Gri)

## Tipografi
- Başlık: Bold Sans-Serif (Poppins, Inter)
- Alt metin: Regular Sans-Serif
- CTA: Semi-Bold

## Layout
- Temiz, minimal tasarım
- Sol üst: Logo
- Merkez: Ana mesaj
- Alt: CTA butonu

## CTA Önerisi
- "Hemen Başlayın"
- "Ücretsiz Teklif Alın"
- "Detaylı Bilgi"

## Notlar
- Mobil uyumlu tasarım
- Yüksek kontrast oranı
- Marka tutarlılığı
"""

    def batch_create(self, business_name: str = "", platforms: list = None,
                     design_type: str = "social_post") -> dict:
        """Create designs for multiple platforms at once."""
        if platforms is None:
            platforms = ["instagram", "facebook", "linkedin"]

        self.log(f"Batch creating {design_type} for {len(platforms)} platforms")
        results = []
        for platform in platforms:
            result = self.run(design_type=design_type, business_name=business_name, platform=platform)
            results.append({"platform": platform, "result": result})

        return {
            "status": "ok",
            "summary": f"{len(platforms)} platform için {design_type} oluşturuldu",
            "metrics": {"platforms": len(platforms), "successful": sum(1 for r in results if r["result"]["status"] == "ok")},
            "results": results,
        }
