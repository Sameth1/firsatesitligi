-- ============================================================
-- 120 · Agent otomatik onayında kesin filtre kanıtı
-- Önkoşul: 105, 110
-- ============================================================
-- Yaş, eğitim, uyruk, dil ve bölüm scraper/LLM tahminiyle yayınlanamaz.
-- İki bağımsız denetim aynı kanonik değerleri ve birebir sayfa
-- alıntılarını vermeli; submission kolonları da bu değerlerle aynı olmalı.

begin;

alter table public.submissions
  add column if not exists required_languages text[];
alter table public.opportunities
  add column if not exists required_languages text[];

comment on column public.opportunities.required_languages is
  'Kanıtlanmış ISO 639-1 dil kodları; {all}=dil şartı yok, NULL=bilinmiyor.';

create or replace function public.copy_verified_submission_languages()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.submitted_by_submission_id is not null then
    select s.required_languages into new.required_languages
    from public.submissions s
    where s.id = new.submitted_by_submission_id;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_copy_verified_submission_languages
  on public.opportunities;
create trigger trg_copy_verified_submission_languages
  before insert on public.opportunities
  for each row execute function public.copy_verified_submission_languages();

create or replace function public.enforce_agent_two_pass_evidence()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_key text;
  v_second jsonb;
  v_filters jsonb;
  v_second_filters jsonb;
begin
  if new.status = 'approved'
     and old.status = 'pending'
     and new.submission_origin = 'agent'
     and new.reviewed_by is null then
    if new.agent_validation is null then
      raise exception 'Agent onayı engellendi: validation nesnesi yok';
    end if;

    v_second := new.agent_validation->'second_pass';
    if jsonb_typeof(v_second) is distinct from 'object'
       or v_second->>'durum' is distinct from 'acik'
       or v_second->>'guven' is distinct from 'yuksek'
       or v_second->'kategori_uygun' is distinct from 'true'::jsonb
       or v_second->'tek_firsat' is distinct from 'true'::jsonb
       or v_second->'dogrudan_firsat_sayfasi' is distinct from 'true'::jsonb
       or v_second->'son_tarih_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'finansman_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'ulke_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'uygunluk_dogrulandi' is distinct from 'true'::jsonb then
      raise exception 'Agent onayı engellendi: ikinci denetim olumlu değil';
    end if;

    foreach v_key in array array[
      'uyruk_dogrulandi', 'yas_dogrulandi', 'egitim_dogrulandi',
      'dil_dogrulandi', 'bolum_dogrulandi'
    ] loop
      if new.agent_validation->v_key is distinct from 'true'::jsonb
         or v_second->v_key is distinct from 'true'::jsonb then
        raise exception 'Agent onayı engellendi: % iki turda doğrulanmadı', v_key;
      end if;
    end loop;

    v_filters := new.agent_validation->'dogrulanmis_filtreler';
    v_second_filters := v_second->'dogrulanmis_filtreler';
    if jsonb_typeof(v_filters) is distinct from 'object'
       or jsonb_typeof(v_second_filters) is distinct from 'object'
       or v_filters is distinct from v_second_filters then
      raise exception 'Agent onayı engellendi: iki tur filtre değerlerinde uzlaşmadı';
    end if;

    foreach v_key in array array[
      'host_countries', 'eligible_citizenships', 'age_min', 'age_max',
      'study_level', 'language_requirement', 'required_languages', 'target_fields'
    ] loop
      if not (v_filters ? v_key) then
        raise exception 'Agent onayı engellendi: % filtre değeri yok', v_key;
      end if;
    end loop;

    if to_jsonb(new.host_countries) is distinct from v_filters->'host_countries'
       or to_jsonb(new.eligible_citizenships) is distinct from v_filters->'eligible_citizenships'
       or coalesce(to_jsonb(new.age_min), 'null'::jsonb) is distinct from v_filters->'age_min'
       or coalesce(to_jsonb(new.age_max), 'null'::jsonb) is distinct from v_filters->'age_max'
       or to_jsonb(new.study_level) is distinct from v_filters->'study_level'
       or coalesce(to_jsonb(new.language_requirement), 'null'::jsonb) is distinct from v_filters->'language_requirement'
       or to_jsonb(new.required_languages) is distinct from v_filters->'required_languages'
       or to_jsonb(new.target_fields) is distinct from v_filters->'target_fields' then
      raise exception 'Agent onayı engellendi: kayıtlı filtreler kanıtlanan değerlerle aynı değil';
    end if;

    foreach v_key in array array[
      'guncellik', 'son_tarih', 'kategori', 'finansman', 'ulke', 'uygunluk',
      'uyruk', 'yas', 'egitim', 'dil', 'bolum'
    ] loop
      if char_length(btrim(coalesce(
           new.agent_validation->'kanitlar'->>v_key, ''))) < 5 then
        raise exception 'Agent onayı engellendi: ilk tur % kanıtı yok', v_key;
      end if;
      if char_length(btrim(coalesce(
           v_second->'kanitlar'->>v_key, ''))) < 5 then
        raise exception 'Agent onayı engellendi: ikinci tur % kanıtı yok', v_key;
      end if;
    end loop;
  end if;
  return new;
end;
$$;

comment on function public.enforce_agent_two_pass_evidence() is
  'Agent auto-approval requires two matching, evidence-backed filter reviews.';

-- Serbest metin dil karşılaştırması kaldırılır. Kullanıcı bir dil
-- seçtiğinde yalnız kanıtlanmış o dil veya açıkça dil şartsız kayıt döner;
-- NULL (bilinmiyor) kayıtlar dil filtreli aramaya sızmaz.
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
