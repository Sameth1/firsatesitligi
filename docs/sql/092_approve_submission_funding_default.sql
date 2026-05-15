-- ============================================================
-- 092 · approve_submission: funding_type NOT NULL uyumu
-- Topluluk önerilerinde funding_type çoğu zaman NULL; opportunities
-- kolonu NOT NULL ise onay patlar. Bilinmiyor → 'free' (mevcut UI değerleriyle uyumlu).
-- Supabase SQL Editor’da çalıştır; 090 sonrası idempotent.
-- ============================================================

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
    array['all']::text[],
    array['all']::text[],
    array['all']::text[],
    array['any']::text[],
    coalesce(sub.funding_type, 'free'),
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
