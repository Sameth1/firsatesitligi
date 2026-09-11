-- ============================================================
-- 114 · Bilgi sayfası ile doğrulanmış başvuru adımını ayır
-- ============================================================
-- Mevcut kayıtlar yayında kalır fakat "unverified" olur; UI bunları
-- "Koşulları Gör" diye gösterir. Yeni bir submission yalnız doğrulanmış
-- form/portal/e-posta/belge taşıyorsa opportunities'e geçirilebilir.

begin;

alter table public.submissions
  add column if not exists details_url text,
  add column if not exists application_route_status text not null default 'unverified',
  add column if not exists application_method text,
  add column if not exists application_url_verified_at timestamptz,
  add column if not exists application_url_check_status integer,
  add column if not exists application_url_final text,
  add column if not exists application_url_evidence text;

alter table public.opportunities
  add column if not exists details_url text,
  add column if not exists source_url text,
  add column if not exists application_route_status text not null default 'unverified',
  add column if not exists application_method text,
  add column if not exists application_url_verified_at timestamptz,
  add column if not exists application_url_check_status integer,
  add column if not exists application_url_final text,
  add column if not exists application_url_evidence text;

update public.opportunities
set details_url = official_url
where details_url is null;

update public.submissions
set details_url = coalesce(details_url, source_url, url)
where details_url is null;

do $constraints$
begin
  if not exists (select 1 from pg_constraint where conname = 'submissions_application_route_status_check') then
    alter table public.submissions add constraint submissions_application_route_status_check
      check (application_route_status in ('verified', 'unverified', 'missing'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'submissions_application_method_check') then
    alter table public.submissions add constraint submissions_application_method_check
      check (application_method is null or application_method in ('online_form', 'portal', 'email', 'document'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'submissions_verified_route_complete_check') then
    alter table public.submissions add constraint submissions_verified_route_complete_check
      check (application_route_status <> 'verified' or (
        application_method is not null
        and application_url_verified_at is not null
        and nullif(btrim(application_url_final), '') is not null
        and nullif(btrim(url), '') is not null
      ));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'opportunities_application_route_status_check') then
    alter table public.opportunities add constraint opportunities_application_route_status_check
      check (application_route_status in ('verified', 'unverified', 'missing'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'opportunities_application_method_check') then
    alter table public.opportunities add constraint opportunities_application_method_check
      check (application_method is null or application_method in ('online_form', 'portal', 'email', 'document'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'opportunities_verified_route_complete_check') then
    alter table public.opportunities add constraint opportunities_verified_route_complete_check
      check (application_route_status <> 'verified' or (
        application_method is not null
        and application_url_verified_at is not null
        and nullif(btrim(application_url_final), '') is not null
        and nullif(btrim(official_url), '') is not null
      ));
  end if;
end
$constraints$;

comment on column public.opportunities.official_url is
  'Birincil aksiyon URL''i. Yalnız application_route_status=verified ise gerçek başvuru adımıdır.';
comment on column public.opportunities.details_url is
  'Koşullar, tarih ve uygunluk bilgilerinin bulunduğu resmî fırsat sayfası.';
comment on column public.opportunities.source_url is
  'Scraper''ın keşif/kanıt kaynağı; bir derleme sitesi olabilir.';

-- Onay RPC'lerinin hangisi çağrılırsa çağrılsın rota tek noktada kopyalanır ve
-- doğrulanmamış submission'ın yayına girmesi engellenir.
create or replace function public.copy_verified_application_route()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  route record;
begin
  if new.submitted_by_submission_id is null then
    if coalesce(new.is_active, true)
       and new.application_route_status is distinct from 'verified' then
      raise exception 'Yeni aktif fırsat engellendi: doğrulanmış doğrudan başvuru adımı yok';
    end if;
    return new;
  end if;

  select details_url, source_url, application_route_status, application_method,
         application_url_verified_at, application_url_check_status,
         application_url_final, application_url_evidence, url
  into route
  from public.submissions
  where id = new.submitted_by_submission_id;

  if not found or route.application_route_status is distinct from 'verified'
     or route.application_method is null
     or route.application_url_verified_at is null
     or nullif(btrim(coalesce(route.application_url_final, '')), '') is null then
    raise exception 'Onay engellendi: doğrulanmış doğrudan başvuru adımı yok';
  end if;

  new.official_url := route.url;
  new.details_url := coalesce(route.details_url, route.url);
  new.source_url := route.source_url;
  new.application_route_status := route.application_route_status;
  new.application_method := route.application_method;
  new.application_url_verified_at := route.application_url_verified_at;
  new.application_url_check_status := route.application_url_check_status;
  new.application_url_final := route.application_url_final;
  new.application_url_evidence := route.application_url_evidence;
  return new;
end;
$function$;

drop trigger if exists trg_copy_verified_application_route on public.opportunities;
create trigger trg_copy_verified_application_route
before insert on public.opportunities
for each row execute function public.copy_verified_application_route();

-- Kart sorgusu: 101 ile aynı filtreler + rota alanları.
drop function if exists public.match_opportunities(text, text, text, integer, text, text);
drop function if exists public.match_opportunities(text, text, text, integer, text, text, text);
drop function if exists public.match_opportunities(text, text, text, integer, text, text, text, text);

create function public.match_opportunities(
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
  left join public.opportunities opp on opp.id = oc.id
  where coalesce(opp.is_active, true) = true
    and (p_host_country is null or '*' = any(oc.host_countries) or p_host_country = any(oc.host_countries))
    and (p_category_slug is null or oc.category_slug = p_category_slug)
    and ('all' = any(oc.eligible_citizenships) or p_citizenship = any(oc.eligible_citizenships))
    and (p_age is null or oc.age_min is null or oc.age_min <= p_age)
    and (p_age is null or oc.age_max is null or oc.age_max >= p_age)
    and (p_study_level is null or 'any' = any(oc.study_level) or p_study_level = any(oc.study_level))
    and (p_field is null or 'all' = any(oc.target_fields) or p_field = any(oc.target_fields))
    and (p_language is null or oc.language_requirement is null
      or oc.language_requirement ilike '%' || p_language || '%'
      or oc.language_requirement ilike '%İngilizce%'
      or oc.language_requirement ilike '%hedef dil%'
      or oc.language_requirement ilike '%ev sahibi%')
    and (oc.deadline is null or oc.deadline >= current_date)
  order by oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;

grant execute on function public.match_opportunities(
  text, text, text, integer, text, text, text, text
) to anon, authenticated, service_role;

commit;
