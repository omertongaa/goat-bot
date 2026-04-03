# GOAT → MANUS-SEVİYESİ DÖNÜŞÜM PLANI

**Tarih:** Nisan 2026
**Hedef:** GOAT'u Manus.im seviyesinde otonom bir AI ajan platformuna dönüştürmek
**Kapsam:** Tüm Manus yetenekleri + ajans odaklı özelleştirmeler

---

## MEVCUT DURUM vs HEDEF

| Boyut | GOAT Şu An | Manus Seviyesi |
|-------|-----------|----------------|
| **Mimari** | Monolitik FastAPI, JSON dosya depolama | Mikroservis, sandbox VM, event stream |
| **Ajan sayısı** | 17 özelleşmiş ajan | Sınırsız dinamik ajan |
| **Ajan zekası** | Template fallback + Claude CLI | CodeAct (çalıştırılabilir kod üretimi) |
| **Planlama** | Sabit pipeline (Scout→Filter→Pitch) | Dinamik plan oluşturma, yeniden planlama |
| **Bellek** | In-memory dict + JSON dosya | Event stream + dosya tabanlı kalıcı bellek |
| **Tarayıcı** | requests kütüphanesi (statik HTML) | Gerçek Chromium (JavaScript render) |
| **Paralel çalışma** | Yok (sıralı) | 100+ paralel ajan |
| **Sandbox** | Yok (doğrudan host üzerinde) | İzole VM per görev |
| **Asenkron** | Kısmen (scheduler) | Tam asenkron, arka plan görevler |
| **Canlı izleme** | Log çıktısı | Gerçek zamanlı replay, adım adım izleme |
| **Entegrasyonlar** | Apify, Instantly, fal.ai | MCP protokolü ile sınırsız |
| **Kullanıcı arayüzü** | Terminal tarzı tek sayfa | Multi-panel, canlı VM görünümü |
| **Çoklu model** | Sadece Claude CLI | Görev tipine göre model seçimi |
| **Dosya üretimi** | PDF, MD, HTML, JSON | Her format (uygulamalar, siteler, videolar) |
| **Monetizasyon** | Yok | Kredi tabanlı kullanım |

---

## DÖNÜŞÜM KATEGORİLERİ

### Kategori A: Ajan Çekirdeği (Agent Core)
### Kategori B: Sandbox & Çalışma Ortamı
### Kategori C: Planlama & Bellek Sistemi
### Kategori D: Tarayıcı & Web Etkileşimi
### Kategori E: Paralel Çalışma (Wide Research)
### Kategori F: MCP Entegrasyon Hub
### Kategori G: Kullanıcı Arayüzü Dönüşümü
### Kategori H: Çoklu Model Orkestrasyon
### Kategori I: Dosya Sistemi & Çıktı Yönetimi
### Kategori J: Monetizasyon & Kullanıcı Yönetimi
### Kategori K: Ajansa Özel Süper Güçler

---

## KATEGORİ A: AJAN ÇEKİRDEĞİ (AGENT CORE)

### A1. CodeAct Paradigması
**Manus ne yapıyor:** JSON tool call yerine çalıştırılabilir Python kodu üretiyor. Tek bir kod bloğunda birden fazla aracı birleştiriyor.

**GOAT'a nasıl uyarlanır:**
- Mevcut `agents/base.py` → `core/agent_engine.py` olarak yeniden yazılacak
- Her ajan `run()` yerine **dinamik kod üretimi** yapacak
- Claude'a "bu görevi tamamlamak için Python kodu yaz ve çalıştır" denilecek
- Üretilen kod sandbox içinde `exec()` ile çalıştırılacak
- Araçlar Python fonksiyonları olarak expose edilecek:
  ```python
  # Ajan'ın ürettiği kod örneği:
  leads = scout.search("restaurant", "Istanbul", limit=50)
  scored = filter.score(leads)
  hot_leads = [l for l in scored if l['category'] == 'hot']
  for lead in hot_leads:
      audit = auditor.check(lead['website'])
      if audit['seo_score'] < 60:
          pitch.generate(lead, audit_data=audit)
  ```

**Dosyalar:**
- YENİ: `core/agent_engine.py` — CodeAct çalıştırma motoru
- YENİ: `core/tool_registry.py` — Tüm araçları fonksiyon olarak kayıt
- GÜNCELLE: `agents/base.py` — CodeAct desteği ekle

### A2. Ajan Döngüsü (Agent Loop)
**Manus ne yapıyor:** Analiz → Eylem Seç → Yürüt → Gözlemle → Tekrar döngüsü. Her iterasyonda tek eylem.

**GOAT'a nasıl uyarlanır:**
```
while not task_complete:
    1. Mevcut durumu analiz et (event stream'den)
    2. Uygun aracı/eylemi seç
    3. Sandbox'ta yürüt
    4. Sonucu gözlemle ve bağlama ekle
    5. Görevi tamamlandı mı kontrol et
    6. Tamamlanmadıysa → 1'e dön
```

**Dosyalar:**
- YENİ: `core/agent_loop.py` — Ana ajan döngüsü
- YENİ: `core/event_stream.py` — Kronolojik olay kaydı
- YENİ: `core/action_space.py` — Kullanılabilir eylemler ve durum makinesi

### A3. Durum Makinesi ile Eylem Kontrolü
**Manus ne yapıyor:** Araçları kaldırmak yerine logit maskeleme ile duruma göre erişim kontrolü yapıyor.

**GOAT'a nasıl uyarlanır:**
- Her ajan durumuna göre hangi araçlara erişebileceği tanımlanacak
- Örnek: `RESEARCHING` durumunda → browser, search aktif / file_write pasif
- Örnek: `GENERATING` durumunda → file_write, code_exec aktif / browser pasif
- Ajan isimlerinde tutarlı ön ekler: `browser_*`, `file_*`, `search_*`, `api_*`

**Dosyalar:**
- YENİ: `core/state_machine.py` — Durum geçişleri ve eylem maskeleme

### A4. Hata Koruma & Kendi Kendini Onarma
**Manus ne yapıyor:** Başarısız eylemler context'te kalıyor. Aynı hata tekrarlanmıyor. Yanılış dönüşler kaldırılmıyor.

**GOAT'a nasıl uyarlanır:**
- Her ajan çalışmasında hata geçmişi tutulacak
- Başarısız adım → context'e "FAILED: {reason}" olarak eklenir
- Ajan bir sonraki iterasyonda farklı strateji dener
- Max retry: 3 (aynı eylem için)
- Fallback zinciri: Claude → template → manual prompt

**Dosyalar:**
- YENİ: `core/error_handler.py` — Hata izleme ve kurtarma
- GÜNCELLE: `core/agent_loop.py` — Hata geçmişi entegrasyonu

---

## KATEGORİ B: SANDBOX & ÇALIŞMA ORTAMI

### B1. İzole Görev Sandbox'ı
**Manus ne yapıyor:** Her görev için E2B Firecracker microVM. Ubuntu, Python, Node.js, Chromium, sudo erişimi.

**GOAT'a nasıl uyarlanır (3 seviye):**

**Seviye 1 — Süreç İzolasyonu (Hemen):**
- Her görev için ayrı Python subprocess
- `tempfile.mkdtemp()` ile izole çalışma dizini
- Görev tamamlanınca temizlik
- `subprocess.run()` ile timeout ve kaynak limiti

**Seviye 2 — Docker Konteyner (Kısa Vade):**
- Her görev için hafif Docker konteyner
- Önceden hazırlanmış image: Python 3.11 + Node.js 20 + Chromium
- Volume mount ile dosya paylaşımı
- Network izolasyonu (sadece belirli portlar)
- Otomatik temizlik (görev bitince konteyner silinir)

**Seviye 3 — E2B/Firecracker (Uzun Vade):**
- Tam VM izolasyonu (Manus seviyesi)
- E2B API entegrasyonu
- Bulut tabanlı sandbox
- Multi-tenant güvenlik

**Dosyalar:**
- YENİ: `core/sandbox/process_sandbox.py` — Seviye 1
- YENİ: `core/sandbox/docker_sandbox.py` — Seviye 2
- YENİ: `core/sandbox/e2b_sandbox.py` — Seviye 3
- YENİ: `core/sandbox/manager.py` — Sandbox yaşam döngüsü yönetimi
- YENİ: `Dockerfile.sandbox` — Ajan sandbox image'ı

### B2. Sandbox Yaşam Döngüsü
**Manus ne yapıyor:** Oluştur → Uyku/Uyanık → Geri Dönüşüm. Sandbox'lar inaktif olunca uyuyor, veri korunuyor.

**GOAT'a nasıl uyarlanır:**
- Sandbox durumları: `CREATING`, `ACTIVE`, `SLEEPING`, `RECYCLED`
- Inaktif sandbox: 5 dakika sonra uyku moduna geç
- Uyandırma: Kullanıcı tekrar görevle etkileşime geçtiğinde
- Veri kalıcılığı: Sandbox dosyaları `data/sandboxes/{task_id}/` altında
- Temizlik: 7 gün sonra otomatik silme (ayarlanabilir)

**Dosyalar:**
- YENİ: `core/sandbox/lifecycle.py`
- YENİ: `data/sandboxes/` dizini

### B3. Sandbox İçi Araçlar
**Manus ne yapıyor:** Sandbox'ta shell, Python, Node.js, tarayıcı, dosya I/O, API çağrıları.

**GOAT'a nasıl uyarlanır:**
- Sandbox içinde kullanılabilir araç seti:
  ```python
  SANDBOX_TOOLS = {
      "shell": ShellTool,        # Bash komutları
      "python": PythonTool,      # Python kodu çalıştır
      "browser": BrowserTool,    # Playwright ile web gezinme
      "file_read": FileReadTool,
      "file_write": FileWriteTool,
      "http": HttpTool,          # API çağrıları
      "search": SearchTool,      # Web araması
      "scrape": ScrapeTool,      # Veri kazıma
  }
  ```

**Dosyalar:**
- YENİ: `core/tools/shell.py`
- YENİ: `core/tools/python_exec.py`
- YENİ: `core/tools/browser.py`
- YENİ: `core/tools/file_ops.py`
- YENİ: `core/tools/http_client.py`
- YENİ: `core/tools/search.py`

---

## KATEGORİ C: PLANLAMA & BELLEK SİSTEMİ

### C1. Dinamik Plan Oluşturma
**Manus ne yapıyor:** Karmaşık görevleri sıralı adımlara ayırıyor. Numaralı sözde kod olarak plan oluşturuyor. Görev değiştikçe dinamik yeniden planlama yapıyor.

**GOAT'a nasıl uyarlanır:**
```python
# Kullanıcı: "Istanbul'daki restoranları bul, en iyi 10'una teklif hazırla"
# Ajan planı:
plan = {
    "goal": "Istanbul restoranlarına teklif hazırla",
    "steps": [
        {"id": 1, "action": "scout.search", "params": {"query": "restaurant", "location": "Istanbul", "limit": 50}, "status": "pending"},
        {"id": 2, "action": "filter.score", "depends_on": [1], "status": "pending"},
        {"id": 3, "action": "filter.top_n", "params": {"n": 10, "category": "hot"}, "depends_on": [2], "status": "pending"},
        {"id": 4, "action": "auditor.batch_audit", "depends_on": [3], "status": "pending"},
        {"id": 5, "action": "pitch.batch_generate", "depends_on": [3, 4], "status": "pending"},
    ],
    "current_step": 1,
    "replanning_allowed": True
}
```

- Plan `todo.md` dosyasına da yazılacak (Manus tarzı dikkat manipülasyonu)
- Her adım tamamlandığında plan güncellenir
- Beklenmeyen sonuçlarda (0 lead bulundu gibi) yeniden planlama tetiklenir

**Dosyalar:**
- YENİ: `core/planner.py` — Plan oluşturma ve yönetim
- YENİ: `core/replanner.py` — Dinamik yeniden planlama

### C2. Event Stream (Olay Akışı)
**Manus ne yapıyor:** Kronolojik olay kaydı tutarak çalışma belleği olarak kullanıyor.

**GOAT'a nasıl uyarlanır:**
```python
# Event stream yapısı
event_stream = [
    {"ts": "2026-04-03T10:00:00", "type": "task_start", "data": {"goal": "..."}},
    {"ts": "2026-04-03T10:00:01", "type": "plan_created", "data": {"steps": [...]}},
    {"ts": "2026-04-03T10:00:05", "type": "tool_call", "data": {"tool": "scout.search", "params": {...}}},
    {"ts": "2026-04-03T10:00:15", "type": "tool_result", "data": {"found": 47, "with_email": 23}},
    {"ts": "2026-04-03T10:00:16", "type": "observation", "data": {"note": "47 lead bulundu, email oranı %49"}},
    {"ts": "2026-04-03T10:00:17", "type": "step_complete", "data": {"step_id": 1}},
    # ...
]
```

- Her olay zaman damgalı ve tiplenmiş
- Ajan her iterasyonda event stream'i okuyarak bağlamı anlıyor
- Stream dosyaya da persist ediliyor: `data/tasks/{task_id}/events.json`

**Dosyalar:**
- YENİ: `core/event_stream.py`

### C3. Dosya Tabanlı Kalıcı Bellek
**Manus ne yapıyor:** Dosya sistemini "sınırsız boyutta, doğası gereği kalıcı" bellek olarak kullanıyor. Web sayfası içerikleri düşer ama URL'ler korunur.

**GOAT'a nasıl uyarlanır:**
```
data/memory/
├── global/
│   ├── learned_patterns.json    # Öğrenilen kalıplar (hangi sektörde ne çalışır)
│   ├── successful_pitches.json  # Başarılı tekliflerin özellikleri
│   └── user_preferences.json   # Kullanıcı tercihleri
├── leads/
│   ├── {lead_id}/
│   │   ├── profile.json         # Lead profili (tüm bilgiler)
│   │   ├── interactions.json    # Tüm etkileşim geçmişi
│   │   ├── audit_history.json   # Audit sonuçları zaman serisi
│   │   └── notes.md             # Serbest notlar
├── tasks/
│   ├── {task_id}/
│   │   ├── plan.json            # Görev planı
│   │   ├── events.json          # Event stream
│   │   ├── todo.md              # Canlı todo listesi
│   │   ├── outputs/             # Üretilen dosyalar
│   │   └── sandbox/             # Sandbox durumu
```

- Bağlam penceresi dolduğunda: detaylar dosyaya yazılır, sadece özet + dosya referansı context'te kalır
- "Web sayfası içeriği düşer ama URL korunur" prensibi: audit detayları dosyada, sadece skor context'te

**Dosyalar:**
- YENİ: `core/memory/persistent.py` — Dosya tabanlı bellek yöneticisi
- YENİ: `core/memory/context_manager.py` — Bağlam penceresi yönetimi
- GÜNCELLE: `core/agent_loop.py` — Bellek entegrasyonu

### C4. todo.md ile Dikkat Manipülasyonu
**Manus ne yapıyor:** Ajan `todo.md` oluşturup sürekli güncelliyor. Bu, hedeflerin bağlam sonuna eklenerek "lost-in-the-middle" sorunuyla mücadele ediyor.

**GOAT'a nasıl uyarlanır:**
```markdown
# GÖREV: Istanbul restoranlarına teklif hazırla

## PLAN
- [x] 1. Scout ile restoran ara (47 bulundu)
- [x] 2. Filter ile puanla (12 hot, 18 warm)
- [x] 3. En iyi 10'u seç
- [ ] 4. Web sitelerini audit et ← ŞU AN BURADA
- [ ] 5. Her birine teklif hazırla

## NOTLAR
- Email oranı düşük (%49), telefon ile ulaşım da düşünülmeli
- 3 restoran zincir, kişiselleştirilmiş teklif gerekebilir

## SON EYLEM
Auditor çalıştırılıyor: lead #3 "Nusret Steakhouse" - website: nusret.com.tr
```

- Her iterasyonda todo.md güncellenir
- Prompt'un sonuna eklenir (attention sink)
- Kullanıcıya da gösterilir (canlı ilerleme)

**Dosyalar:**
- YENİ: `core/memory/todo_tracker.py`

---

## KATEGORİ D: TARAYICI & WEB ETKİLEŞİMİ

### D1. Gerçek Tarayıcı Entegrasyonu
**Manus ne yapıyor:** Gerçek Chromium tarayıcısı (headless değil) ile web sitelerini geziyor, JavaScript render ediyor, form dolduruyor.

**GOAT'a nasıl uyarlanır:**
- Playwright kütüphanesi ile tam tarayıcı kontrolü
- JavaScript render edilen siteleri scrape edebilme (SPA'lar, React siteleri)
- Mevcut `requests` tabanlı scraping'in yanına Playwright ekleme
- Form doldurma, tıklama, kaydırma, screenshot alma

```python
# Yeni tarayıcı aracı kullanım örneği
async def browse_and_extract(url):
    page = await browser.new_page()
    await page.goto(url)
    await page.wait_for_load_state("networkidle")
    
    # JavaScript render sonrası içerik al
    title = await page.title()
    content = await page.content()
    
    # Screenshot al (audit kanıtı)
    await page.screenshot(path=f"data/screenshots/{slug}.png")
    
    # Sosyal medya linklerini bul
    social_links = await page.evaluate("""
        () => Array.from(document.querySelectorAll('a'))
            .filter(a => /instagram|facebook|linkedin|twitter/.test(a.href))
            .map(a => a.href)
    """)
    
    return {title, content, social_links, screenshot}
```

**Faydaları (mevcut sisteme göre):**
- SPA/React siteleri artık scrape edilebilir
- Google Maps JavaScript widget'larından doğrudan veri çekilebilir
- LinkedIn profilleri okunabilir (giriş yapıldığında)
- Screenshot ile görsel kanıt toplanabilir
- Form tabanlı sitelere otomatik kayıt/giriş

**Dosyalar:**
- YENİ: `core/tools/browser.py` — Playwright wrapper
- YENİ: `core/tools/browser_actions.py` — Tıkla, doldur, kaydır, screenshot
- GÜNCELLE: `services/scraper.py` — Playwright fallback ekle
- GÜNCELLE: `services/site_auditor.py` — JS-rendered audit desteği
- GÜNCELLE: `requirements.txt` — `playwright` ekle

### D2. Akıllı Web Kazıma (Smart Scraping)
**Manus ne yapıyor:** Web sitelerini gezerek yapılandırılmış veri çıkarıyor. Sayfalar arası gezinme, pagination, infinite scroll desteği.

**GOAT'a nasıl uyarlanır:**
- Lead sitelerinden otomatik bilgi çıkarma:
  - İletişim sayfası → email, telefon, adres
  - Hakkımızda → şirket büyüklüğü, kuruluş yılı
  - Sosyal medya linkleri
  - Fiyat sayfası (varsa) → mevcut harcama bütçesi tahmini
  - Blog/haber (varsa) → aktiflik skoru
- Google Maps sonuçlarından doğrudan veri (rating, yorum sayısı, fotoğraf sayısı, çalışma saatleri)
- Sayfalama desteği (birden fazla sayfa sonuç)

**Dosyalar:**
- YENİ: `core/tools/smart_scraper.py` — Akıllı veri çıkarma
- YENİ: `core/tools/pagination.py` — Sayfalama yönetimi

### D3. Canlı Tarayıcı Görünümü
**Manus ne yapıyor:** Kullanıcı, ajanın tarayıcıda ne yaptığını gerçek zamanlı izleyebiliyor.

**GOAT'a nasıl uyarlanır:**
- WebSocket ile tarayıcı screenshot stream'i
- Her 2 saniyede bir screenshot → base64 → WebSocket → dashboard
- Kullanıcı "Browser" sekmesinde ajanın gezdiği sayfaları görür
- Tıklama ve scroll olayları overlay olarak gösterilir

**Dosyalar:**
- YENİ: `core/tools/browser_stream.py` — Screenshot streaming
- GÜNCELLE: `templates/dashboard.html` — Browser viewer paneli
- GÜNCELLE: `app.py` — WebSocket endpoint

---

## KATEGORİ E: PARALEL ÇALIŞMA (WIDE RESEARCH)

### E1. Paralel Ajan Çalıştırma
**Manus ne yapıyor:** Wide Research ile 100+ bağımsız ajan paralel çalışıyor. Her biri kendi VM'inde, kendi bağlam penceresinde.

**GOAT'a nasıl uyarlanır:**

**Kullanım Senaryoları:**
1. 50 lead'i aynı anda audit et (şu an sıralı, 50x daha hızlı)
2. 10 şehirde aynı anda lead ara
3. 20 lead'e paralel teklif hazırla
4. 5 rakibi aynı anda analiz et

**Teknik Uygulama:**
```python
# Wide Research mimarisi
class WideResearch:
    def __init__(self, max_workers=10):
        self.executor = ProcessPoolExecutor(max_workers)
        self.results = {}
    
    async def run_parallel(self, tasks: list[AgentTask]):
        futures = []
        for task in tasks:
            future = self.executor.submit(
                self._run_in_sandbox,
                task
            )
            futures.append((task.id, future))
        
        # Sonuçları topla
        for task_id, future in futures:
            self.results[task_id] = future.result()
        
        # Sonuçları birleştir
        return self._merge_results()
```

- Her paralel görev kendi sandbox'unda çalışır
- Sonuçlar merkezi bir koordinatör tarafından birleştirilir
- İlerleme gerçek zamanlı dashboard'da gösterilir
- Kaynak limiti: max 10 paralel (ayarlanabilir)

**Dosyalar:**
- YENİ: `core/wide_research.py` — Paralel ajan orkestratör
- YENİ: `core/task_coordinator.py` — Görev dağıtımı ve sonuç birleştirme
- GÜNCELLE: `app.py` — `/api/wide-research` endpoint'i

### E2. Sonuç Birleştirme ve Sentez
**Manus ne yapıyor:** 100 paralel ajanın sonuçlarını tek bir tutarlı raporda birleştiriyor.

**GOAT'a nasıl uyarlanır:**
- Paralel audit sonuçları → tek tablo (lead adı, SEO skor, broken links, tech stack)
- Paralel araştırma sonuçları → kategorize edilmiş özet rapor
- Çakışan bilgiler → en güvenilir kaynak seçimi
- Claude ile doğal dilde sentez raporu

**Dosyalar:**
- YENİ: `core/result_merger.py`

---

## KATEGORİ F: MCP ENTEGRASYON HUB

### F1. MCP (Model Context Protocol) Altyapısı
**Manus ne yapıyor:** MCP protokolü ile Gmail, Notion, Slack, Stripe, Google Calendar'a bağlanıyor.

**GOAT'a nasıl uyarlanır:**

**Öncelik 1 — Ajans İş Akışı İçin:**
| Entegrasyon | Neden | Kullanım |
|-------------|-------|----------|
| Gmail | Müşteri emaillerini okuma/gönderme | Outreach sonuçlarını takip |
| Google Calendar | Müşteri toplantıları | Pipeline'da "meeting" aşaması |
| Slack/Discord | Bildirimler | Yeni hot lead, tamamlanan görev |
| Stripe | Ödeme alma | Sözleşme → fatura → ödeme |
| Notion | Müşteri wiki | Müşteri bilgi tabanı |
| WhatsApp Business | Mesaj gönderme | Çok kanallı outreach |
| Google Sheets | Veri import/export | Lead listesi paylaşımı |

**Öncelik 2 — Genişletilmiş:**
| Entegrasyon | Neden |
|-------------|-------|
| HubSpot/Pipedrive | CRM senkronizasyon |
| Zapier/Make | Dış otomasyon tetikleme |
| Twilio | SMS/Sesli arama |
| LinkedIn | B2B outreach |
| Instagram/Facebook API | Sosyal medya yönetimi |
| Google Ads/Meta Ads | Reklam yönetimi |
| Parasut.com | Türkiye e-Fatura |

**Teknik Uygulama:**
```python
# MCP Server yapısı
class MCPServer:
    def __init__(self):
        self.tools = {}
        self.auth_tokens = {}
    
    def register_tool(self, name, handler, auth_type="oauth"):
        self.tools[name] = {"handler": handler, "auth": auth_type}
    
    async def call(self, tool_name, params, user_context):
        tool = self.tools[tool_name]
        token = self.auth_tokens.get(tool_name)
        return await tool["handler"](params, token)

# Kullanım:
mcp = MCPServer()
mcp.register_tool("gmail.send", gmail_send_handler)
mcp.register_tool("calendar.create_event", calendar_handler)
mcp.register_tool("stripe.create_invoice", stripe_handler)
```

**Dosyalar:**
- YENİ: `core/mcp/server.py` — MCP sunucusu
- YENİ: `core/mcp/auth.py` — OAuth yönetimi
- YENİ: `core/mcp/tools/gmail.py`
- YENİ: `core/mcp/tools/calendar.py`
- YENİ: `core/mcp/tools/slack.py`
- YENİ: `core/mcp/tools/stripe.py`
- YENİ: `core/mcp/tools/whatsapp.py`
- YENİ: `core/mcp/tools/notion.py`
- YENİ: `core/mcp/tools/sheets.py`
- GÜNCELLE: `agents/mcphub/agent.py` — Tam MCP yönetimi

### F2. Entegrasyon Marketplace
**Manus ne yapıyor:** Kullanıcılar kendi MCP sunucularını bağlayabiliyor.

**GOAT'a nasıl uyarlanır:**
- Dashboard'da "Entegrasyonlar" sekmesi
- Tek tıkla OAuth bağlantısı
- Özel webhook endpoint'leri (Zapier, Make.com ile bağlantı)
- Kullanıcı kendi MCP tool'larını ekleyebilmeli

**Dosyalar:**
- YENİ: `core/mcp/marketplace.py`
- GÜNCELLE: `templates/dashboard.html` — Entegrasyon paneli

---

## KATEGORİ G: KULLANICI ARAYÜZÜ DÖNÜŞÜMÜ

### G1. Multi-Panel Dashboard
**Manus ne yapıyor:** Ajan modu, canlı görünürlük, dosya yöneticisi, çoklu panel.

**GOAT'a nasıl uyarlanır (mevcut Dark Room estetiğini koruyarak):**

```
┌─────────────────────────────────────────────────────────────┐
│  GOAT COMMAND CENTER                           [⚙️] [👤]    │
├────────┬──────────────────────────────┬─────────────────────┤
│        │                              │                     │
│  NAV   │   ANA ÇALIŞMA ALANI          │   DETAY PANELİ      │
│        │                              │                     │
│ • Home │   [Görev Girişi]             │  • Canlı Log        │
│ • Tasks│                              │  • Browser View     │
│ • Leads│   [Aktif Görev İzleme]       │  • Dosya Gezgini    │
│ • CRM  │   ┌──────────────────┐       │  • Event Stream     │
│ • Mail │   │ Adım 1: ✅ Scout │       │                     │
│ • Sites│   │ Adım 2: 🔄 Audit │       │  [Dosya Listesi]    │
│ • Files│   │ Adım 3: ⏳ Pitch │       │  - proposal.pdf     │
│ • MCP  │   └──────────────────┘       │  - audit_report.json│
│ • Stats│                              │  - leads.csv        │
│        │   [Sonuçlar]                 │                     │
│        │   - 47 lead bulundu          │  [Hızlı Aksiyonlar] │
│        │   - 12 hot lead              │  • CSV İndir        │
│        │   - 8 teklif hazır           │  • PDF Oluştur      │
│        │                              │  • Email Gönder     │
└────────┴──────────────────────────────┴─────────────────────┘
```

**Yeni UI Bileşenleri:**
1. **Görev Girişi** — Doğal dille görev tanımlama (Manus tarzı)
2. **Canlı Görev İzleme** — Adım adım ilerleme, gerçek zamanlı
3. **Browser Viewer** — Ajanın web gezinmesini izleme
4. **Dosya Gezgini** — Üretilen tüm dosyalar (indirme, önizleme)
5. **Event Stream Paneli** — Tüm olaylar kronolojik
6. **Entegrasyon Durumu** — Bağlı servislerin durumu
7. **KPI Dashboard** — Gerçek zamanlı metrikler

**Dosyalar:**
- GÜNCELLE: `templates/dashboard.html` — Büyük yeniden tasarım
- YENİ: `templates/components/task_input.html`
- YENİ: `templates/components/task_tracker.html`
- YENİ: `templates/components/browser_viewer.html`
- YENİ: `templates/components/file_explorer.html`
- YENİ: `templates/components/event_stream.html`
- YENİ: `static/js/websocket.js` — Gerçek zamanlı iletişim

### G2. Gerçek Zamanlı İzleme (Live Replay)
**Manus ne yapıyor:** Ajanın her eyleminin replay'i izlenebilir — biri klavyede çalışıyormuş gibi.

**GOAT'a nasıl uyarlanır:**
- WebSocket ile gerçek zamanlı event streaming
- Her araç çağrısı, sonuç, plan güncellemesi anlık dashboard'a
- "Replay" modu: tamamlanmış görevleri tekrar izleme
- Terminal-style log (mevcut estetiğe uygun)
- Typewriter efekti ile ajan düşünce süreci gösterimi

**Dosyalar:**
- YENİ: `core/realtime/websocket_manager.py`
- YENİ: `core/realtime/event_broadcaster.py`
- GÜNCELLE: `app.py` — WebSocket endpoint'leri

### G3. Doğal Dil Görev Girişi
**Manus ne yapıyor:** Kullanıcı doğal dille görev veriyor, Manus kendi planını yapıyor.

**GOAT'a nasıl uyarlanır:**
```
Kullanıcı yazıyor: "Ankara'daki diş kliniklerini bul, web siteleri kötü olanlarına 
teklif hazırla ve email kampanyası oluştur"

Ajan otomatik plan:
1. Scout → "diş kliniği", "Ankara", limit=100
2. Filter → puanla
3. Auditor → hot lead'lerin sitelerini audit et
4. Filter → SEO skoru < 50 olanları seç
5. Pitch → her birine kişisel teklif
6. Outreach → email kampanyası oluştur (DRAFT)
```

- Mevcut chat arayüzü korunacak
- "Akıllı komut çözümleme" eklenecek
- Belirsiz komutlarda netleştirme sorusu soracak
- Onay adımı: "Bu planı uygulayayım mı?"

**Dosyalar:**
- YENİ: `core/nlp/intent_parser.py` — Doğal dil → görev planı
- YENİ: `core/nlp/clarifier.py` — Belirsizlik çözümleme
- GÜNCELLE: `app.py` — `/api/task` endpoint (doğal dil görev)

### G4. Dosya Yöneticisi
**Manus ne yapıyor:** "Bu görevdeki tüm dosyaları görüntüle" arayüzü, dosya indirme.

**GOAT'a nasıl uyarlanır:**
- Görev bazlı dosya listesi
- Dosya türüne göre ikon ve önizleme
- PDF → tarayıcıda önizleme
- HTML → iframe ile canlı önizleme
- JSON → syntax highlighted görünüm
- CSV → tablo görünümü
- Toplu indirme (ZIP)

**Dosyalar:**
- YENİ: `core/file_manager.py`
- GÜNCELLE: `app.py` — Dosya yönetim endpoint'leri

---

## KATEGORİ H: ÇOKLU MODEL ORKESTRASYON

### H1. Görev Tipine Göre Model Seçimi
**Manus ne yapıyor:** Claude 3.5/3.7 + Qwen — farklı görevler için farklı modeller.

**GOAT'a nasıl uyarlanır:**

| Görev Tipi | Önerilen Model | Neden |
|------------|---------------|-------|
| Planlama | Claude Opus/Sonnet | En iyi reasoning |
| Teklif yazma | Claude Sonnet | Yaratıcı Türkçe |
| Kod üretme | Claude Sonnet / GPT-4o | Kod kalitesi |
| Veri analizi | Claude Haiku / GPT-4o-mini | Hızlı, ucuz |
| Görsel prompt | Claude Haiku | Basit, hızlı |
| Sınıflandırma | Yerel model (Ollama) | Ücretsiz, hızlı |
| Embedding | text-embedding-3-small | Ucuz, hızlı |

**Teknik Uygulama:**
```python
class ModelRouter:
    MODELS = {
        "planning": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
        "creative": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
        "code": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
        "analysis": {"provider": "anthropic", "model": "claude-haiku-4-5"},
        "classification": {"provider": "ollama", "model": "llama3.2"},
        "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
    }
    
    def route(self, task_type: str) -> dict:
        return self.MODELS.get(task_type, self.MODELS["creative"])
```

- Kullanıcı kendi API anahtarlarını girebilmeli (Anthropic, OpenAI, Ollama)
- Maliyet takibi: her model çağrısının token kullanımı ve maliyeti
- Fallback zinciri: Claude → GPT → Ollama → Template

**Dosyalar:**
- YENİ: `core/model_router.py` — Model yönlendirici
- YENİ: `core/llm/anthropic_client.py` — Claude API wrapper
- YENİ: `core/llm/openai_client.py` — OpenAI API wrapper
- YENİ: `core/llm/ollama_client.py` — Yerel model wrapper
- YENİ: `core/llm/cost_tracker.py` — Token/maliyet takibi
- GÜNCELLE: `agents/base.py` — Model router entegrasyonu

### H2. KV-Cache Optimizasyonu
**Manus ne yapıyor:** Önbellekli tokenlar 10x ucuz. Prompt ön ekleri sabit, append-only bağlam.

**GOAT'a nasıl uyarlanır:**
- System prompt'lar sabit tutulacak (zaman damgası eklenmeyecek)
- Ajan bağlamı append-only: önceki mesajlar değiştirilmez, sadece yeni eklenir
- Uzun görevlerde bağlam sıkıştırma: detaylar dosyaya, özet context'e
- `cache_control` breakpoint'leri ile Anthropic API önbellek yönetimi

**Dosyalar:**
- YENİ: `core/llm/cache_optimizer.py`

---

## KATEGORİ I: DOSYA SİSTEMİ & ÇIKTI YÖNETİMİ

### I1. Gelişmiş Dosya Üretimi
**Manus ne yapıyor:** PDF, Excel, Word, web siteleri, uygulamalar, dashboard'lar üretiyor.

**GOAT'a eklenecek formatlar:**

| Format | Kütüphane | Kullanım |
|--------|----------|----------|
| PDF | fpdf2 (mevcut) | Teklif, rapor, sözleşme |
| Excel | openpyxl | Lead export, analiz tabloları |
| Word/DOCX | python-docx | Teklif, sözleşme |
| CSV | csv (built-in) | Lead export |
| HTML | Jinja2 (mevcut) | Site, sunum, brand kit |
| PNG/SVG | Pillow / cairosvg | Görsel, logo, infografik |
| ZIP | zipfile (built-in) | Toplu dosya indirme |
| Markdown | (mevcut) | Teklif, içerik |
| JSON | (mevcut) | Veri |
| PPTX | python-pptx | PowerPoint sunum |

**Dosyalar:**
- YENİ: `core/file_generators/excel.py`
- YENİ: `core/file_generators/docx.py`
- YENİ: `core/file_generators/pptx.py`
- YENİ: `core/file_generators/image.py`
- GÜNCELLE: `requirements.txt` — openpyxl, python-docx, python-pptx, Pillow

### I2. Dosya Organizasyonu
**Manus ne yapıyor:** Her görevin kendi dosya alanı var.

**GOAT'a nasıl uyarlanır:**
```
outputs/
├── tasks/
│   ├── {task_id}/
│   │   ├── metadata.json
│   │   ├── plan.json
│   │   ├── files/
│   │   │   ├── proposal_nusret.pdf
│   │   │   ├── audit_report.xlsx
│   │   │   └── leads_qualified.csv
│   │   └── logs/
│   │       └── events.json
├── proposals/     # (mevcut, korunacak)
├── creatives/     # (mevcut, korunacak)
├── sites/         # (mevcut, korunacak)
└── exports/       # Toplu indirmeler
```

**Dosyalar:**
- YENİ: `core/file_manager.py` — Dosya organizasyon yöneticisi

---

## KATEGORİ J: MONETİZASYON & KULLANICI YÖNETİMİ

### J1. Kredi Tabanlı Kullanım Sistemi
**Manus ne yapıyor:** Kredi bazlı fiyatlandırma. Her görev kredi tüketiyor.

**GOAT'a nasıl uyarlanır:**

| Eylem | Kredi Maliyeti |
|-------|---------------|
| Lead arama (Scout) | 5 kredi / 50 lead |
| Lead puanlama (Filter) | 1 kredi |
| Website audit | 2 kredi / site |
| Teklif oluşturma | 10 kredi / teklif |
| Email kampanyası | 5 kredi / kampanya |
| AI görsel | 3 kredi |
| Wide Research (paralel) | 20 kredi |
| Tarayıcı kullanımı | 1 kredi / 10 sayfa |

**Planlar:**
| Plan | Aylık Kredi | Fiyat |
|------|------------|-------|
| Free | 50 | $0 |
| Starter | 500 | $29/ay |
| Pro | 2000 | $79/ay |
| Agency | 10000 | $199/ay |
| Unlimited | ∞ | $399/ay |

**Dosyalar:**
- YENİ: `core/billing/credits.py` — Kredi yönetimi
- YENİ: `core/billing/plans.py` — Plan tanımları
- YENİ: `core/billing/usage_tracker.py` — Kullanım takibi

### J2. Kullanıcı Sistemi
**Manus ne yapıyor:** Kullanıcı hesapları, giriş, çıkış.

**GOAT'a nasıl uyarlanır:**
- JWT tabanlı kimlik doğrulama
- Kullanıcı kayıt/giriş
- Profil yönetimi
- API anahtarı yönetimi (kullanıcı bazlı)
- Çoklu ajans profili (bir kullanıcı birden fazla ajans)

**Dosyalar:**
- YENİ: `core/auth/jwt.py`
- YENİ: `core/auth/users.py`
- YENİ: `core/auth/middleware.py`

### J3. Veritabanı Geçişi
**Mevcut:** JSON dosyalar
**Hedef:** SQLite (yerel) → PostgreSQL (bulut)

- Tüm JSON okuma/yazma → ORM (SQLAlchemy veya Tortoise)
- Lead, deal, task, event, credit tabloları
- Migration sistemi (Alembic)
- JSON dosya import aracı (mevcut verileri taşıma)

**Dosyalar:**
- YENİ: `core/db/models.py` — Veritabanı modelleri
- YENİ: `core/db/connection.py` — Bağlantı yönetimi
- YENİ: `core/db/migrations/` — Migration dosyaları

---

## KATEGORİ K: AJANSA ÖZEL SÜPER GÜÇLER

Bu kategori Manus'ta olmayan ama GOAT'un ajans odaklı farklılaşmasını sağlayacak özellikler:

### K1. AI Chatbot Builder (Müşteriler İçin)
- Ajans sahibinin müşterileri için web chatbot oluşturması
- RAG tabanlı: müşterinin web sitesi içeriğinden eğitim
- Embed kodu ile müşteri sitesine yerleştirme
- Müşteri başına aylık ücretlendirme

### K2. White-Label SaaS Modu
- Özel domain, logo, renk
- Alt hesap sistemi (her müşteri için izole ortam)
- Müşteri portalı

### K3. Sözleşme & Fatura
- Teklif → Sözleşme → Fatura → Ödeme akışı
- Stripe entegrasyonu
- E-imza desteği
- Parasut.com entegrasyonu (Türkiye)

### K4. AI Sesli Ajan
- Twilio/Vapi ile otomatik arama
- Lead'leri telefonla arama (appointment setting)
- Gelen aramaları yanıtlama

### K5. Waterfall Lead Enrichment
- Kademeli veri arama: Apify → Google → LinkedIn → Web scraping → Hunter.io
- Her kaynak başarısız olursa sonrakine geç
- Email doğrulama (MX + SMTP)
- Telefon doğrulama

### K6. Otomatik Müşteri Raporu
- Haftalık/aylık PDF rapor
- Bulunan leadler, gönderilen teklifler, kampanya metrikleri
- White-label (müşterinin logosu ile)
- Otomatik email ile gönderim

### K7. Oyunlaştırılmış Onboarding
- İlerleme çubuğu
- Başarı rozetleri
- "İlk lead'ini bul", "İlk teklifini gönder" görevleri
- Seviye sistemi

---

## UYGULAMA SIRASI (ÖNCELİK)

### Faz 1: Çekirdek Motor (2 hafta)
1. `core/agent_engine.py` — CodeAct motoru
2. `core/agent_loop.py` — Ajan döngüsü
3. `core/event_stream.py` — Olay akışı
4. `core/planner.py` — Dinamik planlama
5. `core/memory/todo_tracker.py` — todo.md sistemi
6. `core/tools/` — Temel araç seti

### Faz 2: Tarayıcı & Paralel (2 hafta)
7. `core/tools/browser.py` — Playwright entegrasyonu
8. `core/sandbox/process_sandbox.py` — Süreç izolasyonu
9. `core/wide_research.py` — Paralel çalışma
10. `core/realtime/websocket_manager.py` — Gerçek zamanlı izleme

### Faz 3: Model & Bellek (1 hafta)
11. `core/model_router.py` — Çoklu model desteği
12. `core/llm/` — API wrapper'lar
13. `core/memory/persistent.py` — Kalıcı bellek
14. `core/memory/context_manager.py` — Bağlam yönetimi

### Faz 4: UI Dönüşümü (2 hafta)
15. Dashboard yeniden tasarım
16. Doğal dil görev girişi
17. Canlı görev izleme
18. Browser viewer
19. Dosya gezgini

### Faz 5: Entegrasyonlar (2 hafta)
20. MCP altyapısı
21. Gmail, Calendar, Slack entegrasyonları
22. Stripe entegrasyonu
23. WhatsApp Business

### Faz 6: Monetizasyon (1 hafta)
24. Kredi sistemi
25. Kullanıcı yönetimi
26. Veritabanı geçişi

### Faz 7: Ajans Süper Güçleri (sürekli)
27. AI Chatbot Builder
28. White-label modu
29. Sesli ajan
30. Waterfall enrichment

---

## DOSYA YAPISI (HEDEF)

```
goat-bot/
├── app.py                          # FastAPI ana uygulama
├── core/
│   ├── agent_engine.py             # CodeAct motor
│   ├── agent_loop.py               # Ajan döngüsü
│   ├── event_stream.py             # Olay akışı
│   ├── planner.py                  # Dinamik planlama
│   ├── replanner.py                # Yeniden planlama
│   ├── state_machine.py            # Durum makinesi
│   ├── error_handler.py            # Hata yönetimi
│   ├── wide_research.py            # Paralel çalışma
│   ├── task_coordinator.py         # Görev koordinasyonu
│   ├── result_merger.py            # Sonuç birleştirme
│   ├── file_manager.py             # Dosya yönetimi
│   ├── model_router.py             # Model yönlendirme
│   │
│   ├── sandbox/
│   │   ├── manager.py              # Sandbox yaşam döngüsü
│   │   ├── process_sandbox.py      # Süreç izolasyonu
│   │   ├── docker_sandbox.py       # Docker konteyner
│   │   └── e2b_sandbox.py          # E2B VM (gelecek)
│   │
│   ├── tools/
│   │   ├── browser.py              # Playwright tarayıcı
│   │   ├── browser_actions.py      # Tarayıcı eylemleri
│   │   ├── browser_stream.py       # Screenshot streaming
│   │   ├── shell.py                # Shell komutları
│   │   ├── python_exec.py          # Python çalıştırma
│   │   ├── file_ops.py             # Dosya işlemleri
│   │   ├── http_client.py          # HTTP istekleri
│   │   ├── search.py               # Web araması
│   │   └── smart_scraper.py        # Akıllı veri çıkarma
│   │
│   ├── memory/
│   │   ├── persistent.py           # Kalıcı bellek
│   │   ├── context_manager.py      # Bağlam yönetimi
│   │   └── todo_tracker.py         # todo.md sistemi
│   │
│   ├── llm/
│   │   ├── anthropic_client.py     # Claude API
│   │   ├── openai_client.py        # OpenAI API
│   │   ├── ollama_client.py        # Yerel model
│   │   ├── cache_optimizer.py      # KV-Cache
│   │   └── cost_tracker.py         # Maliyet takibi
│   │
│   ├── nlp/
│   │   ├── intent_parser.py        # Doğal dil → görev
│   │   └── clarifier.py            # Belirsizlik çözümleme
│   │
│   ├── mcp/
│   │   ├── server.py               # MCP sunucusu
│   │   ├── auth.py                 # OAuth yönetimi
│   │   ├── marketplace.py          # Entegrasyon pazarı
│   │   └── tools/
│   │       ├── gmail.py
│   │       ├── calendar.py
│   │       ├── slack.py
│   │       ├── stripe.py
│   │       ├── whatsapp.py
│   │       ├── notion.py
│   │       └── sheets.py
│   │
│   ├── realtime/
│   │   ├── websocket_manager.py    # WebSocket yönetimi
│   │   └── event_broadcaster.py    # Olay yayını
│   │
│   ├── billing/
│   │   ├── credits.py              # Kredi sistemi
│   │   ├── plans.py                # Plan tanımları
│   │   └── usage_tracker.py        # Kullanım takibi
│   │
│   ├── auth/
│   │   ├── jwt.py                  # JWT kimlik doğrulama
│   │   ├── users.py                # Kullanıcı yönetimi
│   │   └── middleware.py           # Auth middleware
│   │
│   ├── db/
│   │   ├── models.py               # Veritabanı modelleri
│   │   ├── connection.py           # Bağlantı yönetimi
│   │   └── migrations/             # Migration dosyaları
│   │
│   └── file_generators/
│       ├── excel.py                # Excel üretimi
│       ├── docx.py                 # Word üretimi
│       ├── pptx.py                 # PowerPoint üretimi
│       └── image.py                # Görsel üretimi
│
├── agents/                         # (mevcut 17 ajan korunur, core ile entegre)
├── services/                       # (mevcut servisler korunur, genişletilir)
├── templates/                      # (yeniden tasarlanır)
├── static/                         # (yeni: JS, CSS, assets)
├── data/                           # (mevcut yapı + memory/, tasks/, sandboxes/)
├── outputs/                        # (mevcut + tasks/ bazlı organizasyon)
├── Dockerfile.sandbox              # Sandbox image
├── docker-compose.yml              # Geliştirme ortamı
└── requirements.txt                # (genişletilmiş)
```

---

## YENİ BAĞIMLILIKLAR

```
# Mevcut
fastapi==0.115.0
uvicorn==0.30.0
jinja2==3.1.4
python-multipart==0.0.9
httpx==0.27.0
requests==2.31.0
python-dotenv==1.0.1
fpdf2==2.8.4
apscheduler==3.10.4
duckduckgo-search>=8.0.0

# Yeni — Tarayıcı
playwright>=1.45.0

# Yeni — Çoklu Model
anthropic>=0.40.0
openai>=1.50.0

# Yeni — Dosya Üretimi
openpyxl>=3.1.0
python-docx>=1.1.0
python-pptx>=0.6.23
Pillow>=10.0.0

# Yeni — Veritabanı
sqlalchemy>=2.0.0
alembic>=1.13.0
aiosqlite>=0.20.0

# Yeni — Auth
pyjwt>=2.8.0
passlib>=1.7.4
bcrypt>=4.1.0

# Yeni — WebSocket
websockets>=12.0

# Yeni — Paralel İşlem
celery>=5.3.0  # veya sadece asyncio + ProcessPoolExecutor

# Yeni — MCP
stripe>=8.0.0
google-auth>=2.29.0
google-api-python-client>=2.130.0
slack-sdk>=3.30.0
```

---

## BAŞARI METRİKLERİ

Dönüşüm tamamlandığında GOAT şunları yapabilmeli:

1. ✅ Doğal dille görev al ve otonom olarak tamamla
2. ✅ Gerçek tarayıcı ile web sitelerini gez ve veri çıkar
3. ✅ Paralel olarak 10+ görevi aynı anda çalıştır
4. ✅ Her görev için izole sandbox ortamı
5. ✅ Adım adım plan oluştur, yeniden planla
6. ✅ Event stream ile tüm olayları kaydet
7. ✅ todo.md ile görev takibi
8. ✅ Görev tipine göre farklı AI modeli kullan
9. ✅ Gmail, Calendar, Slack, Stripe entegrasyonları
10. ✅ Gerçek zamanlı görev izleme (WebSocket)
11. ✅ Dosya gezgini ve çoklu format üretimi
12. ✅ Kredi tabanlı kullanım ve fiyatlandırma
13. ✅ Kullanıcı sistemi (kayıt, giriş)
14. ✅ White-label müşteri portalı
15. ✅ AI chatbot builder
16. ✅ Asenkron görev yürütme (arka planda)

---

*Bu doküman GOAT'un Manus seviyesine dönüşümü için tam teknik referanstır.*
