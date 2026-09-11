-- ============================================================
-- 114 · Abone formuna rate limit + ölü revize akışının kaldırılması
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- A) ABONE FORMU (subscribers)
--   Bugün tarayıcı doğrudan `insert into subscribers` yapıyor ve politika
--   `with check (true)`. Yani tek bir script saniyede yüzlerce e-posta
--   yazabilir: tablo şişer, "Aboneler" sayacı anlamsızlaşır ve ileride
--   bildirim gönderilirse başkalarının adresleri listeye sokulmuş olur.
--   Öneri formunda (104/107) kurulan deseni buraya da kuruyoruz:
--     tarayıcı → /api/subscribe (IP'yi sunucu okur) → subscribe_email RPC
--   RPC yalnız service_role'a açık; anon bu yoldan IP uydurup limiti aşamaz.
--
--   ÖNEMLİ SIRALAMA: anon INSERT politikası BU DOSYADA KALDIRILMIYOR.
--   Kaldırılırsa, yeni /api/subscribe route'u canlıya çıkana kadar abone
--   formu çalışmaz. Kod deploy edildikten sonra 114b çalıştırılmalı:
--       drop policy if exists "public insert subscribers" on public.subscribers;
--
-- B) ÖLÜ REVİZE AKIŞI
--   E-posta + token'lı revize akışı hiç çalışmadı (mail gönderen kod yok,
--   tabloda 0 satır) ve 108 ile yerine ajan akışı geldi. 113'te yetkileri
--   alınmıştı; burada tamamen siliniyor. `/revise/[token]` sayfası da bu
--   PR'da repodan kaldırıldı.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: A evet; B için tablo/fonksiyonlar
--   091/096'daki tanımlardan yeniden oluşturulabilir (içlerinde veri yoktu).
-- ============================================================

begin;

-- ─── A1) IP kolonu ──────────────────────────────────────────────
alter table public.subscribers
  add column if not exists subscriber_ip inet;

comment on column public.subscribers.subscriber_ip is
  'Kaydı açan IP — yalnız rate limit için. /api/subscribe doldurur.';

create index if not exists subscribers_ip_created_idx
  on public.subscribers (subscriber_ip, created_at desc)
  where subscriber_ip is not null;

-- ─── A2) Rate limit'li kayıt fonksiyonu ─────────────────────────
create or replace function public.subscribe_email(
  p_ip       inet,
  p_email    text,
  p_snapshot jsonb default null
)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  v_email   text := lower(btrim(p_email));
  v_minute  int;
  v_day     int;
begin
  if p_ip is null then
    raise exception 'IP belirlenemedi' using errcode = 'check_violation';
  end if;
  -- Kasıtlı olarak basit: amaç doğrulama değil, saçma girdiyi elemek.
  if v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
     or char_length(v_email) > 254 then
    raise exception 'Geçerli bir e-posta gir' using errcode = 'check_violation';
  end if;

  select
    count(*) filter (where created_at > now() - interval '1 minute'),
    count(*) filter (where created_at > now() - interval '1 day')
  into v_minute, v_day
  from public.subscribers
  where subscriber_ip = p_ip;

  -- 53400 = configuration_limit_exceeded. Route bunu 429'a çeviriyor.
  if v_minute >= 3 then
    raise exception 'Çok hızlı deniyorsun, bir dakika bekle' using errcode = '53400';
  end if;
  if v_day >= 20 then
    raise exception 'Bugünlük kayıt sınırına ulaştın' using errcode = '53400';
  end if;

  insert into public.subscribers (email, search_snapshot, subscriber_ip)
  values (v_email, p_snapshot, p_ip)
  on conflict (email) do update
    set last_seen_at  = now(),
        -- Var olan kaydın snapshot'ı yalnız yenisi doluysa güncellenir.
        search_snapshot = coalesce(excluded.search_snapshot, public.subscribers.search_snapshot);

  return json_build_object('success', true);
end;
$function$;

-- Yalnız sunucu ucu çağırabilsin: anon/authenticated IP uydurup limiti aşamaz.
revoke execute on function public.subscribe_email(inet, text, jsonb) from public, anon, authenticated;
grant  execute on function public.subscribe_email(inet, text, jsonb) to service_role;

-- ─── B) Ölü revize akışı siliniyor ──────────────────────────────
drop function if exists public.submit_revision(
  text, text, text, text, text[], text, text, text, text, text
);
drop function if exists public.get_revision_submission(text);
drop table if exists public.submission_revision_tokens;

commit;
