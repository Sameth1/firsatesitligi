-- ============================================================
-- 118 · Uyruk listeleri (Georg Forster, ADB) + din şartlı kayıtların silinmesi
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- CANLIYA UYGULANDI: 11 Eylül 2026
-- ============================================================
--
-- A) GEORG FORSTER (3 kayıt) — eligible_citizenships dolduruldu
--    Humboldt Vakfı'nın kuralı programme information belgesinde açık:
--    "The list of developing countries is based on the information of the
--     Development Assistance Committee (DAC) of the OECD. The PR of China
--     and India have been excluded from this list."
--    Liste OECD'nin resmî PDF'inden çıkarıldı (DAC List of ODA Recipients,
--    effective for reporting on 2025 flows): 141 ülke → CN ve IN düşüldü → 139.
--    TÜRKİYE LİSTEDE VAR (DAC'ta "Türkiye", üst-orta gelir grubunda).
--    Yani bu kayıtlar TR kullanıcısına doğru gösteriliyordu; eksik olan,
--    listede olmayan ülkelerin vatandaşlarının bunları görmesiydi.
--
--    Eski `link_404` bayrağı da kaldırıldı: bağlantı denetimi 200 döndü.
--    Bu container'dan gelen 403'ler www2.daad.de'nin bot korumasından.
--
-- B) ADB VISITING FELLOW — ÖNCEKİ TESPİTİM YANLIŞTI
--    117'de "Türkiye ADB üyesi değil, kayıt TR kullanıcısına hatalı
--    görünüyor" diye bayraklamıştım. Yanlış: Türkiye 1991'den beri ADB üyesi
--    ve Aralık 2025'te bölgesel üye statüsüne geçti. Kayıt TR için DOĞRUYDU.
--    Yine de 'all' hatalı — şart ADB üyeliği. 69 üyenin kodu yazıldı
--    (50 bölgesel + 19 bölge dışı; İsrail Eylül 2024'te 69. üye oldu).
--
-- C) DİN ŞARTLI KAYITLAR SİLİNDİ — platform politikası
--    Başvuranın dinine göre ayrım yapan fırsatlar yayınlanmıyor. Silinen 6
--    kayıt (geri getirilmek istenirse bu blok kaynak olarak kullanılabilir):
--
--      8af885fd-1626-4e62-8720-7f7a94df5d61
--        "Agora Fellowship in African Countries for Christians 2026"
--        forms.office.com/… · başlıkta "for Christians"
--      c18b8439-dc72-4ff2-87f6-c8b4ec30bab2
--        "Catholic Academic Exchange Service (KAAD): Eastern Europe Programme"
--        daad.de/…detail=10000114 · "involved in the Church"
--      6bdaeafc-4d16-4b4c-afbf-8830346b4298
--        "Ernst Ludwig Ehrlich Studienwerk: Doctoral Scholarship"
--        daad.de/…detail=10000418 · "Jewish doctoral candidates"
--      185c908e-3ad3-4963-9e8a-61e0cc8668d0
--        "Evangelisches Studienwerk: Scholarship for Students"
--        daad.de/…detail=10000117 · "Applicants must be of protestant faith"
--      c4438a2a-63d6-4dbe-bbb5-a8e954bd39b6
--        "Hanns Seidel Foundation: PhD scholarships"
--        daad.de/…detail=10000132 · "uphold Christian social values"
--      c77c3eb4-e1b8-4485-9bb4-ce76860d2494
--        "Konrad Adenauer Stiftung — Almanya Bursu" (zaten pasifti)
--        kas.de/… · "Hristiyan-demokrat değerlere yakın profiller tercih edilir"
--        SINIR KAYIT: "Hristiyan-demokrat" siyasi bir aile adı, dinî bir
--        üyelik testi değil. Kural gereği silindi; geri istenirse tartışılır.
--
--    Kaynak submission'lar da reddedildi ve ajan hafızasına 'din_sarti'
--    emsali yazıldı (submission_review_events → remember_human_rejection
--    trigger'ı → agent_memories). Böylece aynı kaynaklardan (daad-bot,
--    youthop-bot) gelecek benzer öneriler bu emsalle değerlendirilir.
--
--    Ajan tarafında da kural kodlandı (validate_submissions.py):
--      • prompta `din_sarti` alanı eklendi; true → koşulsuz RED
--      • din geçen ama model "şart yok" diyen kayıtlar otomatik onaydan
--        çıkarılıp insana yönlendiriliyor (religion_hint_blockers)
--      • prompt, "o dini ÇALIŞMAK" ile "o dine MENSUP OLMAK" ayrımını
--        açıkça anlatıyor — ilahiyat/İslam araştırmaları bursu engellenmez
--
-- IDEMPOTENT: A ve B evet. C'deki delete tekrar çalıştırılırsa 0 satır.
-- GERİ ALINABİLİR Mİ: A/B evet. C hayır — kayıtlar silindi, yukarıdaki
--   künyeden yeniden girilmeleri gerekir.
-- ============================================================
--
begin;

-- ─── A) Georg Forster: DAC listesi eksi CN, IN (139 ülke) ────────
update public.opportunities
set eligible_citizenships = array[
 'AF','AL','AM','AO','AR','AZ','BA','BD','BF','BI','BJ','BO','BR','BT','BW','BY','BZ','CD','
 CF','CG','CI','CM','CO','CR','CU','CV','DJ','DM','DO','DZ','EC','EG','ER','ET','FJ','FM','G
 A','GD','GE','GH','GM','GN','GQ','GT','GW','GY','HN','HT','ID','IQ','IR','JM','JO','KE','KG
 ','KH','KI','KM','KP','KZ','LA','LB','LC','LK','LR','LS','LY','MA','MD','ME','MG','MH','MK'
 ,'ML','MM','MN','MR','MS','MU','MV','MW','MX','MY','MZ','NA','NE','NG','NI','NP','NR','NU',
 'PA','PE','PG','PH','PK','PS','PW','PY','RS','RW','SB','SD','SH','SL','SN','SO','SR','SS','
 ST','SV','SY','SZ','TD','TG','TH','TJ','TK','TL','TM','TN','TO','TR','TV','TZ','UA','UG','U
 Z','VC','VE','VN','VU','WF','WS','XK','YE','ZA','ZM','ZW'],
    review_flag = null,
    review_note = 'Uyruk listesi dolduruldu: OECD DAC ODA alici listesi (2025 flows) eksi Cin ve Hindistan = 139 ulke. Humboldt bu kurali resmi programme information belgesinde yaziyor. Turkiye listede var. Eski link_404 bayragi kaldirildi: baglanti denetimi 200 dondu, 403lar www2.daad.de bot korumasindan.',
    review_flagged_at = now()
where id in ('3e2e074a-5a04-446c-b68b-b11e6f833036',
             'c7028c7a-cbbc-440d-9c3a-927422e0abb9',
             'd063768b-ba6d-4eb2-8a6f-013d55fe2498');

-- ─── B) ADB: 69 üye ─────────────────────────────────────────────
update public.opportunities
set eligible_citizenships = array[
 'AF','AM','AT','AU','AZ','BD','BE','BN','BT','CA','CH','CK','CN','DE','DK','ES','FI','FJ','
 FM','FR','GB','GE','HK','ID','IE','IL','IN','IT','JP','KG','KH','KI','KR','KZ','LA','LK','L
 U','MH','MM','MN','MV','MY','NL','NO','NP','NR','NU','NZ','PG','PH','PK','PT','PW','SB','SE
 ','SG','TH','TJ','TL','TM','TO','TR','TV','TW','US','UZ','VN','VU','WS'],
    review_flag = null,
    review_note = 'Uyruk listesi dolduruldu: ADB''nin 69 uyesi. Turkiye UYEDIR (1991, 2025''ten beri bolgesel uye) - onceki "Turkiye uye degil" notu hataliydi ve duzeltildi.',
    review_flagged_at = now()
where id = 'f99d5011-3fac-45ce-8c06-06968e19044d';

-- ─── C) Din şartlı kayıtlar ─────────────────────────────────────
-- Önce ajan hafızasına red emsali (trigger: remember_human_rejection)
insert into public.submission_review_events
  (submission_id, actor_type, decision, reason_code, reason_text,
   source_nickname, category_slug, submission_snapshot)
select s.id, 'human', 'rejected', 'din_sarti',
       'Basvuru kosulu basvuranin dinine/inancina sart kosuyor. Platform politikasi: bu kayitlar yayinlanmaz.',
       coalesce(s.submitter_nickname, 'manual/unknown'),
       coalesce(s.category_slug, 'unknown'),
       to_jsonb(s)
from public.submissions s
where s.id in ('5f05816b-663a-4c66-ad41-c28d0844b35b','f05a1731-6fb8-448d-87dc-cbb8e22dc2be',
 'bdb89c23-ffcf-417e-84b3-88be2fc312dc','0091c454-93e7-456d-861a-412190541275',
 'e963c5ef-e9c5-4723-8f37-eb1a9cb30286');

update public.submissions
set status = 'rejected',
    reviewed_at = now(),
    admin_note = 'Din sarti iceren firsat - platform politikasi geregi reddedildi.',
    created_opportunity_id = null,
    opportunity_id = null
where id in ('5f05816b-663a-4c66-ad41-c28d0844b35b','f05a1731-6fb8-448d-87dc-cbb8e22dc2be',
 'bdb89c23-ffcf-417e-84b3-88be2fc312dc','0091c454-93e7-456d-861a-412190541275',
 'e963c5ef-e9c5-4723-8f37-eb1a9cb30286');

delete from public.documents
where opportunity_id in ('8af885fd-1626-4e62-8720-7f7a94df5d61','c18b8439-dc72-4ff2-87f6-c8b4ec30bab2',
 '6bdaeafc-4d16-4b4c-afbf-8830346b4298','185c908e-3ad3-4963-9e8a-61e0cc8668d0',
 'c4438a2a-63d6-4dbe-bbb5-a8e954bd39b6','c77c3eb4-e1b8-4485-9bb4-ce76860d2494');

delete from public.opportunities
where id in ('8af885fd-1626-4e62-8720-7f7a94df5d61','c18b8439-dc72-4ff2-87f6-c8b4ec30bab2',
 '6bdaeafc-4d16-4b4c-afbf-8830346b4298','185c908e-3ad3-4963-9e8a-61e0cc8668d0',
 'c4438a2a-63d6-4dbe-bbb5-a8e954bd39b6','c77c3eb4-e1b8-4485-9bb4-ce76860d2494');

commit;
