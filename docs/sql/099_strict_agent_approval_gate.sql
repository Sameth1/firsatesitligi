-- ============================================================
-- 099 · Agent otomatik onayını fail-closed yap
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- Önkoşul: 095 ve 097
-- ============================================================

alter table public.submissions
  add column if not exists agent_validation jsonb;

drop function if exists public.agent_approve_submission(uuid);
drop function if exists public.agent_approve_submission(uuid, jsonb);

create or replace function public.agent_approve_submission(
  p_id uuid,
  p_validation jsonb
)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare
  sub record;
  new_opp_id uuid;
  v_category_id uuid;
  v_deadline date;
begin
  select * into sub
  from public.submissions
  where id = p_id
  for update;

  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;
  if sub.status <> 'pending' then
    raise exception 'Yalnız pending kayıt otomatik onaylanabilir';
  end if;
  if sub.submission_origin is distinct from 'agent' then
    raise exception 'Yalnız agent kaydı otomatik onaylanabilir';
  end if;

  -- Zorunlu kayıt alanları: hiçbir varsayılanla veri uydurulmaz.
  if char_length(btrim(coalesce(sub.title, ''))) < 8 then
    raise exception 'Otomatik onay engellendi: başlık eksik veya çok kısa';
  end if;
  if coalesce(sub.url, '') !~* '^https?://[^[:space:]]+$' then
    raise exception 'Otomatik onay engellendi: geçerli URL yok';
  end if;
  if nullif(btrim(coalesce(sub.category_slug, '')), '') is null then
    raise exception 'Otomatik onay engellendi: kategori eksik';
  end if;
  if coalesce(cardinality(sub.host_countries), 0) = 0 then
    raise exception 'Otomatik onay engellendi: ülke/global bilgisi eksik';
  end if;
  if sub.funding_type is null
     or sub.funding_type not in ('full', 'partial', 'free', 'stipend') then
    raise exception 'Otomatik onay engellendi: finansman türü eksik/geçersiz';
  end if;
  if char_length(btrim(coalesce(sub.eligibility_notes, ''))) < 20 then
    raise exception 'Otomatik onay engellendi: uygunluk koşulları eksik';
  end if;
  begin
    v_deadline := nullif(btrim(coalesce(sub.deadline_text, '')), '')::date;
  exception when others then
    raise exception 'Otomatik onay engellendi: tam ve işlenebilir son tarih yok';
  end;
  if v_deadline < current_date then
    raise exception 'Otomatik onay engellendi: son tarih geçmiş (%)', v_deadline;
  end if;

  -- Model kararı yalnız açık JSON boolean true ile geçer. Eksik anahtar, null,
  -- string "true" veya orta güven otomatik yayına izin vermez.
  if p_validation is null
     or p_validation->>'durum' is distinct from 'acik'
     or p_validation->>'guven' is distinct from 'yuksek'
     or p_validation->'kategori_uygun' is distinct from 'true'::jsonb
     or p_validation->'tek_firsat' is distinct from 'true'::jsonb
     or p_validation->'dogrudan_firsat_sayfasi' is distinct from 'true'::jsonb
     or p_validation->'son_tarih_dogrulandi' is distinct from 'true'::jsonb
     or p_validation->'finansman_dogrulandi' is distinct from 'true'::jsonb
     or p_validation->'ulke_dogrulandi' is distinct from 'true'::jsonb
     or p_validation->'uygunluk_dogrulandi' is distinct from 'true'::jsonb then
    raise exception 'Otomatik onay engellendi: bütün yayın kanıtları doğrulanmadı';
  end if;

  select id into v_category_id
  from public.categories
  where slug = sub.category_slug
  limit 1;
  if v_category_id is null then
    raise exception 'Otomatik onay engellendi: kategori bulunamadı (%)', sub.category_slug;
  end if;

  new_opp_id := gen_random_uuid();
  insert into public.opportunities (
    id, title, official_url, deadline,
    host_countries, target_countries, eligible_citizenships,
    target_fields, study_level,
    funding_type, funding_notes, eligibility_notes,
    language_requirement, age_min, age_max,
    category_id, is_active, is_featured,
    submitted_by_nickname, submitted_by_submission_id
  ) values (
    new_opp_id, sub.title, sub.url, v_deadline,
    sub.host_countries,
    array['all']::text[], array['all']::text[], array['all']::text[],
    coalesce(sub.study_level, array['any']::text[]),
    sub.funding_type, sub.funding_notes, sub.eligibility_notes,
    sub.language_requirement, sub.age_min, sub.age_max,
    v_category_id, true, false,
    sub.submitter_nickname, p_id
  );

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
    reviewed_by = null,
    review_stage = 'decided',
    agent_validation = p_validation
  where id = p_id;

  return json_build_object(
    'success', true,
    'opportunity_id', new_opp_id,
    'approved_by', 'agent'
  );
end;
$$;

revoke all on function public.agent_approve_submission(uuid, jsonb) from public;
revoke all on function public.agent_approve_submission(uuid, jsonb) from anon;
revoke all on function public.agent_approve_submission(uuid, jsonb) from authenticated;
grant execute on function public.agent_approve_submission(uuid, jsonb) to service_role;

comment on function public.agent_approve_submission(uuid, jsonb) is
  'Fail-closed agent approval: complete record + high-confidence page evidence required.';
