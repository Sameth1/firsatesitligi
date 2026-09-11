-- ============================================================
-- 102 · Fırsat veri denetimi: "belirsizler" kuyruğu + yaş düzeltmesi
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- NEDEN:
--   agent_reach_url_scraper.extract_age_range, DAAD sayfalarındaki
--   "awarded for a period of between 10 and 24 months" ifadesini yaş aralığı
--   sanıyordu ("between" tek başına yaş sinyali sayılıyordu). Sonuç: 5 fırsata
--   age_min=10 gibi imkânsız değerler yazıldı.
--
--   Yaş RPC'de HARD filtre (age_min <= p_age <= age_max). Yanlış aralık
--   kullanıcıyı sessizce eliyor: 25 yaşındaki biri bu burslara uygun olduğu
--   hâlde sonuçlarda göremiyordu. Kök neden kodda düzeltildi
--   (+ tests/test_extract_age_range.py); bu script mevcut kayıtları temizler.
--
-- NE YAPIYOR:
--   1) opportunities'e üç NULLABLE kolon: review_flag / review_note /
--      review_flagged_at. Emin olunamayan kayıtlar buraya işaretlenir ve
--      admin panelindeki "Belirsizler" ekranında görünür.
--   2) KESİN olan 4 DAAD kaydının yaş alanlarını NULL'a çeker. NULL = yaş
--      filtresi yok = herkese görünür. Yanlış bir aralık bırakmaktansa
--      filtresiz bırakmak güvenli taraf.
--   3) EMİN OLUNAMAYAN 2 kaydı incelemeye işaretler (silmez, gizlemez):
--        • Gerda Henkel — "under 28 AT THE TIME OF OBTAINING THE DEGREE".
--          Bu başvuru anındaki yaş değil; age_max=27 yazmak, 30 yaşında olup
--          derecesini 26'da almış uygun bir adayı yanlışlıkla elerdi.
--        • George Weidenfeld — "citizens OR RESIDENTS of the United Kingdom".
--          eligible_citizenships'i ['GB'] yapmak, Birleşik Krallık'ta ikamet
--          eden bir TC vatandaşını elerdi. Kart zaten Türkçe özetinde şartı
--          yazıyor, o yüzden görünür bırakılıp insana bırakıldı.
--   4) Admin RPC'leri: kuyruğu okuma + işareti kaldırma. Mevcut
--      get_opportunity_link_audit / mark_opportunity_verified desenine birebir
--      uyar (SECURITY DEFINER + admins tablosu kontrolü).
--
-- IDEMPOTENT: evet (add column if not exists, create or replace, koşullu update).
-- GERİ ALINABİLİR Mİ: evet — kolonları drop etmek yeterli; yaş alanları zaten
--   bozuk veriydi, eski hâline döndürmenin bir değeri yok.
-- ============================================================

begin;

-- ─── 1) İnceleme kolonları ───────────────────────────────────────
alter table public.opportunities
  add column if not exists review_flag       text,
  add column if not exists review_note       text,
  add column if not exists review_flagged_at timestamptz;

comment on column public.opportunities.review_flag is
  'Kısa makine-okur sebep (age_belirsiz, uyruk_belirsiz...). NULL = inceleme gerekmiyor.';
comment on column public.opportunities.review_note is
  'Admin için Türkçe açıklama: neyin belirsiz olduğu ve neden otomatik karar verilmediği.';

-- Kuyruk küçük; kısmi indeks tarama maliyetini sıfıra yakın tutar.
create index if not exists opportunities_review_flag_idx
  on public.opportunities (review_flagged_at desc)
  where review_flag is not null;

-- ─── 2) Kesin hata: süre (ay) yaş alanına yazılmış ───────────────
-- Hepsi DAAD "Study Scholarships" kayıtları; lisansüstü programlar için
-- age_min=10 imkânsız. Koşul dar tutuldu ki doğru veriye dokunulmasın.
update public.opportunities
set age_min = null,
    age_max = null
where id in (
  'a5d9c386-2379-4b20-9283-5c8ebf4c74ec',  -- Performing Arts
  'b1a9e2b9-8be3-4eff-b02f-4647a115a990',  -- Architecture
  'b8e8815f-9929-4cfa-8ec3-468f4f18cb1c',  -- Fine Art
  '50410085-9455-40e2-b2af-adf09814cc14'   -- Master Studies, All Disciplines
)
and age_min = 10 and age_max = 24;

-- ─── 3) Belirsizler: insana bırakılanlar ─────────────────────────
-- Gerda Henkel: yaş şartı var ama başvuru anına değil, derecenin alındığı ana
-- bağlı. Modellenemediği için yaş filtresi kaldırılıp incelemeye alındı.
update public.opportunities
set age_min = null,
    age_max = null,
    review_flag = 'age_belirsiz',
    review_note = 'Kaynak metin "doktoraya başlamayı sağlayan dereceyi alırken 28 yaşından '
               || 'küçük olmak" diyor — bu BAŞVURU anındaki yaş değil. age_max=27 yazmak, '
               || 'bugün 30 yaşında olup derecesini 26''da almış uygun bir adayı elerdi. '
               || 'DB''deki 12-24 değeri ise burs süresinden (ay) yanlış çıkarılmıştı, '
               || 'temizlendi. Şu an yaş filtresi YOK; şart kartta metin olarak görünüyor.',
    review_flagged_at = now()
where id = '1918f15a-ce77-414b-891a-ea02bd52176c'
  and review_flag is distinct from 'age_belirsiz';

-- George Weidenfeld: uyruk şartı var ama "vatandaş VEYA ikamet eden" biçiminde.
update public.opportunities
set review_flag = 'uyruk_belirsiz',
    review_note = 'Kaynak metin "Birleşik Krallık vatandaşı VEYA orada ikamet eden" diyor. '
               || 'eligible_citizenships ["all"] olduğu için Türkiye''den arayanlara da '
               || 'çıkıyor. ["GB"] yapmak, Birleşik Krallık''ta yaşayan bir TC vatandaşını '
               || 'elerdi — bu yüzden otomatik daraltılmadı. Kartın Türkçe özeti şartı '
               || 'zaten yazıyor. Karar admine bırakıldı.',
    review_flagged_at = now()
where id = 'bc722162-0b1f-4859-9f93-825fe0ae13be'
  and review_flag is distinct from 'uyruk_belirsiz';

-- ─── 4) Admin RPC'leri ───────────────────────────────────────────
-- Desen: 091/link-audit ile aynı — SECURITY DEFINER + admins kontrolü.
-- RLS opportunities'te yalnız "is_active = true" public SELECT'e izin verdiği
-- için admin ekranı doğrudan tablodan okuyamaz.

create or replace function public.get_opportunity_review_queue()
returns table(
  id                    uuid,
  title                 text,
  official_url          text,
  is_active             boolean,
  review_flag           text,
  review_note           text,
  review_flagged_at     timestamptz,
  age_min               integer,
  age_max               integer,
  host_countries        text[],
  eligible_citizenships text[],
  eligibility_notes     text
)
language plpgsql
security definer
set search_path to 'public'
as $function$
begin
  if not exists (select 1 from public.admins a where a.user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  return query
  select o.id, o.title, o.official_url, o.is_active,
         o.review_flag, o.review_note, o.review_flagged_at,
         o.age_min, o.age_max, o.host_countries, o.eligible_citizenships,
         o.eligibility_notes
  from public.opportunities o
  where o.review_flag is not null
  order by o.review_flagged_at desc nulls last, o.title asc;
end;
$function$;

create or replace function public.resolve_opportunity_review(p_id uuid)
returns json
language plpgsql
security definer
set search_path to 'public'
as $function$
declare
  n integer;
begin
  if not exists (select 1 from public.admins a where a.user_id = auth.uid()) then
    raise exception 'Yetkisiz: admin değilsiniz';
  end if;

  update public.opportunities
  set review_flag = null,
      review_note = null,
      review_flagged_at = null
  where public.opportunities.id = p_id
    and public.opportunities.review_flag is not null;

  get diagnostics n = row_count;
  if n = 0 then
    raise exception 'İncelemede böyle bir fırsat yok: %', p_id;
  end if;

  return json_build_object('success', true, 'resolved_at', now());
end;
$function$;

grant execute on function public.get_opportunity_review_queue() to authenticated;
grant execute on function public.resolve_opportunity_review(uuid) to authenticated;

commit;
