# Fırsat Eşitliği — Güncel Proje Devralma Notu

Son güncelleme: 8 Eylül 2026

## Amaç

Türkiye'deki gençlere yurt dışı burs, staj, gönüllülük, gençlik projesi, değişim ve yaz okulu fırsatları sunan Next.js + Supabase uygulaması. Otomatik tarayıcıların bulduğu kayıtlar agent tarafından doğrulanır; kullanıcıların gönderdiği kayıtları insan admin inceler.

## Aktif teknik yapı

- Frontend: Next.js 16, React 19, TypeScript.
- Veritabanı/auth: Supabase.
- Agent LLM: NVIDIA NIM, OpenAI uyumlu API.
- Varsayılan model: `nvidia/nemotron-3-super-120b-a12b`.
- Gizli değerler yalnız `.env` içinde tutulur: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `NVIDIA_API_KEY`.

## Fırsatlar nereden geliyor?

- `nasilgitmis_scraper.py`: nasilgitmis.com içerikleri.
- `youthop_scraper.py`: Youth Opportunities içerikleri.
- `daad_scraper.py`: DAAD burs veritabanı.
- `agent_reach_url_scraper.py`: Verilen herhangi bir fırsat URL'sini ortak şemaya dönüştürür.
- `idealist_scraper.py`: eski/ayrı Idealist akışı; yeni denetimli submission hattının dışında değerlendirilmelidir.

Yeni scraper kayıtları `submissions` tablosuna `submission_origin=agent`, `review_stage=agent_queue`, `status=pending` olarak girer. Kullanıcı formu `submission_origin=human`, `review_stage=human_review` olarak kayıt açar.

## Karar akışı

### Kullanıcı gönderisi

1. Doğrudan admin panelindeki **Kullanıcı Kayıtları** sekmesine düşer.
2. Admin: Onayla / Revize / Reddet seçeneklerini kullanır.
3. Revize yalnız e-posta bırakılmış kullanıcı kaydında vardır.
4. Kullanıcı tek kullanımlık, 7 günlük güvenli bağlantıdan düzenleme yapar.
5. Revize tamamlanınca kayıt yeniden `pending + human_review` olur.

### Agent/scraper gönderisi

1. Agent her `agent_queue` kaydını inceler.
2. Kopya URL, geçmiş tarih ve 404/410 önce heuristiklerle değerlendirilir.
3. Eksik başlık, URL, kategori, ülke/global bilgisi, kesin güncel tarih, finansman veya uygunluk koşulu varsa kayıt LLM'e gitmeden reddedilir.
4. Eksiksiz HTTP-200 kayıtları NVIDIA NIM'e gider. Otomatik onay için güven yüksek olmalı; tek fırsat, doğrudan fırsat sayfası, son tarih, finansman, ülke ve uygunluk kanıtlarının tamamı ayrı ayrı doğrulanmalıdır.
5. Migration 099 aynı kapıları RPC içinde tekrar denetler; Python hatası dahi eksik kaydı yayımlayamaz ve eksik finansmanı `free` varsaymaz.
6. Eski tarih, yanlış/eksik bilgi, liste-kaynak sayfası veya doğrudan olmayan link reddedilir. `agent_uncertain` yalnız tarihi güncel, doğrudan hedefi ve bütün alanları doğrulanmış kayıtta açık/kapalı kararı gerçekten çelişkiliyse kullanılır.
7. Agent kaydında Revize yoktur; admin alanları düzeltebilir, sonra Onayla veya Reddet seçer.

## İnsan redlerinden öğrenme

- Her insan kararı `submission_review_events` tablosuna kalıcı snapshot olarak yazılır.
- Yapılandırılmış insan redleri `agent_memories` tablosuna kaynak + kategori + neden bazında eklenir.
- Ağırlıklar: ilk kayıt `example`, 3 tekrar `warning`, 5 tekrar `strong`.
- `validate_submissions.py` aynı kaynak/kategori için ilgili hafızayı her LLM kararına ekler.
- Agent hafızayı karar emsali olarak doğrudan kullanır; güncel sayfada aynı sorunu arar ve kanıt varsa ağırlığa göre karar verir.
- Güncel açık kanıt hafızayla çelişirse güncel kanıt üstündür. Hafıza tek başına kanıtsız red sebebi değildir.
- Hafıza script değişikliği, manuel geliştirme işi veya PR önerisi üretmez.

## Red nedenleri nerede görülür?

- Admin kartında ve kayıt detayında `admin_note` gösterilir.
- Yeni insan redleri kodlu biçimdedir: `[insan] RED:<neden_kodu> — <açıklama>`.
- Kalıcı geçmiş: `submission_review_events`.
- Toplu salt-okunur rapor: `python validate_submissions.py --feedback-report`.
- Eski serbest metin redlerini güvenli/idempotent aktarım: önce
  `python validate_submissions.py --backfill-rejection-memory --dry-run`, sonra
  `python validate_submissions.py --backfill-rejection-memory`.

## Supabase durumu

Uygulanan migration'lar: 094, 095, 096, 097, **099 ve 100**. Migration 099 sıkı agent onay kapısını; migration 100 ise kanıt sayfası `source_url` ile doğrudan başvuru/resmî hedef `url` ayrımını canlı Supabase'e ekledi. Migration 098 yalnız eski kullanılmayan görünüm temizliğidir ve henüz uygulanmadı.

Doğrudan link geçmişi: Eski `official_url=kaynak yazı` hatası için `audit_apply_links.py` ve `backfill_apply_links.py` yazılmıştı. Youthop ve Nasıl Gitmiş scraper'ları dış Apply linkini çıkarmaya başlamıştı; ancak kaynak ile hedef ayrı DB alanlarında tutulmuyordu. Migration 100 ve güncel scraper'lar bu ayrımı kalıcı hale getirir. Agent hedef linki kontrol ederken tarih/kategori kanıtını ayrı kaynak sayfasından okuyabilir.

Migration 097 sonrası doğrulanan canlı durum:

- 104 geçmiş insan karar olayı kaydedildi.
- 377 submission: 130 agent onaylı, 245 agent reddedilmiş, 1 insan onaylı, 1 insan reddedilmiş.
- O anda pending kayıt yoktu.
- Eski 84 insan reddinin 68'inde neden yok, 16'sı eski serbest metin biçimindeydi. Anlamı kesin 4 eski red (`expired`: 2, `not_eligible`: 2) hafızaya aktarıldı; `yok`/`am` gibi 12 belirsiz not agent'ı yanlış yönlendirmemesi için atlandı. Yeni panelde yapılandırılmış red geldikçe hafıza otomatik güncellenir.

8 Eylül salt-okunur eski onay taraması (`--reaudit-agent-approvals`):

- Gerçek agent otomatik onayı: 111 (adminin sonradan onayladığı 19 kayıt hariç).
- Yeni sıkı kapıyı geçen: 0.
- Aktif fakat süresi geçmiş, kapatılmalı: 30.
- Eksik/kanıtsız, admin kontrolü gerekli: 64.
- Zaten kapalı: 17.
- En yaygın sorun: 75 kayıtta tam ve işlenebilir son tarih yok.
- Ayrıntılı salt-okunur rapor: `docs/reports/agent-approval-reaudit-2026-09-08.json`.

## Kod ve PR durumu

- Çalışma dalı: `codex/backfill-admin-rejection-memory`.
- PR [#40](https://github.com/Sameth1/firsatesitligi/pull/40) `master` dalına merge edildi.
- `supabase/functions/notify-submission/index.ts` içindeki yeni güvenli revize e-postası kodu ayrıca Supabase Edge Function olarak deploy edilmelidir. Bunu frontend merge ile aynı anda yapmak gerekir.

## Son doğrulamalar

- Python `py_compile`: geçti.
- TypeScript `tsc --noEmit`: geçti.
- Değiştirilen frontend ve Edge Function dosyalarında ESLint: geçti.
- `next build --webpack`: geçti.
- Vercel preview kontrolleri: geçti.
- Agent yayın/onay/red kapıları ve eski red hafızası için 17 birim testi: geçti.
- Canlı DB'de `source_url` kolonu: doğrulandı.
- Canlı DB'de `agent_validation` kolonu ve yeni RPC imzası: doğrulandı.
- Canlı DB'de 4 anlamlı eski insan reddi 2 hafıza grubuna aktarıldı ve
  agent bağlamından okunabildiği doğrulandı.
- NVIDIA NIM izole şema çağrısı: başarılı; bütün yeni doğrulama alanları döndü ve sıkı kapıdan geçti.

## Sonraki güvenli adım

1. Rapordaki 30 süresi geçmiş kaydı admin onayıyla pasifleştir; 64 kaydı panelden incele.
2. İsteğe bağlı temizlik olarak migration 098'i çalıştır.
3. PR #40'ı incele ve merge et.
4. `notify-submission` Edge Function'ını deploy et; webhook ve `APP_URL`/Resend env değerlerini doğrula.

## Çalışma ilkesi

Production kodu doğrudan değiştirilmez. Değişiklikler test edilmiş PR üzerinden ilerler. Ancak çalışma zamanındaki agent, insan red hafızasını kendi kararında otomatik kullanır; bunun için ayrıca script geliştirme görevi veya PR üretmez.
