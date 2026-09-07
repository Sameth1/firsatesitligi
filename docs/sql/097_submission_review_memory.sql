-- ============================================================
-- 097 · İnsan/agent inceleme akışı, kalıcı karar geçmişi ve hafıza
-- ============================================================

create extension if not exists pgcrypto;

alter table public.submissions
  add column if not exists submission_origin text not null default 'human',
  add column if not exists review_stage text not null default 'human_review';

do $$ begin
  alter table public.submissions add constraint submissions_origin_check
    check (submission_origin in ('human', 'agent'));
exception when duplicate_object then null;
end $$;

do $$ begin
  alter table public.submissions add constraint submissions_review_stage_check
    check (review_stage in ('human_review', 'agent_queue', 'agent_uncertain',
                            'awaiting_revision', 'decided'));
exception when duplicate_object then null;
end $$;

-- Bilinen tarayıcı kayıtlarını ayır. Yeni kayıtlar scriptlerde açıkça agent gelir.
update public.submissions
set submission_origin = 'agent'
where submitter_nickname in ('nasilgitmis-bot', 'youthop-bot', 'daad-bot', 'agent-reach');

update public.submissions
set review_stage = case
  when status in ('approved', 'rejected') then 'decided'
  when status = 'needs_revision' then 'awaiting_revision'
  when submission_origin = 'agent' and coalesce(admin_note, '') like '[ajan] BELİRSİZ:%'
    then 'agent_uncertain'
  when submission_origin = 'agent' then 'agent_queue'
  else 'human_review'
end;

create index if not exists idx_submissions_review_queue
  on public.submissions (submission_origin, review_stage, status, created_at);

-- Anon kullanıcı kendisini agent gibi gösteremez. Service-role kullanan
-- tarayıcılar RLS'i bypass eder.
drop policy if exists "Anyone can insert submissions" on public.submissions;
create policy "Anyone can insert human submissions"
  on public.submissions for insert
  with check (submission_origin = 'human' and review_stage = 'human_review');

create table if not exists public.submission_review_events (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.submissions(id),
  actor_type text not null check (actor_type in ('human', 'agent', 'submitter', 'system')),
  actor_user_id uuid,
  decision text not null check (decision in (
    'approved', 'rejected', 'revision_requested', 'revised', 'uncertain'
  )),
  reason_code text,
  reason_text text,
  source_nickname text not null default 'manual/unknown',
  category_slug text not null default 'unknown',
  submission_snapshot jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_review_events_submission
  on public.submission_review_events (submission_id, created_at desc);
create index if not exists idx_review_events_learning
  on public.submission_review_events (actor_type, decision, source_nickname,
                                      category_slug, reason_code, created_at desc);

alter table public.submission_review_events enable row level security;
drop policy if exists "Admins can read review events" on public.submission_review_events;
create policy "Admins can read review events"
  on public.submission_review_events for select
  using (exists (select 1 from public.admins where user_id = auth.uid()));

create table if not exists public.agent_memories (
  id uuid primary key default gen_random_uuid(),
  source_nickname text not null default 'manual/unknown',
  category_slug text not null default 'unknown',
  reason_code text not null,
  summary text not null,
  evidence_count integer not null default 1 check (evidence_count > 0),
  weight text not null default 'example' check (weight in ('example', 'warning', 'strong')),
  active boolean not null default true,
  first_evidence_at timestamptz not null default now(),
  last_evidence_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_nickname, category_slug, reason_code)
);

alter table public.agent_memories enable row level security;
drop policy if exists "Admins can read agent memories" on public.agent_memories;
create policy "Admins can read agent memories"
  on public.agent_memories for select
  using (exists (select 1 from public.admins where user_id = auth.uid()));

create or replace function public.sync_submission_review_stage()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.status in ('approved', 'rejected') then
    new.review_stage := 'decided';
  elsif new.status = 'needs_revision' then
    new.review_stage := 'awaiting_revision';
  elsif new.status = 'pending' and new.submission_origin = 'human' then
    new.review_stage := 'human_review';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_sync_submission_review_stage on public.submissions;
create trigger trg_sync_submission_review_stage
  before insert or update of status, submission_origin, review_stage
  on public.submissions for each row execute function public.sync_submission_review_stage();

create or replace function public.remember_human_rejection()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.actor_type = 'human'
     and new.decision = 'rejected'
     and new.reason_code is not null then
    insert into public.agent_memories (
      source_nickname, category_slug, reason_code, summary,
      evidence_count, weight, first_evidence_at, last_evidence_at, updated_at
    ) values (
      new.source_nickname, new.category_slug, new.reason_code,
      coalesce(nullif(new.reason_text, ''), new.reason_code),
      1, 'example', new.created_at, new.created_at, now()
    )
    on conflict (source_nickname, category_slug, reason_code) do update set
      evidence_count = public.agent_memories.evidence_count + 1,
      summary = excluded.summary,
      weight = case
        when public.agent_memories.evidence_count + 1 >= 5 then 'strong'
        when public.agent_memories.evidence_count + 1 >= 3 then 'warning'
        else 'example'
      end,
      active = true,
      last_evidence_at = excluded.last_evidence_at,
      updated_at = now();
  end if;
  return new;
end;
$$;

drop trigger if exists trg_remember_human_rejection on public.submission_review_events;
create trigger trg_remember_human_rejection
  after insert on public.submission_review_events
  for each row execute function public.remember_human_rejection();

create or replace function public.record_submission_review_event()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_decision text;
  v_actor text;
  v_reason_code text;
begin
  if old.status is not distinct from new.status
     and old.review_stage is not distinct from new.review_stage then
    return new;
  end if;

  v_decision := case
    when new.status = 'approved' then 'approved'
    when new.status = 'rejected' then 'rejected'
    when new.status = 'needs_revision' then 'revision_requested'
    when old.status = 'needs_revision' and new.status = 'pending' then 'revised'
    when new.review_stage = 'agent_uncertain' then 'uncertain'
    else null
  end;
  if v_decision is null then return new; end if;

  v_actor := case
    when old.status = 'needs_revision' and new.status = 'pending' then 'submitter'
    when new.reviewed_by is not null then 'human'
    when new.submission_origin = 'agent' then 'agent'
    else 'system'
  end;

  v_reason_code := substring(coalesce(new.admin_note, '')
    from '^\[insan\][[:space:]]+RED:([a-z0-9_]+)');

  insert into public.submission_review_events (
    submission_id, actor_type, actor_user_id, decision, reason_code, reason_text,
    source_nickname, category_slug, submission_snapshot, created_at
  ) values (
    new.id, v_actor, new.reviewed_by, v_decision, v_reason_code,
    nullif(new.admin_note, ''),
    coalesce(nullif(new.submitter_nickname, ''), 'manual/unknown'),
    coalesce(nullif(new.category_slug, ''), 'unknown'),
    to_jsonb(new), coalesce(new.reviewed_at, now())
  );
  return new;
end;
$$;

drop trigger if exists trg_record_submission_review_event on public.submissions;
create trigger trg_record_submission_review_event
  after update of status, review_stage on public.submissions
  for each row execute function public.record_submission_review_event();

-- Eski insan kararlarını bir kez geçmişe al. Uydurma sebep üretilmez.
insert into public.submission_review_events (
  submission_id, actor_type, actor_user_id, decision, reason_code, reason_text,
  source_nickname, category_slug, submission_snapshot, created_at
)
select s.id, 'human', s.reviewed_by,
  case s.status
    when 'approved' then 'approved'
    when 'rejected' then 'rejected'
    when 'needs_revision' then 'revision_requested'
  end,
  substring(coalesce(s.admin_note, '') from '^\[insan\][[:space:]]+RED:([a-z0-9_]+)'),
  nullif(s.admin_note, ''),
  coalesce(nullif(s.submitter_nickname, ''), 'manual/unknown'),
  coalesce(nullif(s.category_slug, ''), 'unknown'),
  to_jsonb(s), coalesce(s.reviewed_at, s.created_at)
from public.submissions s
where s.reviewed_by is not null
  and s.status in ('approved', 'rejected', 'needs_revision')
  and not exists (
    select 1 from public.submission_review_events e
    where e.submission_id = s.id and e.actor_type = 'human'
  );

-- 5+ aynı red veya tam 20 son insan kararında >= %30: script iyileştirme adayı.
create or replace view public.agent_improvement_candidates
with (security_invoker = true) as
with ranked as (
  select e.*,
    row_number() over (
      partition by e.source_nickname, e.category_slug order by e.created_at desc
    ) as rn
  from public.submission_review_events e
  where e.actor_type = 'human' and e.decision in ('approved', 'rejected')
), last_twenty as (
  select * from ranked where rn <= 20
), totals as (
  select source_nickname, category_slug, count(*) as sample_size
  from last_twenty group by source_nickname, category_slug
), rejected as (
  select source_nickname, category_slug, reason_code, count(*) as reject_count
  from last_twenty
  where decision = 'rejected' and reason_code is not null
  group by source_nickname, category_slug, reason_code
)
select r.source_nickname, r.category_slug, r.reason_code,
  r.reject_count, t.sample_size,
  round(r.reject_count::numeric / nullif(t.sample_size, 0), 3) as reject_rate
from rejected r join totals t using (source_nickname, category_slug)
where r.reject_count >= 5
   or (t.sample_size = 20 and r.reject_count::numeric / t.sample_size >= 0.30);

revoke all on public.agent_improvement_candidates from public, anon, authenticated;
grant select on public.agent_improvement_candidates to service_role;

-- Tek kullanımlık, hash'lenmiş revize bağlantıları.
create table if not exists public.submission_revision_tokens (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.submissions(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
alter table public.submission_revision_tokens enable row level security;

create or replace function public.get_revision_submission(p_token text)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare v_sub record;
begin
  select s.* into v_sub
  from public.submission_revision_tokens t
  join public.submissions s on s.id = t.submission_id
  where t.token_hash = encode(digest(p_token, 'sha256'), 'hex')
    and t.used_at is null and t.expires_at > now()
    and s.status = 'needs_revision';
  if not found then raise exception 'Revize bağlantısı geçersiz veya süresi dolmuş'; end if;

  return json_build_object(
    'title', v_sub.title, 'url', v_sub.url,
    'category_slug', v_sub.category_slug,
    'host_countries', v_sub.host_countries,
    'deadline_text', v_sub.deadline_text,
    'funding_type', v_sub.funding_type,
    'eligibility_notes', v_sub.eligibility_notes,
    'language_requirement', v_sub.language_requirement,
    'description', v_sub.description,
    'revision_note', v_sub.admin_note
  );
end;
$$;

create or replace function public.submit_revision(
  p_token text, p_title text, p_url text, p_category_slug text,
  p_host_countries text[], p_deadline_text text, p_funding_type text,
  p_eligibility_notes text, p_language_requirement text, p_description text
)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare v_token public.submission_revision_tokens%rowtype;
begin
  if nullif(btrim(p_title), '') is null then raise exception 'Başlık zorunludur'; end if;
  if p_url !~* '^https?://' then raise exception 'Geçerli bir bağlantı girin'; end if;
  if nullif(btrim(p_category_slug), '') is null then raise exception 'Kategori zorunludur'; end if;

  select * into v_token from public.submission_revision_tokens
  where token_hash = encode(digest(p_token, 'sha256'), 'hex')
    and used_at is null and expires_at > now()
  for update;
  if not found then raise exception 'Revize bağlantısı geçersiz veya süresi dolmuş'; end if;

  update public.submissions set
    title = btrim(p_title), url = btrim(p_url), category_slug = p_category_slug,
    host_countries = coalesce(p_host_countries, '{}'::text[]),
    deadline_text = nullif(btrim(p_deadline_text), ''), funding_type = p_funding_type,
    eligibility_notes = nullif(btrim(p_eligibility_notes), ''),
    language_requirement = nullif(btrim(p_language_requirement), ''),
    description = nullif(btrim(p_description), ''),
    status = 'pending', review_stage = 'human_review', admin_note = null,
    reviewed_at = null, reviewed_by = null
  where id = v_token.submission_id and status = 'needs_revision';
  if not found then raise exception 'Bu öneri artık revize beklemiyor'; end if;

  update public.submission_revision_tokens set used_at = now() where id = v_token.id;
  return json_build_object('success', true);
end;
$$;

revoke all on function public.get_revision_submission(text) from public;
grant execute on function public.get_revision_submission(text) to anon, authenticated;
revoke all on function public.submit_revision(text,text,text,text,text[],text,text,text,text,text) from public;
grant execute on function public.submit_revision(text,text,text,text,text[],text,text,text,text,text) to anon, authenticated;

-- Revize yalnızca e-postası olan insan gönderilerinde kullanılabilir.
create or replace function public.request_revision(p_id uuid, p_note text)
returns json
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;
  if nullif(btrim(p_note), '') is null then raise exception 'Revize notu zorunludur'; end if;

  update public.submissions set
    status = 'needs_revision', admin_note = btrim(p_note),
    reviewed_at = now(), reviewed_by = auth.uid()
  where id = p_id and submission_origin = 'human' and submitter_email is not null;
  if not found then raise exception 'Yalnızca e-postalı kullanıcı gönderisi revize edilebilir'; end if;
  return json_build_object('success', true);
end;
$$;

revoke all on function public.request_revision(uuid, text) from public;
revoke all on function public.request_revision(uuid, text) from anon;
grant execute on function public.request_revision(uuid, text) to authenticated;
