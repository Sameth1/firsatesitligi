-- ============================================================
-- 090 · TEK DOSYA — 006 sonrası tüm “gap” düzeltmeleri
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- İçerik: (A) resmi URL denetim kolonları + admin RPC’ler (007 ile aynı)
--         (B) match_opportunities: p_highest_edu + submitted_by_nickname
--             + son HTTP kontrol bilgisi (kart uyarısı için)
--         (C) last_verified_at + manuel doğrulama RPC (admin "doğruladım" butonu)
--         (D) approve_submission düzeltmesi: category_id lookup +
--             eksik NOT NULL kolonlarına güvenli default'lar
--         (E) get_admin_stats(): submission + abone (subscribers) sayıları
-- Önkoşul: 001–006 (özellikle opportunities + admins + submitted_by kolonları)
-- ============================================================

-- ─── A) URL sağlığı (007 ile özdeş, idempotent) ─────────────────

alter table public.opportunities
  add column if not exists last_url_check_at timestamptz,
  add column if not exists last_url_check_status integer,
  add column if not exists last_url_check_error text,
  add column if not exists last_url_check_final_url text;

alter table public.opportunities
  add column if not exists last_verified_at timestamptz;

create index if not exists idx_opportunities_last_url_check_at
  on public.opportunities (last_url_check_at asc nulls first);

create or replace function public.pick_opportunities_for_url_check(p_limit integer default 5)
returns table (id uuid, official_url text)
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from public.admins a where a.user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  if p_limit is null or p_limit < 1 then
    p_limit := 5;
  elsif p_limit > 20 then
    p_limit := 20;
  end if;

  return query
  select o.id, o.official_url
  from public.opportunities o
  where coalesce(trim(o.official_url), '') <> ''
  order by o.last_url_check_at asc nulls first, o.title asc
  limit p_limit;
end;
$$;

create or replace function public.record_opportunity_url_check(
  p_id uuid,
  p_http_status integer,
  p_error text,
  p_final_url text
)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  if not exists (select 1 from public.admins a where a.user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  update public.opportunities
  set
    last_url_check_at = now(),
    last_url_check_status = p_http_status,
    last_url_check_error = nullif(trim(p_error), ''),
    last_url_check_final_url = nullif(trim(p_final_url), '')
  where public.opportunities.id = p_id;

  get diagnostics n = row_count;
  if n = 0 then
    raise exception 'Fırsat bulunamadı: %', p_id;
  end if;

  return json_build_object('success', true);
end;
$$;

drop function if exists public.get_opportunity_link_audit();

create or replace function public.get_opportunity_link_audit()
returns table (
  id uuid,
  title text,
  official_url text,
  is_active boolean,
  deadline date,
  last_url_check_at timestamptz,
  last_url_check_status integer,
  last_url_check_error text,
  last_url_check_final_url text,
  last_verified_at timestamptz
)
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from public.admins a where a.user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  return query
  select
    o.id,
    o.title,
    o.official_url,
    o.is_active,
    o.deadline,
    o.last_url_check_at,
    o.last_url_check_status,
    o.last_url_check_error,
    o.last_url_check_final_url,
    o.last_verified_at
  from public.opportunities o
  order by o.last_url_check_at asc nulls first, o.title asc;
end;
$$;

grant execute on function public.pick_opportunities_for_url_check(integer) to authenticated;
grant execute on function public.record_opportunity_url_check(uuid, integer, text, text) to authenticated;
grant execute on function public.get_opportunity_link_audit() to authenticated;

-- ─── B) match_opportunities — frontend + attribution + link özeti ─
-- Eski imzalar (PostgREST çakışmasın diye) kaldırılır:

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

-- p_highest_edu: şema genişleyene kadar WHERE'de kullanılmaz (imza uyumu).

grant execute on function public.match_opportunities(
  text, text, text, integer, text, text, text, text
) to anon, authenticated, service_role;

-- ─── C) Manuel doğrulama RPC (admin "doğruladım" butonu) ────────

create or replace function public.mark_opportunity_verified(p_id uuid)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  if not exists (select 1 from public.admins a where a.user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  update public.opportunities
  set last_verified_at = now()
  where public.opportunities.id = p_id;

  get diagnostics n = row_count;
  if n = 0 then
    raise exception 'Fırsat bulunamadı: %', p_id;
  end if;

  return json_build_object('success', true, 'verified_at', now());
end;
$$;

grant execute on function public.mark_opportunity_verified(uuid) to authenticated;

-- ─── D) approve_submission düzeltmesi ──────────────────────────
-- Eski sürüm `opportunities` tablosuna `category_slug` yazmaya çalışıyordu —
-- o kolon tabloda YOK (`category_id` var). Ayrıca NOT NULL `target_countries`,
-- `eligible_citizenships`, `target_fields`, `study_level` kolonları boş geçiliyordu.
-- Bu sürüm: slug → id lookup yapar ve eksik dizilere güvenli default'lar verir.
-- Idempotent: önce var olan tüm imzayı düşürür, sonra yenisini yaratır.

drop function if exists public.approve_submission(uuid);

create or replace function public.approve_submission(p_id uuid)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  sub record;
  new_opp_id uuid;
  v_category_id uuid;
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  select * into sub from public.submissions where id = p_id;
  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;
  if sub.status = 'approved' then
    raise exception 'Bu öneri zaten onaylanmış';
  end if;

  -- category_slug → category_id lookup (kategori yoksa NULL kalır,
  -- opportunities.category_id NOT NULL ise admin önce kategoriyi düzeltmeli).
  if sub.category_slug is not null then
    select id into v_category_id
    from public.categories
    where slug = sub.category_slug
    limit 1;

    if v_category_id is null then
      raise exception 'Kategori bulunamadı: % (önce kategoriyi düzeltin veya null bırakın)', sub.category_slug;
    end if;
  end if;

  new_opp_id := gen_random_uuid();

  insert into public.opportunities (
    id, title, official_url,
    host_countries, target_countries, eligible_citizenships,
    target_fields, study_level,
    funding_type, funding_notes, eligibility_notes,
    language_requirement, age_min, age_max,
    category_id, is_active, is_featured,
    submitted_by_nickname, submitted_by_submission_id
  ) values (
    new_opp_id,
    sub.title,
    sub.url,
    coalesce(sub.host_countries, '{}'::text[]),
    array['all']::text[],   -- bilinmiyor → tüm hedef ülkeler
    array['all']::text[],   -- bilinmiyor → tüm vatandaşlıklar
    array['all']::text[],   -- bilinmiyor → tüm bölümler
    array['any']::text[],   -- bilinmiyor → tüm eğitim kademeleri
    sub.funding_type,
    sub.funding_notes,
    sub.eligibility_notes,
    sub.language_requirement,
    sub.age_min,
    sub.age_max,
    v_category_id,
    true,
    false,
    sub.submitter_nickname,
    p_id
  );

  if sub.deadline_text is not null then
    begin
      update public.opportunities
      set deadline = sub.deadline_text::date
      where id = new_opp_id;
    exception when others then
      update public.opportunities
      set deadline_notes = sub.deadline_text
      where id = new_opp_id;
    end;
  end if;

  if sub.documents is not null and sub.documents <> '[]'::jsonb then
    insert into public.documents (opportunity_id, name, is_required, notes)
    select
      new_opp_id,
      (doc->>'name')::text,
      coalesce((doc->>'is_required')::boolean, false),
      (doc->>'notes')::text
    from jsonb_array_elements(sub.documents) as doc;
  end if;

  update public.submissions set
    status = 'approved',
    created_opportunity_id = new_opp_id,
    reviewed_at = now(),
    reviewed_by = auth.uid()
  where id = p_id;

  return json_build_object(
    'success', true,
    'opportunity_id', new_opp_id
  );
end;
$$;

grant execute on function public.approve_submission(uuid) to authenticated;

-- ─── E) Genişletilmiş admin istatistikleri ─────────────────────
-- get_submission_stats'in üstüne ek olarak: abone sayısı + onaylanmış
-- toplam fırsat sayısı + manuel/HTTP doğrulanmamış kaynak sayısı.
-- Frontend admin paneli bu RPC'yi çağırıp tek seferde tüm sayıları alır.

create or replace function public.get_admin_stats()
returns json
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_subscribers_count integer := 0;
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  -- subscribers tablosu opsiyonel; yoksa 0 dön
  begin
    select count(*) into v_subscribers_count from public.subscribers;
  exception when undefined_table then
    v_subscribers_count := 0;
  end;

  return json_build_object(
    'pending_count',        (select count(*) from public.submissions where status = 'pending'),
    'approved_this_week',   (select count(*) from public.submissions
                              where status = 'approved'
                                and reviewed_at >= date_trunc('week', now())),
    'submissions_total',    (select count(*) from public.submissions),
    'opportunities_total',  (select count(*) from public.opportunities where is_active is true),
    'subscribers_total',    v_subscribers_count,
    'never_url_checked',    (select count(*) from public.opportunities
                              where last_url_check_at is null),
    'never_verified',       (select count(*) from public.opportunities
                              where last_verified_at is null)
  );
end;
$$;

grant execute on function public.get_admin_stats() to authenticated;
