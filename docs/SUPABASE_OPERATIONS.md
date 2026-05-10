# Supabase işlemleri

## Önerilen SQL çalıştırma sırası

Aşağıdaki dosyaları `docs/sql/` altından **bu sırayla** Supabase Dashboard → SQL Editor’da çalıştırın:

1. `004_language_and_filter_options.sql`
2. `005_smart_language_filter.sql`
3. `006_submissions_v2.sql`
4. `007_opportunity_url_health.sql`
5. `090_one_shot_after_006.sql`
6. `091_admin_rpc_grants.sql`
7. `092_approve_submission_funding_default.sql` (onayda boş `funding_type` → `free`; 090 sonrası mevcut projeler için)

Önceki adımlar şemayı ve RPC’leri oluşturur; `091` özellikle `authenticated` rolüne ilgili admin RPC’ler için `EXECUTE` verir (PostgREST / istemci çağrıları için).

## Vercel + admin magic link (localhost’a düşmemesi)

**Repo tarafı (otomatik):** [`next.config.ts`](../next.config.ts) Vercel’de `VERCEL_URL` ile `NEXT_PUBLIC_SITE_URL` üretir; ayrıca [`src/lib/site-origin.ts`](../src/lib/site-origin.ts) + admin login bu değeri kullanır. Özel domain kullanıyorsan Vercel’e `NEXT_PUBLIC_SITE_URL=https://alanadin.com` eklemen yeterli.

**Senin bir kez yapman gereken (Supabase hesabına sadece sen girebilirsin):** Dashboard → **Authentication → URL Configuration**

1. **Site URL:** `https://firsatesitligi.vercel.app` (veya özel domainin).
2. **Redirect URLs:** şunları ekle (her satır ayrı veya wildcard):
   - `https://firsatesitligi.vercel.app/auth/callback`
   - İstersen: `https://firsatesitligi.vercel.app/**`
3. E-posta şablonunda magic link için **`{{ .ConfirmationURL }}`** kullan; sabit `localhost` yazma.

`redirect_to` bu listede yoksa Supabase linki **Site URL**’e (çoğu zaman eski localhost) düşürür; bu adım kodla otomatik yapılamaz.

## 006 sonrası: admin kaydı

`006_submissions_v2.sql` sonrası kendi kullanıcınızı `public.admins` tablosuna ekleyin:

- `user_id`: `auth.users` içindeki satırın `id` değeri (UUID).
- `email`: kullanıcının e-postası (ör. `auth.users.email` ile aynı).

Admin değilseniz submission satırlarına RLS ile erişemez ve RPC’ler “Yetkisiz” verir.

## `approve_submission` ve kategori

`090_one_shot_after_006.sql` içindeki `approve_submission`, gönderinin `category_slug` değerini `public.categories.slug` ile eşleştirir. Slug tabloda yoksa onay **hata** ile düşer; önce kategoriyi düzeltin veya (şema izin veriyorsa) slug’ı boş/geçerli bir değere çekin. Ayrıntı için 090 dosyasındaki yorumlara bakın.

`opportunities.funding_type` **NOT NULL** ise ve öneride burs tipi seçilmemişse, `092_approve_submission_funding_default.sql` dosyasını çalıştırın (NULL → `'free'`).

## n8n / içe aktarma

- **Service role** anahtarını yalnızca sunucu tarafında (güvenilir ortam) kullanın; tarayıcıya veya n8n’de herkese açık akışlara koymayın.
- Önerilen model: kayıtlar `submissions` tablosunda **`pending`** kalır; yayına alma mevcut **admin onayı** (panel + RPC) ile yapılır.
- Aynı **URL** ile tekrarlayan kayıtlar için uygulama tarafında veya veri katmanında **dedupe** kuralı tanımlayın (iş kurallarınıza göre).
