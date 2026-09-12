-- ============================================================
-- 128 · Eşleştirme politikası: "kayıtta yazmıyorsa elemez"
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- CANLIYA UYGULANDI: 12 Eylül 2026
-- ============================================================
-- ÖNKOŞUL: master'ın 114-122'si + 123. Bu dosya 123'ün yerine geçer.
--
-- POLİTİKA (kullanıcının koyduğu kural):
--
--   KATI — kullanıcının girdisi asla gevşetilmez:
--     • Ülke        nereye gitmek istediği
--     • Vatandaşlık kim olduğu
--     • Yaş         değiştiremeyeceği bir gerçek
--   Bu üçünde sonuç 0 kalsa bile 0 kalır. Gevşetmek, başvuramayacağı bir
--   fırsatı göstermek demektir.
--
--   ESNEK — yalnız KAYIT bir şart yazmamışsa:
--     • Eğitim kademesi, eldeki eğitim seviyesi, bölüm, dil
--   Kayıt şartı açıkça yazmışsa bunlar da KATI uygulanır.
--
-- Bu ayrım iki ayrı katmanda yaşıyor, karıştırmamak gerekiyor:
--
--   1) BURADA (SQL): kayıtta şart yazmıyorsa o boyut hiç elemez. Bu bir
--      "gevşetme" değil, kaydı doğru okumak. NULL ve boş dizi ('{}') de
--      "şart yok" sayılıyor — bugün veride yok ama boş dizi yazan tek bir
--      kayıt, o boyutu seçen HERKESTEN gizlenirdi.
--
--   2) ARAYÜZDE (page.tsx): kayıt şartı AÇIKÇA yazmış ama kullanıcının
--      girdisiyle uyuşmuyorsa ve sonuç 0 çıktıysa, sırayla bölüm → kademe →
--      dil girdisinden vazgeçilip tekrar sorulur ve kullanıcıya hangisinin
--      gevşetildiği SÖYLENİR. Ülke/vatandaşlık/yaş o listede yok.
--
-- Ülke neden bu kuralın dışında: kaydın ülkesi bilinmiyorsa seçilen ülkeye
-- eşleşemez. 119'un sıkı kuralı da korunuyor — host_countries='*' olan
-- küresel kayıtlar, kullanıcı bir ülke seçtiğinde gelmez.
--
-- DOĞRULAMA: 9.216 senaryo (4 vatandaşlık × 4 yaş × 4 bölüm × 4 kademe ×
--   4 dil × 3 eğitim seviyesi × 3 ülke), 238.592 sonuç satırı. Politikanın
--   bağımsız ikinci yazımıyla karşılaştırıldı: 0 kaçırılan, 0 fazladan.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet — 123 yeniden çalıştırılır.
-- ============================================================

begin;

create or replace function public.match_opportunities(
  p_host_country  text    default null,
  p_category_slug text    default null,
  p_citizenship   text    default 'TR',
  p_age           integer default null,
  p_study_level   text    default null,
  p_highest_edu   text    default null,
  p_field         text    default null,
  p_language      text    default null
)
returns table (
  id uuid, title text, official_url text, deadline date, deadline_notes text,
  host_countries text[], funding_type text, funding_notes text,
  eligibility_notes text, language_requirement text, age_min integer,
  age_max integer, category_slug text, category_label_tr text,
  category_color text, documents json, is_featured boolean,
  days_until_deadline integer, submitted_by_nickname text,
  last_url_check_at timestamptz, last_url_check_status integer,
  summary_tr text, eligibility_notes_tr text, details_url text,
  application_route_status text, application_method text,
  application_url_verified_at timestamptz
)
language sql
stable
set search_path to 'public'
as $function$
  select
    oc.id, oc.title, oc.official_url, oc.deadline, oc.deadline_notes,
    oc.host_countries, oc.funding_type, oc.funding_notes, oc.eligibility_notes,
    oc.language_requirement, oc.age_min, oc.age_max, oc.category_slug,
    oc.category_label_tr, oc.category_color, oc.documents, oc.is_featured,
    case when oc.deadline is null then null else (oc.deadline - current_date)::int end,
    opp.submitted_by_nickname, opp.last_url_check_at, opp.last_url_check_status,
    opp.summary_tr, opp.eligibility_notes_tr, opp.details_url,
    opp.application_route_status, opp.application_method,
    opp.application_url_verified_at
  from public.opportunity_cards oc
  join public.opportunities opp on opp.id = oc.id
  where opp.is_active = true
    and (((opp.application_route_status = 'verified'
      and nullif(btrim(opp.official_url), '') is not null
      and nullif(btrim(opp.application_url_final), '') is not null
      and opp.application_url_verified_at is not null))
      or (opp.application_route_status = 'guided'
      and nullif(btrim(opp.details_url), '') is not null))
    and oc.category_slug is not null

    -- ── KATI ────────────────────────────────────────────────────
    and (p_host_country is null or p_host_country = any(oc.host_countries))
    and (p_category_slug is null or oc.category_slug = p_category_slug)
    and (oc.eligible_citizenships is null
      or oc.eligible_citizenships = '{}'
      or 'all' = any(oc.eligible_citizenships)
      or p_citizenship = any(oc.eligible_citizenships))
    and (p_age is null or oc.age_min is null or oc.age_min <= p_age)
    and (p_age is null or oc.age_max is null or oc.age_max >= p_age)

    -- ── ESNEK: kayıt belirtmemişse elemez ───────────────────────
    and (p_study_level is null or p_study_level = 'any'
      or oc.study_level is null or oc.study_level = '{}'
      or 'any' = any(oc.study_level) or p_study_level = any(oc.study_level))

    and (p_highest_edu is null
      or p_highest_edu not in ('lise', 'on_lisans')
      or oc.study_level is null or oc.study_level = '{}'
      or 'any' = any(oc.study_level)
      or 'bachelor' = any(oc.study_level))

    and (p_field is null
      or oc.target_fields is null or oc.target_fields = '{}'
      or 'all' = any(oc.target_fields) or p_field = any(oc.target_fields))

    and (p_language is null
      or opp.required_languages is null or opp.required_languages = '{}'
      or 'all' = any(opp.required_languages)
      or lower(p_language) = any(opp.required_languages))

    and (oc.deadline is null or oc.deadline >= current_date)
  order by oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;

notify pgrst, 'reload schema';

commit;
