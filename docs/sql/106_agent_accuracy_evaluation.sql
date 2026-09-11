-- ============================================================
-- 106 · Kör insan etiketli agent doğruluk testi
-- Önkoşul: 097 (admins + agent_memories)
-- ============================================================

begin;

create table if not exists public.agent_evaluation_batches (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  target_size integer not null check (target_size between 1 and 50),
  status text not null default 'running'
    check (status in ('running', 'ready', 'completed', 'failed')),
  model text not null,
  prompt_version text not null default 'two-pass-evidence-v1',
  created_at timestamptz not null default now(),
  ready_at timestamptz,
  completed_at timestamptz
);

create table if not exists public.agent_evaluation_cases (
  id uuid primary key default gen_random_uuid(),
  batch_id uuid not null references public.agent_evaluation_batches(id) on delete cascade,
  source_submission_id uuid references public.submissions(id) on delete set null,
  source_nickname text not null default 'manual/unknown',
  category_slug text not null default 'unknown',
  submission_snapshot jsonb not null,
  agent_decision text not null
    check (agent_decision in ('approve', 'reject', 'uncertain', 'retry')),
  agent_outcome text not null,
  agent_reason text not null,
  agent_validation jsonb,
  evaluated_at timestamptz not null default now(),
  human_decision text check (human_decision in ('approve', 'reject')),
  human_reason_code text,
  human_note text,
  labeled_by uuid references auth.users(id),
  labeled_at timestamptz,
  unique (batch_id, source_submission_id)
);

create index if not exists agent_evaluation_cases_batch_idx
  on public.agent_evaluation_cases (batch_id, labeled_at nulls first, evaluated_at);

alter table public.agent_evaluation_batches enable row level security;
alter table public.agent_evaluation_cases enable row level security;

-- Ajanın kararı insan etiketini vermeden gösterilmez. Böylece ölçüm,
-- ajanın kararından etkilenmeyen kör bir insan değerlendirmesidir.
create or replace function public.get_agent_evaluation_queue(p_batch_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_batch public.agent_evaluation_batches%rowtype;
  v_cases jsonb;
  v_total integer;
  v_labeled integer;
  v_auto_decided integer;
  v_comparable integer;
  v_correct integer;
  v_false_approvals integer;
  v_agent_approvals integer;
  v_true_approvals integer;
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  if p_batch_id is null then
    select * into v_batch
    from public.agent_evaluation_batches
    where status in ('ready', 'completed')
    order by created_at desc
    limit 1;
  else
    select * into v_batch
    from public.agent_evaluation_batches
    where id = p_batch_id;
  end if;

  if not found then
    return jsonb_build_object('batch', null, 'cases', '[]'::jsonb, 'summary', null);
  end if;

  select
    count(*)::integer,
    count(*) filter (where human_decision is not null)::integer,
    count(*) filter (where agent_decision in ('approve', 'reject'))::integer,
    count(*) filter (
      where human_decision is not null and agent_decision in ('approve', 'reject')
    )::integer,
    count(*) filter (
      where (agent_decision = 'approve' and human_decision = 'approve')
         or (agent_decision = 'reject' and human_decision = 'reject')
    )::integer,
    count(*) filter (
      where agent_decision = 'approve' and human_decision = 'reject'
    )::integer,
    count(*) filter (
      where agent_decision = 'approve' and human_decision is not null
    )::integer,
    count(*) filter (
      where agent_decision = 'approve' and human_decision = 'approve'
    )::integer
  into v_total, v_labeled, v_auto_decided, v_comparable, v_correct,
       v_false_approvals, v_agent_approvals, v_true_approvals
  from public.agent_evaluation_cases
  where batch_id = v_batch.id;

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'id', c.id,
      'snapshot', c.submission_snapshot,
      'source_nickname', c.source_nickname,
      'category_slug', c.category_slug,
      'human_decision', c.human_decision,
      'human_reason_code', c.human_reason_code,
      'human_note', c.human_note,
      'labeled_at', c.labeled_at,
      'agent_decision', case when c.human_decision is null then null else c.agent_decision end,
      'agent_reason', case when c.human_decision is null then null else c.agent_reason end,
      'agent_outcome', case when c.human_decision is null then null else c.agent_outcome end,
      'is_match', case
        when c.human_decision is null or c.agent_decision not in ('approve', 'reject') then null
        else c.agent_decision = c.human_decision
      end
    )
    order by c.labeled_at nulls first, c.evaluated_at
  ), '[]'::jsonb)
  into v_cases
  from public.agent_evaluation_cases c
  where c.batch_id = v_batch.id;

  return jsonb_build_object(
    'batch', jsonb_build_object(
      'id', v_batch.id,
      'name', v_batch.name,
      'status', v_batch.status,
      'model', v_batch.model,
      'created_at', v_batch.created_at
    ),
    'cases', v_cases,
    'summary', jsonb_build_object(
      'total', v_total,
      'labeled', v_labeled,
      'auto_decided', v_auto_decided,
      'comparable', v_comparable,
      'correct', v_correct,
      'false_approvals', v_false_approvals,
      'coverage_percent', case when v_total = 0 then null
        else round(100.0 * v_auto_decided / v_total, 1) end,
      'accuracy_percent', case when v_comparable = 0 then null
        else round(100.0 * v_correct / v_comparable, 1) end,
      'approval_precision_percent', case when v_agent_approvals = 0 then null
        else round(100.0 * v_true_approvals / v_agent_approvals, 1) end
    )
  );
end;
$$;

create or replace function public.label_agent_evaluation_case(
  p_id uuid,
  p_decision text,
  p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_batch_id uuid;
  v_reason_code text;
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;
  if p_decision not in ('approve', 'reject') then
    raise exception 'Karar approve veya reject olmalıdır';
  end if;

  if p_decision = 'reject' then
    v_reason_code := substring(coalesce(p_note, '')
      from '^\[insan\][[:space:]]+RED:([a-z0-9_]+)');
    if v_reason_code is null then
      raise exception 'Red nedeni seçilmelidir';
    end if;
  end if;

  update public.agent_evaluation_cases
  set human_decision = p_decision,
      human_reason_code = v_reason_code,
      human_note = nullif(btrim(p_note), ''),
      labeled_by = auth.uid(),
      labeled_at = now()
  where id = p_id and human_decision is null
  returning batch_id into v_batch_id;

  if not found then
    raise exception 'Kayıt bulunamadı veya daha önce etiketlendi';
  end if;

  if not exists (
    select 1 from public.agent_evaluation_cases
    where batch_id = v_batch_id and human_decision is null
  ) then
    update public.agent_evaluation_batches
    set status = 'completed', completed_at = now()
    where id = v_batch_id;
  end if;

  return jsonb_build_object('success', true, 'batch_id', v_batch_id);
end;
$$;

-- Testteki insan redleri de normal admin redleri gibi gelecekteki kararlarda
-- kaynak+kategori+neden hafızasına dönüşür. Kayıtlı agent tahmini değişmez;
-- dolayısıyla mevcut test skoru geriye dönük etkilenmez.
create or replace function public.remember_agent_evaluation_rejection()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if old.human_decision is null
     and new.human_decision = 'reject'
     and new.human_reason_code is not null then
    insert into public.agent_memories (
      source_nickname, category_slug, reason_code, summary,
      evidence_count, weight, first_evidence_at, last_evidence_at, updated_at
    ) values (
      new.source_nickname, new.category_slug, new.human_reason_code,
      coalesce(nullif(new.human_note, ''), new.human_reason_code),
      1, 'example', new.labeled_at, new.labeled_at, now()
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

drop trigger if exists trg_remember_agent_evaluation_rejection
  on public.agent_evaluation_cases;
create trigger trg_remember_agent_evaluation_rejection
  after update of human_decision on public.agent_evaluation_cases
  for each row execute function public.remember_agent_evaluation_rejection();

revoke all on function public.get_agent_evaluation_queue(uuid) from public;
revoke all on function public.label_agent_evaluation_case(uuid, text, text) from public;
grant execute on function public.get_agent_evaluation_queue(uuid) to authenticated;
grant execute on function public.label_agent_evaluation_case(uuid, text, text) to authenticated;

commit;
