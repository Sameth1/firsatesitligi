-- ============================================================
-- 006 · 10 yeni fırsat programı (manuel ekleme)
-- Supabase Dashboard → SQL Editor → çalıştır
-- ============================================================

INSERT INTO opportunities (
  title, official_url, deadline, deadline_notes,
  host_countries, target_countries, eligible_citizenships,
  target_fields, study_level, age_min, age_max,
  language_requirement, eligibility_notes,
  funding_type, funding_notes,
  category_id, is_featured, is_active, is_verified
) VALUES

-- 1. MEXT – Japonya Hükümeti Bursu
(
  'MEXT Bursu — Japonya',
  'https://www.studyinjapan.go.jp/en/smap-stopj-applications-scholarships.html',
  '2027-06-30',
  'Türkiye Japonya Büyükelçiliği üzerinden Mayıs–Haziran aylarında başvurulur',
  ARRAY['JP'],
  ARRAY['TR'],
  ARRAY['TR'],
  ARRAY['all'],
  ARRAY['bachelor', 'master', 'phd'],
  18, 35,
  'Japonca veya İngilizce',
  'Japonya Büyükelçiliği kanalıyla başvurulur. Lisans, yüksek lisans ve doktora programları için ayrı kategoriler mevcuttur.',
  'full',
  'Uçak bileti + aylık ¥117,000–144,000 harçlık + öğrenim ücreti muafiyeti',
  'c492a2d8-04fe-42f4-bbe7-a1dfb703d1df',
  false, true, true
),

-- 2. Kore Hükümeti Bursu (GKS / KGSP)
(
  'Kore Hükümeti Bursu (GKS) — Güney Kore',
  'https://www.studyinkorea.go.kr/en/sub/gks/allnew_korea.do',
  '2027-03-31',
  'Büyükelçilik veya üniversite kanalıyla Şubat–Mart ayında başvurulur',
  ARRAY['KR'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['bachelor', 'master', 'phd'],
  18, 34,
  'Korece (TOPIK) veya İngilizce',
  '147 ülkeden başvuru alınır. Büyükelçilik ya da doğrudan üniversite kanalıyla başvurulabilir. 1 yıllık hazırlık Korece kursu dahildir.',
  'full',
  'Aylık ₩900,000–1,000,000 harçlık + öğrenim ücreti + uçak bileti + sağlık sigortası',
  'c492a2d8-04fe-42f4-bbe7-a1dfb703d1df',
  false, true, true
),

-- 3. İsveç Enstitüsü Bursu (SI)
(
  'İsveç Enstitüsü Bursu (SI) — İsveç',
  'https://si.se/en/apply/scholarships/sweden-institute-scholarships-for-global-professionals/',
  '2027-02-10',
  'Her yıl Şubat başında başvurular kapanır',
  ARRAY['SE'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['master'],
  NULL, NULL,
  'İngilizce (IELTS 6.5+)',
  'En az 3,000 saat iş deneyimi gerektirir. Liderlik potansiyeli ve Türkiye ile İsveç arasında köprü kurma hedefi önem taşır.',
  'full',
  'Aylık 11,000 SEK + öğrenim ücreti + seyahat katkısı + sağlık sigortası',
  'c492a2d8-04fe-42f4-bbe7-a1dfb703d1df',
  false, true, true
),

-- 4. Stipendium Hungaricum – Macaristan
(
  'Stipendium Hungaricum — Macaristan',
  'https://stipendiumhungaricum.hu',
  '2027-01-16',
  'Her yıl Ocak ayı ortasında kapanır; YÖK üzerinden başvurulur',
  ARRAY['HU'],
  ARRAY['TR'],
  ARRAY['TR'],
  ARRAY['all'],
  ARRAY['bachelor', 'master', 'phd'],
  NULL, NULL,
  'İngilizce veya Macarca',
  'Türkiye kota ülkeler arasındadır. Başvurular YÖK ve Macaristan Büyükelçiliği üzerinden yapılır. Çok geniş program ve üniversite seçeneği sunar.',
  'full',
  'Öğrenim ücreti muafiyeti + aylık HUF 43,700–140,000 harçlık + yurt veya konut katkısı',
  'c492a2d8-04fe-42f4-bbe7-a1dfb703d1df',
  true, true, true
),

-- 5. Holland Scholarship – Hollanda
(
  'Holland Scholarship — Hollanda',
  'https://www.studyinholland.nl/finances/grants-and-scholarships/holland-scholarship',
  '2027-02-01',
  'Her yıl Ocak–Şubat arasında kapanır; ilgili Hollanda üniversitesi üzerinden başvurulur',
  ARRAY['NL'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['bachelor', 'master'],
  NULL, NULL,
  'İngilizce (IELTS/TOEFL)',
  'AB/AEA üyesi olmayan ülkelerden Hollanda üniversitelerine başvuran öğrenciler için. Başvuruyu ilgili üniversite üzerinden yaparsın.',
  'partial',
  '€5,000 tek seferlik hibe (ilk yıl için)',
  'c492a2d8-04fe-42f4-bbe7-a1dfb703d1df',
  false, true, true
),

-- 6. ETH Zürich Excellence Scholarship – İsviçre
(
  'ETH Zürich Mükemmellik Bursu — İsviçre',
  'https://ethz.ch/en/the-eth-zurich/education/excellence-scholarship.html',
  '2026-12-15',
  'Aralık ayı ortasında kapanır (sonraki akademik yıl için)',
  ARRAY['CH'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['computer_science', 'electrical_engineering', 'mechanical_engineering', 'architecture', 'mathematics', 'physics', 'chemistry', 'data_science', 'environmental_science'],
  ARRAY['master'],
  NULL, NULL,
  'İngilizce veya Almanca',
  'ETH Zürich Master programına kabul almış olmak gerekmektedir. Üstün akademik başarı ve araştırma deneyimi beklenir.',
  'full',
  'Aylık CHF 12,000 + öğrenim ücreti muafiyeti',
  'c492a2d8-04fe-42f4-bbe7-a1dfb703d1df',
  false, true, true
),

-- 7. CERN Yaz Öğrencisi Programı – İsviçre
(
  'CERN Yaz Öğrencisi Programı — İsviçre',
  'https://home.cern/students-educators/summer-student-programme',
  '2027-01-27',
  'Başvurular her yıl Ocak ayı sonunda kapanır',
  ARRAY['CH'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['physics', 'computer_science', 'electrical_engineering', 'mathematics', 'mechanical_engineering'],
  ARRAY['bachelor', 'master'],
  18, 31,
  'İngilizce',
  'Fizik, bilgisayar veya mühendislikte en az 3 yıl lisans eğitimi tamamlanmış olmalıdır. 8–13 haftalık program; CERN üye ülke şartı aranmaz.',
  'stipend',
  'Günlük 91 CHF harçlık + konaklama katkısı + gidiş-dönüş uçak bileti',
  '2db63ccc-3cf2-4659-90f6-f8b799559cfe',
  true, true, true
),

-- 8. Avrupa Parlamentosu Schuman Stajı
(
  'Avrupa Parlamentosu Schuman Stajı — Brüksel/Lüksemburg',
  'https://www.europarl.europa.eu/at-your-service/en/be-part-of-it/traineeships',
  NULL,
  'Şubat dönemi için Eylül, Ekim dönemi için Nisan başında başvurular kapanır',
  ARRAY['BE', 'LU'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['law', 'international_relations', 'political_science', 'economics', 'communication', 'linguistics'],
  ARRAY['bachelor', 'master'],
  NULL, NULL,
  'İngilizce, Fransızca veya Almanca',
  'Üniversite diploması veya en az 3 yıl yükseköğrenim tamamlanmış olmalıdır. 5 aylık ücretli staj; Şubat ve Ekim''de başlayan iki dönem mevcuttur.',
  'stipend',
  'Aylık ~€1,400 harcırah',
  '2db63ccc-3cf2-4659-90f6-f8b799559cfe',
  false, true, true
),

-- 9. IAESTE Uluslararası Teknik Staj
(
  'IAESTE Uluslararası Teknik Staj',
  'https://iaeste.org/students/',
  NULL,
  'Türkiye için başvurular genellikle Aralık–Şubat arasında yapılır',
  ARRAY['*'],
  ARRAY['TR'],
  ARRAY['TR'],
  ARRAY['computer_science', 'electrical_engineering', 'mechanical_engineering', 'chemistry', 'agriculture', 'architecture'],
  ARRAY['bachelor', 'master'],
  NULL, NULL,
  'İngilizce veya ev sahibi ülke dili',
  'IAESTE Türkiye üzerinden başvurulur. 50''den fazla ülkede teknik alanda ücretli staj imkânı sunar.',
  'stipend',
  'Konaklama + yerel ulaşım + haftalık harçlık (ülkeye göre değişir)',
  '2db63ccc-3cf2-4659-90f6-f8b799559cfe',
  false, true, true
),

-- 10. Birleşmiş Milletler Staj Programı
(
  'Birleşmiş Milletler Staj Programı',
  'https://www.un.org/en/about-us/internships',
  NULL,
  'Sürekli açık; pozisyona göre 2–3 ay öncesinde başvurulur',
  ARRAY['US', 'CH', 'AT', 'KE'],
  ARRAY['all'],
  ARRAY['all'],
  ARRAY['international_relations', 'law', 'economics', 'public_health', 'communication', 'human_rights', 'environmental_science'],
  ARRAY['master', 'phd'],
  NULL, NULL,
  'İngilizce veya Fransızca',
  'Yüksek lisans öğrencisi veya son bir yıl içinde mezun olmuş olmak gerekmektedir. New York, Cenevre, Viyana ve Nairobi''de pozisyonlar mevcuttur.',
  'partial',
  'Çoğu pozisyon ücretsizdir; bazı programlarda günlük harcırah ödenir',
  '2db63ccc-3cf2-4659-90f6-f8b799559cfe',
  false, true, true
);
