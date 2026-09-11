-- ============================================================
-- 109 · Kanıtsız yaş sınırlarının temizlenmesi
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- SORUN: Yaş sınırı, kaydı SESSİZCE gizleyen tek filtredir — kullanıcı
--   "28 yaşındayım" der, uygun olduğu burs hiç görünmez ve bunu asla öğrenmez.
--   Aktif 141 kaydın 33'ünde yaş sınırı var; kaynak sayfa + kayıt metni tek tek
--   tarandığında 20'sinde bu sınırın HİÇBİR dayanağı olmadığı görüldü
--   (scraper'ın varsayılanı gibi duran age_max=30 / 35 kümeleri).
--
--   İki kayıtta ise dayanak, yazılı değerle ÇELİŞİYOR:
--     • Kore GKS: kayıtta 18-34, kaynakta "under 25 as of March 1" — sınır
--       programa (lisans/lisansüstü) göre değişiyor, tek aralıkla modellenemez.
--     • Türkiye Araştırma Bursu: kaynak "under 45 ... (PREFERABLY)" diyor —
--       tercih, şart değil. 44 yazmak 45 yaşındaki uygun adayı eliyor.
--
-- KURAL: Yaş sınırı yalnız kaynakta AÇIK ve TEK aralık olarak yazılıysa kalır.
--   Şüphe varsa sınır kaldırılır: kayıt herkese görünür, şart zaten kartın
--   "Kimler başvurabilir" metninde yazıyor.
--
-- DOKUNULMAYANLAR (kanıtı olanlar): Erasmus+ Gençlik Değişimi 13-30,
--   ESC gönüllülük 18-30, Bundestag IPS ≤29, Afreximbank 20-32,
--   Agora 22-40, IJP 28-40, Weidenfeld 18-40, Schwarzman 18-28 (programın
--   kendi kuralı), AIESEC / ESC staj 18-30.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet (değerler aşağıda yorumda).
-- ============================================================

begin;

-- ─── 1) Dayanağı olmayan yaş sınırları kaldırılıyor ─────────────
-- Parantez içinde silinen eski değer — geri almak istersen bu değerler.
update public.opportunities
set age_min = null, age_max = null
where id in (
  '749bf2eb-60a7-4e4d-9d30-1dac8ce71924',  -- Ford Philanthropy Fellowship (18-)
  'f3660ac7-32d6-4e23-8846-76cf28e88c30',  -- Erasmus+ KA1 Personel (18-)
  '56aabfbe-f902-4f9d-8c28-e8d6708eb0ea',  -- EED Stajyer (-30)
  '24bc7d5c-e773-4f79-be2a-ade0300612b1',  -- Yazılım Test Derneği Bursu (-30)
  '287848b3-4ff7-4b7d-b3fb-7197cf71cf1f',  -- SBW Berlin Scholarship (18-30)
  '539010fc-c65d-4c13-83a6-c123cef8c30b',  -- TEV Mesleki Ortaöğretim / LİSE (-30)
  '5c46ce38-c51e-413e-a500-bba83bc047b6',  -- Kahev Bursu (-30)
  'c3ae6a7f-9700-495a-a793-613a1a5da831',  -- Doğuş Otomotiv Staj (-30)
  'c4d4c3a5-b971-4313-9932-c7ad2d51153e',  -- Coca Cola Next Talent (-30)
  '562bb9de-ae68-499d-90a6-b258b8a4e112',  -- CERN Yaz Öğrencisi (18-31)
  '5989ccc5-01ac-41cd-83df-66c87edb4b58',  -- MEXT Japonya (18-35)
  '1e4b8c7d-cf3f-48f9-b8d4-3cf0e477d9c9',  -- TWAS-CUI Fellowship (-35)
  '950baf9a-892f-48bb-93d4-8446840a2555',  -- NGFP Fellowship (18-35)
  'a57d31d9-4a39-4697-9a36-0e434762ff8f',  -- Erasmus+ Öğrenci Değişimi (18-35)
  'e17cbc30-8345-4b02-aad5-b4aeb9e1ff86',  -- Kore GKS (18-34) — kaynakla çelişiyor
  'bfbf5caf-1673-43d1-b442-4fd16be4e2bd',  -- Türkiye Araştırma Bursu (-44) "preferably"
  '575d77f5-d5c9-490d-b496-e394e5d3e0ce'   -- Tekinder (-30) — sınır kademeye göre değişiyor
);

-- ─── 2) Dayanaksız aralık → programın resmî kuralı ──────────────
-- Erasmus+ Gençlik Değişimi'nin resmî yaş aralığı 13-30'dur. Kayıttaki 15-25
-- ilanda yazmıyor; 26 yaşındaki uygun bir genci eliyordu.
update public.opportunities
set age_min = 13, age_max = 30
where id = '5cc7d978-c750-455b-8ce3-9e3a4f3d171f'
  and age_min = 15 and age_max = 25;

commit;
