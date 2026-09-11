-- ============================================================
-- 109 · eligible_citizenships: yanlış "herkese açık" kayıtlarının düzeltilmesi
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- SORUN (ölçüldü):
--   Aktif 141 fırsatın 135'inde eligible_citizenships = {all}. Yani "TR" diye
--   arayan kullanıcıya, yalnız Çin/Filistin/Yemen/Afrika vatandaşlarına açık
--   programlar da çıkıyor. match_opportunities'teki filtre DOĞRU çalışıyor:
--
--     'all' = any(oc.eligible_citizenships) or p_citizenship = any(...)
--
--   Sorun veride: bu kolonu DOLDURAN hiçbir yol yok. Formda alan yok,
--   scraper'lar çıkarmıyor, approve_submission ise INSERT'te
--   `array['all']::text[]` diye SABİT yazıyor. Yani her kayıt tanımı gereği
--   "herkese açık" doğuyor. (Kaynak sebep 107'de kapatılıyor.)
--
-- BU DOSYA NE YAPIYOR:
--   Yalnızca KANITI OLAN kayıtları düzeltir. Her satırın gerekçesi resmî
--   sayfadan okunmuştur (aşağıda tek tek yazılı). Emin olunamayanlar
--   değiştirilmez, 102'deki inceleme kuyruğuna 'uyruk_belirsiz' olarak
--   düşer — admin paneli → "Belirsizler".
--
-- IDEMPOTENT: evet (where koşulları mevcut değeri kontrol ediyor).
-- GERİ ALINABİLİR Mİ: evet — ilgili id'lerde eligible_citizenships tekrar
--   array['all'] yapılırsa eski davranış döner.
-- ============================================================

begin;

comment on column public.opportunities.eligible_citizenships is
  'Bu fırsata başvurabilen UYRUKLAR (ISO 3166-1 alfa-2). {all} = uyruk şartı '
  'yok. match_opportunities yalnız ''all'' veya kullanıcının uyruğu listede '
  'varsa kaydı döndürür. Yanlışlıkla {all} bırakmak, kaydı başvuramayacak '
  'kullanıcılara göstermek demektir — emin değilsen {all} yerine '
  'review_flag=''uyruk_belirsiz'' kullan.';

-- ─── 1) Kanıtlı daraltmalar ─────────────────────────────────────

-- DAAD-K.C.Wong Postdoc Fellowships
-- Kaynak: "Applicants must be citizens of the People's Republic of China
--          based in Mainland China" (daad.de detail=50015446)
update public.opportunities
set eligible_citizenships = array['CN']
where id = 'ce395c6c-a9e0-4b58-b4d5-beaf783c5ea1'
  and eligible_citizenships = array['all'];

-- "In-Country Palestinian Territories"
-- Kaynak sayfanın gerçek başlığı: "In-Country Scholarships for Postgraduate
-- Studies for PALESTINIANS in the Palestinian Territories (West Bank)".
-- Kayıttaki başlık da eksik kaydedilmiş, birlikte düzeltiliyor.
update public.opportunities
set eligible_citizenships = array['PS'],
    title = 'In-Country Scholarships for Postgraduate Studies for Palestinians in the Palestinian Territories (West Bank)'
where id = 'a8473830-489a-474e-8ba8-a30794fd4481'
  and eligible_citizenships = array['all'];

-- "Third Country Scholarships for Postgraduate Studies for Students from"
-- Başlık yarıda kesilmiş; kaynak sayfanın gerçek başlığı:
-- "In-Region Scholarships for Postgraduate Studies for YEMENIS in Jordan".
-- Kullanıcının "Ürdün'e özel kayıt çıkıyor" dediği kayıt tam olarak budur.
update public.opportunities
set eligible_citizenships = array['YE'],
    title = 'In-Region Scholarships for Postgraduate Studies for Yemenis in Jordan'
where id = '77111d1f-5131-47c2-b40d-75df6ee8bc1a'
  and eligible_citizenships = array['all'];

-- DBU (Alman Federal Çevre Vakfı) Orta/Doğu Avrupa bursu
-- Kaynak, uygun ülkeleri TEK TEK sayıyor ve Türkiye listede YOK:
-- Arnavutluk, Bosna-Hersek, Bulgaristan, Çekya, Hırvatistan, Estonya,
-- Macaristan, Kosova, Letonya, Litvanya, Kuzey Makedonya, Moldova,
-- Karadağ, Polonya, Romanya, Sırbistan, Slovakya, Slovenya, Ukrayna.
update public.opportunities
set eligible_citizenships = array['AL','BA','BG','CZ','HR','EE','HU','XK','LV',
                                  'LT','MK','MD','ME','PL','RO','RS','SK','SI','UA']
where id = 'fe611f1b-f280-4e73-a893-0438fba1c36e'
  and eligible_citizenships = array['all'];

-- Afrika Birliği üyesi ülke vatandaşlarına açık üç kayıt.
--   • African Union Internship — "Internship Program for citizens of AU Member States"
--   • Nelson Mandela Essay Prize — "Open to citizens of African countries"
--   • Afreximbank Internship — "nationals of the Bank's member countries"
--     (Afreximbank üyeleri Afrika devletleridir; Türkiye üye değil)
update public.opportunities
set eligible_citizenships = array[
  'DZ','AO','BJ','BW','BF','BI','CV','CM','CF','TD','KM','CG','CD','CI','DJ',
  'EG','GQ','ER','SZ','ET','GA','GM','GH','GN','GW','KE','LS','LR','LY','MG',
  'MW','ML','MR','MU','MA','MZ','NA','NE','NG','RW','ST','SN','SC','SL','SO',
  'ZA','SS','SD','TZ','TG','TN','UG','ZM','ZW','EH']
where id in (
  '164e48e7-78cb-4958-a24f-e34b56132b93',  -- African Union Internship Program
  '700ed165-b09d-4929-bb85-1c4afd05d815',  -- Nelson Mandela Essay Prize
  'c7f0f575-73fd-4f71-bbc5-911bc4877e85'   -- Afreximbank Internship
)
and eligible_citizenships = array['all'];

-- ─── 2) Kanıtlı GENİŞLETME (yanlış {all} değil ama eksik bilgi) ──
-- Jean Monnet: kaydın kendi metni uygun uyrukları açıkça yazıyor —
-- "citizens of an EU member state, Turkey or an IPA Beneficiary Country".
-- {all} bırakmak TR'li kullanıcıyı etkilemiyor ama Türkiye'den arayan
-- başka uyruklu (ör. Suriyeli) bir kullanıcıya yanlış sonuç veriyordu.
update public.opportunities
set eligible_citizenships = array[
  'AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT',
  'LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE',   -- AB 27
  'TR','AL','BA','XK','ME','MK','RS']                             -- TR + IPA
where id = 'a55df5a4-dec6-4ee3-b805-be8d01bcdb9e'
  and eligible_citizenships = array['all'];

-- ─── 3) Belirsizler: insana bırakılanlar ────────────────────────

-- Humboldt Georg Forster (iki kayıt): "gelişmekte olan / geçiş ülkesi
-- vatandaşı" şartı var ama uygun ülke listesi ayrı bir sayfada ve
-- kayıtlardaki resmî link BUGÜN 404 dönüyor (ikisi de doğrulandı).
-- Türkiye'nin listede olup olmadığı kaynaktan teyit edilemedi.
update public.opportunities
set review_flag = 'uyruk_belirsiz',
    review_note = 'Şart: "citizen of a developing or transition country" — uygun ülke '
               || 'listesi ayrı sayfada ve kayıttaki resmî link 404 veriyor, Türkiye''nin '
               || 'listede olup olmadığı doğrulanamadı. Otomatik daraltılmadı. Önce linki '
               || 'güncelle, sonra listeye bakıp uyruğu gir ya da kaydı kapat.',
    review_flagged_at = now()
where id in (
  '3e2e074a-5a04-446c-b68b-b11e6f833036',  -- Georg Forster (experienced)
  'c7028c7a-cbbc-440d-9c3a-927422e0abb9'   -- Georg Forster (postdoc)
)
and review_flag is distinct from 'uyruk_belirsiz';

-- Bundestag IPS: "nationality of one of the participating countries" —
-- kaynak sayfa yalnız "50 nations" diyor, listeyi vermiyor.
update public.opportunities
set review_flag = 'uyruk_belirsiz',
    review_note = 'Şart: "katılımcı ülkelerden birinin vatandaşı olmak". Kaynak sayfa '
               || 'yalnız "50 ülke" diyor, listeyi yayımlamıyor; Türkiye''nin dâhil olup '
               || 'olmadığı doğrulanamadı. bundestag.de/ips üzerinden teyit edip uyruğu gir.',
    review_flagged_at = now()
where id = 'ef6edb37-bf64-465d-a3ac-b02858deaf33'
  and review_flag is distinct from 'uyruk_belirsiz';

-- Fondation Rainbow Bridge: "African and Asian Women" — Türkiye coğrafi
-- olarak kısmen Asya'da; kaynak sayfa (405) okunamadı.
update public.opportunities
set review_flag = 'uyruk_belirsiz',
    review_note = 'Program "Afrikalı ve Asyalı kadınlar" için. Türkiye kısmen Asya''da '
               || 'olduğu için otomatik eleme yapılmadı; kaynak sayfa da (HTTP 405) '
               || 'okunamadı. HEC sayfasından uygun ülke tanımını teyit et.',
    review_flagged_at = now()
where id = 'eb461e59-6763-416b-8ec1-655f5fb548c0'
  and review_flag is distinct from 'uyruk_belirsiz';

commit;
