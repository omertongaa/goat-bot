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
}

CATEGORIES = {
    "master":      {"name": "Orchestrator",  "color": "#00ff41"},
    "acquisition": {"name": "Acquisition",   "color": "#3b82f6"},
    "sales":       {"name": "Sales",         "color": "#ef4444"},
    "education":   {"name": "Education",     "color": "#8b5cf6"},
    "delivery":    {"name": "Delivery",      "color": "#f59e0b"},
}
