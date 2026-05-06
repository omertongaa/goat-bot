# n8n Workflow Kütüphanesi

> 10 import-ready workflow. Her biri gerçek müşteri projesinde kullanıldı, üretti, para getirdi.

## Kurulum

1. **n8n self-host** (tavsiye):
   ```bash
   docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
   ```
   → `http://localhost:5678` → owner hesap yarat

2. **veya n8n.cloud**: ücretsiz plan — 20 workflow, 5K execution/ay (çoğu müşteri için yeter)

## Workflow'u Import Etme

1. n8n UI → sağ üst `+` → `Import from File`
2. Bu klasörden `.json` seç
3. Credentials'ı aç (örn: Gmail, Slack, OpenAI) — her workflow README'sinde yazar hangi credential lazım
4. Test node → `Execute Node` → çalıştığını gör
5. Workflow'u `Active` yap (sağ üst toggle)

## Workflow'lar

| # | Dosya | Ne Yapar | Satış Fiyatı |
|---|---|---|---|
| 01 | [`01-lead-form-to-crm.json`](./01-lead-form-to-crm.json) | Web form gelir → Google Sheets + sahibine mail | $150-300 kur, $50/ay host |
| 02 | [`02-hot-lead-slack-alert.json`](./02-hot-lead-slack-alert.json) | Yeni lead geldi, skor yüksek → anında Slack bildirim | $200 tek sefer |
| 03 | [`03-invoice-reminder.json`](./03-invoice-reminder.json) | Her gün 09:00 → vadesi geçen faturalar → müşteriye mail | $400-800 (mali müşavir için) |
| 04 | [`04-appointment-confirmation.json`](./04-appointment-confirmation.json) | Randevu alındı → WhatsApp + e-posta onay | $300 kur |
| 05 | [`05-cold-email-drip.json`](./05-cold-email-drip.json) | Lead → 4 adımlı soğuk mail dizisi, 2 günde bir | $500-1000 |
| 06 | [`06-whatsapp-order-to-sheet.json`](./06-whatsapp-order-to-sheet.json) | WhatsApp Business'tan gelen sipariş → Sheet + kurye bildirim | $400 (restoran için) |
| 07 | [`07-review-request.json`](./07-review-request.json) | 7 gün sonra müşteriye Google review/Yandex isteme maili | $200-400 |
| 08 | [`08-stripe-to-notion.json`](./08-stripe-to-notion.json) | Stripe ödeme → Notion CRM + müşteriye teşekkür | $150-300 |
| 09 | [`09-instagram-dm-autoresponder.json`](./09-instagram-dm-autoresponder.json) | IG DM geldi → OpenAI yanıtla → takas gerekiyorsa insan | $800-1500 (Meta API gerekli) |
| 10 | [`10-weekly-report.json`](./10-weekly-report.json) | Her Pazartesi → DB query → haftalık özet maili | $300-500/kurulum |

## Ortak Credentials

Çoğu workflow şunlardan birini ister:

- **Gmail / Postmark / Resend** — email gönderim
- **Google Sheets** — data yazma/okuma
- **Slack / Telegram** — bildirimler
- **OpenAI** — metin üretimi
- **Postgres / Neon** — DB query
- **Stripe** — ödeme webhook
- **WhatsApp Business Cloud API** — mesajlaşma (Meta hesap şart)

Her workflow'un JSON içinde hangi node'un hangi credential'ı beklediği yazılı.

## Müşteriye Sunum

Müşteriye tek workflow değil, **paket** sat:

- **Emlak paketi** → 01 + 02 + 07 (lead → hızlı takip → satış sonrası review)
- **Klinik paketi** → 01 + 04 + 07 (form → randevu onay → değerlendirme)
- **Mali müşavir paketi** → 03 + 10 (otomatik hatırlatma + haftalık rapor)
- **Restoran paketi** → 06 + 07 (WhatsApp sipariş + review)
- **SaaS paketi** → 08 + 10 (ödeme → CRM + haftalık MRR raporu)

Paket fiyatı: $500-$1500 kurulum + $100-$300/ay yönetim.

## Yönetim Ücreti Nedir

"Yönetim" dediğin:
- n8n sunucunun ayakta kalması (Hetzner $5/ay + Docker)
- Haftada 1 kez execution loglarına bakıp hata varsa düzeltme
- Müşteri yeni bir senaryo istedi → küçük değişiklik (1-2 saat)
- Credential yenileme (Gmail token 6 ay sonra düşüyor)

Aylık 1-2 saat işin, $100-$300/ay net kar.

## Güvenlik

- Her workflow'un webhook URL'i **secret** içerir — paylaşma
- API key'leri **n8n Credentials** ile tut, hardcode etme
- Müşterinin n8n instance'ı müşterinin Hetzner/DigitalOcean hesabında olsun, senin değil
- `.env` yedeği al — instance çökerse 10 dakikada geri getirirsin
