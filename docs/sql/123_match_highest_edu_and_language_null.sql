-- ============================================================
-- 123 · match_opportunities: ölü eğitim filtresi + dil filtresinin blokajı
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- CANLIYA UYGULANDI: 12 Eylül 2026
-- ============================================================
-- ÖNKOŞUL: master'ın 114-122'si. Bu dosya onların üzerine yazar; gövde
-- 122'nin (guided başvuru rotası) sürümüdür, iki satır eklenmiştir.
--
-- SIRA ÖNEMLİ: 116 (eski 9 parametreli overload'u siler) ve 119 (sıkı ülke
-- filtresi) bu dosyadan SONRA çalıştırılırsa buradaki düzeltmeler kaybolur.
-- İmza bilerek 8 parametrede tutuldu ki 116'nın çözdüğü PostgREST overload
-- belirsizliği geri gelmesin.
--
-- ── DÜZELTME A · p_highest_edu ölü parametreydi ────────────────
-- Parametre listesinde vardı, WHERE'de adı bile geçmiyordu. Kullanıcı
-- "eldeki eğitim seviyesi"ni seçiyor, sonuç hiç değişmiyordu. Dahası
-- sonuç 0 çıkınca arayüz "bu filtreyi gevşettik" diyordu — hiç
-- uygulanmamış bir filtreyi.
--
-- Yeni kural yalnız KESİN olanı eler: lise veya ön lisans seviyesindeki
-- biri, kademesi tamamen yüksek lisans/doktora olan kayda başvuramaz.
-- Lisans için doktora ELENMEZ — birçok ülkede lisanstan doğrudan doktora
-- mümkün, elemek yanlış negatif üretirdi.
-- Ölçüm: filtresiz 75 sonuç → 'lise' seçilince 50, 'lisans' seçilince 75.
--
-- ── DÜZELTME B · dil filtresi her kaydı eliyordu ───────────────
-- 120 `required_languages text[]` kolonunu ekledi ve tanımını yazdı:
-- "{all}=dil şartı yok, NULL=bilinmiyor". Filtre ise şöyleydi:
--     p_language is null or 'all' = any(required_languages)
--                        or lower(p_language) = any(required_languages)
-- Kolon 98 aktif kaydın 98'inde NULL. NULL dizide `= any(...)` hiçbir zaman
-- true dönmez → dil seviyesi beyan eden kullanıcıya SIFIR sonuç kalıyordu.
-- Ölçüldü: ülke DE + dil Almanca → 0 sonuç. (Arayüzdeki fallback filtreyi
-- gevşetip tekrar sorduğu için kullanıcı bunu "dil filtresi gevşetildi"
-- olarak görüyordu; yani filtre hiç çalışmıyordu.)
--
-- Bilinmeyeni elemek yerine geçiriyoruz — projenin kuralı bu: kayıtta bir
-- şart YAZMIYORSA o boyut elemez. required_languages dolmaya başlayınca
-- (120'nin trigger'ı yeni onaylarda dolduruyor) bu satır kaldırılıp sıkı
-- kurala dönülebilir.
--
-- ── DEĞİŞTİRİLMEYENLER ────────────────────────────────────────
-- • 119'un sıkı ülke filtresi AYNEN korundu: kullanıcı ülke seçtiğinde
--   host_countries='*' olan küresel kayıtlar GELMEZ. (Bir ara bunu
--   "regresyon" sanıp geri almıştım; 119'un gerekçesi haklı — hatalı '*'
--   girilmiş kayıtlar her ülke aramasına sızıyordu.)
-- • 121/122'nin başvuru rotası kapısı, 117'nin kategori şartı: dokunulmadı.
-- • search_path yeniden sabitlendi (113'te yapılmıştı, gövde yeniden
--   yazılınca kaybolmuştu).
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet — 122 yeniden çalıştırılır.
-- ============================================================

begin;

create or replace function public.match_opportunities(
  p_host_country  text    default null,
  p_category_slug text    default null,
  p_citizenship   text    default 'TR',
  p_age           integer default null,
  p_study_level   text    default null,
  p_highest_edu   text    default null,
  p_field         text    default null,
  p_language      text    default null
)
returns table (
  id uuid, title text, official_url text, deadline date, deadline_notes text,
  host_countries text[], funding_type text, funding_notes text,
  eligibility_notes text, language_requirement text, age_min integer,
  age_max integer, category_slug text, category_label_tr text,
  category_color text, documents json, is_featured boolean,
  days_until_deadline integer, submitted_by_nickname text,
  last_url_check_at timestamptz, last_url_check_status integer,
  summary_tr text, eligibility_notes_tr text, details_url text,
  application_route_status text, application_method text,
  application_url_verified_at timestamptz
)
language sql
stable
set search_path to 'public'
as $function$
  select
    oc.id, oc.title, oc.official_url, oc.deadline, oc.deadline_notes,
    oc.host_countries, oc.funding_type, oc.funding_notes, oc.eligibility_notes,
    oc.language_requirement, oc.age_min, oc.age_max, oc.category_slug,
    oc.category_label_tr, oc.category_color, oc.documents, oc.is_featured,
    case when oc.deadline is null then null else (oc.deadline - current_date)::int end,
    opp.submitted_by_nickname, opp.last_url_check_at, opp.last_url_check_status,
    opp.summary_tr, opp.eligibility_notes_tr, opp.details_url,
    opp.application_route_status, opp.application_method,
    opp.application_url_verified_at
  from public.opportunity_cards oc
  join public.opportunities opp on opp.id = oc.id
  where opp.is_active = true
    and (((opp.application_route_status = 'verified'
      and nullif(btrim(opp.official_url), '') is not null
      and nullif(btrim(opp.application_url_final), '') is not null
      and opp.application_url_verified_at is not null))
      or (opp.application_route_status = 'guided'
      and nullif(btrim(opp.details_url), '') is not null))
    and oc.category_slug is not null
    and (p_host_country is null or p_host_country = any(oc.host_countries))
    and (p_category_slug is null or oc.category_slug = p_category_slug)
    and ('all' = any(oc.eligible_citizenships) or p_citizenship = any(oc.eligible_citizenships))
    and (p_age is null or oc.age_min is null or oc.age_min <= p_age)
    and (p_age is null or oc.age_max is null or oc.age_max >= p_age)
    and (p_study_level is null or p_study_level = 'any'
      or 'any' = any(oc.study_level) or p_study_level = any(oc.study_level))

    -- A) Eldeki eğitim seviyesi — ön koşul kapısı
    and (p_highest_edu is null
      or p_highest_edu not in ('lise', 'on_lisans')
      or 'any' = any(oc.study_level)
      or 'bachelor' = any(oc.study_level))

    and (p_field is null or 'all' = any(oc.target_fields) or p_field = any(oc.target_fields))

    -- B) Dil — kayıtta şart yazmıyorsa (NULL/boş) eleme yok
    and (p_language is null
      or opp.required_languages is null
      or opp.required_languages = '{}'
      or 'all' = any(opp.required_languages)
      or lower(p_language) = any(opp.required_languages))

    and (oc.deadline is null or oc.deadline >= current_date)
  order by oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;

notify pgrst, 'reload schema';

commit;
