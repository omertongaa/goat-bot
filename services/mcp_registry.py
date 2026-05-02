"""MCP Registry service — Model Context Protocol tools catalog and config generator."""

import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("GOAT_DATA_DIR") or (BASE_DIR / "data"))


# MCP Server catalog — curated list of useful MCP servers
MCP_CATALOG = {
    # === Official Anthropic Servers ===
    "filesystem": {
        "name": "Filesystem",
        "author": "Anthropic",
        "description": "Dosya ve dizin okuma, yazma, arama işlemleri",
        "category": "core",
        "package": "@anthropic/mcp-server-filesystem",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-filesystem", "{ALLOWED_DIR}"],
        },
        "env_vars": [],
        "tags": ["file", "read", "write", "search"],
    },
    "fetch": {
        "name": "Fetch",
        "author": "Anthropic",
        "description": "Web sayfalarını çek ve parse et — markdown çıktı",
        "category": "core",
        "package": "@anthropic/mcp-server-fetch",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-fetch"],
        },
        "env_vars": [],
        "tags": ["web", "scraping", "http"],
    },
    "brave-search": {
        "name": "Brave Search",
        "author": "Anthropic",
        "description": "Brave Search API ile web araması",
        "category": "search",
        "package": "@anthropic/mcp-server-brave-search",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-brave-search"],
            "env": {"BRAVE_API_KEY": "{BRAVE_API_KEY}"},
        },
        "env_vars": ["BRAVE_API_KEY"],
        "tags": ["search", "web", "api"],
    },
    "github": {
        "name": "GitHub",
        "author": "Anthropic",
        "description": "GitHub repo, issue, PR ve Actions yönetimi",
        "category": "dev",
        "package": "@anthropic/mcp-server-github",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-github"],
            "env": {"GITHUB_TOKEN": "{GITHUB_TOKEN}"},
        },
        "env_vars": ["GITHUB_TOKEN"],
        "tags": ["github", "git", "code", "pr", "issues"],
    },
    "sqlite": {
        "name": "SQLite",
        "author": "Anthropic",
        "description": "SQLite veritabanı sorgulama ve yönetimi",
        "category": "data",
        "package": "@anthropic/mcp-server-sqlite",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-sqlite", "--db-path", "{DB_PATH}"],
        },
        "env_vars": [],
        "tags": ["database", "sql", "query"],
    },
    "postgres": {
        "name": "PostgreSQL",
        "author": "Anthropic",
        "description": "PostgreSQL veritabanına bağlanma ve sorgulama",
        "category": "data",
        "package": "@anthropic/mcp-server-postgres",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-postgres", "{POSTGRES_URL}"],
        },
        "env_vars": ["POSTGRES_URL"],
        "tags": ["database", "sql", "postgres"],
    },
    "puppeteer": {
        "name": "Puppeteer",
        "author": "Anthropic",
        "description": "Browser otomasyonu — screenshot, scraping, form doldurma",
        "category": "web",
        "package": "@anthropic/mcp-server-puppeteer",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-puppeteer"],
        },
        "env_vars": [],
        "tags": ["browser", "automation", "screenshot", "scraping"],
    },
    "google-drive": {
        "name": "Google Drive",
        "author": "Anthropic",
        "description": "Google Drive dosya ve klasör yönetimi",
        "category": "productivity",
        "package": "@anthropic/mcp-server-google-drive",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-google-drive"],
        },
        "env_vars": [],
        "tags": ["google", "drive", "files", "cloud"],
    },
    "slack": {
        "name": "Slack",
        "author": "Anthropic",
        "description": "Slack mesaj gönderme, kanal yönetimi",
        "category": "comm",
        "package": "@anthropic/mcp-server-slack",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-slack"],
            "env": {"SLACK_TOKEN": "{SLACK_TOKEN}"},
        },
        "env_vars": ["SLACK_TOKEN"],
        "tags": ["slack", "messaging", "team"],
    },

    # === Community Servers ===
    "git": {
        "name": "Git",
        "author": "Community",
        "description": "Git operasyonları — clone, commit, branch, log",
        "category": "dev",
        "package": "mcp-server-git",
        "transport": "stdio",
        "config": {
            "command": "uvx",
            "args": ["mcp-server-git"],
        },
        "env_vars": [],
        "tags": ["git", "version-control", "code"],
    },
    "notion": {
        "name": "Notion",
        "author": "Community",
        "description": "Notion sayfa, veritabanı ve blok yönetimi",
        "category": "productivity",
        "package": "mcp-server-notion",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "mcp-server-notion"],
            "env": {"NOTION_TOKEN": "{NOTION_TOKEN}"},
        },
        "env_vars": ["NOTION_TOKEN"],
        "tags": ["notion", "notes", "wiki", "database"],
    },
    "replicate": {
        "name": "Replicate",
        "author": "Community",
        "description": "Replicate üzerinden AI model çalıştırma (görsel, video, ses)",
        "category": "ai",
        "package": "mcp-server-replicate",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "mcp-server-replicate"],
            "env": {"REPLICATE_API_TOKEN": "{REPLICATE_API_TOKEN}"},
        },
        "env_vars": ["REPLICATE_API_TOKEN"],
        "tags": ["ai", "image", "video", "audio", "model"],
    },
    "elevenlabs": {
        "name": "ElevenLabs",
        "author": "Community",
        "description": "Text-to-speech ve ses klonlama",
        "category": "ai",
        "package": "mcp-server-elevenlabs",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "mcp-server-elevenlabs"],
            "env": {"ELEVENLABS_API_KEY": "{ELEVENLABS_API_KEY}"},
        },
        "env_vars": ["ELEVENLABS_API_KEY"],
        "tags": ["tts", "voice", "audio", "speech"],
    },
    "shopify": {
        "name": "Shopify",
        "author": "Community",
        "description": "Shopify mağaza yönetimi — ürün, sipariş, müşteri",
        "category": "ecommerce",
        "package": "mcp-server-shopify",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "mcp-server-shopify"],
            "env": {"SHOPIFY_ACCESS_TOKEN": "{SHOPIFY_ACCESS_TOKEN}"},
        },
        "env_vars": ["SHOPIFY_ACCESS_TOKEN"],
        "tags": ["ecommerce", "shop", "products", "orders"],
    },
    "stripe": {
        "name": "Stripe",
        "author": "Community",
        "description": "Ödeme, abonelik ve fatura yönetimi",
        "category": "ecommerce",
        "package": "mcp-server-stripe",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "mcp-server-stripe"],
            "env": {"STRIPE_API_KEY": "{STRIPE_API_KEY}"},
        },
        "env_vars": ["STRIPE_API_KEY"],
        "tags": ["payment", "billing", "subscription"],
    },
    "hubspot": {
        "name": "HubSpot",
        "author": "Community",
        "description": "CRM — contact, deal, company yönetimi",
        "category": "crm",
        "package": "mcp-server-hubspot",
        "transport": "stdio",
        "config": {
            "command": "npx",
            "args": ["-y", "mcp-server-hubspot"],
            "env": {"HUBSPOT_ACCESS_TOKEN": "{HUBSPOT_ACCESS_TOKEN}"},
        },
        "env_vars": ["HUBSPOT_ACCESS_TOKEN"],
        "tags": ["crm", "contacts", "deals", "sales"],
    },
}

MCP_CATEGORIES = {
    "core": {"name": "Temel", "icon": "⚙️", "description": "Temel MCP araçları — dosya, web, arama"},
    "search": {"name": "Arama", "icon": "🔍", "description": "Web arama entegrasyonları"},
    "web": {"name": "Web", "icon": "🌐", "description": "Web scraping ve browser otomasyonu"},
    "data": {"name": "Veritabanı", "icon": "🗄️", "description": "SQL ve NoSQL veritabanları"},
    "dev": {"name": "Geliştirici", "icon": "💻", "description": "Git, GitHub ve geliştirici araçları"},
    "comm": {"name": "İletişim", "icon": "💬", "description": "Mesajlaşma ve iletişim"},
    "productivity": {"name": "Verimlilik", "icon": "📋", "description": "Doküman ve proje yönetimi"},
    "ai": {"name": "AI & Medya", "icon": "🤖", "description": "AI model çalıştırma, görsel/ses üretimi"},
    "analytics": {"name": "Analitik", "icon": "📊", "description": "Veri analizi ve raporlama"},
    "ecommerce": {"name": "E-Ticaret", "icon": "🛒", "description": "Online mağaza ve ödeme"},
    "crm": {"name": "CRM", "icon": "👥", "description": "Müşteri ilişkileri yönetimi"},
}


def list_tools(category=None, log=None):
    """List all MCP tools, optionally filtered by category."""
    tools = []
    for tid, tool in MCP_CATALOG.items():
        if category and tool["category"] != category:
            continue
        tools.append({
            "id": tid,
            "name": tool["name"],
            "author": tool["author"],
            "description": tool["description"],
            "category": tool["category"],
            "package": tool["package"],
            "requires_key": len(tool["env_vars"]) > 0,
        })

    if log:
        log(f"Listed {len(tools)} MCP tools")
    return tools


def get_tool_config(tool_id, log=None):
    """Get the configuration snippet for a specific MCP tool."""
    tool = MCP_CATALOG.get(tool_id)
    if not tool:
        return None

    config = {
        "mcpServers": {
            tool_id: tool["config"]
        }
    }

    if log:
        log(f"Config for {tool['name']}: {json.dumps(config, indent=2)}")
    return config


def generate_full_config(tool_ids, log=None):
    """Generate a full MCP config for multiple tools."""
    servers = {}
    for tid in tool_ids:
        tool = MCP_CATALOG.get(tid)
        if tool:
            servers[tid] = tool["config"]

    config = {"mcpServers": servers}

    if log:
        log(f"Generated config for {len(servers)} tools")
    return config


def search_tools(query, log=None):
    """Search MCP tools by name, description, or tags."""
    query_lower = query.lower()
    results = []
    for tid, tool in MCP_CATALOG.items():
        searchable = f"{tool['name']} {tool['description']} {' '.join(tool['tags'])}".lower()
        if query_lower in searchable or query_lower in tid:
            results.append({
                "id": tid,
                "name": tool["name"],
                "description": tool["description"],
                "category": tool["category"],
            })

    if log:
        log(f"Search '{query}': {len(results)} results")
    return results


def save_installed_tools(tool_ids, log=None):
    """Save list of installed MCP tools."""
    mcp_dir = DATA_DIR / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    installed = {}
    for tid in tool_ids:
        tool = MCP_CATALOG.get(tid)
        if tool:
            installed[tid] = {
                "name": tool["name"],
                "package": tool["package"],
                "config": tool["config"],
                "installed_at": datetime.now().isoformat(),
            }

    path = mcp_dir / "installed.json"
    with open(path, "w") as f:
        json.dump(installed, f, indent=2, ensure_ascii=False)

    if log:
        log(f"Saved {len(installed)} installed tools")
    return installed
