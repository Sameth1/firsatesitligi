-- ============================================================
-- 104 · Öneri formu için gerçek rate limit
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- SORUN:
--   check_submission_rate_limit trigger'ı zaten vardı ama ilk satırı
--     if new.submitter_ip is not null then
--   Halka açık form (SuggestOpportunityModal) tarayıcıdan doğrudan insert
--   ediyor ve submitter_ip GÖNDERMİYOR — gönderemez de: tarayıcı kendi genel
--   IP'sini bilmez, bilse bile istemciden gelen IP'ye güvenilemez. Sonuç:
--   trigger her seferinde no-op, rate limit fiilen YOK. Herhangi biri
--   submissions tablosunu sınırsız şişirebiliyordu.
--
-- ÇÖZÜM:
--   IP'yi yalnız SUNUCU bilebilir. Öneri artık kendi API route'umuzdan
--   (/api/submit-opportunity) geçiyor; route, Vercel'in yazdığı
--   x-forwarded-for başlığından gerçek IP'yi okuyup bu RPC'ye veriyor.
--
--   RPC EXECUTE yetkisi yalnız service_role'a verildi. anon çağıramaz, yani
--   istemci sahte IP ile rate limit'i atlayamaz.
--
--   Sayım ve insert aynı ifadede/işlemde olduğu için eşzamanlı isteklerde
--   yarış koşulu yok (trigger'daki select-sonra-insert deseninin aksine).
--
-- SINIRLAR (ikisi birden uygulanır):
--   • 3 / dakika  → hızlı seri gönderimi keser
--   • 20 / gün    → yavaş ama ısrarlı doldurmayı keser
--   IP'si bilinmeyen (null) çağrı reddedilir; sessizce limitsiz geçmesin.
--
-- NOT: eski trigger yerinde bırakıldı — service_role'ün doğrudan yazdığı
--   scraper akışları için zararsız bir emniyet ağı olarak kalıyor.
--
-- IDEMPOTENT: evet.
-- ============================================================

begin;

-- IP + zaman sorgusu indekssiz tablo taraması yapmasın.
create index if not exists idx_submissions_ip_created
  on public.submissions (submitter_ip, created_at desc)
  where submitter_ip is not null;

create or replace function public.submit_human_opportunity(
  p_ip      inet,
  p_payload jsonb
)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
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

  select
    count(*) filter (where created_at > now() - interval '1 minute'),
    count(*) filter (where created_at > now() - interval '1 day')
  into v_dakika, v_gun
  from public.submissions
  where submitter_ip = p_ip;

  -- 53400 = configuration_limit_exceeded. GEÇERLİ bir Postgres SQLSTATE'i
  -- olması şart: 'too_many_requests' diye bir koşul adı yok, kullanılırsa
  -- Postgres 42704 (undefined_object) fırlatır ve çağıran taraf limiti
  -- diğer hatalardan ayırt edemez. Route bu kodu HTTP 429'a çeviriyor.
  if v_dakika >= 3 then
    raise exception 'Çok hızlı gönderiyorsun, bir dakika bekle'
      using errcode = '53400';
  end if;
  if v_gun >= 20 then
    raise exception 'Bugünlük gönderim sınırına ulaştın'
      using errcode = '53400';
  end if;

  -- submission_origin / review_stage BİLİNÇLİ olarak sabit: istemciden
  -- gelen değerlere bakılmıyor, böylece "agent" gibi görünüp otomatik onay
  -- hattına düşmek mümkün değil (bkz. 103).
  insert into public.submissions (
    title, url, category_slug, submitter_nickname, submitter_email,
    host_countries, deadline_text, funding_type, eligibility_notes,
    language_requirement, description, submitter_ip,
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
$function$;

-- Yalnız service_role. anon/authenticated çağıramaz → sahte IP ile atlatma yok.
revoke all on function public.submit_human_opportunity(inet, jsonb) from public, anon, authenticated;
grant execute on function public.submit_human_opportunity(inet, jsonb) to service_role;

commit;
