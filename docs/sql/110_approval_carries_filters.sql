-- ============================================================
-- 110 · Onay RPC'leri filtre alanlarını SABİT yazmayı bıraksın
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- SORUN (109'daki veri bozukluğunun KAYNAĞI):
--   approve_submission ve agent_approve_submission, opportunities'e INSERT
--   ederken üç filtre kolonunu submission'dan okumak yerine sabit yazıyordu:
--
--     target_countries       array['all']
--     eligible_citizenships  array['all']   ← "Ürdün'e özel kayıt TR aramasında
--     target_fields          array['all']       çıkıyor" şikâyetinin kaynağı
--
--   Yani bu kolonları doğru doldurmanın hiçbir yolu yoktu: kayıt tanımı gereği
--   "herkese açık" doğuyordu. Ölçüm (aktif 141 kayıt): uyruk 127 × {all},
--   bölüm 134 × {all}. Kullanıcının uyruk ve bölüm filtreleri fiilen çalışmıyordu.
--
--   Ayrıca canlıdaki approve_submission 095 ÖNCESİ sürümde kalmış: study_level'ı
--   submission'dan almıyor, array['any'] yazıyordu. (099 ile gelen
--   agent_approve_submission alıyordu; yani elle onaylanan kayıtlarda eğitim
--   kademesi kayboluyordu.) Bu da burada düzeltiliyor.
--
-- NE YAPIYOR:
--   1) submissions'a iki NULLABLE kolon: eligible_citizenships, target_fields.
--      NULL/boş = "bilinmiyor" ve eskisi gibi {all}/{any}'ye düşer — yani bu
--      migration tek başına hiçbir mevcut davranışı bozmaz, yalnızca doğru
--      değeri TAŞIYABİLİR hâle getirir.
--   2) İki onay RPC'si de bu alanları submission'dan okur.
--
-- Fonksiyon gövdeleri CANLIDAN alınmıştır (pg_get_functiondef); aşağıda
-- yalnızca yukarıda sayılan satırlar değişti, başka hiçbir mantık değişmedi.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet — 092/099 yeniden çalıştırılırsa.
-- ============================================================

begin;

-- ─── 1) submission'lar artık uyruk/bölüm taşıyabiliyor ──────────

alter table public.submissions
  add column if not exists eligible_citizenships text[],
  add column if not exists target_fields text[];

comment on column public.submissions.eligible_citizenships is
  'Bu fırsata başvurabilen uyruklar (ISO 3166-1 alfa-2). NULL/boş = uyruk şartı '
  'bilinmiyor → onayda {all} yazılır. Ajan yalnız sayfada AÇIK yazan kısıtı doldurur.';

comment on column public.submissions.target_fields is
  'Hedef bölüm/alan listesi. NULL/boş = bilinmiyor → onayda {all} yazılır.';

-- ─── 2) approve_submission (elle onay) ──────────────────────────

create or replace function public.approve_submission(p_id uuid)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
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
    array['all']::text[],                                             -- hedef ülke: submission'da alan yok
    coalesce(nullif(sub.eligible_citizenships, '{}'), array['all']),   -- 110
    coalesce(nullif(sub.target_fields, '{}'), array['all']),           -- 110
    coalesce(nullif(sub.study_level, '{}'), array['any']),             -- 110 (095'in niyeti)
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
$function$;

-- ─── 3) agent_approve_submission (otomatik onay) ────────────────
-- 099'daki bütün yayın kapıları AYNEN duruyor; yalnız INSERT'teki üç satır
-- değişti.

create or replace function public.agent_approve_submission(p_id uuid, p_validation jsonb)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
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
    array['all']::text[],                                             -- hedef ülke: alan yok
    coalesce(nullif(sub.eligible_citizenships, '{}'), array['all']),   -- 110
    coalesce(nullif(sub.target_fields, '{}'), array['all']),           -- 110
    coalesce(nullif(sub.study_level, '{}'), array['any']),
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
$function$;

commit;
