-- ============================================================
-- 115 · Yapılandırılmış ve Ölçülebilir İnsan Önerisi Girişleri
-- ============================================================
-- Kullanıcının öneri formundan girdiği yaş (age_min, age_max),
-- öğrenim seviyesi (study_level) ve uygun vatandaşlıklar (eligible_citizenships)
-- alanlarını submissions tablosuna yapılandırılmış olarak yazar.

create or replace function public.submit_human_opportunity(
  p_ip      inet,
  p_payload jsonb
)
returns json
language plpgsql
security definer
set search_path to 'public'
as $
declare
  v_dakika integer;
  v_gun    integer;
  v_id     uuid;
  v_url    text := btrim(coalesce(p_payload->>'url', ''));
  v_title  text := btrim(coalesce(p_payload->>'title', ''));
begin
  if p_ip is null then
    raise exception 'IP belirlenemedi' using errcode = 'check_violation';
  end if;
  if v_title = '' or v_url = '' then
    raise exception 'Başlık ve bağlantı zorunlu' using errcode = 'check_violation';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(host(p_ip), 0));

  select
    count(*) filter (where created_at > now() - interval '1 minute'),
    count(*) filter (where created_at > now() - interval '1 day')
  into v_dakika, v_gun
  from public.submissions
  where submitter_ip = p_ip;

  if v_dakika >= 3 then
    raise exception 'Çok hızlı gönderiyorsun, bir dakika bekle'
      using errcode = '53400';
  end if;
  if v_gun >= 20 then
    raise exception 'Bugünlük gönderim sınırına ulaştın'
      using errcode = '53400';
  end if;

  insert into public.submissions (
    title, url, category_slug, submitter_nickname, submitter_email,
    host_countries, deadline_text, funding_type,
    age_min, age_max, study_level, eligible_citizenships,
    eligibility_notes, language_requirement, description, submitter_ip,
    submission_origin, review_stage
  ) values (
    v_title,
    v_url,
    nullif(btrim(coalesce(p_payload->>'category_slug', '')), ''),
    nullif(btrim(coalesce(p_payload->>'submitter_nickname', '')), ''),
    nullif(btrim(coalesce(p_payload->>'submitter_email', '')), ''),
    coalesce(
      (select array_agg(upper(btrim(x)))
         from jsonb_array_elements_text(
           case when jsonb_typeof(p_payload->'host_countries') = 'array'
                then p_payload->'host_countries' else '[]'::jsonb end) as t(x)
         where btrim(x) <> ''),
      '{}'::text[]),
    nullif(btrim(coalesce(p_payload->>'deadline_text', '')), ''),
    nullif(btrim(coalesce(p_payload->>'funding_type', '')), ''),
    case when p_payload->>'age_min' ~ '^[0-9]+$' then (p_payload->>'age_min')::integer else null end,
    case when p_payload->>'age_max' ~ '^[0-9]+$' then (p_payload->>'age_max')::integer else null end,
    case when jsonb_typeof(p_payload->'study_level') = 'array'
         then (select array_agg(lower(btrim(x)))
                 from jsonb_array_elements_text(p_payload->'study_level') as t(x)
                 where btrim(x) <> '')
         else null end,
    case when jsonb_typeof(p_payload->'eligible_citizenships') = 'array'
         then (select array_agg(upper(btrim(x)))
                 from jsonb_array_elements_text(p_payload->'eligible_citizenships') as t(x)
                 where btrim(x) <> '')
         else null end,
    nullif(btrim(coalesce(p_payload->>'eligibility_notes', '')), ''),
    nullif(btrim(coalesce(p_payload->>'language_requirement', '')), ''),
    nullif(btrim(coalesce(p_payload->>'description', '')), ''),
    p_ip,
    'human',
    'human_review'
  )
  returning id into v_id;

  return json_build_object('success', true, 'id', v_id);
end;
$;

revoke all on function public.submit_human_opportunity(inet, jsonb)
  from public, anon, authenticated;
grant execute on function public.submit_human_opportunity(inet, jsonb)
  to service_role;
