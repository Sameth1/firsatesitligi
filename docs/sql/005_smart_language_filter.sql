-- ============================================================
-- 005 · Akıllı dil filtresi (ILIKE) + İngilizce her zaman geçer
-- Supabase Dashboard → SQL Editor → çalıştır
-- ============================================================
-- Not: 004'ün yerini alır. p_language artık dil ADI alır
--      (örn. "İspanyolca", "Almanca") ve ILIKE ile eşleşir.
--      "B2 İspanyolca", "İspanyolca veya İngilizce" gibi
--      free-text language_requirement değerleriyle çalışır.
-- ============================================================

CREATE OR REPLACE FUNCTION public.match_opportunities(
  p_host_country  text    DEFAULT NULL,
  p_category_slug text    DEFAULT NULL,
  p_citizenship   text    DEFAULT 'TR',
  p_age           integer DEFAULT NULL,
  p_study_level   text    DEFAULT NULL,
  p_field         text    DEFAULT NULL,
  p_language      text    DEFAULT NULL    -- dil ADI: "İspanyolca", "Almanca"
)
RETURNS TABLE(
  id                  uuid,
  title               text,
  official_url        text,
  deadline            date,
  deadline_notes      text,
  host_countries      text[],
  funding_type        text,
  funding_notes       text,
  eligibility_notes   text,
  language_requirement text,
  age_min             integer,
  age_max             integer,
  category_slug       text,
  category_label_tr   text,
  category_color      text,
  documents           json,
  is_featured         boolean,
  days_until_deadline integer
)
LANGUAGE sql
STABLE
AS $function$
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
    end as days_until_deadline
  from opportunity_cards oc
  where
    (
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
    -- Akıllı dil filtresi:
    -- Kullanıcı dil seçmediyse (null) → her şey gelir
    -- Seçtiyse → ya dil şartı yok, ya İngilizce'yi kabul ediyor,
    --            ya kullanıcının dilini içeriyor, ya "hedef dil" diyor
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
