# FırsatBul — DB Migration Kılavuzu

## Çalıştırma Sırası

Supabase Dashboard → SQL Editor → her dosyayı sırayla yapıştır ve çalıştır:

```
001_initial_schema.sql   → Tablolar, indexler, RLS, helper view
002_seed_data.sql        → 15 başlangıç fırsatı + belge listeleri
003_match_function.sql   → Kullanıcı profili eşleştirme fonksiyonu
004_language_and_filter_options.sql → Dil filtresi + dinamik filtre seçenekleri
005_smart_language_filter.sql       → Akıllı dil filtresi (ILIKE)
006_submissions_v2.sql   → Community sourcing: submissions v2, admins, RLS, approve/revise/reject RPC
007_opportunity_url_health.sql → (İsteğe bağlı ayrı dosya) URL kolonları + admin RPC — aynısı 090’da da var
090_one_shot_after_006.sql → 006 sonrası TEK seferde: 007 + match_opportunities düzeltmesi (p_highest_edu, submitted_by_nickname, link özeti, last_verified_at)
```

**Canlı projede en az yapman gereken:** `001`–`006` zaten uygulandıysa, Dashboard’ta yalnızca **`090_one_shot_after_006.sql`** dosyasını bir kez çalıştır (veya `npm run db:090`). Böylece link denetimi şeması ve `match_opportunities` uygulamayla uyumlu hale gelir.

---

## Supabase CLI ile 006 (Dashboard yerine)

Senin bilgisayarında çalışır; tarayıcıda SQL yapıştırmak zorunda kalmazsın.

1. **CLI kurulumu yoksa:** `npm install` zaten yeterli; komutlar `npx supabase` ile de çalışır.
2. **Giriş:** `npm run supabase:login` → tarayıcıda Supabase hesabınla onayla.
3. **Projeyi bağla:** [Dashboard](https://supabase.com/dashboard) → projen → **Settings → General → Reference ID** kopyala. Sonra:
   ```bash
   npm run supabase:link
   ```
   Sorunca Reference ID’yi yapıştır.
4. **006 SQL’i uzak veritabanında çalıştır:**
   ```bash
   npm run db:006
   ```

Önce `001`–`005` (veya mevcut şeman) Dashboard’ta çalışmış olmalı; yoksa `006` tabloları bulamaz. Hata mesajını kaydedersen düzeltiriz.

**Admin satırı** (Auth’ta kullanıcın oluştuktan sonra, UUID’yi Authentication → Users’tan al):

```sql
insert into public.admins (user_id, email)
values ('AUTH_USER_UUID_BURAYA', 'senin@email.com');
```

Bu satırı yine `npm run db:006` gibi değil; Dashboard **SQL Editor**’da veya `supabase db query --linked -c "insert ..."` ile çalıştırabilirsin.

---

## Frontend'den Kullanım

### Eşleştirme sorgusu (Supabase JS client)

```js
// Kullanıcı: Türk, 23 yaşında, İspanya, lisans, moda tasarımı
const { data } = await supabase.rpc('match_opportunities', {
  p_host_country:  'ES',
  p_category_slug:  null,       // tüm kategoriler
  p_citizenship:   'TR',
  p_age:           23,
  p_study_level:   'bachelor',
  p_highest_edu:   null,         // 090 sonrası imzada var; null = filtre yok
  p_field:         null         // tüm bölümler
})
```

### Tüm fırsatlar (filtresiz)
```js
const { data } = await supabase.rpc('match_opportunities', {})
```

### Sadece gönüllülük
```js
const { data } = await supabase.rpc('match_opportunities', {
  p_category_slug: 'volunteering'
})
```

---

## Email Kayıt (Subscribers)

```js
// Kullanıcı email girer → soft subscribe
const { error } = await supabase
  .from('subscribers')
  .insert({
    email: 'user@example.com',
    search_snapshot: {
      countries: ['ES'],
      categories: ['scholarship'],
      fields: ['fashion']
    }
  })
```

---

## Community Sourcing (Submissions)

```js
// Form submit
const { error } = await supabase
  .from('submissions')
  .insert({
    title:           'KAIST Scholarship — Güney Kore',
    url:             'https://admission.kaist.ac.kr/international/scholarship/',
    category_slug:   'scholarship',
    deadline_text:   '15 Eylül 2026',
    host_country:    'KR',
    description:     'Tam burslu lisans ve yüksek lisans programları',
    submitter_email: 'user@example.com'   // opsiyonel
  })
```

---

## N8n Scraper Entegrasyonu

N8n'de Supabase node kullanarak `sources` tablosundan aktif kaynakları çek:

```sql
select id, name, url from sources
where is_active = true
and (
  last_scraped_at is null
  or (scrape_frequency = 'daily'    and last_scraped_at < now() - interval '1 day')
  or (scrape_frequency = 'weekly'   and last_scraped_at < now() - interval '7 days')
  or (scrape_frequency = 'biweekly' and last_scraped_at < now() - interval '14 days')
)
```

Scrape sonrası `last_scraped_at`'i güncelle:
```sql
update sources set last_scraped_at = now() where id = :source_id
```

---

## RLS Özeti

| Tablo         | Okuma                   | Yazma                       |
|---------------|-------------------------|-----------------------------|
| opportunities | Herkese açık (aktif)    | Service role (n8n, admin)   |
| documents     | Herkese açık            | Service role                |
| categories    | Herkese açık            | Service role                |
| sources       | Kapalı                  | Service role                |
| subscribers   | Kapalı                  | Herkes INSERT yapabilir     |
| submissions   | Kapalı                  | Herkes INSERT yapabilir     |
