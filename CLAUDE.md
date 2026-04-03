# goat — Agency-in-a-Box

## What This Is

goat is a FastAPI application that helps solo entrepreneurs build and run AI automation agencies. It runs on `localhost:7778` with a dark-themed "A Dark Room" style dashboard.

## Quick Start

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:7778
```

## Architecture

- **Backend:** FastAPI (Python 3.9+)
- **Frontend:** Single-page dashboard (`templates/dashboard.html`)
- **Storage:** JSON files in `data/` (no database)
- **Port:** 7778

## API Keys Required

| Key | Env Var | Purpose | Source |
|-----|---------|---------|--------|
| Apify | `APIFY_TOKEN` | Google Maps lead scraping | console.apify.com |
| fal.ai | `FAL_KEY` | Image generation (proposals, ads) | fal.ai |
| Instantly.ai | `INSTANTLY_API_KEY` | Email campaigns (optional) | app.instantly.ai |

Keys are stored in `.env` AND/OR `data/config/user_profile.json` (set via dashboard onboarding).

## Agent System

17 agents, each in `agents/{name}/agent.py`:

### Pipeline Flow
```
Scout → Filter → Pitch / Outreach
```

### Agent Details

**1. GOAT (Master Orchestrator)** — `agents/goat/agent.py`
- Runs Scout → Filter pipeline sequentially
- Category: master (green)

**2. Scout** — `agents/scout/agent.py`
- Finds leads via Google Maps using Apify (`compass~crawler-google-places` actor)
- **Fallback:** Free Google search via `googlesearch-python` if no Apify token
- Input: search query + location (from config or params)
- Output: `data/leads/raw/{timestamp}_{slug}.json`
- Report: `outputs/reports/scout_leads_report.json`
- **Requires:** `APIFY_TOKEN` (optional — falls back to free Google search)

**3. Filter** — `agents/filter/agent.py`
- Scores leads based on: email (+5), website (+3), phone (+1), rating 3.5-4.5 (+2), 20+ reviews (+2), 50+ reviews (+1), weak SEO (+2), no analytics (+1)
- Hot (≥8) / Warm (5-7) / Cold (<5)
- Now includes website SEO/analytics checks in scoring
- Output: `data/leads/qualified/{timestamp}_qualified.json`
- Report: `outputs/reports/filter_qualified_report.json`

**4. Auditor** — `agents/auditor/agent.py`
- Analyzes lead websites: SEO audit, broken link detection, tech stack identification
- Runs on single URL or batch-audits all qualified leads with websites
- Generates pitch ammunition (low SEO = opportunity)
- Output: `data/audits/{timestamp}.json`
- Report: `outputs/reports/auditor_report.json`
- **Requires:** Nothing — pure Python

**5. Pitch** — `agents/pitch/agent.py`
- Generates Turkish proposal markdown for hot leads
- Auto-generates PDF version alongside markdown
- Auto-appends website audit report (SEO score, broken links, tech stack)
- Uses Claude CLI (subprocess) or falls back to template
- Generates cover image via fal.ai
- Output: `data/proposals/{slug}_{timestamp}.md` + `outputs/proposals/{slug}_{timestamp}.pdf`
- **Requires:** `FAL_KEY` (optional, for cover images)

**5. Outreach** — `agents/outreach/agent.py`
- Creates 3-step email campaigns via Instantly.ai API v2
- Day 0: Intro, Day 3: Value prop, Day 7: Follow-up
- Campaigns created as DRAFT (user activates in Instantly dashboard)
- Output: `data/campaigns/{campaign_id}.json`
- **Requires:** `INSTANTLY_API_KEY`

**6. Mentor** — `agents/mentor/agent.py`
- Answers agency questions using classroom content in `data/classroom/`
- Topics: getting_started, pricing_guide, client_acquisition, tools_guide, service_catalog
- Uses Claude CLI or returns static content
- All content in Turkish

### Creative Agents

**7. Designer** — `agents/designer/agent.py`
- Creates visual content: social posts, banners, ads, logos, infographics, carousels
- Platform-specific sizing (Instagram, Facebook, TikTok, LinkedIn, YouTube)
- Generates design brief + fal.ai image
- Batch mode: create for multiple platforms at once
- Input: design_type, business_name, platform, theme, text
- Output: `data/designs/{timestamp}_{type}.json`

**8. VideoMaker** — `agents/videomaker/agent.py`
- Video scripts, storyboards, and content plans
- Formats: reels, youtube_short, youtube, tiktok, ad_video, testimonial, explainer
- Generates scripts + storyboard + thumbnail
- Input: video_type, business_name, topic, target_audience, count
- Output: `data/videos/{timestamp}_{type}.json`

**9. Content** — `agents/content/agent.py`
- Blog posts, social media copy, email marketing, newsletters, case studies
- Content calendar generation (30-day plans)
- Social media batch creation
- SEO-optimized content
- Input: content_type, topic, tone, language, platform, count
- Output: `data/content/{timestamp}_{type}.json` + `outputs/content/{slug}.md`

**10. Presenter** — `agents/presenter/agent.py`
- Professional HTML presentations with keyboard navigation
- Templates: pitch_deck, proposal, report, training, company, case_study
- Generates slide content + interactive HTML
- Input: template, topic, business_name, audience
- Output: `data/presentations/{timestamp}_{template}.json` + `outputs/presentations/{slug}.html`

**11. BrandKit** — `agents/brandkit/agent.py`
- Complete brand identity: colors, fonts, tone of voice, guidelines
- Style presets: modern, minimal, bold, corporate, warm, tech
- Generates HTML brand board
- Logo concept via fal.ai
- Input: business_name, industry, style, values
- Output: `data/brandkit/{timestamp}_brand.json` + `outputs/brandkit/{timestamp}_brand_board.html`

### Marketing Agents

**12. AdManager** — `agents/admanager/agent.py`
- Ad campaign planning for Google, Meta, TikTok, LinkedIn
- Generates campaign strategy + ad copies (5 variants)
- Budget allocation and KPI targets
- Input: platform, campaign_type, budget, business_name, target_audience
- Output: `data/ads/{timestamp}_{platform}_{type}.json`

**13. Social** — `agents/social/agent.py`
- Social media strategy, hashtag research, bio generation, profile audit
- Platform-specific guidance: Instagram, TikTok, LinkedIn, Twitter, Facebook, YouTube
- 90-day growth plans
- Input: action (strategy/hashtags/bio/audit/growth), platform, business_name
- Output: `data/social/{timestamp}_{platform}_{action}.json`

### Intelligence Agent

**14. Analytics** — `agents/analytics/agent.py`
- Business analytics: competitor, market, SWOT, pricing, trend analysis
- Internal performance reporting from pipeline data
- Conversion funnel calculation
- Input: analysis_type, target, industry, location
- Output: `data/analytics/{timestamp}_{type}.json`

### System Agent

**15. MCP Hub** — `agents/mcphub/agent.py`
- MCP (Model Context Protocol) tools registry
- Browse 20+ MCP servers by category
- Install, search, and get config snippets
- Niche-based recommendations
- Actions: list, info, install, installed, search, recommend
- Output: `data/mcp/installed.json`
- Documentation: `docs/MCP.md`

## API Routes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Dashboard |
| `/api/agent/{id}/run` | POST | Run agent (Scout accepts: query, location, limit) |
| `/api/agents/run-pipeline` | POST | Run Scout → Filter pipeline |
| `/api/agent/{id}/result` | GET | Get latest agent result |
| `/api/leads` | GET | Raw leads |
| `/api/leads/qualified` | GET | Scored leads |
| `/api/chat` | POST | Chat with agent (body: {message, agent_id}) |
| `/api/config` | GET/POST | Load/save config |
| `/api/creative` | POST | Generate image (body: {prompt, type, business_name, ...}) |
| `/api/reset` | POST | Delete all data |
| `/api/audit` | POST | Run SEO/broken links/tech audit (body: {url}) |
| `/api/audit/lead/{name}` | GET | Audit a specific lead's website |
| `/api/proposal/pdf` | POST | Convert markdown to PDF (body: {path} or {markdown}) |
| `/api/proposals/pdf/all` | POST | Convert all markdown proposals to PDF |
| `/api/search/google` | POST | Free Google search for leads (body: {query, location, limit}) |
| `/api/schedules` | GET/POST | List or create scheduled agent runs |
| `/api/schedules/{id}` | DELETE | Remove a scheduled run |
| `/api/schedules/logs` | GET | View recent scheduled run logs |
| `/api/presentations` | GET | List generated presentations |
| `/presentation/{filename}` | GET | Preview presentation HTML |
| `/api/brandkit` | GET | Get latest brand kit |
| `/brandkit/{filename}` | GET | Preview brand board HTML |
| `/api/mcp/tools` | GET | List MCP tools (optional: ?category=) |
| `/api/mcp/tools/{id}` | GET | Get MCP tool details + config |
| `/api/mcp/install` | POST | Save MCP tool config |
| `/api/mcp/installed` | GET | List installed MCP tools |
| `/api/mcp/config` | GET | Generate full MCP config file |
| `/api/mcp/search` | POST | Search MCP tools by keyword |
| `/api/analytics/dashboard` | GET | Full analytics dashboard data |
| `/api/analytics/funnel` | GET | Conversion funnel data |
| `/api/analytics/summary` | GET | Weekly performance summary |
| `/api/content` | GET | List generated content files |
| `/api/designs` | GET | List generated design briefs |
| `/api/videos` | GET | List generated video projects |

## Services

**1. Scraper** (`services/scraper.py`)
- `scrape_google_maps(query, location, max_results)` → list of leads
- Uses Apify REST API, polls every 10s, max 10min timeout

**2. Email** (`services/email.py`)
- `test_connection(api_key)` → bool
- `create_campaign(name, api_key)` → campaign_id
- `add_leads_to_campaign(campaign_id, leads, api_key)` → bool
- Uses Instantly.ai API v2 with Bearer auth

**3. Image** (`services/image.py`)
- `generate_image(prompt, size, model, filename)` → path
- `generate_ad_creative(business_name, type, service)` → path
- `generate_proposal_cover(agency, client, type)` → path
- `generate_social_example(type, platform)` → path
- Default model: `fal-ai/fast-sdxl`
- Output: `outputs/creatives/`

**4. Site Auditor** (`services/site_auditor.py`)
- `check_seo(url)` → SEO score + issues (title, meta, OG, H1, viewport, HTTPS, robots, sitemap)
- `check_broken_links(url)` → broken link count + details
- `detect_tech_stack(url)` → detected technologies (CMS, frameworks, analytics, hosting)
- `full_audit(url)` → combined report with overall score
- **No API keys needed** — pure Python + requests

**5. PDF Generator** (`services/pdf_generator.py`)
- `markdown_to_pdf(text, filename)` → styled PDF with goat branding
- `proposal_file_to_pdf(md_path)` → convert existing .md file
- `convert_all_proposals()` → batch convert all proposals
- Uses fpdf2 (pure Python, no system dependencies)
- Output: `outputs/proposals/`

**6. Scheduler** (`services/scheduler.py`)
- `add_schedule(agent_id, cron, params)` → schedule recurring agent runs
- `remove_schedule(id)` → cancel a schedule
- `list_schedules()` → view all active schedules
- Supports cron expressions or shorthands: "daily", "hourly", "weekly", "twice_daily"
- Auto-starts on app startup, restores saved schedules
- Logs all runs to `data/logs/scheduled_runs.json`
- Uses APScheduler (pure Python)

**7. Video** (`services/video.py`)
- `get_format_spec(platform_format)` → video specs (width, height, fps, ratio)
- `get_script_template(template_name)` → script structure (hook_story_cta, listicle, etc.)
- `generate_shot_list(scenes)` → detailed shot list
- `save_video_project(project_data)` → save to disk
- Formats: instagram_reel, tiktok, youtube, youtube_short, ad_video, etc.
- **No API keys needed**

**8. Analytics Engine** (`services/analytics_engine.py`)
- `gather_pipeline_metrics()` → aggregate all internal metrics
- `calculate_conversion_funnel()` → lead → qualified → hot → deal → won
- `generate_weekly_summary()` → performance summary with highlights
- **No API keys needed** — reads from internal data files

**9. Presentation** (`services/presentation.py`)
- `generate_presentation_html(title, slides, theme)` → interactive HTML presentation
- `list_presentations()` → list all generated presentations
- Themes: dark, light, corporate, creative, minimal
- Keyboard navigation (arrow keys + fullscreen)
- **No API keys needed**

**10. Social Media** (`services/social_media.py`)
- `get_posting_schedule(platform)` → optimal posting times (Turkey TZ)
- `get_content_mix()` → recommended content ratio (education/engagement/proof/entertainment/promo)
- `generate_hashtag_sets(niche, platform)` → categorized hashtags
- `save_content_calendar(data)` → save calendar to disk
- **No API keys needed**

**11. Brand** (`services/brand.py`)
- `get_palette_for_industry(industry)` → industry-specific color palette
- `get_font_pairing(style)` → Google Fonts recommendations
- `generate_css_variables(colors, fonts)` → CSS custom properties
- `save_brand_kit(data)` → save brand kit to disk
- 11 industry palettes, 7 font pairings
- **No API keys needed**

**12. MCP Registry** (`services/mcp_registry.py`)
- `list_tools(category)` → browse MCP server catalog (20+ servers)
- `get_tool_config(tool_id)` → config snippet for claude_desktop_config.json
- `generate_full_config(tool_ids)` → multi-tool config
- `search_tools(query)` → keyword search across tools
- `save_installed_tools(tool_ids)` → persist installed tools
- Categories: core, search, web, data, dev, comm, productivity, ai, ecommerce, crm
- Documentation: `docs/MCP.md`
- **No API keys needed**

**13. Google Search** (`services/google_search.py`)
- `search_and_enrich(query, location, num_results)` → leads from Google
- Extracts: name, website, email, phone, description from result pages
- **No API keys needed** — free alternative to Apify
- Auto-used as Scout fallback when APIFY_TOKEN is not set

## Data Structure

```
data/
├── config/user_profile.json    # Agency config + API keys
├── leads/raw/                  # Apify scrape results
├── leads/qualified/            # Scored + classified leads
├── campaigns/                  # Instantly.ai campaign data
├── proposals/                  # Generated pitch documents
├── audits/                     # Website audit reports
├── logs/scheduled_runs.json    # Scheduled run history
├── designs/                    # Design briefs (Designer agent)
├── videos/                     # Video projects (VideoMaker agent)
├── content/                    # Written content (Content agent)
├── presentations/              # Presentation data (Presenter agent)
├── brandkit/                   # Brand identity kits (BrandKit agent)
├── ads/                        # Ad campaigns (AdManager agent)
├── social/                     # Social media plans (Social agent)
├── analytics/                  # Analysis reports (Analytics agent)
├── mcp/installed.json          # Installed MCP tools (MCP Hub)
├── pipeline/                   # CRM pipeline data
│   ├── stages.json
│   ├── notes.json
│   ├── reminders.json
│   └── deals.json
└── classroom/                  # Educational markdown content
    ├── getting_started.md
    ├── pricing_guide.md
    ├── client_acquisition.md
    ├── tools_guide.md
    └── service_catalog.md

outputs/
├── reports/                    # Agent execution reports (JSON)
├── creatives/                  # Generated images (fal.ai)
├── proposals/                  # PDF versions of proposals
├── sites/                      # Generated landing pages (HTML)
├── presentations/              # Generated presentations (HTML)
├── brandkit/                   # Brand board HTML files
├── content/                    # Generated blog/article markdown
└── logs/                       # Scheduled run execution logs
```

## Dashboard Onboarding Flow

1. Owner name → 2. Agency name → 3. Niche → 4. Target cities → 5. Apify token → 6. fal.ai key

Config saved to `data/config/user_profile.json` and keys injected to env at runtime.

## Key Design Decisions

- **No database** — all JSON file storage
- **Claude CLI optional** — every LLM call has a template fallback
- **Turkish language** — all user-facing text in Turkish
- **Agent reports standardized** — every agent returns `{status, summary, metrics, recommendations}`
- **Dark Room aesthetic** — terminal-style UI with pixel art bot character
- **Draft campaigns** — outreach never auto-sends; user must activate in Instantly.ai

## Dashboard Colors

```
--bg: #0a0a0c     --accent: #e85d26 (orange)
--surface: #111114  --green: #34d399
--text: #e8e8e8     --yellow: #fbbf24
--dim: #8a8a98      --blue: #60a5fa
```
