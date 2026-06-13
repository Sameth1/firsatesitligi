-- ============================================================
-- 095 · submissions.study_level + agent_approve_submission eşlemesi
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- NEDEN:
--   Scraper'lar (youthop/nasilgitmis) artık extract_study_level ile hedef
--   eğitim kademesini çıkarıyor (bachelor/master/phd/any). Ama submissions'ta
--   study_level kolonu YOKTU ve agent_approve_submission opportunities.study_level'a
--   HARDCODED array['any'] yazıyordu → çıkarılan kademe yayına asla yansımıyordu.
--
--   Bu migration: (1) submissions'a study_level text[] ekler, (2) RPC'yi
--   coalesce(sub.study_level, array['any']) ile günceller — submission kademe
--   taşıyorsa onu, yoksa güvenli 'any' default'unu kullanır.
--
-- Önkoşul: 094. Idempotent — tekrar çalıştırılabilir.
-- ============================================================

-- 1) submissions.study_level (nullable; null → onayda 'any')
alter table public.submissions
  add column if not exists study_level text[];

-- 2) RPC'yi yeniden tanımla — yalnız study_level satırı değişti (array['any'] →
--    coalesce(sub.study_level, array['any'])). Geri kalan 094 ile birebir aynı.
create or replace function public.agent_approve_submission(p_id uuid)
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
    array['all']::text[],   -- bilinmiyor → tüm hedef ülkeler
    array['all']::text[],   -- bilinmiyor → tüm vatandaşlıklar
    array['all']::text[],   -- bilinmiyor → tüm bölümler
    coalesce(sub.study_level, array['any']::text[]),   -- 095: submission'dan ya da 'any'
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
    reviewed_by = null
  where id = p_id;

  return json_build_object(
    'success', true,
    'opportunity_id', new_opp_id,
    'approved_by', 'agent'
  );
end;
$$;

revoke all on function public.agent_approve_submission(uuid) from public;
revoke all on function public.agent_approve_submission(uuid) from anon;
revoke all on function public.agent_approve_submission(uuid) from authenticated;
grant execute on function public.agent_approve_submission(uuid) to service_role;
