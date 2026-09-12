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
3. Revize seçilince admin notu kayda yazılır ve kayıt `pending + agent_revision` olur; e-posta şartı yoktur.
4. Agent notu görev olarak okur, sayfayı yeniden indirir ve yalnız boş alanları birebir sayfa kanıtıyla doldurur. Dolu alanı değiştirmez, onay/red kararı vermez.
5. Agent bitirince raporunu ekler ve kayıt yeniden `pending + human_review` olur; son kararı admin verir.

Not: e-posta ile revize hiç çalışmadı — projede mail gönderen kod yok ve
`submission_revision_tokens` tablosunda 0 satır var. `/revise/[token]` sayfası
bu yüzden ölü koddur.

### Agent/scraper gönderisi

1. Agent her `agent_queue` kaydını inceler.
2. Kopya URL, geçmiş tarih ve 404/410 önce heuristiklerle değerlendirilir.
3. Eksik başlık, URL, kategori, ülke/global bilgisi, kesin güncel tarih, finansman veya uygunluk koşulu varsa kayıt LLM'e gitmeden reddedilir.
4. Eksiksiz HTTP-200 kayıtları NVIDIA NIM'e gider. Model güncellik, tarih, kategori, finansman, ülke ve uygunluk için birebir sayfa alıntısı verir; kod bu alıntıları sayfa metniyle eşleştirir.
5. İlk olumlu karar bağımsız karşı-denetim prompt'uyla ikinci kez incelenir. Yalnızca iki tur da yüksek güvenle aynı olumlu kanıtları bulursa otomatik onay verilir.
6. Migration 099 temel kapıları, migration 105 ise iki tur + kanıt zorunluluğunu DB içinde tekrar denetler.
7. Eski tarih, yanlış/eksik bilgi, liste-kaynak sayfası veya doğrudan olmayan link reddedilir. `agent_uncertain` yalnız tarihi güncel, doğrudan hedefi ve bütün alanları doğrulanmış kayıtta açık/kapalı kararı gerçekten çelişkiliyse kullanılır.
8. Geçici HTTP/LLM hatası admin kuyruğuna gitmez; `agent_queue` içinde yeniden denenir. Agent kaydında Revize yoktur.

## Filtre alanları ve uyruk (109 / 110)

Arama filtresi `match_opportunities` içinde doğru kurulu:

```
'all' = any(oc.eligible_citizenships) or p_citizenship = any(oc.eligible_citizenships)
```

Sorun bu kolonların hiç dolmamasıydı. Onay RPC'leri `opportunities`'e INSERT
ederken `eligible_citizenships`, `target_fields` ve (elle onayda) `study_level`
alanlarını submission'dan okumak yerine **sabit** `{all}` / `{any}` yazıyordu.
Sonuç: yalnız Çin/Filistin/Yemen/Afrika vatandaşlarına açık programlar Türkiye
uyruğuyla arayan kullanıcıya da çıkıyordu (ölçüm: aktif 141 kaydın 127'sinde
uyruk `{all}`, 134'ünde bölüm `{all}`).

- **109** kanıtı olan kayıtları düzeltti, emin olunamayanları
  `review_flag='uyruk_belirsiz'` ile admin panelindeki **Belirsizler**'e attı.
- **110** kaynağı kapattı: `submissions`'a `eligible_citizenships` ve
  `target_fields` kolonları eklendi, iki onay RPC'si de artık bu alanları
  submission'dan okuyor (boş/NULL → eskisi gibi `{all}`).
- Ajan, sayfada **açıkça yazan** uyruk şartını çıkarıp onaydan önce
  submission'a yazıyor; emin değilse boş bırakıyor. Uyruğu yanlış daraltmak,
  hiç daraltmamaktan daha zararlıdır — uygun bir adayı sistemden siler.
- Admin panelinde öneri detayında "Uyruk şartı" alanı elle düzenlenebilir.

### 111 / 112 — kaynaktan doğrulanmış backfill

141 aktif kaydın resmî sayfası tek tek indirildi (111'i alınabildi) ve uyruk,
bölüm, kademe, yaş kanıtları okundu. Uygulanan kural: **yanlış daraltmak, hiç
daraltmamaktan zararlıdır.** Daraltma yalnız kaynakta açık şart varken yapılır;
bir bölüm ailesi yazılırken ailenin BÜTÜN slug'ları birlikte yazılır.

- **111**: 17 kayıtta bölüm/kademe/uyruk kaynağından dolduruldu. 109'da
  Afreximbank stajını yanlış daralttığım ortaya çıktı (kaynak "non-African
  students" da kabul ediyor) — geri alındı. Georg Forster kayıtlarının uyruk
  şüphesi Humboldt'un resmî PDF listesiyle kapandı: **Türkiye listede var**.
- **112**: yaş sınırı kaydı SESSİZCE gizleyen tek filtre. 33 kaydın 20'sinde
  sınırın kaynakta hiçbir dayanağı yoktu (`age_max=30/35` kümeleri); bunlar
  kaldırıldı, yaş sınırlı kayıt 33 → 16'ya indi. Kaynağı da kapatıldı:
  `scraper_api.py` yaş bulamayınca `age_max = age_max or 30` yazıyordu.

Ajan artık hem uyruk hem bölüm kısıtını sayfadan çıkarıp onaydan önce
submission'a yazıyor; emin değilse boş bırakıyor. Admin panelinde ikisi de elle
düzenlenebiliyor.

## Güvenlik (113 / 114)

Sistem baştan tarandı; bulgular ve durumları:

- **SSRF (kapatıldı).** Öneri URL'ini ajan servis anahtarıyla indiriyor.
  `assertPublicHttpUrl` yalnız birkaç IPv4 önekine bakıyordu — 169.254.169.254
  (bulut metadata), `[::1]`, `metadata.google.internal` geçiyordu; ajanın
  `fetch_page`'inde ise hiç koruma yoktu ve yönlendirmeleri takip ediyordu.
  Her iki katman da kapatıldı, ajan ad çözümlemesi yapıp her yönlendirme
  adımını süzüyor.
- **RPC yüzeyi (daraltıldı, 113).** 14 SECURITY DEFINER fonksiyonu anon'a
  açıktı. Dikkat: `revoke ... from anon` YETMİYOR — PostgreSQL fonksiyonlara
  PUBLIC'e de EXECUTE verir; PUBLIC'ten alıp role açıkça vermek gerekir.
- **Güvenlik başlıkları (eklendi).** Canlıda yalnız HSTS vardı; admin paneli
  iframe'e alınabiliyordu.
- **Abone formu rate limit (114).** `subscribers`'a INSERT herkese açıktı ve
  limit yoktu. Öneri formundaki desen kuruldu: `/api/subscribe` → IP'yi sunucu
  okur → `subscribe_email` RPC (yalnız service_role). Dakikada 3, günde 20.
  **Anon INSERT politikası, kod canlıya çıktıktan SONRA kaldırılmalı** —
  114'ün başındaki 114b notuna bak.
- **Ölü revize akışı (silindi).** `/revise/[token]` sayfası, iki RPC ve
  `submission_revision_tokens` tablosu kaldırıldı (0 satır, hiç çalışmamıştı).
- **Açık kalan:** Supabase'de **parola ile giriş açık** ve iki admin hesabının
  da parolası var; oysa arayüz yalnız magic link kullanıyor. Bu, admin
  hesaplarına karşı parola deneme yolunu açık bırakıyor. Panelden ya parola
  girişi kapatılmalı ya da hesapların parolası kaldırılmalı; ayrıca "leaked
  password protection" açılmalı.

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

Doğrudan link geçmişi: Eski `official_url=kaynak yazı` hatası için `audit_apply_links.py` ve `backfill_apply_links.py` yazılmıştı. Migration 114 ile üç adres ayrılır: `source_url` keşif kaynağı, `details_url` resmî koşul sayfası, `official_url` gerçek başvuru aksiyonu. En fazla iki adım izleyen çözücü yalnız doğrulanmış form/portal/e-posta/belgeyi “Başvur” olarak işaretler. Eski kayıtlar silinmez; doğrulanana kadar kartta “Koşulları Gör” görünür. Yeni submission doğrulanmış rota olmadan onaylanamaz. Migration 114 henüz canlıya uygulanmadı; `backfill_apply_links.py` varsayılan olarak salt-okunur rapordur.

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

- PR [#40](https://github.com/Sameth1/firsatesitligi/pull/40)–[#45](https://github.com/Sameth1/firsatesitligi/pull/45) `master` dalına merge edildi. PR #47 açık ve CI temizdir; bu çalışma onun üstünden başlayan `codex/direct-application-links` dalındadır.
- Kör doğruluk testi PR #42 ile merge edildi; migration 106 henüz canlıya uygulanmadı.
- Revize e-posta/token yolu migration 108 sonrasında kullanılmaz; bildirim Edge Function'ı canlıya alınmadı.

## Öneri formu ve revize altyapısı

- Form yalnız `/api/submit-opportunity` route'una gider; doğrudan Supabase fallback'i güvenlik nedeniyle yoktur.
- `SUPABASE_SERVICE_ROLE_KEY` 11 Eylül 2026'da yalnız Vercel Production kapsamına eklendi. PR #43 deployundan sonra canlı route'un yeni doğrulama cevabı (400) doğrulandı.
- Migration 107 canlıya uygulandı. Aynı IP'deki eşzamanlı istekler advisory lock ile sıraya alınır; doğrudan anon INSERT politikası kalmamıştır.
- Migration 108, 11 Eylül 2026'da canlıya uygulandı. `/revise/[token]` ve `needs_revision` eski uyumluluk kodu olarak kalır; yeni admin akışı bunları kullanmaz.
- Yeni `agent_revision` kuyruğunda teknik HTTP/LLM hatası olursa kayıt agentta yeniden denenir; kanıt bulunamazsa raporla insan incelemesine döner.

## Son doğrulamalar

- Python `py_compile`: geçti.
- TypeScript `tsc --noEmit`: geçti.
- Değiştirilen frontend ve Edge Function dosyalarında ESLint: geçti.
- `next build --webpack`: geçti.
- Vercel preview kontrolleri: geçti.
- Agent yayın/onay/red kapıları, revize güvenliği, eski red hafızası ve kör test ayrımı için 41 birim testi: geçti.
- Canlı DB'de `source_url` kolonu: doğrulandı.
- Canlı DB'de `agent_validation` kolonu ve yeni RPC imzası: doğrulandı.
- Canlı DB'de 4 anlamlı eski insan reddi 2 hafıza grubuna aktarıldı ve
  agent bağlamından okunabildiği doğrulandı.
- Canlı DB'de `trg_agent_two_pass_evidence` etkin (`tgenabled=O`) olarak doğrulandı.
- Güncel Youthop örneği NVIDIA NIM'de iki tur ve birebir kanıt kontrolünden geçti; dry-run sonucu otomatik onay oldu.
- İzole NVIDIA NIM revize denemesinde yalnız boş son tarih ve dil alanları kanıtla dolduruldu; dolu alanlar korunup DB'ye yazılmadı.
- Canlı öneri route'u Production secret ile çalışıyor; migration 107 sonrası INSERT politika sayısı `0`, RPC erişimi anon/authenticated için `false`, service role için `true` olarak doğrulandı.

## Sonraki güvenli adım

1. Bir kullanıcı kaydını panelden agenta göndererek gerçek revize turunu doğrula.
2. Migration 106'yı uygula ve 40 kayıtlık kör agent testini başlat.
3. Yanlış onay hedefi `0`; sonuçlara göre agent eşiklerini kanıta dayalı ayarla.

## Çalışma ilkesi

Production kodu doğrudan değiştirilmez. Değişiklikler test edilmiş PR üzerinden ilerler. Ancak çalışma zamanındaki agent, insan red hafızasını kendi kararında otomatik kullanır; bunun için ayrıca script geliştirme görevi veya PR üretmez.
