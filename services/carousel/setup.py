"""
Carousel Template — Kurulum Scripti
Kullanim: python setup.py
"""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
SKILL_TEMPLATE = HERE / ".claude-skill" / "SKILL.md.template"
BRAND_FILE = HERE / "brand.json"
BRAND_EXAMPLE = HERE / "brand.json.example"
VOICE_FILE = HERE / "voice.md"
VOICE_EXAMPLE = HERE / "voice.md.example"


def _slug(handle: str) -> str:
    replacements = str.maketrans(
        "ğĞüÜşŞıİöÖçÇ", "gGuUsSiIoOcC", "@"
    )
    s = handle.translate(replacements).lower()
    return "".join(c if c.isalnum() else "-" for c in s).strip("-")


def setup_brand() -> dict:
    if BRAND_FILE.exists():
        brand = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
        print(f"brand.json mevcut — handle: {brand.get('handle', '?')}")
        return brand

    print("\n--- Marka Ayarlari ---")
    handle = input("Marka handle'iniz (örn. @markam.io): ").strip()
    if not handle:
        handle = "@marka_handle"

    lang = input("Dil kodu (varsayilan: tr): ").strip() or "tr"

    print("Temalar: terminal-dark, editorial-cream, vibrant-gradient, minimal-mono, data-viz")
    theme = input("Varsayilan tema (varsayilan: terminal-dark): ").strip() or "terminal-dark"

    example = json.loads(BRAND_EXAMPLE.read_text(encoding="utf-8"))
    example["handle"] = handle
    example["lang"] = lang
    example["default_theme"] = theme

    BRAND_FILE.write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"brand.json olusturuldu ({handle}, {theme})")
    return example


def setup_voice() -> None:
    if VOICE_FILE.exists():
        print("voice.md mevcut — marka sesi tanimli.")
        return
    shutil.copy(VOICE_EXAMPLE, VOICE_FILE)
    print("\n[!] voice.md olusturuldu (sablondan kopyalandi).")
    print("    Lutfen voice.md dosyasini markanizin sesine gore doldurun,")
    print("    sonra bu scripti tekrar calistirin.")


def install_skill(brand: dict) -> None:
    slug = _slug(brand.get("handle", "marka"))
    handle = brand.get("handle", "@marka")
    project_path = str(HERE)
    voice_path = str(VOICE_FILE)

    skill_dir = CLAUDE_SKILLS / f"{slug}-carousel"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_out = skill_dir / "SKILL.md"

    if skill_out.exists():
        answer = input(f"\n{skill_out} zaten var. Üzerine yazilsin mi? [y/N]: ").strip().lower()
        if answer != "y":
            print("Skill kurulumu atildi.")
            return

    template = SKILL_TEMPLATE.read_text(encoding="utf-8")
    filled = (
        template
        .replace("{{BRAND_SLUG}}", slug)
        .replace("{{BRAND_HANDLE}}", handle)
        .replace("{{PROJECT_PATH}}", project_path)
        .replace("{{VOICE_PATH}}", voice_path)
    )
    skill_out.write_text(filled, encoding="utf-8")
    print(f"\nSkill kuruldu: {skill_out}")
    print(f"Claude Code'da kullanim: /{slug}-carousel \"konu\"")


def check_playwright() -> bool:
    if importlib.util.find_spec("playwright") is not None:
        print("playwright kurulu.")
        return True
    print("\n[!] playwright bulunamadi. Asagidaki komutla yukleyin:")
    print("    pip install playwright")
    print("    playwright install chromium")
    return False


def test_render() -> bool:
    import subprocess
    ornek = HERE / "content" / "ornek.json"
    if not ornek.exists():
        print("[!] content/ornek.json bulunamadi, test atiliyor.")
        return True

    print("\nTest render basliyor (content/ornek.json)...")
    result = subprocess.run(
        [sys.executable, str(HERE / "generate.py"), str(ornek)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        slides = list((HERE / "output").rglob("slide_*.png"))
        print(f"Test basarili: {len(slides)} PNG uretildi.")
        return True
    print("Test render hatasi:")
    print(result.stderr[-800:] if result.stderr else result.stdout[-800:])
    return False


def main() -> None:
    print("=== Carousel Template Kurulum ===\n")

    if not BRAND_EXAMPLE.exists():
        print("Hata: brand.json.example bulunamadi. Bu scripti carousel-template/ klasorunden calistirin.")
        sys.exit(1)

    brand = setup_brand()
    setup_voice()

    if not VOICE_FILE.exists() or VOICE_FILE.read_text(encoding="utf-8") == VOICE_EXAMPLE.read_text(encoding="utf-8"):
        print("\nUyari: voice.md henuz doldurulmamis. Skill kurulumu yapilacak ama")
        print("       markanizin sesini tanimlamadan once voice.md'yi duzenleyin.")

    install_skill(brand)

    playwright_ok = check_playwright()

    if playwright_ok:
        test_render()

    slug = _slug(brand.get("handle", "marka"))
    print(f"\n{'='*40}")
    print("Kurulum tamamlandi.")
    if playwright_ok:
        print(f"Claude Code'da baslatmak icin: /{slug}-carousel \"konu\"")
    else:
        print("Playwright yukledikten sonra bu scripti tekrar calistirin.")
    print("Branding icin brand.json ve voice.md dosyalarini duzenleyin.")


if __name__ == "__main__":
    main()
