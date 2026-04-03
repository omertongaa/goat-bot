"""Social media service — platform specs, hashtag tools, posting schedules."""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# Optimal posting times by platform (Turkey timezone, UTC+3)
POSTING_TIMES = {
    "instagram": {
        "best_days": ["Salı", "Çarşamba", "Perşembe"],
        "best_hours": ["10:00", "13:00", "18:00"],
        "worst_hours": ["02:00-06:00"],
        "frequency": "3-5 post/hafta + daily stories",
    },
    "tiktok": {
        "best_days": ["Salı", "Perşembe", "Cuma"],
        "best_hours": ["12:00", "15:00", "21:00"],
        "worst_hours": ["03:00-07:00"],
        "frequency": "1-3 video/gün",
    },
    "linkedin": {
        "best_days": ["Salı", "Çarşamba", "Perşembe"],
        "best_hours": ["08:00", "10:00", "12:00"],
        "worst_hours": ["hafta sonu", "18:00 sonrası"],
        "frequency": "3-5 post/hafta",
    },
    "twitter": {
        "best_days": ["Pazartesi", "Salı", "Çarşamba"],
        "best_hours": ["09:00", "12:00", "17:00"],
        "worst_hours": ["23:00-06:00"],
        "frequency": "3-7 tweet/gün",
    },
    "facebook": {
        "best_days": ["Çarşamba", "Perşembe", "Cuma"],
        "best_hours": ["09:00", "13:00", "16:00"],
        "worst_hours": ["22:00-06:00"],
        "frequency": "3-5 post/hafta",
    },
    "youtube": {
        "best_days": ["Perşembe", "Cuma", "Cumartesi"],
        "best_hours": ["12:00", "15:00", "18:00"],
        "worst_hours": ["02:00-08:00"],
        "frequency": "1-2 video/hafta + 3-5 shorts",
    },
}

# Content mix ratios (percentage)
CONTENT_MIX = {
    "education": 40,      # Tips, tutorials, how-tos
    "engagement": 20,     # Questions, polls, behind-the-scenes
    "social_proof": 20,   # Testimonials, case studies, results
    "entertainment": 10,  # Trends, memes, fun content
    "promotion": 10,      # CTAs, offers, product/service
}


def get_posting_schedule(platform, log=None):
    """Get optimal posting schedule for a platform."""
    schedule = POSTING_TIMES.get(platform, POSTING_TIMES["instagram"])
    if log:
        log(f"Schedule for {platform}: {schedule['frequency']}")
    return schedule


def get_content_mix():
    """Get recommended content mix ratios."""
    return CONTENT_MIX


def generate_hashtag_sets(niche, platform="instagram", log=None):
    """Generate categorized hashtag sets for a niche."""
    max_tags = {
        "instagram": 30, "tiktok": 10, "linkedin": 5,
        "twitter": 3, "facebook": 10, "youtube": 15,
    }

    # Base hashtags — universal Turkish business hashtags
    base_tags = [
        "işletme", "girişimci", "dijitalpazarlama", "sosyalmedya",
        "büyüme", "başarı", "motivasyon", "türkiye", "iş",
    ]

    # Niche-specific additions
    niche_lower = niche.lower()
    niche_tags = []
    if "pazarlama" in niche_lower or "marketing" in niche_lower:
        niche_tags = ["contentmarketing", "seo", "reklam", "marka", "pazarlama", "onlinepazarlama"]
    elif "teknoloji" in niche_lower or "tech" in niche_lower:
        niche_tags = ["teknoloji", "yazılım", "ai", "yapayZeka", "startup", "saas"]
    elif "eğitim" in niche_lower:
        niche_tags = ["eğitim", "öğrenme", "kişiselgelişim", "kariyer", "mentorluk"]
    elif "sağlık" in niche_lower:
        niche_tags = ["sağlık", "wellness", "fitness", "beslenme", "yaşam"]
    elif "e-ticaret" in niche_lower or "ecommerce" in niche_lower:
        niche_tags = ["eticaret", "onlinesatış", "shopify", "mağaza", "satış"]

    all_tags = list(set(base_tags + niche_tags))[:max_tags.get(platform, 10)]
    tagged = ["#" + t for t in all_tags]

    sets = {
        "awareness": tagged[:len(tagged)//3],
        "niche": tagged[len(tagged)//3:2*len(tagged)//3],
        "engagement": tagged[2*len(tagged)//3:],
    }

    if log:
        log(f"Generated {len(all_tags)} hashtags for {platform}")

    return sets


def save_content_calendar(calendar_data, log=None):
    """Save a content calendar to disk."""
    out_dir = DATA_DIR / "social"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{timestamp}_calendar.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(calendar_data, f, indent=2, ensure_ascii=False, default=str)

    if log:
        log(f"Content calendar saved: {path}")
    return str(path)
