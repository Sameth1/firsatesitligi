-- ============================================================
-- 108 · Filtre alanlarının kaynaktan doğrulanmış backfill'i
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- KAPSAM: 141 aktif kaydın resmî sayfası tek tek indirildi (111'i alınabildi;
--   kalanında kayıttaki eligibility_notes kullanıldı). Uyruk, bölüm, eğitim
--   kademesi ve yaş kanıtları çıkarıldı ve TEK TEK okundu.
--
-- KURAL (bu dosyanın tamamı buna göre yazıldı):
--   Bir kaydı YANLIŞ DARALTMAK, hiç daraltmamaktan daha zararlıdır. Daraltma
--   yalnızca kaynak sayfada AÇIK ve kesin bir şart varken yapılır; şüphe varsa
--   alan {all}/{any} bırakılır ve gerekirse inceleme kuyruğuna düşer.
--   Ayrıca bir bölüm kısıtı yazılırken o bölümün UI'daki BÜTÜN eş slug'ları
--   birlikte yazılır (ör. "mühendislik" → 10 mühendislik slug'ı); eksik liste,
--   uygun bir adayı sonuçlardan siler.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet (ilgili kayıtlarda alanı
--   array['all'] / array['any'] / null yapmak yeterli).
-- ============================================================

begin;

-- ─── 1) 106'DA YAPTIĞIM HATANIN DÜZELTİLMESİ ────────────────────
-- Afreximbank stajını "yalnız Afrika Birliği üyeleri" diye daralttım. Kaynak
-- sayfanın tam cümlesi bunu YALANLIYOR:
--   "...open to students who are nationals of the Bank's member countries;
--    students of African descent in the diaspora AND NON-AFRICAN STUDENTS
--    whose vision for the transformation of Africa resonates with the mission"
-- Yani Türkiye'den biri de başvurabiliyor. Uyruk şartı geri alınıyor.
-- Aynı sayfadaki açık yaş şartı ("aged between 20 and 32") ise ekleniyor.
update public.opportunities
set eligible_citizenships = array['all'],
    age_min = 20,
    age_max = 32
where id = 'c7f0f575-73fd-4f71-bbc5-911bc4877e85';

-- ─── 2) Kanıtlı yeni uyruk daraltmaları ─────────────────────────

-- CAS-DAAD: "up and coming young CHINESE scientists from the University of
-- Chinese Academy of Sciences (UCAS) and CAS research institutes"
update public.opportunities
set eligible_citizenships = array['CN'],
    study_level = array['phd']
where id = 'a043855a-cbe3-4a0c-87c4-d07e99069d03'
  and eligible_citizenships = array['all'];

-- Taiwan Summer Institute: "Doctoral candidates and students of Master's
-- degree courses FROM TAIWAN"
update public.opportunities
set eligible_citizenships = array['TW'],
    study_level = array['master', 'phd']
where id = '672aa938-8581-4900-adf8-121c00b55ddb'
  and eligible_citizenships = array['all'];

-- ─── 3) Georg Forster: uyruk sorusu KAPANDI ─────────────────────
-- 106'da "Türkiye listede var mı bilinmiyor" diye işaretlemiştim. Humboldt
-- Vakfı'nın resmî uygun-ülkeler PDF'i indirildi ve okundu: TÜRKİYE LİSTEDE.
-- Yani kayıtlar Türkiye vatandaşlarına açık, {all} doğru. Ancak iki kaydın
-- resmî linki 404 veriyor — işaret bu kez ONA çevriliyor, silinmiyor.
update public.opportunities
set review_flag = 'link_404',
    review_note = 'Uyruk sorusu çözüldü: Humboldt''un resmî uygun-ülkeler listesinde '
               || 'Türkiye VAR, kayıt Türkiye vatandaşlarına açık ({all} doğru). '
               || 'Kalan sorun: bu kaydın resmî linki 404 veriyor. Linki güncelle '
               || 'ya da kaydı kapat.',
    review_flagged_at = now()
where id in (
  '3e2e074a-5a04-446c-b68b-b11e6f833036',
  'c7028c7a-cbbc-440d-9c3a-927422e0abb9'
)
and review_flag = 'uyruk_belirsiz';

-- ─── 4) Bölüm (target_fields) daraltmaları ──────────────────────
-- Hepsi kaynak sayfadaki açık ifadeye dayanıyor; her biri UI'daki eş
-- slug'ların TAMAMINI içeriyor.

-- ADB Visiting Fellow: "PhD in Economics or a related discipline such as
-- development economics, public policy, finance, political economy,
-- statistics, or data science"
update public.opportunities
set target_fields = array['economics','finance','public_policy','political_science',
                          'statistics','data_science','international_relations'],
    study_level = array['phd']
where id = 'f99d5011-3fac-45ce-8c06-06968e19044d'
  and target_fields = array['all'];

-- DAAD Zuse School'ları — yapay zekâ okulları (başlıkta açık)
update public.opportunities
set target_fields = array['computer_science','software_engineering','data_science',
                          'mathematics','electrical_engineering']
where id in (
  'e7c80151-c137-40c9-be3b-703414b1fc07',   -- Reliable Artificial Intelligence
  '6abcbdfc-d51e-478b-938e-59f89287d579'    -- Embedded Composite AI
)
and target_fields = array['all'];

-- Gazetecilik programları
update public.opportunities
set target_fields = array['journalism','communication','data_science']
where id = 'ea4e6e08-415c-4ea4-8dc5-0db4977c30a5'   -- Data Journalism Grants
  and target_fields = array['all'];

update public.opportunities
set target_fields = array['journalism','communication']
where id in (
  'c0c689a4-5076-441d-92df-47474d1c93b4',   -- Fund for Women Journalists
  '737043f7-5624-4e1c-82f9-e15d82e403e5',   -- Kurt Schork Award
  'bc722162-0b1f-4859-9f93-825fe0ae13be'    -- George Weidenfeld Fellowship
)
and target_fields = array['all'];

-- Gerda Henkel: "archaeology, historical sciences, historical Islamic studies,
-- history of art, history of law, history of science" + komşu disiplinler
update public.opportunities
set target_fields = array['history','anthropology','philosophy','social_sciences',
                          'fine_arts','law']
where id in (
  '1918f15a-ce77-414b-891a-ea02bd52176c',
  'ceef4e11-3925-49fb-84f9-c8c1d907d220'
)
and target_fields = array['all'];

-- Leibniz IEG Mainz: "European history, history of religion, historical
-- theology, or other historical disciplines" (doktora)
update public.opportunities
set target_fields = array['history','philosophy','social_sciences'],
    study_level = array['phd']
where id = 'bc4c7fb7-deb0-4080-8b72-562fc0ad6f33'
  and target_fields = array['all'];

-- Herder Institute for Historical Research (başlıkta açık)
update public.opportunities
set target_fields = array['history','social_sciences']
where id = '7fa0e988-5b86-49d5-a757-022221102d8d'
  and target_fields = array['all'];

-- RWTH Women in Engineering — mühendislik slug'larının TAMAMI
update public.opportunities
set target_fields = array['computer_science','software_engineering','electrical_engineering',
                          'mechanical_engineering','industrial_engineering','civil_engineering',
                          'chemical_engineering','environmental_engineering',
                          'aerospace_engineering','biomedical_engineering'],
    study_level = array['master']
where id = 'd071f66c-c3e5-4fee-906c-9629083ca472'
  and target_fields = array['all'];

-- DAAD alan-özel yüksek lisans bursları (başlıkta açık)
update public.opportunities
set target_fields = array['architecture','urban_planning']
where id = 'b1a9e2b9-8be3-4eff-b02f-4647a115a990'
  and target_fields = array['all'];

update public.opportunities
set target_fields = array['music','fine_arts']
where id = 'de279f9a-2a5c-4e3d-94ef-c955042f27ea'
  and target_fields = array['all'];

-- "Fine Art, Design, Visual Communication and Film"
update public.opportunities
set target_fields = array['fine_arts','graphic_design','industrial_design',
                          'cinema','communication']
where id = 'b8e8815f-9929-4cfa-8ec3-468f4f18cb1c'
  and target_fields = array['all'];

-- DLR/DAAD — DLR havacılık-uzay, enerji, ulaşım araştırma merkezi
update public.opportunities
set target_fields = array['aerospace_engineering','mechanical_engineering',
                          'electrical_engineering','computer_science','software_engineering',
                          'physics','mathematics','environmental_engineering']
where id = '40e813d4-e29a-4402-b7bc-89e951deed7b'
  and target_fields = array['all'];

-- KPMG Data Analytics sanal stajı
update public.opportunities
set target_fields = array['data_science','statistics','mathematics','computer_science',
                          'business','finance','economics']
where id = '0a96473d-69e0-42d7-bf5a-09c20026bcba'
  and target_fields = array['all'];

-- ─── 5) Kanıtlı kademe daraltmaları ─────────────────────────────

-- Avicenna: "enrolment for a Master's degree or doctorate"
update public.opportunities
set study_level = array['master','phd']
where id = 'dab646f5-b5d2-4940-aa73-fdab23eca83e'
  and study_level = array['any'];

-- Brezilya kısa süreli araştırma bursu: "must hold the official status as a
-- doctoral candidate at a university in Brazil".
-- NOT: bu bir UYRUK şartı değil, Brezilya'da doktora yapıyor olma şartı —
-- bu yüzden uyruk {all} bırakıldı.
update public.opportunities
set study_level = array['phd']
where id = '11420574-98ca-4777-9f3e-e1329a3968a5'
  and study_level = array['any'];

-- ─── 6) Yeni belirsiz: bölümü okunamayan kayıt ──────────────────
-- Copernicus Hamburg sayfası "Candidates from the following disciplines are
-- eligible" diyor ama listeyi bu sayfada vermiyor ve kaynak indirilemedi.
update public.opportunities
set review_flag = 'bolum_belirsiz',
    review_note = 'Kaynak "şu disiplinlerden adaylar uygundur" diyor ama listeyi bu '
               || 'sayfada vermiyor; sayfa da indirilemedi. Bölüm {all} bırakıldı '
               || '(yanlış daraltmamak için). Listeyi bulup target_fields''i gir.',
    review_flagged_at = now()
where id = '13b32a89-c01d-46c5-bec8-0eed9b8654e5'
  and review_flag is null;

commit;
