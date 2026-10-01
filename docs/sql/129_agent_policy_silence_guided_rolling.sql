-- ============================================================
-- 129 · Ajan onayı: "sayfa bahsetmiyorsa kısıt yok", resmî program
--       sayfası (guided) ve kanıtlı sürekli başvuru
-- Önkoşul: 114, 120, 122
-- ============================================================
-- NEDEN: 120 ile gelen sözleşme beş kullanıcı filtresinin HER BİRİ için
-- sayfadan birebir alıntı istiyordu — kısıt yoksa bile "all nationalities",
-- "no age limit" gibi bir cümle. Gerçek sayfaların neredeyse hiçbiri bunu
-- yazmıyor; sonuç: ajan hemen her kaydı reddetti, site büyümedi (Eylül
-- 2026'da 18 günde 9 kayıttan 1'i yayına girdi, 4'ü yalnız "dil alıntısı
-- yok" diye reddedildi).
--
-- YENİ SÖZLEŞME (kullanıcı politikası: tek ölçüt doğruluk):
--   * Filtre sayfada KISIT olarak yazıyorsa değer + birebir alıntı zorunlu
--     (değişmedi). Sayfa bahsetmiyorsa kısıtsız değer doğrudur ve alıntı
--     gerekmez. Uyruk ve yaşta bu karar Python tarafında ayrıca TAM sayfa
--     taramasıyla sınanıyor (validate_submissions.strict_silence_blockers).
--   * Başvuru rotası: doğrudan form/portal (verified) ya da form iki adımda
--     bulunamadığında kurumun kendi program sayfası (guided). 122 'guided'i
--     yalnız eski kayıtlar için açmıştı; artık ajan da üretebiliyor. Model
--     guided için `resmi_kaynak=true` vermeli (blog/derleme değil).
--   * Son tarih: modelin kanıtladığı ISO tarih (dogrulanmis_filtreler.deadline)
--     submission'a yazılır ve burada karşılaştırılır. NULL son tarih yalnız
--     iki turun da `surekli_basvuru=true` dediği (sayfada "rolling basis",
--     "no deadline" gibi açık ifade) kayıtlarda kabul.
--
-- Geriye uyum: eski biçimdeki bir doğrulama nesnesi (bütün alıntılar dolu,
-- route=verified, ISO son tarih) yeni kuralları da karşılar — `deadline`
-- anahtarı hariç; o artık zorunlu.

begin;

-- ── 1. submissions: ajan 'guided' rota yazabilsin ─────────────────────────
alter table public.submissions
  drop constraint if exists submissions_application_route_status_check;
alter table public.submissions
  add constraint submissions_application_route_status_check
  check (application_route_status in ('verified', 'guided', 'unverified', 'missing'));

-- ── 2. Onaylanan submission'ın rotası fırsata kopyalanır ──────────────────
create or replace function public.copy_verified_application_route()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  route record;
begin
  if new.submitted_by_submission_id is null then
    if coalesce(new.is_active, true)
       and new.application_route_status is distinct from 'verified' then
      raise exception 'Yeni aktif fırsat engellendi: doğrulanmış doğrudan başvuru adımı yok';
    end if;
    return new;
  end if;

  select details_url, source_url, application_route_status, application_method,
         application_url_verified_at, application_url_check_status,
         application_url_final, application_url_evidence, url
  into route
  from public.submissions
  where id = new.submitted_by_submission_id;

  if not found then
    raise exception 'Onay engellendi: submission bulunamadı';
  end if;

  if route.application_route_status = 'verified' then
    if route.application_method is null
       or route.application_url_verified_at is null
       or nullif(btrim(coalesce(route.application_url_final, '')), '') is null then
      raise exception 'Onay engellendi: doğrulanmış doğrudan başvuru adımı eksik';
    end if;
  elsif route.application_route_status = 'guided' then
    if nullif(btrim(coalesce(route.details_url, route.url, '')), '') is null then
      raise exception 'Onay engellendi: resmî program sayfası adresi yok';
    end if;
  else
    raise exception 'Onay engellendi: doğrudan başvuru adımı ya da resmî program sayfası yok';
  end if;

  new.official_url := route.url;
  new.details_url := coalesce(route.details_url, route.url);
  new.source_url := route.source_url;
  new.application_route_status := route.application_route_status;
  new.application_method := route.application_method;
  new.application_url_verified_at := route.application_url_verified_at;
  new.application_url_check_status := route.application_url_check_status;
  new.application_url_final := route.application_url_final;
  new.application_url_evidence := route.application_url_evidence;
  return new;
end;
$$;

-- ── 3. Ajanın onay RPC'si ─────────────────────────────────────────────────
create or replace function public.agent_approve_submission(p_id uuid, p_validation jsonb)
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
  v_filters jsonb;
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

  if p_validation is null
     or p_validation->>'durum' is distinct from 'acik'
     or p_validation->>'guven' is distinct from 'yuksek'
     or p_validation->'kategori_uygun' is distinct from 'true'::jsonb
     or p_validation->'tek_firsat' is distinct from 'true'::jsonb
     or p_validation->'son_tarih_dogrulandi' is distinct from 'true'::jsonb
     or p_validation->'finansman_dogrulandi' is distinct from 'true'::jsonb
     or p_validation->'ulke_dogrulandi' is distinct from 'true'::jsonb
     or p_validation->'uygunluk_dogrulandi' is distinct from 'true'::jsonb then
    raise exception 'Otomatik onay engellendi: bütün yayın kanıtları doğrulanmadı';
  end if;

  -- Rota: doğrudan form için model hedefi doğrulamalı; resmî program
  -- sayfası için sayfanın kurumun kendi sayfası olduğunu doğrulamalı.
  if sub.application_route_status = 'verified' then
    if p_validation->'dogrudan_firsat_sayfasi' is distinct from 'true'::jsonb then
      raise exception 'Otomatik onay engellendi: doğrudan başvuru sayfası doğrulanmadı';
    end if;
  elsif sub.application_route_status = 'guided' then
    if p_validation->'resmi_kaynak' is distinct from 'true'::jsonb then
      raise exception 'Otomatik onay engellendi: resmî program sayfası doğrulanmadı';
    end if;
  else
    raise exception 'Otomatik onay engellendi: başvuru rotası yok';
  end if;

  -- Son tarih: submission'a yazılan değer kanıtlanan değerle aynı olmalı.
  v_filters := p_validation->'dogrulanmis_filtreler';
  if jsonb_typeof(v_filters) is distinct from 'object' or not (v_filters ? 'deadline') then
    raise exception 'Otomatik onay engellendi: kanıtlanmış son tarih yok';
  end if;
  begin
    v_deadline := nullif(btrim(coalesce(sub.deadline_text, '')), '')::date;
  exception when others then
    raise exception 'Otomatik onay engellendi: tam ve işlenebilir son tarih yok';
  end;
  if v_deadline is null then
    if p_validation->'surekli_basvuru' is distinct from 'true'::jsonb
       or v_filters->'deadline' is distinct from 'null'::jsonb then
      raise exception 'Otomatik onay engellendi: son tarih yok ve sürekli başvuru kanıtlanmadı';
    end if;
  else
    if v_deadline < current_date then
      raise exception 'Otomatik onay engellendi: son tarih geçmiş (%)', v_deadline;
    end if;
    if v_filters->>'deadline' is distinct from v_deadline::text then
      raise exception 'Otomatik onay engellendi: kayıtlı son tarih kanıtlanan tarihle aynı değil';
    end if;
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
    array['all']::text[],
    coalesce(nullif(sub.eligible_citizenships, '{}'), array['all']),
    coalesce(nullif(sub.target_fields, '{}'), array['all']),
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
$$;

revoke all on function public.agent_approve_submission(uuid, jsonb) from public, anon, authenticated;
grant execute on function public.agent_approve_submission(uuid, jsonb) to service_role;

-- ── 4. İki tur kanıt tetikleyicisi ────────────────────────────────────────
create or replace function public.enforce_agent_two_pass_evidence()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  v_key text;
  v_second jsonb;
  v_filters jsonb;
  v_second_filters jsonb;
  v_restricted boolean;
begin
  if new.status = 'approved'
     and old.status = 'pending'
     and new.submission_origin = 'agent'
     and new.reviewed_by is null then
    if new.agent_validation is null then
      raise exception 'Agent onayı engellendi: validation nesnesi yok';
    end if;

    v_second := new.agent_validation->'second_pass';
    if jsonb_typeof(v_second) is distinct from 'object'
       or v_second->>'durum' is distinct from 'acik'
       or v_second->>'guven' is distinct from 'yuksek'
       or v_second->'kategori_uygun' is distinct from 'true'::jsonb
       or v_second->'tek_firsat' is distinct from 'true'::jsonb
       or v_second->'son_tarih_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'finansman_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'ulke_dogrulandi' is distinct from 'true'::jsonb
       or v_second->'uygunluk_dogrulandi' is distinct from 'true'::jsonb then
      raise exception 'Agent onayı engellendi: ikinci denetim olumlu değil';
    end if;

    if new.application_route_status = 'verified' then
      if v_second->'dogrudan_firsat_sayfasi' is distinct from 'true'::jsonb then
        raise exception 'Agent onayı engellendi: ikinci tur doğrudan başvuru sayfasını doğrulamadı';
      end if;
    elsif new.application_route_status = 'guided' then
      if new.agent_validation->'resmi_kaynak' is distinct from 'true'::jsonb
         or v_second->'resmi_kaynak' is distinct from 'true'::jsonb then
        raise exception 'Agent onayı engellendi: resmî program sayfası iki turda doğrulanmadı';
      end if;
    else
      raise exception 'Agent onayı engellendi: başvuru rotası yok';
    end if;

    if coalesce(new.agent_validation->'surekli_basvuru', 'false'::jsonb)
       is distinct from coalesce(v_second->'surekli_basvuru', 'false'::jsonb) then
      raise exception 'Agent onayı engellendi: iki tur sürekli başvuruda uzlaşmadı';
    end if;

    foreach v_key in array array[
      'uyruk_dogrulandi', 'yas_dogrulandi', 'egitim_dogrulandi',
      'dil_dogrulandi', 'bolum_dogrulandi'
    ] loop
      if new.agent_validation->v_key is distinct from 'true'::jsonb
         or v_second->v_key is distinct from 'true'::jsonb then
        raise exception 'Agent onayı engellendi: % iki turda doğrulanmadı', v_key;
      end if;
    end loop;

    v_filters := new.agent_validation->'dogrulanmis_filtreler';
    v_second_filters := v_second->'dogrulanmis_filtreler';
    if jsonb_typeof(v_filters) is distinct from 'object'
       or jsonb_typeof(v_second_filters) is distinct from 'object'
       or v_filters is distinct from v_second_filters then
      raise exception 'Agent onayı engellendi: iki tur filtre değerlerinde uzlaşmadı';
    end if;

    foreach v_key in array array[
      'host_countries', 'eligible_citizenships', 'age_min', 'age_max',
      'study_level', 'language_requirement', 'required_languages', 'target_fields',
      'deadline'
    ] loop
      if not (v_filters ? v_key) then
        raise exception 'Agent onayı engellendi: % filtre değeri yok', v_key;
      end if;
    end loop;

    if to_jsonb(new.host_countries) is distinct from v_filters->'host_countries'
       or to_jsonb(new.eligible_citizenships) is distinct from v_filters->'eligible_citizenships'
       or coalesce(to_jsonb(new.age_min), 'null'::jsonb) is distinct from v_filters->'age_min'
       or coalesce(to_jsonb(new.age_max), 'null'::jsonb) is distinct from v_filters->'age_max'
       or to_jsonb(new.study_level) is distinct from v_filters->'study_level'
       or coalesce(to_jsonb(new.language_requirement), 'null'::jsonb) is distinct from v_filters->'language_requirement'
       or to_jsonb(new.required_languages) is distinct from v_filters->'required_languages'
       or to_jsonb(new.target_fields) is distinct from v_filters->'target_fields' then
      raise exception 'Agent onayı engellendi: kayıtlı filtreler kanıtlanan değerlerle aynı değil';
    end if;

    -- Yayın kanıtları her zaman alıntı ister; kullanıcı filtreleri yalnız
    -- bir KISIT yazıldığında. Kısıtsız değer sayfanın sessizliğinden gelir.
    foreach v_key in array array[
      'guncellik', 'son_tarih', 'kategori', 'finansman', 'ulke', 'uygunluk',
      'uyruk', 'yas', 'egitim', 'dil', 'bolum'
    ] loop
      v_restricted := case v_key
        when 'uyruk' then v_filters->'eligible_citizenships' is distinct from '["all"]'::jsonb
        when 'yas' then v_filters->'age_min' is distinct from 'null'::jsonb
                     or v_filters->'age_max' is distinct from 'null'::jsonb
        when 'egitim' then v_filters->'study_level' is distinct from '["any"]'::jsonb
        when 'dil' then v_filters->'required_languages' is distinct from '["all"]'::jsonb
                     or v_filters->'language_requirement' is distinct from 'null'::jsonb
        when 'bolum' then v_filters->'target_fields' is distinct from '["all"]'::jsonb
        else true
      end;
      if not v_restricted then
        continue;
      end if;
      if char_length(btrim(coalesce(
           new.agent_validation->'kanitlar'->>v_key, ''))) < 5 then
        raise exception 'Agent onayı engellendi: ilk tur % kanıtı yok', v_key;
      end if;
      if char_length(btrim(coalesce(
           v_second->'kanitlar'->>v_key, ''))) < 5 then
        raise exception 'Agent onayı engellendi: ikinci tur % kanıtı yok', v_key;
      end if;
    end loop;
  end if;
  return new;
end;
$$;

comment on function public.enforce_agent_two_pass_evidence() is
  'Agent auto-approval: two matching reviews; quotes required for publication '
  'evidence always and for user filters only when a restriction is recorded.';

commit;
