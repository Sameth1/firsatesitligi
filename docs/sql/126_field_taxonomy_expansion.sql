-- ============================================================
-- 117 · Bölüm sözlüğü genişlemesi · veri hizalaması
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- src/lib/fields.ts 59 → 135 slug'a çıktı (mekatronik, malzeme, gıda, maden,
-- fizyoterapi, beslenme-diyetetik, sosyal hizmet, arkeoloji, iç mimarlık,
-- peyzaj, moda tasarımı, muhasebe, aktüerya, siber güvenlik, yapay zeka …).
--
-- YENİ SLUG TEK BAŞINA ZARARLIDIR: bölüm kısıtı olan bir kayıt eski dar
-- listesiyle kalırsa, artık listede olan kardeş bölümü seçen aday o kaydı
-- HİÇ göremez. Örnek: "RWTH Women in Engineering" mühendisliğin tamamına
-- açıkken kayıtta 10 slug vardı; mekatronik öğrencisi bu bursu göremiyordu.
-- Bu yüzden aile kısıtlı kayıtlar yeni kardeş slug'larla GENİŞLETİLİYOR.
-- Hiçbir kayıt daraltılmıyor: her update yalnız ekleme yapar.
--
-- AYRICA iki kayıtta dayanaksız bölüm kısıtı bulundu (kendi uygunluk
-- notlarında bölüm şartı yok) → {all}'a çekildi; biri de uyruk şartı için
-- insan denetimine bayraklandı.
--
-- IDEMPOTENT: evet (distinct + union). GERİ ALINABİLİR Mİ: evet, ama eski
--   dar listeler zaten hatalıydı — geri almak hatayı geri getirir.
-- ============================================================

begin;

-- RWTH Women in Engineering — mühendisliğin tamamı
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['materials_engineering', 'mechatronics', 'mining_engineering', 'geological_engineering', 'geomatics_engineering', 'energy_engineering', 'nuclear_engineering', 'automotive_engineering', 'manufacturing_engineering', 'textile_engineering', 'robotics', 'biotechnology', 'bioengineering']) order by 1))
where id = 'd071f66c-c3e5-4fee-906c-9629083ca472' and not ('all' = any(target_fields));

-- CERN — fizik/mühendislik/bilişim/matematik
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['nuclear_engineering', 'materials_engineering', 'mechatronics', 'robotics', 'artificial_intelligence', 'cybersecurity']) order by 1))
where id = '562bb9de-ae68-499d-90a6-b258b8a4e112' and not ('all' = any(target_fields));

-- IAESTE — teknik dalların tamamı (civil/endüstri/kimya müh. eksikti)
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['civil_engineering', 'industrial_engineering', 'chemical_engineering', 'environmental_engineering', 'materials_engineering', 'mechatronics', 'energy_engineering', 'food_engineering', 'biotechnology', 'robotics', 'physics', 'mathematics', 'biology']) order by 1))
where id = 'd49e945f-e2f3-4ddd-a484-928ed5064c4f' and not ('all' = any(target_fields));

-- DLR — havacılık, enerji, ulaşım araştırmaları
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['robotics', 'materials_engineering', 'energy_engineering', 'artificial_intelligence', 'mechatronics', 'automotive_engineering']) order by 1))
where id = '40e813d4-e29a-4402-b7bc-89e951deed7b' and not ('all' = any(target_fields));

-- DAAD Konrad Zuse AI okulu
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['artificial_intelligence', 'robotics']) order by 1))
where id = 'e7c80151-c137-40c9-be3b-703414b1fc07' and not ('all' = any(target_fields));

-- DAAD SECAI AI okulu
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['artificial_intelligence', 'robotics']) order by 1))
where id = '6abcbdfc-d51e-478b-938e-59f89287d579' and not ('all' = any(target_fields));

-- KPMG veri analitiği stajı
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['information_systems', 'artificial_intelligence', 'accounting', 'actuarial_science']) order by 1))
where id = '0a96473d-69e0-42d7-bf5a-09c20026bcba' and not ('all' = any(target_fields));

-- ADB Visiting Fellow — kalkınma/kamu yönetimi
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['development_studies', 'public_administration', 'international_trade']) order by 1))
where id = 'f99d5011-3fac-45ce-8c06-06968e19044d' and not ('all' = any(target_fields));

-- BM stajı — çok geniş disiplin yelpazesi
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['public_administration', 'social_work', 'development_studies', 'peace_conflict_studies', 'gender_studies', 'migration_studies', 'translation', 'statistics', 'data_science']) order by 1))
where id = 'da4d33a4-7b19-4c9d-b367-90704c94cd5c' and not ('all' = any(target_fields));

-- AP Schuman stajı
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['translation', 'public_administration', 'area_studies', 'journalism']) order by 1))
where id = 'a09adede-289c-4cc9-8b7b-bd7efed9dac3' and not ('all' = any(target_fields));

-- Gerda Henkel — tarihsel beşeri bilimler
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['archaeology', 'art_history', 'theology', 'area_studies']) order by 1))
where id = '1918f15a-ce77-414b-891a-ea02bd52176c' and not ('all' = any(target_fields));

-- Gerda Henkel — tarihsel beşeri bilimler
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['archaeology', 'art_history', 'theology', 'area_studies']) order by 1))
where id = 'ceef4e11-3925-49fb-84f9-c8c1d907d220' and not ('all' = any(target_fields));

-- Herder — Doğu-Orta Avrupa tarih/kültür
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['area_studies', 'art_history', 'geography']) order by 1))
where id = '7fa0e988-5b86-49d5-a757-022221102d8d' and not ('all' = any(target_fields));

-- Leibniz IEG Mainz — Avrupa ve din tarihi
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['theology', 'area_studies']) order by 1))
where id = 'bc4c7fb7-deb0-4080-8b72-562fc0ad6f33' and not ('all' = any(target_fields));

-- Open Society — sosyal bilimler geneli
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['sociology', 'political_science', 'public_administration', 'gender_studies', 'migration_studies', 'development_studies', 'social_work', 'peace_conflict_studies', 'criminology', 'anthropology']) order by 1))
where id = 'ca0097f9-a6e1-4782-b9af-cd38d0d9e60a' and not ('all' = any(target_fields));

-- DAAD Mimarlık
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['interior_architecture', 'landscape_architecture', 'conservation_restoration']) order by 1))
where id = 'b1a9e2b9-8be3-4eff-b02f-4647a115a990' and not ('all' = any(target_fields));

-- DAAD Müzik
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['performing_arts']) order by 1))
where id = 'de279f9a-2a5c-4e3d-94ef-c955042f27ea' and not ('all' = any(target_fields));

-- DAAD Güzel Sanatlar / Tasarım / Film
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['photography', 'animation', 'fashion_design', 'new_media']) order by 1))
where id = 'b8e8815f-9929-4cfa-8ec3-468f4f18cb1c' and not ('all' = any(target_fields));

-- Veri gazeteciliği
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['new_media']) order by 1))
where id = 'ea4e6e08-415c-4ea4-8dc5-0db4977c30a5' and not ('all' = any(target_fields));

-- Kadın gazeteciler fonu
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['new_media']) order by 1))
where id = 'c0c689a4-5076-441d-92df-47474d1c93b4' and not ('all' = any(target_fields));

-- Weidenfeld gazetecilik
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['new_media']) order by 1))
where id = 'bc722162-0b1f-4859-9f93-825fe0ae13be' and not ('all' = any(target_fields));

-- Kurt Schork gazetecilik
update public.opportunities set target_fields = (
  select array(select distinct unnest(target_fields || array['new_media']) order by 1))
where id = '737043f7-5624-4e1c-82f9-e15d82e403e5' and not ('all' = any(target_fields));

-- ── Dayanaksız bölüm kısıtları ──────────────────────────────────
-- ETH Mükemmellik Bursu: kaydın kendi uygunluk notu "ETH Master programına
-- kabul almış olmak" diyor; bölüm şartı yok. Burs ETH'nin BÜTÜN master
-- programlarına açık. 9 slug'lık liste biyoloji/eczacılık/işletme gibi
-- bölümlerdeki adayı hatalı eliyordu.
update public.opportunities set target_fields = array['all']
where id = 'd57d66d8-6654-4269-9280-504c4596019d';

-- Erasmus+ KA1 personel hareketliliği: uygunluk notu "kurum çalışanı veya
-- gönüllü uzman olmak" — disiplin şartı yok. {education,ngo,youth_work}
-- kısıtı diğer bütün bölümlerdeki personeli eliyordu.
update public.opportunities set target_fields = array['all']
where id = 'f3660ac7-32d6-4e23-8846-76cf28e88c30';

-- ── İnsan denetimi gereken uyruk şartı ──────────────────────────
-- ADB Visiting Fellow: uygunluk notu "Be a national of one of ADB's members"
-- diyor ve Türkiye ADB üyesi DEĞİL. Yani kayıt şu an TR kullanıcısına hatalı
-- görünüyor. 68 ülkelik üye listesini ezberden yazmak yeni hata üretir;
-- karar insana bırakılıyor (/admin/review kuyruğuna düşer).
update public.opportunities
set review_flag = 'uyruk_belirsiz',
    review_note = 'Uygunluk notu ADB üyesi ülke vatandaşlığı şartı koyuyor; '
                  'Türkiye ADB üyesi değil. eligible_citizenships=all olduğu '
                  'için TR kullanıcısına gösteriliyor. Resmî üye listesiyle '
                  'doldurulmalı ya da kayıt pasifleştirilmeli.',
    review_flagged_at = now()
where id = 'f99d5011-3fac-45ce-8c06-06968e19044d'
  and review_flag is null;

-- ── Son başvuru tarihi geçmiş aktif kayıtlar ────────────────────
-- Bunlar aramada zaten görünmüyordu (match_opportunities deadline süzüyor)
-- ama is_active=true durdukları için sayaçları ve denetim kuyruğunu
-- kirletiyorlardı. Ajanın --audit-opportunities adımının yaptığı işin
-- birebir aynısı: tarihi geçmiş = pasif.
update public.opportunities
set is_active = false, last_verified_at = now()
where is_active and deadline is not null and deadline < current_date;

commit;
