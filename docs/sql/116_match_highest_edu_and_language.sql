-- ============================================================
-- 116 · match_opportunities: ölü eğitim filtresi + ölü dil filtresi
-- Supabase Dashboard → SQL Editor → tek seferde çalıştır
-- ============================================================
-- ÖLÇÜLEN İKİ HATA (ikisi de "filtre var" görünüp hiçbir şey yapmıyordu):
--
-- 1) p_highest_edu parametre listesinde VARDI ama WHERE'de HİÇ kullanılmıyordu.
--    Form bu değeri gönderiyor, kullanıcı "en yüksek eğitim" seçiyor, sonuç
--    hiç değişmiyordu. Dahası: sonuç 0 çıkınca arayüz "En yüksek eğitim
--    filtresini gevşettik" diyordu — hiç uygulanmamış bir filtreyi.
--
-- 2) Dil filtresi her kaydı geçiriyordu. Kural şuydu:
--        ... or language_requirement ilike '%İngilizce%'
--    Ölçüm: aktif 141 kaydın 141'inde "İngilizce" geçiyor. Yani bu tek satır
--    yüzünden dil koşulu her zaman true idi; seçilen seviye sonucu hiç
--    etkilemiyordu.
--
-- YENİ DAVRANIŞ — yalnızca KANITLA ELEME. Kayıt ancak şu iki durumda düşer:
--   • Kullanıcı İngilizceyi "hiç bilmiyorum" dedi ve kayıt İngilizce istiyor,
--     kullanıcının sahip olduğu bir alternatif (Türkçe / beyan ettiği ev sahibi
--     ülke dili / "ev sahibi ülke dili" / "hedef dil") sunmuyorsa.
--   • Kayıt metninde İngilizce için AÇIK bir CEFR seviyesi yazıyor (ör.
--     "C1 İngilizce") ve kullanıcının beyan ettiği seviye bunun altındaysa.
--   Seviye yazmayan kayıt, seviye beyan etmeyen kullanıcı → eleme yok.
--
--   p_highest_edu yalnız lise/ön lisans için eler; o da sadece kaydın kademesi
--   tamamen yüksek lisans/doktora ise. Lisans mezunu için doktora ELENMEZ
--   (birçok ülkede lisanstan doğrudan doktora mümkün).
--
-- NEDEN İMZA DEĞİŞİYOR: p_english yeni parametre. Postgres'te parametre
--   eklemek overload yaratır (iki fonksiyon birden kalır, PostgREST hangisini
--   çağıracağını bilemez), bu yüzden eski sürüm aynı transaction içinde
--   düşürülüyor. Tek işlem olduğu için siteye kesinti yansımıyor.
--
-- IDEMPOTENT: evet. GERİ ALINABİLİR Mİ: evet — 093'teki tanım geri yüklenir.
-- ============================================================

begin;

drop function if exists public.match_opportunities(
  text, text, text, integer, text, text, text, text
);

create or replace function public.match_opportunities(
  p_host_country  text    default null,
  p_category_slug text    default null,
  p_citizenship   text    default 'TR',
  p_age           integer default null,
  p_study_level   text    default null,
  p_highest_edu   text    default null,
  p_field         text    default null,
  p_language      text    default null,
  p_english       text    default null
)
returns table (
  id uuid, title text, official_url text, deadline date, deadline_notes text,
  host_countries text[], funding_type text, funding_notes text,
  eligibility_notes text, language_requirement text, age_min integer,
  age_max integer, category_slug text, category_label_tr text,
  category_color text, documents json, is_featured boolean,
  days_until_deadline integer, submitted_by_nickname text,
  last_url_check_at timestamptz, last_url_check_status integer,
  summary_tr text, eligibility_notes_tr text
)
language sql
stable
set search_path to 'public'
as $function$
  with kullanici as (
    select array_position(array['A1','A2','B1','B2','C1','C2'], p_english) as ing_seviye
  )
  select
    oc.id, oc.title, oc.official_url, oc.deadline, oc.deadline_notes,
    oc.host_countries, oc.funding_type, oc.funding_notes, oc.eligibility_notes,
    oc.language_requirement, oc.age_min, oc.age_max, oc.category_slug,
    oc.category_label_tr, oc.category_color, oc.documents, oc.is_featured,
    case when oc.deadline is null then null
         else (oc.deadline - current_date)::int end as days_until_deadline,
    opp.submitted_by_nickname, opp.last_url_check_at, opp.last_url_check_status,
    opp.summary_tr, opp.eligibility_notes_tr
  from public.opportunity_cards oc
  left join public.opportunities opp on opp.id = oc.id
  cross join kullanici k
  where
    coalesce(opp.is_active, true) = true

    -- ── Ülke ────────────────────────────────────────────────────
    and (p_host_country is null
         or '*' = any(oc.host_countries)
         or p_host_country = any(oc.host_countries))

    -- ── Kategori ────────────────────────────────────────────────
    and (p_category_slug is null or oc.category_slug = p_category_slug)

    -- ── Vatandaşlık (gevşetilmez: kullanıcının kimliği) ──────────
    and ('all' = any(oc.eligible_citizenships)
         or p_citizenship = any(oc.eligible_citizenships))

    -- ── Yaş: kayıtta sınır yoksa eleme yok ──────────────────────
    and (p_age is null or oc.age_min is null or oc.age_min <= p_age)
    and (p_age is null or oc.age_max is null or oc.age_max >= p_age)

    -- ── Başvurulacak kademe ─────────────────────────────────────
    and (p_study_level is null
         or 'any' = any(oc.study_level)
         or p_study_level = any(oc.study_level))

    -- ── Eldeki eğitim seviyesi (ÖN KOŞUL kapısı) ────────────────
    -- Lise / ön lisans seviyesindeki biri yüksek lisans veya doktora
    -- bursuna başvuramaz. Diğer seviyelerde eleme yok.
    and (p_highest_edu is null
         or p_highest_edu not in ('lise', 'on_lisans')
         or 'any'      = any(oc.study_level)
         or 'bachelor' = any(oc.study_level))

    -- ── Bölüm ───────────────────────────────────────────────────
    and (p_field is null
         or 'all' = any(oc.target_fields)
         or p_field = any(oc.target_fields))

    -- ── Dil: yalnız kanıtlı eleme ───────────────────────────────
    and (
      oc.language_requirement is null
      -- Kullanıcının elindeki bir alternatif kayıtta geçiyorsa hiç bakma
      or oc.language_requirement ilike '%ürkçe%'
      or oc.language_requirement ilike '%ev sahibi%'
      or oc.language_requirement ilike '%hedef dil%'
      or (p_language is not null
          and oc.language_requirement ilike '%' || p_language || '%')
      -- Kayıt İngilizce istemiyorsa, İngilizce beyanı bu kaydı etkilemez
      or oc.language_requirement not ilike '%ngilizce%'
      -- Buradan sonrası: kayıt İngilizce istiyor ve alternatif yok
      or (
        p_english is distinct from 'none'
        and (
          k.ing_seviye is null                               -- seviye beyan edilmedi
          or array_position(
               array['A1','A2','B1','B2','C1','C2'],
               substring(oc.language_requirement from '([ABC][12])[^,;/()]{0,12}ngilizce')
             ) is null                                        -- kayıtta açık seviye yok
          or k.ing_seviye >= array_position(
               array['A1','A2','B1','B2','C1','C2'],
               substring(oc.language_requirement from '([ABC][12])[^,;/()]{0,12}ngilizce')
             )
        )
      )
    )

    -- ── Son başvuru tarihi geçmiş kayıt hiç gösterilmez ─────────
    and (oc.deadline is null or oc.deadline >= current_date)
  order by
    oc.is_featured desc,
    case when oc.deadline is null then 1 else 0 end,
    oc.deadline asc
$function$;

comment on function public.match_opportunities(
  text, text, text, integer, text, text, text, text, text
) is
  'Arama filtresi. Kural: yalnız KANITLA ele. Kayıtta bir sınır yazmıyorsa '
  '(yaş yok, bölüm ''all'', uyruk ''all'', seviye yok) o boyut hiç elemez.';

commit;
