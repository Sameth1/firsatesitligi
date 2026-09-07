# Fırsat Eşitliği — Güncel Proje Devralma Notu

Son güncelleme: 7 Eylül 2026

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
3. Belirsiz HTTP-200 kayıtları NVIDIA NIM'e gider.
4. Agent açık+uygun kayıtları otomatik onaylar, net uygunsuz/kapalı kayıtları otomatik reddeder.
5. Gerçekten belirsiz kalanlar `agent_uncertain` olur ve admin panelindeki **Agent Belirsizleri** sekmesine düşer.
6. Agent kaydında Revize yoktur; admin alanları düzeltebilir, sonra Onayla veya Reddet seçer.

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

## Supabase durumu

Uygulanan migration'lar: 094, 095, 096 ve 097. `098_remove_manual_improvement_queue.sql` kodda hazırdır; tarayıcı bağlantısı yanıt vermediği için canlı projede henüz çalıştırılmadı. Bu yalnız artık kullanılmayan eski PR-adayı görünümünü siler; agent karar akışını etkilemez.

Migration 097 sonrası doğrulanan canlı durum:

- 104 geçmiş insan karar olayı kaydedildi.
- 377 submission: 130 agent onaylı, 245 agent reddedilmiş, 1 insan onaylı, 1 insan reddedilmiş.
- O anda pending kayıt yoktu.
- `agent_memories` başlangıçta 0 idi; eski 84 insan reddinin 68'inde neden yok, 16'sı eski serbest metin biçimindeydi. Yeni panelde yapılandırılmış red geldikçe hafıza otomatik oluşacak.

## Kod ve PR durumu

- Çalışma dalı: `claude/proje-durumu-eksikler-vu5n31`.
- Açık draft PR: [#40](https://github.com/Sameth1/firsatesitligi/pull/40).
- PR #40 Vercel kontrollerinden geçti fakat henüz production'a merge edilmedi.
- Migration veritabanında uygulanmış olsa da yeni admin arayüzü ve `/revise/[token]` sayfası PR merge edilene kadar production'da görünmez.
- `supabase/functions/notify-submission/index.ts` içindeki yeni güvenli revize e-postası kodu ayrıca Supabase Edge Function olarak deploy edilmelidir. Bunu frontend merge ile aynı anda yapmak gerekir.

## Son doğrulamalar

- Python `py_compile`: geçti.
- TypeScript `tsc --noEmit`: geçti.
- Değiştirilen frontend ve Edge Function dosyalarında ESLint: geçti.
- `next build --webpack`: geçti.
- Vercel preview kontrolleri: geçti.

## Sonraki güvenli adım

1. İsteğe bağlı temizlik olarak migration 098'i çalıştır.
2. PR #40'ı incele ve merge et.
3. `notify-submission` Edge Function'ını deploy et; webhook ve `APP_URL`/Resend env değerlerini doğrula.
4. Bir test kullanıcı gönderisiyle Revize → güvenli link → yeniden pending akışını uçtan uca dene.
5. Ardından kullanıcının ertelediği kaynak toplama planındaki “2-3-4” başlıklarına dön. Önceki konuşmada bu başlıkların ayrıntısı tamamlanmadığı için kullanıcıdan kısa teyit al.

## Çalışma ilkesi

Production kodu doğrudan değiştirilmez. Değişiklikler test edilmiş PR üzerinden ilerler. Ancak çalışma zamanındaki agent, insan red hafızasını kendi kararında otomatik kullanır; bunun için ayrıca script geliştirme görevi veya PR üretmez.
