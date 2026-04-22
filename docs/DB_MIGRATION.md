# FırsatBul — DB Migration Kılavuzu

## Çalıştırma Sırası

Supabase Dashboard → SQL Editor → her dosyayı sırayla yapıştır ve çalıştır:

```
001_initial_schema.sql   → Tablolar, indexler, RLS, helper view
002_seed_data.sql        → 15 başlangıç fırsatı + belge listeleri
003_match_function.sql   → Kullanıcı profili eşleştirme fonksiyonu
```

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
