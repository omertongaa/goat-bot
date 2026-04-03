"""goat — Agency-in-a-Box Agent System"""

AGENTS = {
    "goat":     {"name": "goat",     "role": "Master orchestrator — runs the full pipeline",       "category": "master",      "icon": "🎯"},
    "scout":    {"name": "Scout",    "role": "Finds potential clients via Google Maps / Apify",     "category": "acquisition", "icon": "🔍"},
    "filter":   {"name": "Filter",   "role": "Scores and qualifies leads for outreach",            "category": "acquisition", "icon": "⚡"},
    "auditor":  {"name": "Auditor",  "role": "Analyzes lead websites — SEO, broken links, tech",   "category": "acquisition", "icon": "🔬"},
    "outreach": {"name": "Outreach", "role": "Email warmup + cold campaigns via Instantly.ai",     "category": "sales",       "icon": "📧"},
    "pitch":    {"name": "Pitch",    "role": "Generates service proposals and pitch decks + PDF",   "category": "sales",       "icon": "📋"},
    "mentor":      {"name": "Mentor",      "role": "Agency guide — answers any business question",       "category": "education",   "icon": "🎓"},
    "sitebuilder": {"name": "SiteBuilder", "role": "Generates landing pages for agency and clients",    "category": "delivery",    "icon": "🌐"},

    # === Creative ===
    "designer":    {"name": "Designer",    "role": "Creates visuals — social posts, banners, ads, logos",     "category": "creative",    "icon": "🎨"},
    "videomaker":  {"name": "VideoMaker",  "role": "Video scripts, storyboards, short-form content",         "category": "creative",    "icon": "🎬"},
    "content":     {"name": "Content",     "role": "Blog posts, social media copy, email marketing text",    "category": "creative",    "icon": "✍️"},
    "presenter":   {"name": "Presenter",   "role": "Professional presentations and pitch decks (HTML)",      "category": "creative",    "icon": "📊"},
    "brandkit":    {"name": "BrandKit",    "role": "Brand identity — colors, fonts, guidelines, assets",     "category": "creative",    "icon": "💎"},

    # === Marketing ===
    "admanager":   {"name": "AdManager",   "role": "Ad campaign planning, copy, and optimization",           "category": "marketing",   "icon": "📢"},
    "social":      {"name": "Social",      "role": "Social media strategy, content planning, growth",        "category": "marketing",   "icon": "📱"},

    # === Intelligence ===
    "analytics":   {"name": "Analytics",   "role": "Business analytics, competitor & market research",       "category": "intelligence", "icon": "📈"},
}

CATEGORIES = {
    "master":       {"name": "Orchestrator",  "color": "#00ff41"},
    "acquisition":  {"name": "Acquisition",   "color": "#3b82f6"},
    "sales":        {"name": "Sales",         "color": "#ef4444"},
    "creative":     {"name": "Creative",      "color": "#f59e0b"},
    "marketing":    {"name": "Marketing",     "color": "#ec4899"},
    "intelligence": {"name": "Intelligence",  "color": "#8b5cf6"},
    "education":    {"name": "Education",     "color": "#6366f1"},
    "delivery":     {"name": "Delivery",      "color": "#14b8a6"},
}
