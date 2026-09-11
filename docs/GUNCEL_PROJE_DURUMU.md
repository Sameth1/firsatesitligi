# Fırsat Eşitliği — Güncel Proje Devralma Notu

Son güncelleme: 11 Eylül 2026

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
4. Eksiksiz HTTP-200 kayıtları NVIDIA NIM'e gider. Model güncellik, tarih, kategori, finansman, ülke ve uygunluk için birebir sayfa alıntısı verir; kod bu alıntıları sayfa metniyle eşleştirir.
5. İlk olumlu karar bağımsız karşı-denetim prompt'uyla ikinci kez incelenir. Yalnızca iki tur da yüksek güvenle aynı olumlu kanıtları bulursa otomatik onay verilir.
6. Migration 099 temel kapıları, migration 105 ise iki tur + kanıt zorunluluğunu DB içinde tekrar denetler.
7. Eski tarih, yanlış/eksik bilgi, liste-kaynak sayfası veya doğrudan olmayan link reddedilir. `agent_uncertain` yalnız tarihi güncel, doğrudan hedefi ve bütün alanları doğrulanmış kayıtta açık/kapalı kararı gerçekten çelişkiliyse kullanılır.
8. Geçici HTTP/LLM hatası admin kuyruğuna gitmez; `agent_queue` içinde yeniden denenir. Agent kaydında Revize yoktur.

## İnsan redlerinden öğrenme

- Her insan kararı `submission_review_events` tablosuna kalıcı snapshot olarak yazılır.
- Yapılandırılmış insan redleri `agent_memories` tablosuna kaynak + kategori + neden bazında eklenir.
- Ağırlıklar: ilk kayıt `example`, 3 tekrar `warning`, 5 tekrar `strong`.
- `validate_submissions.py` aynı kaynak/kategori için ilgili hafızayı her LLM kararına ekler.
- Agent hafızayı karar emsali olarak doğrudan kullanır; güncel sayfada aynı sorunu arar ve kanıt varsa ağırlığa göre karar verir.
- Güncel açık kanıt hafızayla çelişirse güncel kanıt üstündür. Hafıza tek başına kanıtsız red sebebi değildir.
- Hafıza script değişikliği, manuel geliştirme işi veya PR önerisi üretmez.

## Kör agent doğruluk testi

- `python validate_submissions.py --create-eval-batch --limit 40`, kaynak/kategori çeşitliliği olan 40 eski agent kaydını bugünkü sayfalarıyla yeniden değerlendirir.
- Test `submissions` veya `opportunities` durumlarını değiştirmez; sonuçlar ayrı eval tablolarına yazılır.
- Admin `/admin/agent-eval` ekranında ajan kararını görmeden Onay/Red etiketi verir.
- Etiketten sonra ajan sonucu açılır; doğruluk, otomatik karar kapsamı, onay isabeti ve yanlış onay sayısı hesaplanır.
- Testteki insan redleri, test skoru değişmeden sonraki agent kararları için `agent_memories` hafızasına eklenir.

## Red nedenleri nerede görülür?

- Admin kartında ve kayıt detayında `admin_note` gösterilir.
- Yeni insan redleri kodlu biçimdedir: `[insan] RED:<neden_kodu> — <açıklama>`.
- Kalıcı geçmiş: `submission_review_events`.
- Toplu salt-okunur rapor: `python validate_submissions.py --feedback-report`.
- Eski serbest metin redlerini güvenli/idempotent aktarım: önce
  `python validate_submissions.py --backfill-rejection-memory --dry-run`, sonra
  `python validate_submissions.py --backfill-rejection-memory`.

## Supabase durumu

Uygulanan agent migration'ları: 094, 095, 096, 097, **099, 100 ve iki-tur kapısı**. İki-tur kapısının SQL'i canlı projeye uygulanmıştır; repoda migration 105 olarak tutulur. Migration 106 kör doğruluk testi için hazırlanmıştır ve canlıya uygulanmayı bekler. Migration 098 yalnız eski kullanılmayan görünüm temizliğidir ve henüz uygulanmadı.

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

- PR [#40](https://github.com/Sameth1/firsatesitligi/pull/40), [#41](https://github.com/Sameth1/firsatesitligi/pull/41), [#42](https://github.com/Sameth1/firsatesitligi/pull/42) ve [#43](https://github.com/Sameth1/firsatesitligi/pull/43) `master` dalına merge edildi.
- Kör doğruluk testi PR #42 ile merge edildi; migration 106 henüz canlıya uygulanmadı.
- `supabase/functions/notify-submission/index.ts` içindeki yeni güvenli revize e-postası kodu ayrıca Supabase Edge Function olarak deploy edilmelidir; henüz canlıya alınmadı.

## Öneri formu ve revize altyapısı

- Form yalnız `/api/submit-opportunity` route'una gider; doğrudan Supabase fallback'i güvenlik nedeniyle yoktur.
- `SUPABASE_SERVICE_ROLE_KEY` 11 Eylül 2026'da yalnız Vercel Production kapsamına eklendi. PR #43 deployundan sonra canlı route'un yeni doğrulama cevabı (400) doğrulandı.
- Migration 107 canlıya uygulandı. Aynı IP'deki eşzamanlı istekler advisory lock ile sıraya alınır; doğrudan anon INSERT politikası kalmamıştır.
- `/revise/[token]` ölü kod değildir: PR #40'taki tasarım, `notify-submission` Edge Function'ının tek kullanımlık token üretip e-posta göndermesine dayanır. Edge Function deployu, webhook başlığı ve Resend ayarları doğrulanmadan akış tamamlanmış sayılmaz.
- Edge Function, `SUBMISSION_WEBHOOK_SECRET` başlığını zorunlu tutar; webhook içeriği yerine gerçek submission'ı DB'den tekrar okur ve e-posta HTML'inde kullanıcı girdilerini escape eder.

## Son doğrulamalar

- Python `py_compile`: geçti.
- TypeScript `tsc --noEmit`: geçti.
- Değiştirilen frontend ve Edge Function dosyalarında ESLint: geçti.
- `next build --webpack`: geçti.
- Vercel preview kontrolleri: geçti.
- Agent yayın/onay/red kapıları, eski red hafızası ve kör test ayrımı için 35 birim testi: geçti.
- Canlı DB'de `source_url` kolonu: doğrulandı.
- Canlı DB'de `agent_validation` kolonu ve yeni RPC imzası: doğrulandı.
- Canlı DB'de 4 anlamlı eski insan reddi 2 hafıza grubuna aktarıldı ve
  agent bağlamından okunabildiği doğrulandı.
- Canlı DB'de `trg_agent_two_pass_evidence` etkin (`tgenabled=O`) olarak doğrulandı.
- Güncel Youthop örneği NVIDIA NIM'de iki tur ve birebir kanıt kontrolünden geçti; dry-run sonucu otomatik onay oldu.
- Canlı öneri route'u Production secret ile çalışıyor; migration 107 sonrası INSERT politika sayısı `0`, RPC erişimi anon/authenticated için `false`, service role için `true` olarak doğrulandı.

## Sonraki güvenli adım

1. `notify-submission` için `RESEND_API_KEY`, `APP_URL`, `ADMIN_NOTIFY_FROM` ve `SUBMISSION_WEBHOOK_SECRET` ayarla; aynı secret'ı Database Webhook başlığına ekleyip Edge Function'ı deploy et.
2. Migration 106'yı uygula ve 40 kayıtlık kör agent testini başlat.
3. Yanlış onay hedefi `0`; sonuçlara göre agent eşiklerini kanıta dayalı ayarla.

## Çalışma ilkesi

Production kodu doğrudan değiştirilmez. Değişiklikler test edilmiş PR üzerinden ilerler. Ancak çalışma zamanındaki agent, insan red hafızasını kendi kararında otomatik kullanır; bunun için ayrıca script geliştirme görevi veya PR üretmez.
