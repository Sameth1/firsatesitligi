-- ============================================================
-- 004 · Dil filtresi + dinamik filtre seçenekleri
-- Supabase Dashboard → SQL Editor → çalıştır
-- ============================================================

-- 1. match_opportunities fonksiyonunu p_language parametresiyle güncelle
-- ============================================================
CREATE OR REPLACE FUNCTION public.match_opportunities(
  p_host_country  text    DEFAULT NULL,
  p_category_slug text    DEFAULT NULL,
  p_citizenship   text    DEFAULT 'TR',
  p_age           integer DEFAULT NULL,
  p_study_level   text    DEFAULT NULL,
  p_field         text    DEFAULT NULL,
  p_language      text    DEFAULT NULL   -- YENİ: kullanıcının bildiği dil
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
    -- YENİ: dil şartı yoksa (null) herkese açık; kullanıcı dil girdiyse
    -- sadece o dili veya dil şartı olmayan fırsatları göster
    and (
      p_language is null
      or oc.language_requirement is null
      or oc.language_requirement = p_language
    )
    and (oc.deadline is null or oc.deadline >= current_date)
  order by
    oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;


-- 2. Dinamik filtre seçenekleri fonksiyonu
-- Frontend bu fonksiyonu çağırarak chip listelerini DB'den çeker
-- ============================================================
CREATE OR REPLACE FUNCTION public.get_filter_options()
RETURNS json
LANGUAGE sql
STABLE
AS $function$
  select json_build_object(
    'fields', (
      select coalesce(
        array_agg(distinct f order by f),
        array[]::text[]
      )
      from opportunity_cards, unnest(target_fields) as f
      where f <> 'all'
        and (deadline is null or deadline >= current_date)
    ),
    'languages', (
      select coalesce(
        array_agg(distinct language_requirement order by language_requirement),
        array[]::text[]
      )
      from opportunity_cards
      where language_requirement is not null
        and (deadline is null or deadline >= current_date)
    )
  )
$function$;
