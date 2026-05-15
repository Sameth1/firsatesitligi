-- ============================================================
-- 093 · match_opportunities: is_active filtresi ekle + duplicate overload temizliği
-- Pasifleştirilen kayıtlar (is_active=false) artık kullanıcıya
-- görünmez. Önceden RPC'de bu filtre yoktu; pasifleştirme yalnızca
-- DB seviyesinde işaretlemeydi, frontend yine listeliyordu.
-- Ayrıca DB'de eski 6-arg overload duruyordu; PostgREST overload
-- çözümünde takılıyordu (PGRST203). Burada drop ediyoruz.
-- Supabase SQL Editor'da çalıştır; 092 sonrası idempotent.
-- ============================================================

-- 1) Eski overload'u temizle — yoksa PostgREST PGRST203 atar
drop function if exists public.match_opportunities(text, text, text, integer, text, text);

-- 2) Mevcut 8-arg fonksiyonu is_active filtresi eklenmiş hâliyle yenile
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
  last_url_check_status integer
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
    opp.last_url_check_status
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

grant execute on function public.match_opportunities(
  text, text, text, integer, text, text, text, text
) to anon, authenticated, service_role;
