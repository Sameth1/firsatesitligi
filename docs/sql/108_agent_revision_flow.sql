-- ============================================================
-- 108 · İnsan gönderisini admin → agent → admin revize akışına al
-- Önkoşul: 097
-- ============================================================

begin;

alter table public.submissions
  drop constraint if exists submissions_review_stage_check;

alter table public.submissions
  add constraint submissions_review_stage_check
  check (review_stage in (
    'human_review', 'agent_queue', 'agent_revision', 'agent_uncertain',
    'awaiting_revision', 'decided'
  ));

-- Pending insan kaydında agent_revision aşamasını ezme. Önceki trigger her
-- pending insan kaydını koşulsuz human_review'e çeviriyordu.
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
  elsif new.status = 'pending' and new.submission_origin = 'human'
        and new.review_stage not in ('human_review', 'agent_revision') then
    new.review_stage := 'human_review';
  end if;
  return new;
end;
$$;

-- Admin revize istediğinde kullanıcıya e-posta göndermek yerine kaydı agent
-- kuyruğuna al. Final onay/red yine insandadır.
create or replace function public.request_revision(p_id uuid, p_note text)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  v_note text := btrim(coalesce(p_note, ''));
begin
  if not exists (select 1 from public.admins where user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;
  if v_note = '' then
    raise exception 'Agent revize notu zorunludur';
  end if;

  update public.submissions set
    status = 'pending',
    review_stage = 'agent_revision',
    admin_note = '[insan] REVİZE İSTENDİ: ' || v_note,
    reviewed_at = now(),
    reviewed_by = auth.uid()
  where id = p_id
    and submission_origin = 'human'
    and status = 'pending'
    and review_stage = 'human_review';

  if not found then
    raise exception 'Yalnız insan incelemesindeki kullanıcı kaydı agenta gönderilebilir';
  end if;
  return json_build_object('success', true, 'review_stage', 'agent_revision');
end;
$$;

revoke all on function public.request_revision(uuid, text) from public, anon;
grant execute on function public.request_revision(uuid, text) to authenticated;

-- İki yönü de kalıcı karar geçmişine yaz: insanın revize isteği ve agentın
-- kaydı yeniden insan incelemesine teslim etmesi.
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
    when new.review_stage = 'agent_revision'
         and old.review_stage is distinct from 'agent_revision'
      then 'revision_requested'
    when old.review_stage = 'agent_revision'
         and new.review_stage = 'human_review'
      then 'revised'
    when new.status = 'needs_revision' then 'revision_requested'
    when old.status = 'needs_revision' and new.status = 'pending' then 'revised'
    when new.review_stage = 'agent_uncertain' then 'uncertain'
    else null
  end;
  if v_decision is null then return new; end if;

  v_actor := case
    when old.review_stage = 'agent_revision'
         and new.review_stage = 'human_review' then 'agent'
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

commit;
