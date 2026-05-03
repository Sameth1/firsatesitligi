-- ============================================================
-- 007 · Resmi bağlantı sağlığı (HTTP kontrolü + audit kolonları)
-- Supabase Dashboard → SQL Editor → çalıştır
-- Not: 006 sonrası tek seferde her şeyi almak için 090_one_shot_after_006.sql
--      tercih edilebilir (007 + match düzeltmesi bir arada).
-- ============================================================
-- Admin paneli: /admin/link-audit + POST /api/admin/check-opportunity-links
-- Önce 006 (admins tablosu) çalışmış olmalı.
-- ============================================================

alter table public.opportunities
  add column if not exists last_url_check_at timestamptz,
  add column if not exists last_url_check_status integer,
  add column if not exists last_url_check_error text,
  add column if not exists last_url_check_final_url text;

create index if not exists idx_opportunities_last_url_check_at
  on public.opportunities (last_url_check_at asc nulls first);

-- Sırada kontrol edilecek kayıtlar (en eski / hiç kontrol edilmemiş önce)
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

-- Sunucu kontrol sonucunu yazar (admin)
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

-- Tüm fırsatlar + son kontrol (admin tablosu)
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
  last_url_check_final_url text
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
    o.last_url_check_final_url
  from public.opportunities o
  order by o.last_url_check_at asc nulls first, o.title asc;
end;
$$;

grant execute on function public.pick_opportunities_for_url_check(integer) to authenticated;
grant execute on function public.record_opportunity_url_check(uuid, integer, text, text) to authenticated;
grant execute on function public.get_opportunity_link_audit() to authenticated;
