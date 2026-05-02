-- ============================================================
-- 006 Community Sourcing: submissions v2 + admin
-- Supabase Dashboard -> SQL Editor -> run whole file
-- ============================================================
-- Needs: Supabase Auth (Email). After run, insert your user into admins.
-- ============================================================

-- ------------------------------------------------------------
-- 1. submissions table
-- ------------------------------------------------------------

alter table public.submissions add column if not exists created_at timestamptz not null default now();

-- email optional (run 001 first if column missing)
alter table public.submissions
  alter column submitter_email drop not null;

-- nickname: kullanıcı "bu fırsatı ben paylaştım" diyebilsin
alter table public.submissions
  add column if not exists submitter_nickname text;

-- opportunity alanlarıyla hizalama
alter table public.submissions
  add column if not exists host_countries text[] default '{}',
  add column if not exists funding_type text,
  add column if not exists funding_notes text,
  add column if not exists eligibility_notes text,
  add column if not exists language_requirement text,
  add column if not exists age_min integer,
  add column if not exists age_max integer,
  add column if not exists documents jsonb default '[]';

-- state machine
alter table public.submissions
  add column if not exists status text not null default 'pending',
  add column if not exists admin_note text,
  add column if not exists created_opportunity_id uuid,
  add column if not exists reviewed_at timestamptz,
  add column if not exists reviewed_by uuid;

-- spam koruması
alter table public.submissions
  add column if not exists submitter_ip inet;

-- status check constraint
do $$ begin
  alter table public.submissions
    add constraint submissions_status_check
    check (status in ('pending', 'approved', 'needs_revision', 'rejected'));
exception when duplicate_object then null;
end $$;

-- host_country to host_countries backfill if old column exists
do $$ begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'host_country'
  ) then
    update public.submissions
    set host_countries = array[host_country]
    where host_country is not null
      and (host_countries is null or host_countries = '{}');
  end if;
end $$;

-- indexes
create index if not exists idx_submissions_status on public.submissions (status);
create index if not exists idx_submissions_created_at on public.submissions (created_at desc);

-- ------------------------------------------------------------
-- 2. opportunities tablosuna attribution kolonları ekle
-- ------------------------------------------------------------

alter table public.opportunities
  add column if not exists submitted_by_nickname text,
  add column if not exists submitted_by_submission_id uuid;

-- ------------------------------------------------------------
-- 3. admins tablosu
-- ------------------------------------------------------------

create table if not exists public.admins (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  email      text not null,
  created_at timestamptz not null default now()
);

alter table public.admins enable row level security;

create policy "Admins can read own row"
  on public.admins for select
  using (auth.uid() = user_id);

-- ------------------------------------------------------------
-- 4. submissions RLS güncellemesi
-- ------------------------------------------------------------

-- Mevcut policy'leri temizle (idempotent)
drop policy if exists "Anyone can insert submissions" on public.submissions;
drop policy if exists "Admins can read submissions" on public.submissions;
drop policy if exists "Admins can update submissions" on public.submissions;

-- Herkes INSERT yapabilir (anon dahil)
create policy "Anyone can insert submissions"
  on public.submissions for insert
  with check (true);

-- Sadece adminler okuyabilir
create policy "Admins can read submissions"
  on public.submissions for select
  using (exists (select 1 from public.admins where user_id = auth.uid()));

-- Sadece adminler güncelleyebilir
create policy "Admins can update submissions"
  on public.submissions for update
  using (exists (select 1 from public.admins where user_id = auth.uid()));

-- ------------------------------------------------------------
-- 5. approve_submission RPC
-- ------------------------------------------------------------

create or replace function public.approve_submission(p_id uuid)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  sub record;
  new_opp_id uuid;
begin
  -- admin guard
  if not exists (select 1 from admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  select * into sub from submissions where id = p_id;
  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;
  if sub.status = 'approved' then
    raise exception 'Bu öneri zaten onaylanmış';
  end if;

  new_opp_id := gen_random_uuid();

  insert into opportunities (
    id, title, official_url, host_countries,
    funding_type, funding_notes, eligibility_notes,
    language_requirement, age_min, age_max,
    category_slug, is_active, is_featured,
    submitted_by_nickname, submitted_by_submission_id
  ) values (
    new_opp_id,
    sub.title,
    sub.url,
    coalesce(sub.host_countries, '{}'),
    sub.funding_type,
    sub.funding_notes,
    sub.eligibility_notes,
    sub.language_requirement,
    sub.age_min,
    sub.age_max,
    sub.category_slug,
    true,
    false,
    sub.submitter_nickname,
    p_id
  );

  -- deadline: try cast text to date, else store as notes
  if sub.deadline_text is not null then
    begin
      update opportunities
      set deadline = sub.deadline_text::date
      where id = new_opp_id;
    exception when others then
      update opportunities
      set deadline_notes = sub.deadline_text
      where id = new_opp_id;
    end;
  end if;

  -- documents
  if sub.documents is not null and sub.documents != '[]'::jsonb then
    insert into documents (opportunity_id, name, is_required, notes)
    select
      new_opp_id,
      (doc->>'name')::text,
      coalesce((doc->>'is_required')::boolean, false),
      (doc->>'notes')::text
    from jsonb_array_elements(sub.documents) as doc;
  end if;

  -- submission güncelle
  update submissions set
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

-- ------------------------------------------------------------
-- 6. request_revision RPC
-- ------------------------------------------------------------

create or replace function public.request_revision(p_id uuid, p_note text)
returns json
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  update submissions set
    status = 'needs_revision',
    admin_note = p_note,
    reviewed_at = now(),
    reviewed_by = auth.uid()
  where id = p_id;

  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;

  return json_build_object('success', true);
end;
$$;

-- ------------------------------------------------------------
-- 7. reject_submission RPC
-- ------------------------------------------------------------

create or replace function public.reject_submission(p_id uuid, p_note text)
returns json
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  update submissions set
    status = 'rejected',
    admin_note = p_note,
    reviewed_at = now(),
    reviewed_by = auth.uid()
  where id = p_id;

  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;

  return json_build_object('success', true);
end;
$$;

-- ------------------------------------------------------------
-- 8. Basit IP rate-limit trigger (aynı IP 1 dakika içinde max 3)
-- ------------------------------------------------------------

create or replace function public.check_submission_rate_limit()
returns trigger
language plpgsql
as $$
declare
  recent_count integer;
begin
  if new.submitter_ip is not null then
    select count(*) into recent_count
    from submissions
    where submitter_ip = new.submitter_ip
      and created_at > now() - interval '1 minute';

    if recent_count >= 3 then
      raise exception 'Çok fazla öneri gönderildi, lütfen biraz bekleyin';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_submission_rate_limit on public.submissions;
create trigger trg_submission_rate_limit
  before insert on public.submissions
  for each row execute function check_submission_rate_limit();

-- ------------------------------------------------------------
-- 9. Admin pending count helper
-- ------------------------------------------------------------

create or replace function public.get_submission_stats()
returns json
language sql
stable
security definer
set search_path = public
as $$
  select json_build_object(
    'pending_count', (select count(*) from submissions where status = 'pending'),
    'approved_this_week', (
      select count(*) from submissions
      where status = 'approved'
        and reviewed_at >= date_trunc('week', now())
    ),
    'total', (select count(*) from submissions)
  )
$$;
