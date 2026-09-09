-- ============================================================
-- 101 · opportunities: Türkçe kısa özet + Türkçe uygunluk metni
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- NEDEN:
--   Sonuç kartlarında gösterecek Türkçe bir açıklama alanı YOK. Elimizdeki
--   metin kolonları (eligibility_notes, funding_notes, deadline_notes) kaynak
--   sayfalardan geldiği için çoğunlukla İNGİLİZCE. Türkçe bir siteyi İngilizce
--   notlarla listelemek hem okunurluğu hem güveni düşürüyor.
--
-- NE YAPIYOR:
--   1) public.opportunities'e iki NULLABLE kolon ekler:
--        • summary_tr            → fırsatın ne olduğunu anlatan 2-3 cümlelik
--                                  Türkçe özet (LLM ile backfill edilir).
--        • eligibility_notes_tr  → mevcut eligibility_notes'un Türkçe karşılığı.
--      Orijinal eligibility_notes SİLİNMEZ / DEĞİŞTİRİLMEZ. UI önce Türkçesine
--      bakar, yoksa orijinali gösterir (progressive enhancement).
--   2) match_opportunities RPC'sini bu iki kolonu da döndürecek şekilde
--      yeniden tanımlar. Fonksiyonun gövdesi 093 ile BİREBİR aynıdır — filtre
--      mantığı, is_active kontrolü, sıralama, documents json'u ve
--      days_until_deadline hesabı hiç değişmedi; yalnızca SELECT listesine ve
--      RETURNS TABLE'a iki kolon eklendi.
--
-- NOT (kolonlar neden opp.'dan okunuyor):
--   RPC public.opportunity_cards view'ından okuyor; view'ın tanımı bu repoda
--   değil (001'de, canlı DB'de). View'a dokunmamak için yeni kolonlar zaten
--   var olan `left join public.opportunities opp` üzerinden seçiliyor. Böylece
--   view'ı değiştirmeye gerek kalmıyor ve mevcut davranış korunuyor.
--
-- ÖNKOŞUL: 093 (match_opportunities'in en güncel tanımı).
-- IDEMPOTENT: evet — `add column if not exists` + `drop ... if exists`.
--
-- GERİ ALINABİLİR Mİ: evet.
--   • Kolonları geri almak için:
--       alter table public.opportunities
--         drop column if exists summary_tr,
--         drop column if exists eligibility_notes_tr;
--   • RPC'yi eski hâline döndürmek için 093_match_filter_is_active.sql'i
--     yeniden çalıştırmak yeterli (önce yukarıdaki drop'ları yap, yoksa
--     kolonlar tabloda kalır ama RPC onları döndürmez — bu da zararsızdır).
-- ============================================================

-- ─── 1) Yeni kolonlar (nullable — mevcut veri bozulmaz) ─────────

alter table public.opportunities
  add column if not exists summary_tr text,
  add column if not exists eligibility_notes_tr text;

comment on column public.opportunities.summary_tr is
  'Kart üzerinde gösterilen 2-3 cümlelik Türkçe özet. NULL ise UI özet göstermez.';

comment on column public.opportunities.eligibility_notes_tr is
  'eligibility_notes''un Türkçe karşılığı. NULL ise UI orijinal eligibility_notes''u gösterir.';

-- ─── 2) match_opportunities — dönüş tipi değişiyor ──────────────
-- Postgres'te RETURNS TABLE değişen bir fonksiyon `create or replace` ile
-- güncellenemez ("cannot change return type of existing function"), önce TAM
-- İMZAYLA drop edilmeli. Eski 6-arg overload'u da (varsa) temizliyoruz —
-- PostgREST overload çözümünde PGRST203 atıyordu (bkz. 093).

drop function if exists public.match_opportunities(text, text, text, integer, text, text);
drop function if exists public.match_opportunities(text, text, text, integer, text, text, text);
drop function if exists public.match_opportunities(text, text, text, integer, text, text, text, text);

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
returns table(
  id                      uuid,
  title                   text,
  official_url            text,
  deadline                date,
  deadline_notes          text,
  host_countries          text[],
  funding_type            text,
  funding_notes           text,
  eligibility_notes       text,
  language_requirement   text,
  age_min                 integer,
  age_max                 integer,
  category_slug           text,
  category_label_tr       text,
  category_color          text,
  documents               json,
  is_featured             boolean,
  days_until_deadline     integer,
  submitted_by_nickname text,
  last_url_check_at     timestamptz,
  last_url_check_status integer,
  -- 101 ile eklenen iki kolon (sona eklendi; mevcut sıra korundu)
  summary_tr            text,
  eligibility_notes_tr  text
)
language sql
stable
as $function$
  select
    oc.id,
    oc.title,
    oc.official_url,
    oc.deadline,
    oc.deadline_notes,
    oc.host_countries,
    oc.funding_type,
    oc.funding_notes,
    oc.eligibility_notes,
    oc.language_requirement,
    oc.age_min,
    oc.age_max,
    oc.category_slug,
    oc.category_label_tr,
    oc.category_color,
    oc.documents,
    oc.is_featured,
    case
      when oc.deadline is null then null
      else (oc.deadline - current_date)::int
    end as days_until_deadline,
    opp.submitted_by_nickname,
    opp.last_url_check_at,
    opp.last_url_check_status,
    opp.summary_tr,
    opp.eligibility_notes_tr
  from public.opportunity_cards oc
  left join public.opportunities opp on opp.id = oc.id
  where
    coalesce(opp.is_active, true) = true
    and (
      p_host_country is null
      or '*' = any(oc.host_countries)
      or p_host_country = any(oc.host_countries)
    )
    and (p_category_slug is null or oc.category_slug = p_category_slug)
    and (
      'all' = any(oc.eligible_citizenships)
      or p_citizenship = any(oc.eligible_citizenships)
    )
    and (p_age is null or oc.age_min is null or oc.age_min <= p_age)
    and (p_age is null or oc.age_max is null or oc.age_max >= p_age)
    and (
      p_study_level is null
      or 'any' = any(oc.study_level)
      or p_study_level = any(oc.study_level)
    )
    and (
      p_field is null
      or 'all' = any(oc.target_fields)
      or p_field = any(oc.target_fields)
    )
    and (
      p_language is null
      or oc.language_requirement is null
      or oc.language_requirement ilike '%' || p_language || '%'
      or oc.language_requirement ilike '%İngilizce%'
      or oc.language_requirement ilike '%hedef dil%'
      or oc.language_requirement ilike '%ev sahibi%'
    )
    and (oc.deadline is null or oc.deadline >= current_date)
  order by
    oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;

-- ─── 3) GRANT'leri geri ver ─────────────────────────────────────
-- drop function, fonksiyona verilmiş EXECUTE yetkilerini de siler. 090/093'te
-- verilen grant'ler burada aynen tekrarlanıyor; anon (giriş yapmamış ziyaretçi)
-- yetkisi olmadan arama tamamen çalışmaz.
-- 091'deki diğer grant'ler (approve_submission, request_revision,
-- reject_submission, get_submission_stats, get_admin_stats) bu migration'dan
-- ETKİLENMEZ — o fonksiyonlar drop edilmiyor, tekrar vermeye gerek yok.

grant execute on function public.match_opportunities(
  text, text, text, integer, text, text, text, text
) to anon, authenticated, service_role;
