# MCP (Model Context Protocol) — goat Entegrasyon Rehberi

## MCP Nedir?

Model Context Protocol (MCP), AI asistanların harici araçlar ve servislerle güvenli şekilde iletişim kurmasını sağlayan açık bir standarttır. Anthropic tarafından geliştirilmiştir.

goat, MCP Hub agent'ı üzerinden MCP araçlarını keşfetmenizi, yapılandırmanızı ve kullanmanızı sağlar.

## Hızlı Başlangıç

### 1. MCP Hub ile Araçları Listele

```bash
# Dashboard üzerinden
POST /api/agent/mcphub/run
{"action": "list"}

# Kategori bazında
POST /api/agent/mcphub/run
{"action": "list", "category": "web"}

# Arama
POST /api/agent/mcphub/run
{"action": "search", "tool_id": "github"}
```

### 2. Araç Detayları ve Config

```bash
# Araç bilgisi
POST /api/agent/mcphub/run
{"action": "info", "tool_id": "brave-search"}

# Önerilen araçlar (sektörünüze göre)
POST /api/agent/mcphub/run
{"action": "recommend"}
```

### 3. Config Oluşturma

```bash
# Kurulum (config kaydetme)
POST /api/agent/mcphub/run
{"action": "install", "tool_id": "fetch"}

# Full config al
GET /api/mcp/config
```

## MCP API Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/mcp/tools` | GET | Tüm MCP araçlarını listele |
| `/api/mcp/tools?category=web` | GET | Kategori bazında filtrele |
| `/api/mcp/tools/{tool_id}` | GET | Araç detayı ve config |
| `/api/mcp/search` | POST | Anahtar kelime ile arama |
| `/api/mcp/install` | POST | Araç config'i kaydet |
| `/api/mcp/installed` | GET | Kurulu araçları listele |
| `/api/mcp/config` | GET | Full MCP config dosyası oluştur |

## Mevcut MCP Araçları

### Temel (Core)
| Araç | Paket | Açıklama |
|------|-------|----------|
| **Filesystem** | `@anthropic/mcp-server-filesystem` | Dosya okuma, yazma, arama |
| **Fetch** | `@anthropic/mcp-server-fetch` | Web sayfası çekme ve parse etme |

### Arama
| Araç | Paket | API Key |
|------|-------|---------|
| **Brave Search** | `@anthropic/mcp-server-brave-search` | `BRAVE_API_KEY` |

### Web & Scraping
| Araç | Paket | Açıklama |
|------|-------|----------|
| **Puppeteer** | `@anthropic/mcp-server-puppeteer` | Browser otomasyonu |

### Veritabanı
| Araç | Paket | Açıklama |
|------|-------|----------|
| **SQLite** | `@anthropic/mcp-server-sqlite` | SQLite sorgulama |
| **PostgreSQL** | `@anthropic/mcp-server-postgres` | PostgreSQL bağlantısı |

### Geliştirici
| Araç | Paket | API Key |
|------|-------|---------|
| **GitHub** | `@anthropic/mcp-server-github` | `GITHUB_TOKEN` |
| **Git** | `mcp-server-git` | — |

### İletişim
| Araç | Paket | API Key |
|------|-------|---------|
| **Slack** | `@anthropic/mcp-server-slack` | `SLACK_TOKEN` |
| **Gmail** | `mcp-server-gmail` | OAuth |

### Verimlilik
| Araç | Paket | API Key |
|------|-------|---------|
| **Google Drive** | `@anthropic/mcp-server-google-drive` | OAuth |
| **Google Calendar** | `mcp-server-google-calendar` | OAuth |
| **Notion** | `mcp-server-notion` | `NOTION_TOKEN` |

### AI & Medya
| Araç | Paket | API Key |
|------|-------|---------|
| **DALL-E** | `mcp-server-dalle` | `OPENAI_API_KEY` |
| **Replicate** | `mcp-server-replicate` | `REPLICATE_API_TOKEN` |
| **ElevenLabs** | `mcp-server-elevenlabs` | `ELEVENLABS_API_KEY` |

### E-Ticaret
| Araç | Paket | API Key |
|------|-------|---------|
| **Shopify** | `mcp-server-shopify` | `SHOPIFY_ACCESS_TOKEN` |
| **Stripe** | `mcp-server-stripe` | `STRIPE_API_KEY` |

### CRM
| Araç | Paket | API Key |
|------|-------|---------|
| **HubSpot** | `mcp-server-hubspot` | `HUBSPOT_ACCESS_TOKEN` |

## Claude Desktop Config

goat'ın MCP Hub'ı ile oluşturulan config'i Claude Desktop'a eklemek için:

### macOS
```bash
# Config dosyası konumu:
~/Library/Application Support/Claude/claude_desktop_config.json
```

### Örnek Config
```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-fetch"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-key-here"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "your-token-here"
      }
    }
  }
}
```

### Claude Code Config
```bash
# Claude Code settings.json:
~/.claude/settings.json

# Veya proje bazında:
.claude/settings.json
```

## Kendi MCP Server'ınızı Yazmak

MCP server'ı `stdio` transport üzerinden çalışır. Temel yapı:

```python
# my_mcp_server.py
import json
import sys

def handle_request(request):
    method = request.get("method")
    
    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "my_tool",
                    "description": "My custom tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        }
                    }
                }
            ]
        }
    
    if method == "tools/call":
        tool_name = request["params"]["name"]
        args = request["params"]["arguments"]
        # Your logic here
        return {"content": [{"type": "text", "text": "Result"}]}

# Stdio loop
for line in sys.stdin:
    request = json.loads(line)
    response = handle_request(request)
    print(json.dumps(response))
    sys.stdout.flush()
```

## goat + MCP Kullanım Senaryoları

### 1. Lead Araştırma (Scout + Brave Search + Fetch)
Scout ile bulunan lead'lerin web sitelerini Fetch ile çekip, Brave Search ile sektör bilgisi toplayın.

### 2. Otomatik Raporlama (Analytics + Google Drive)
Haftalık performans raporunu otomatik oluşturup Google Drive'a kaydedin.

### 3. CRM Senkronizasyonu (Pipeline + HubSpot)
goat pipeline'ındaki lead'leri HubSpot CRM'e otomatik aktarın.

### 4. İçerik Üretimi (Content + Replicate + ElevenLabs)
Blog yazısı + görsel (Replicate) + podcast sesli versiyonu (ElevenLabs).

### 5. E-Ticaret (SiteBuilder + Shopify + Stripe)
Müşteri landing page + Shopify mağaza + Stripe ödeme entegrasyonu.
