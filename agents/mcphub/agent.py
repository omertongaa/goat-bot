"""MCP Hub Agent — Model Context Protocol tools registry and integration."""

import json
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class MCPHubAgent(BaseAgent):
    agent_id = "mcphub"
    name = "MCP Hub"
    role = "MCP tools registry — browse, install, and manage MCP integrations"
    category = "system"

    # Built-in MCP tool registry
    MCP_REGISTRY = {
        # File & Data
        "filesystem": {
            "name": "Filesystem",
            "description": "Read, write, and manage files and directories",
            "category": "file",
            "package": "@anthropic/mcp-server-filesystem",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/dir"]},
        },
        "sqlite": {
            "name": "SQLite",
            "description": "Query and manage SQLite databases",
            "category": "data",
            "package": "@anthropic/mcp-server-sqlite",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-sqlite", "--db-path", "data.db"]},
        },
        "postgres": {
            "name": "PostgreSQL",
            "description": "Connect and query PostgreSQL databases",
            "category": "data",
            "package": "@anthropic/mcp-server-postgres",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-postgres", "postgresql://localhost/db"]},
        },
        # Web & Search
        "brave-search": {
            "name": "Brave Search",
            "description": "Web search via Brave Search API",
            "category": "search",
            "package": "@anthropic/mcp-server-brave-search",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-brave-search"], "env": {"BRAVE_API_KEY": ""}},
        },
        "fetch": {
            "name": "Fetch",
            "description": "Fetch and parse web pages, extract content",
            "category": "web",
            "package": "@anthropic/mcp-server-fetch",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-fetch"]},
        },
        "puppeteer": {
            "name": "Puppeteer",
            "description": "Browser automation — screenshots, scraping, form filling",
            "category": "web",
            "package": "@anthropic/mcp-server-puppeteer",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-puppeteer"]},
        },
        # Developer Tools
        "github": {
            "name": "GitHub",
            "description": "Manage repos, issues, PRs, and GitHub Actions",
            "category": "dev",
            "package": "@anthropic/mcp-server-github",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-github"], "env": {"GITHUB_TOKEN": ""}},
        },
        "git": {
            "name": "Git",
            "description": "Git operations — clone, commit, branch, log",
            "category": "dev",
            "package": "mcp-server-git",
            "config": {"command": "uvx", "args": ["mcp-server-git"]},
        },
        # Communication
        "slack": {
            "name": "Slack",
            "description": "Send messages, manage channels, read conversations",
            "category": "comm",
            "package": "@anthropic/mcp-server-slack",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-slack"], "env": {"SLACK_TOKEN": ""}},
        },
        "gmail": {
            "name": "Gmail",
            "description": "Read, send, and manage Gmail emails",
            "category": "comm",
            "package": "mcp-server-gmail",
            "config": {"command": "npx", "args": ["-y", "mcp-server-gmail"]},
        },
        # Productivity
        "google-drive": {
            "name": "Google Drive",
            "description": "Manage Google Drive files and folders",
            "category": "productivity",
            "package": "@anthropic/mcp-server-google-drive",
            "config": {"command": "npx", "args": ["-y", "@anthropic/mcp-server-google-drive"]},
        },
        "google-calendar": {
            "name": "Google Calendar",
            "description": "Manage calendar events and schedules",
            "category": "productivity",
            "package": "mcp-server-google-calendar",
            "config": {"command": "npx", "args": ["-y", "mcp-server-google-calendar"]},
        },
        "notion": {
            "name": "Notion",
            "description": "Read and write Notion pages, databases, blocks",
            "category": "productivity",
            "package": "mcp-server-notion",
            "config": {"command": "npx", "args": ["-y", "mcp-server-notion"], "env": {"NOTION_TOKEN": ""}},
        },
        # AI & Media
        "dalle": {
            "name": "DALL-E",
            "description": "Generate images via OpenAI DALL-E",
            "category": "ai",
            "package": "mcp-server-dalle",
            "config": {"command": "npx", "args": ["-y", "mcp-server-dalle"], "env": {"OPENAI_API_KEY": ""}},
        },
        "replicate": {
            "name": "Replicate",
            "description": "Run AI models via Replicate (image, video, audio)",
            "category": "ai",
            "package": "mcp-server-replicate",
            "config": {"command": "npx", "args": ["-y", "mcp-server-replicate"], "env": {"REPLICATE_API_TOKEN": ""}},
        },
        "elevenlabs": {
            "name": "ElevenLabs",
            "description": "Text-to-speech and voice cloning",
            "category": "ai",
            "package": "mcp-server-elevenlabs",
            "config": {"command": "npx", "args": ["-y", "mcp-server-elevenlabs"], "env": {"ELEVENLABS_API_KEY": ""}},
        },
        # Analytics
        "google-analytics": {
            "name": "Google Analytics",
            "description": "Read GA4 data — pageviews, sessions, conversions",
            "category": "analytics",
            "package": "mcp-server-google-analytics",
            "config": {"command": "npx", "args": ["-y", "mcp-server-google-analytics"]},
        },
        # E-Commerce
        "shopify": {
            "name": "Shopify",
            "description": "Manage Shopify store — products, orders, customers",
            "category": "ecommerce",
            "package": "mcp-server-shopify",
            "config": {"command": "npx", "args": ["-y", "mcp-server-shopify"], "env": {"SHOPIFY_ACCESS_TOKEN": ""}},
        },
        "stripe": {
            "name": "Stripe",
            "description": "Manage payments, subscriptions, and invoices",
            "category": "ecommerce",
            "package": "mcp-server-stripe",
            "config": {"command": "npx", "args": ["-y", "mcp-server-stripe"], "env": {"STRIPE_API_KEY": ""}},
        },
        # CRM
        "hubspot": {
            "name": "HubSpot",
            "description": "CRM operations — contacts, deals, companies",
            "category": "crm",
            "package": "mcp-server-hubspot",
            "config": {"command": "npx", "args": ["-y", "mcp-server-hubspot"], "env": {"HUBSPOT_ACCESS_TOKEN": ""}},
        },
    }

    MCP_CATEGORIES = {
        "file": "Dosya & Sistem",
        "data": "Veritabanı",
        "search": "Arama",
        "web": "Web & Scraping",
        "dev": "Geliştirici",
        "comm": "İletişim",
        "productivity": "Verimlilik",
        "ai": "AI & Medya",
        "analytics": "Analitik",
        "ecommerce": "E-Ticaret",
        "crm": "CRM",
    }

    def run(self, action: str = "list", tool_id: str = "", category: str = "") -> dict:
        self.log("MCP Hub agent started")

        if action == "list":
            return self._list_tools(category)
        elif action == "info":
            return self._tool_info(tool_id)
        elif action == "install":
            return self._install_tool(tool_id)
        elif action == "installed":
            return self._list_installed()
        elif action == "search":
            return self._search_tools(tool_id)  # tool_id used as query
        elif action == "recommend":
            return self._recommend_tools()
        else:
            return self._list_tools(category)

    def _list_tools(self, category: str = "") -> dict:
        tools = []
        for tid, tool in self.MCP_REGISTRY.items():
            if category and tool["category"] != category:
                continue
            tools.append({
                "id": tid,
                "name": tool["name"],
                "description": tool["description"],
                "category": tool["category"],
                "category_name": self.MCP_CATEGORIES.get(tool["category"], tool["category"]),
            })

        # Group by category
        grouped = {}
        for t in tools:
            cat = t["category_name"]
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(t)

        results = {
            "status": "ok",
            "summary": f"{len(tools)} MCP tool listelendi" + (f" ({self.MCP_CATEGORIES.get(category, category)})" if category else ""),
            "metrics": {
                "total_tools": len(tools),
                "categories": len(grouped),
                "timestamp": datetime.now().isoformat(),
            },
            "tools": grouped,
            "recommendations": [
                "İhtiyacınıza göre MCP tool seçin",
                "Brave Search + Fetch = güçlü web araştırma",
                "GitHub + Git = tam geliştirici iş akışı",
                "Google Drive + Notion = verimlilik boost",
                "Replicate = görsel/video AI modelleri",
            ],
        }

        self.save_output("mcphub_report.json", results)
        self.log(f"Listed {len(tools)} MCP tools")
        return results

    def _tool_info(self, tool_id: str) -> dict:
        tool = self.MCP_REGISTRY.get(tool_id)
        if not tool:
            return {"status": "error", "summary": f"Tool bulunamadı: {tool_id}", "metrics": {}, "recommendations": []}

        # Generate config snippet
        config_snippet = json.dumps({
            "mcpServers": {
                tool_id: tool["config"]
            }
        }, indent=2)

        return {
            "status": "ok",
            "summary": f"{tool['name']} — {tool['description']}",
            "metrics": {
                "tool_id": tool_id,
                "category": self.MCP_CATEGORIES.get(tool["category"], tool["category"]),
                "package": tool["package"],
            },
            "tool": tool,
            "config_snippet": config_snippet,
            "recommendations": [
                f"Paket: {tool['package']}",
                f"Kurulum config'i hazır — claude_desktop_config.json'a ekleyin",
                "API key gerekliyse .env dosyasına ekleyin",
            ],
        }

    def _install_tool(self, tool_id: str) -> dict:
        tool = self.MCP_REGISTRY.get(tool_id)
        if not tool:
            return {"status": "error", "summary": f"Tool bulunamadı: {tool_id}", "metrics": {}, "recommendations": []}

        # Save to installed tools config
        installed_path = DATA_DIR / "mcp" / "installed.json"
        installed_path.parent.mkdir(parents=True, exist_ok=True)

        installed = {}
        if installed_path.exists():
            with open(installed_path) as f:
                installed = json.load(f)

        installed[tool_id] = {
            "name": tool["name"],
            "package": tool["package"],
            "config": tool["config"],
            "installed_at": datetime.now().isoformat(),
        }

        with open(installed_path, "w") as f:
            json.dump(installed, f, indent=2, ensure_ascii=False)

        self.log(f"Tool installed: {tool['name']}")

        return {
            "status": "ok",
            "summary": f"{tool['name']} MCP config'e eklendi",
            "metrics": {"tool_id": tool_id, "total_installed": len(installed)},
            "config": tool["config"],
            "recommendations": [
                f"Config'i Claude Desktop veya Claude Code ayarlarına ekleyin",
                "Gerekli API key'leri yapılandırın",
                "Claude'u yeniden başlatın",
            ],
        }

    def _list_installed(self) -> dict:
        installed_path = DATA_DIR / "mcp" / "installed.json"
        installed = {}
        if installed_path.exists():
            with open(installed_path) as f:
                installed = json.load(f)

        return {
            "status": "ok",
            "summary": f"{len(installed)} MCP tool kurulu",
            "metrics": {"total_installed": len(installed)},
            "installed": installed,
            "recommendations": ["Kullanmadığınız tool'ları kaldırın" if installed else "Henüz tool kurulmamış — 'list' ile göz atın"],
        }

    def _search_tools(self, query: str) -> dict:
        query_lower = query.lower()
        results = []
        for tid, tool in self.MCP_REGISTRY.items():
            if (query_lower in tool["name"].lower() or
                query_lower in tool["description"].lower() or
                query_lower in tool["category"].lower() or
                query_lower in tid.lower()):
                results.append({"id": tid, "name": tool["name"], "description": tool["description"], "category": tool["category"]})

        return {
            "status": "ok",
            "summary": f"'{query}' için {len(results)} sonuç bulundu",
            "metrics": {"query": query, "results_count": len(results)},
            "results": results,
            "recommendations": [],
        }

    def _recommend_tools(self) -> dict:
        """Recommend MCP tools based on user's config and usage."""
        config = self.load_config()
        niche = config.get("niche", "").lower()

        recommended = []

        # Everyone needs these
        essentials = ["fetch", "brave-search", "filesystem"]
        for tid in essentials:
            tool = self.MCP_REGISTRY[tid]
            recommended.append({"id": tid, "name": tool["name"], "reason": "Temel araç — herkes için gerekli"})

        # Based on niche
        if any(w in niche for w in ["e-ticaret", "ecommerce", "mağaza", "shop"]):
            recommended.append({"id": "shopify", "name": "Shopify", "reason": "E-ticaret yönetimi"})
            recommended.append({"id": "stripe", "name": "Stripe", "reason": "Ödeme yönetimi"})

        if any(w in niche for w in ["pazarlama", "marketing", "reklam"]):
            recommended.append({"id": "google-analytics", "name": "Google Analytics", "reason": "Trafik analizi"})

        # Productivity for everyone
        recommended.append({"id": "google-drive", "name": "Google Drive", "reason": "Dosya yönetimi"})
        recommended.append({"id": "slack", "name": "Slack", "reason": "Ekip iletişimi"})
        recommended.append({"id": "replicate", "name": "Replicate", "reason": "AI model çalıştırma"})

        return {
            "status": "ok",
            "summary": f"{len(recommended)} MCP tool önerildi",
            "metrics": {"niche": niche, "recommended_count": len(recommended)},
            "recommended": recommended,
            "recommendations": [
                "Önce essential tool'ları kurun",
                "Sektörünüze özel tool'ları ekleyin",
                "Hepsini bir anda kurmayın — ihtiyaç duydukça ekleyin",
            ],
        }
