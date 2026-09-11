-- Doğrudan formu olmayan fakat çalışan, resmî ve sade fırsat sayfası bulunan
-- eski kayıtlar için ikinci görünürlük seviyesi.

begin;

alter table public.opportunities
  drop constraint if exists opportunities_application_route_status_check;
alter table public.opportunities
  add constraint opportunities_application_route_status_check
  check (application_route_status in ('verified', 'guided', 'unverified', 'missing'));

create or replace function public.match_opportunities(
  p_host_country text default null,
  p_category_slug text default null,
  p_citizenship text default 'TR',
  p_age integer default null,
  p_study_level text default null,
  p_highest_edu text default null,
  p_field text default null,
  p_language text default null
)
returns table(
  id uuid, title text, official_url text, deadline date, deadline_notes text,
  host_countries text[], funding_type text, funding_notes text,
  eligibility_notes text, language_requirement text, age_min integer,
  age_max integer, category_slug text, category_label_tr text,
  category_color text, documents json, is_featured boolean,
  days_until_deadline integer, submitted_by_nickname text,
  last_url_check_at timestamptz, last_url_check_status integer,
  summary_tr text, eligibility_notes_tr text,
  details_url text, application_route_status text, application_method text,
  application_url_verified_at timestamptz
)
language sql stable
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
    and (
      (
        opp.application_route_status = 'verified'
        and nullif(btrim(opp.official_url), '') is not null
        and nullif(btrim(opp.application_url_final), '') is not null
        and opp.application_url_verified_at is not null
      )
      or (
        opp.application_route_status = 'guided'
        and nullif(btrim(opp.details_url), '') is not null
      )
    )
    and oc.category_slug is not null
    and (p_host_country is null or p_host_country = any(oc.host_countries))
    and (p_category_slug is null or oc.category_slug = p_category_slug)
    and ('all' = any(oc.eligible_citizenships) or p_citizenship = any(oc.eligible_citizenships))
    and (p_age is null or oc.age_min is null or oc.age_min <= p_age)
    and (p_age is null or oc.age_max is null or oc.age_max >= p_age)
    and (p_study_level is null or p_study_level = 'any'
      or 'any' = any(oc.study_level) or p_study_level = any(oc.study_level))
    and (p_field is null or 'all' = any(oc.target_fields) or p_field = any(oc.target_fields))
    and (p_language is null
      or 'all' = any(opp.required_languages)
      or lower(p_language) = any(opp.required_languages))
    and (oc.deadline is null or oc.deadline >= current_date)
  order by oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;

commit;
