-- ============================================================
-- 094 · agent_approve_submission — service-role onay RPC'si
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- NEDEN:
--   Mevcut approve_submission() RPC'si auth.uid()'yi admins tablosuyla
--   kontrol eder. Bir otomasyon (ör. validate_submissions.py) service key
--   ile çağırdığında auth.uid() NULL döner ve RPC 'Yetkisiz: admin
--   değilsiniz' hatası verir — yani scriptler submission onaylayamaz.
--
--   Bu migration, approve_submission ile AYNI onay mantığını çalıştıran
--   ama auth.uid() admin kontrolü OLMAYAN ikiz fonksiyonu ekler:
--   agent_approve_submission(). approve_submission'dan tek farkları:
--     (1) admin guard yok,
--     (2) reviewed_by NULL bırakılır — "insan değil, otomasyon onayladı"
--         denetim sinyali (insan onayı reviewed_by'ı doldurur).
--
-- GÜVENLİK:
--   Fonksiyon admin kontrolü yapmadığından, yetki sınırı = ONU ÇAĞIRMA
--   YETKİSİ. Bu yüzden EXECUTE izni PUBLIC / anon / authenticated'tan
--   ALINIR ve yalnızca service_role'a VERİLİR. Sonuç: fonksiyonu yalnızca
--   service_role anahtarına sahip bir çağıran tetikleyebilir; giriş yapmış
--   sıradan bir kullanıcı (authenticated) ÇAĞIRAMAZ.
--
--   Çağırma (PostgREST RPC), service_role anahtarıyla:
--     POST {SUPABASE_URL}/rest/v1/rpc/agent_approve_submission
--     headers: apikey + Authorization: Bearer <service_role key>
--     body: {"p_id": "<submission uuid>"}
--
--   ⚠ Bu fonksiyon eklendikten sonra service key'in gizli kalması daha da
--   kritik — anahtarı ele geçiren herkes submission onaylayabilir.
--
-- Önkoşul: 006 + 090 + 092 (submissions, opportunities, categories,
--          documents, approve_submission). Idempotent — tekrar çalıştırılabilir.
-- ============================================================

drop function if exists public.agent_approve_submission(uuid);

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
  -- DİKKAT: approve_submission'daki auth.uid() admin guard'ı burada KASTEN
  -- yok. Yetki sınırı, EXECUTE izninin yalnızca service_role'a verilmiş
  -- olmasıdır (bu dosyanın sonundaki revoke/grant bloğu).

  select * into sub from public.submissions where id = p_id;
  if not found then
    raise exception 'Submission bulunamadı: %', p_id;
  end if;
  if sub.status = 'approved' then
    raise exception 'Bu öneri zaten onaylanmış';
  end if;

  -- category_slug → category_id lookup (kategori yoksa hata; çağıran önce
  -- kategoriyi düzeltmeli ya da null bırakmalı).
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

  -- submission → opportunities. Bilinmeyen NOT NULL diziler için güvenli
  -- default'lar (approve_submission ile aynı).
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
    array['any']::text[],   -- bilinmiyor → tüm eğitim kademeleri
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

  -- deadline_text → tarihe cast etmeyi dene; olmazsa serbest metin olarak
  -- deadline_notes'a yaz.
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

  -- belgeler (varsa)
  if sub.documents is not null and sub.documents <> '[]'::jsonb then
    insert into public.documents (opportunity_id, name, is_required, notes)
    select
      new_opp_id,
      (doc->>'name')::text,
      coalesce((doc->>'is_required')::boolean, false),
      (doc->>'notes')::text
    from jsonb_array_elements(sub.documents) as doc;
  end if;

  -- submission'ı onaylandı işaretle. reviewed_by KASTEN NULL: bu onay bir
  -- insan admin tarafından değil, service-role otomasyonu tarafından yapıldı.
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

-- ─── Güvenlik: yalnızca service_role çağırabilsin ───────────────
-- CREATE FUNCTION, EXECUTE'i varsayılan olarak PUBLIC'e verir. Admin kontrolü
-- olmadığından bu varsayılanı geri alıp izni yalnızca service_role'a veriyoruz.
revoke all on function public.agent_approve_submission(uuid) from public;
revoke all on function public.agent_approve_submission(uuid) from anon;
revoke all on function public.agent_approve_submission(uuid) from authenticated;
grant execute on function public.agent_approve_submission(uuid) to service_role;
