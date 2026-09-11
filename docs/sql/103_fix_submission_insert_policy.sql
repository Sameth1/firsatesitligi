-- ============================================================
-- 103 · GÜVENLİK: submissions'a anon insert'inde politika boşluğu
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- SORUN:
--   097, anonim kullanıcının kendini "agent" gibi göstermesini engellemek için
--   sıkı bir INSERT politikası ekledi:
--     with_check: submission_origin='human' AND review_stage='human_review'
--   ve eskisini silmeyi amaçladı:
--     drop policy if exists "Anyone can insert submissions"
--
--   Ama canlıdaki eski politikanın adı "public insert submissions" idi —
--   farklı bir ad. `if exists` yüzünden drop sessizce hiçbir şey yapmadı ve
--   eski politika (with_check: true) hayatta kaldı.
--
--   Postgres'te aynı komut için birden çok PERMISSIVE politika OR'lanır.
--   with_check=true olan biri varsa diğerinin hiçbir kısıtlayıcı etkisi kalmaz.
--   Sonuç: 097'nin güvenlik amacı üretimde tamamen etkisiz.
--
-- ETKİSİ (neden önemli):
--   anon anahtar tarayıcıya gönderilen bundle'da — tasarımı gereği herkese
--   açık. Bu boşlukla herhangi bir ziyaretçi şunu yazabiliyordu:
--     submission_origin='agent', review_stage='agent_queue'
--   validate_submissions.py tam olarak bu iki değere bakıp kaydı OTOMATİK
--   ONAY hattına alıyor (bkz. satır 176-177), 099'daki onay kapısı da yalnız
--   'agent' kaynaklı kayıtlara açılıyor. Yani insan incelemesi atlanabiliyor
--   ve yeterince makul görünen bir sayfa canlı listeye düşebiliyordu.
--   Sitenin tek değeri güvenilir bağlantılar olduğu için etki yüksek.
--
-- ÇÖZÜM:
--   Eski, sınırsız politikayı gerçek adıyla düşür. Geriye 097'nin sıkı
--   politikası kalır.
--
-- KIRILMA RİSKİ: yok.
--   • Halka açık "Fırsat Öner" formu (SuggestOpportunityModal) zaten
--     submission_origin:'human', review_stage:'human_review' gönderiyor —
--     sıkı politikanın izin verdiği tam değerler.
--   • Scraper'lar SUPABASE_SERVICE_ROLE_KEY kullanıyor; service_role RLS'i
--     tamamen bypass eder, bu politikalardan etkilenmez.
--
-- DOĞRULANDI (anon rolüne geçilip denendi, hiçbir satır kalıcı yazılmadı):
--   • human / human_review  → INSERT BAŞARILI (form yolu bozulmadı)
--   • agent  / agent_queue   → 42501 RLS reddi (açık kapandı)
--
-- NOT: anon'un submissions üzerinde SELECT politikası YOK. Bu yüzden
--   `insert ... returning` 42501 verir. Halka açık form supabase-js'te
--   `.select()` çağırmadığı için RETURNING üretmiyor ve etkilenmiyor —
--   ama ileride forma `.select()` eklenirse insert kırılır.
--
-- IDEMPOTENT: evet.
-- ============================================================

begin;

drop policy if exists "public insert submissions" on public.submissions;

-- 097'nin sıkı politikası yoksa (eski bir veritabanında) kur — bu script tek
-- başına da doğru son duruma getirsin.
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'submissions'
      and policyname = 'Anyone can insert human submissions'
  ) then
    create policy "Anyone can insert human submissions"
      on public.submissions for insert
      with check (submission_origin = 'human' and review_stage = 'human_review');
  end if;
end $$;

commit;
