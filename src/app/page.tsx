'use client'
import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { supabase } from '@/lib/supabase'
import { Opportunity, MatchParams } from '@/types'
import OpportunityCard from '@/components/OpportunityCard'
import EmailCapture from '@/components/EmailCapture'
import AppHeader from '@/components/AppHeader'
import Hero from '@/components/hero/Hero'
import SearchScene from '@/components/scene/SearchScene'
import { pulseScene, hexToRgb01 } from '@/components/scene/sceneBus'
import { CATEGORY_ICON_SRC, CATEGORY_ACCENT } from '@/lib/category-assets'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import RangeSlider from '@/components/form/RangeSlider'
import StepSlider from '@/components/form/StepSlider'
import ChoiceGrid from '@/components/form/ChoiceGrid'

const COUNTRIES: { code: string; label: string; language: string | null }[] = [
  { code: 'DE', label: '🇩🇪 Almanya',     language: 'Almanca' },
  { code: 'FR', label: '🇫🇷 Fransa',      language: 'Fransızca' },
  { code: 'ES', label: '🇪🇸 İspanya',     language: 'İspanyolca' },
  { code: 'GB', label: '🇬🇧 İngiltere',   language: 'İngilizce' },
  { code: 'US', label: '🇺🇸 ABD',         language: 'İngilizce' },
  { code: 'IT', label: '🇮🇹 İtalya',      language: 'İtalyanca' },
  { code: 'NL', label: '🇳🇱 Hollanda',    language: 'Hollandaca' },
  { code: 'SE', label: '🇸🇪 İsveç',       language: 'İsveççe' },
  { code: 'AT', label: '🇦🇹 Avusturya',   language: 'Almanca' },
  { code: 'BE', label: '🇧🇪 Belçika',     language: 'Fransızca' },
]

const CATEGORIES = [
  { slug: 'scholarship',   label: 'Burs' },
  { slug: 'volunteering',  label: 'Gönüllülük' },
  { slug: 'youth_project', label: 'Gençlik Projesi' },
  { slug: 'internship',    label: 'Staj' },
  { slug: 'summer_school', label: 'Yaz Okulu' },
  { slug: 'exchange',      label: 'Değişim' },
]

const HIGHEST_EDU_LEVELS = [
  { value: 'lise',          label: 'Lise' },
  { value: 'on_lisans',     label: 'Ön Lisans' },
  { value: 'lisans',        label: 'Lisans' },
  { value: 'yuksek_lisans', label: 'Yüksek Lisans' },
  { value: 'doktora',       label: 'Doktora' },
]

// ChoiceGrid / StepSlider için görünüm listeleri. Değerler (value) yukarıdaki
// listelerle birebir aynı — yalnız sunum katmanı zenginleşiyor,
// match_opportunities'e giden parametreler değişmiyor.
const COUNTRY_OPTIONS = COUNTRIES.map(c => ({
  value: c.code,
  label: c.label.replace(/^\S+\s/, ''),
  icon: c.label.split(' ')[0],
  note: c.language ?? undefined,
}))

// Kategoriler tek showpiece satırında duruyor: Higgsfield ile üretilmiş cam 3B
// ikonlar + her kartın kendi vurgu rengi.
const CATEGORY_OPTIONS = CATEGORIES.map(c => ({
  value: c.slug,
  label: c.label,
  iconSrc: CATEGORY_ICON_SRC[c.slug],
  accent: CATEGORY_ACCENT[c.slug],
}))

const CATEGORY_BLURB: Record<string, string> = {
  scholarship:   'Öğrenim ücreti + yaşam gideri',
  volunteering:  'Masrafların karşılanır',
  youth_project: 'Kısa süreli, tam fonlu',
  internship:    'Şirket / kurum deneyimi',
  summer_school: '2–6 haftalık programlar',
  exchange:      'Bir–iki dönem yurt dışı',
}

const STUDY_LEVEL_OPTIONS = [
  { value: 'bachelor', label: 'Lisans',        icon: '📘' },
  { value: 'master',   label: 'Yüksek Lisans', icon: '📗' },
  { value: 'phd',      label: 'Doktora',       icon: '🔬' },
  { value: 'any',      label: 'Fark etmez',    icon: '✨' },
]

// Eğitim seviyesi doğal bir merdiven — bu yüzden kart yerine çekmeli bar.
const HIGHEST_EDU_STOPS = [
  { value: 'lise',          short: 'Lise',   label: 'Lise',          icon: '🏫' },
  { value: 'on_lisans',     short: 'Ön Lis.', label: 'Ön Lisans',    icon: '📒' },
  { value: 'lisans',        short: 'Lisans', label: 'Lisans',        icon: '📘' },
  { value: 'yuksek_lisans', short: 'Y.Lis.', label: 'Yüksek Lisans', icon: '📗' },
  { value: 'doktora',       short: 'Dr.',    label: 'Doktora',       icon: '🎓' },
]

// Dil barının durakları — "Bilmiyorum" en solda, filtre uygulanmaz.
const CEFR_STOPS = [
  { value: 'none', short: '—',  label: 'Bilmiyorum / önemli değil' },
  { value: 'A1',   short: 'A1', label: 'A1 — Başlangıç' },
  { value: 'A2',   short: 'A2', label: 'A2 — Temel' },
  { value: 'B1',   short: 'B1', label: 'B1 — Orta' },
  { value: 'B2',   short: 'B2', label: 'B2 — İyi' },
  { value: 'C1',   short: 'C1', label: 'C1 — İleri' },
  { value: 'C2',   short: 'C2', label: 'C2 — Anadil seviyesi' },
]

// Popüler bölümler — kullanıcı dostu etiket + DB'de eşlenebilecek slug
// Not: DB'de bire bir slug olmasa da sorun değil — sonuç 0 gelirse
// handleSearch otomatik olarak bu filtreyi gevşetip tekrar sorguluyor.
type FieldOption = { value: string; label: string; group: string }

const FIELDS: FieldOption[] = [
  // — Mühendislik —
  { value: 'computer_science',        label: 'Bilgisayar Mühendisliği',         group: 'Mühendislik' },
  { value: 'software_engineering',    label: 'Yazılım Mühendisliği',            group: 'Mühendislik' },
  { value: 'electrical_engineering',  label: 'Elektrik-Elektronik Mühendisliği', group: 'Mühendislik' },
  { value: 'mechanical_engineering',  label: 'Makine Mühendisliği',             group: 'Mühendislik' },
  { value: 'industrial_engineering',  label: 'Endüstri Mühendisliği',           group: 'Mühendislik' },
  { value: 'civil_engineering',       label: 'İnşaat Mühendisliği',             group: 'Mühendislik' },
  { value: 'chemical_engineering',    label: 'Kimya Mühendisliği',              group: 'Mühendislik' },
  { value: 'environmental_engineering', label: 'Çevre Mühendisliği',            group: 'Mühendislik' },
  { value: 'aerospace_engineering',   label: 'Uzay / Havacılık Mühendisliği',   group: 'Mühendislik' },
  { value: 'biomedical_engineering',  label: 'Biyomedikal Mühendislik',         group: 'Mühendislik' },

  // — Sağlık —
  { value: 'medicine',                label: 'Tıp',                             group: 'Sağlık' },
  { value: 'dentistry',               label: 'Diş Hekimliği',                   group: 'Sağlık' },
  { value: 'pharmacy',                label: 'Eczacılık',                       group: 'Sağlık' },
  { value: 'nursing',                 label: 'Hemşirelik',                      group: 'Sağlık' },
  { value: 'veterinary',              label: 'Veterinerlik',                    group: 'Sağlık' },
  { value: 'psychology',              label: 'Psikoloji',                       group: 'Sağlık' },
  { value: 'public_health',           label: 'Halk Sağlığı',                    group: 'Sağlık' },

  // — Temel Bilimler —
  { value: 'mathematics',             label: 'Matematik',                       group: 'Temel Bilimler' },
  { value: 'physics',                 label: 'Fizik',                           group: 'Temel Bilimler' },
  { value: 'chemistry',               label: 'Kimya',                           group: 'Temel Bilimler' },
  { value: 'biology',                 label: 'Biyoloji',                        group: 'Temel Bilimler' },
  { value: 'molecular_biology',       label: 'Moleküler Biyoloji & Genetik',    group: 'Temel Bilimler' },
  { value: 'statistics',              label: 'İstatistik',                      group: 'Temel Bilimler' },
  { value: 'data_science',            label: 'Veri Bilimi',                     group: 'Temel Bilimler' },

  // — Sosyal Bilimler & Hukuk —
  { value: 'law',                     label: 'Hukuk',                           group: 'Sosyal Bilimler' },
  { value: 'international_relations', label: 'Uluslararası İlişkiler',          group: 'Sosyal Bilimler' },
  { value: 'political_science',       label: 'Siyaset Bilimi',                  group: 'Sosyal Bilimler' },
  { value: 'public_policy',           label: 'Kamu Politikası',                 group: 'Sosyal Bilimler' },
  { value: 'sociology',               label: 'Sosyoloji',                       group: 'Sosyal Bilimler' },
  { value: 'anthropology',            label: 'Antropoloji',                     group: 'Sosyal Bilimler' },
  { value: 'history',                 label: 'Tarih',                           group: 'Sosyal Bilimler' },
  { value: 'philosophy',              label: 'Felsefe',                         group: 'Sosyal Bilimler' },
  { value: 'social_sciences',         label: 'Sosyal Bilimler (genel)',         group: 'Sosyal Bilimler' },
  { value: 'human_rights',            label: 'İnsan Hakları',                   group: 'Sosyal Bilimler' },

  // — İşletme & Ekonomi —
  { value: 'business',                label: 'İşletme',                         group: 'İşletme & Ekonomi' },
  { value: 'economics',               label: 'Ekonomi / İktisat',               group: 'İşletme & Ekonomi' },
  { value: 'finance',                 label: 'Finans',                          group: 'İşletme & Ekonomi' },
  { value: 'marketing',               label: 'Pazarlama',                       group: 'İşletme & Ekonomi' },
  { value: 'management',              label: 'Yönetim',                         group: 'İşletme & Ekonomi' },
  { value: 'logistics',               label: 'Lojistik',                        group: 'İşletme & Ekonomi' },

  // — Eğitim & Dil —
  { value: 'education',               label: 'Eğitim Bilimleri',                group: 'Eğitim & Dil' },
  { value: 'english_teaching',        label: 'İngilizce Öğretmenliği',          group: 'Eğitim & Dil' },
  { value: 'linguistics',             label: 'Dilbilim / Mütercim-Tercümanlık', group: 'Eğitim & Dil' },
  { value: 'literature',              label: 'Edebiyat',                        group: 'Eğitim & Dil' },

  // — Tasarım, Sanat, Medya —
  { value: 'architecture',            label: 'Mimarlık',                        group: 'Tasarım & Sanat' },
  { value: 'urban_planning',          label: 'Şehir Planlama',                  group: 'Tasarım & Sanat' },
  { value: 'industrial_design',       label: 'Endüstriyel Tasarım',             group: 'Tasarım & Sanat' },
  { value: 'graphic_design',          label: 'Grafik Tasarım',                  group: 'Tasarım & Sanat' },
  { value: 'fine_arts',               label: 'Güzel Sanatlar',                  group: 'Tasarım & Sanat' },
  { value: 'music',                   label: 'Müzik',                           group: 'Tasarım & Sanat' },
  { value: 'cinema',                  label: 'Sinema & TV',                     group: 'Tasarım & Sanat' },
  { value: 'communication',           label: 'İletişim',                        group: 'Tasarım & Sanat' },
  { value: 'journalism',              label: 'Gazetecilik',                     group: 'Tasarım & Sanat' },

  // — Diğer —
  { value: 'agriculture',             label: 'Ziraat / Tarım',                  group: 'Diğer' },
  { value: 'tourism',                 label: 'Turizm & Otelcilik',              group: 'Diğer' },
  { value: 'gastronomy',              label: 'Gastronomi',                      group: 'Diğer' },
  { value: 'ngo',                     label: 'STK / Sivil Toplum',              group: 'Diğer' },
  { value: 'youth_work',              label: 'Gençlik Çalışması',               group: 'Diğer' },
  { value: 'environmental_science',   label: 'Çevre Bilimleri',                 group: 'Diğer' },
]

const FIELD_LOOKUP: Record<string, string> = Object.fromEntries(
  FIELDS.map(f => [f.value, f.label])
)

function fieldLabel(slug: string) {
  return FIELD_LOOKUP[slug] ?? slug.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

/** Yaş barının altındaki teşvik metni — hangi programlar açık? */
function ageBlurb(age: number) {
  if (age < 18) return 'Lise programları ve gençlik değişimleri sana açık.'
  if (age <= 30) return 'En geniş aralık — Erasmus+, ESC ve çoğu burs bu yaşta açık.'
  if (age <= 35) return 'Yüksek lisans ve araştırma bursları hâlâ açık.'
  return 'Araştırma, uzman değişimi ve mesleki programlara odaklanalım.'
}

type Step = 'form' | 'results'

export default function Home() {
  const [step, setStep] = useState<Step>('form')
  const [results, setResults] = useState<Opportunity[]>([])
  const [loading, setLoading] = useState(false)
  const [activeCategory, setActiveCategory] = useState<string | null>(null)
  const [searchSnapshot, setSearchSnapshot] = useState<Record<string, unknown>>({})
  const [relaxedFilters, setRelaxedFilters] = useState<string[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)

  // Form state
  const [country, setCountry] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)
  const [citizenship, setCitizenship] = useState('TR')
  const [age, setAge] = useState('')
  const [studyLevel, setStudyLevel] = useState<string | null>(null)
  const [highestEdu, setHighestEdu] = useState<string | null>(null)
  const [field, setField] = useState<string | null>(null)
  const [languageLevel, setLanguageLevel] = useState<string | null>(null)

  const formRef = useRef<HTMLElement>(null)
  const prevStepRef = useRef<Step | null>(null)

  function scrollToForm() {
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Adım değişiminde kaydırma konumu. Hero tam ekran olduğu için form,
  // sayfanın 1 ekran altında duruyor: arama sonrası kullanıcı listenin
  // ortasında açılmasın diye başa alınır; sonuçtan forma dönüşte de hero'ya
  // değil doğrudan forma inilir. İlk yüklemede hiç dokunulmaz (hero görünür).
  useEffect(() => {
    const prev = prevStepRef.current
    prevStepRef.current = step
    if (prev === null || prev === step) return

    if (step === 'results') {
      window.scrollTo({ top: 0, behavior: 'auto' })
    } else {
      formRef.current?.scrollIntoView({ behavior: 'auto', block: 'start' })
    }
  }, [step])

  // Form ve sonuç ekranlarının giriş koreografisi. Adım değiştiğinde (ya da
  // sonuç listesi yenilendiğinde) yeniden kurulur; gsap.context sayesinde
  // önceki tween'ler ve ScrollTrigger'lar temizlenir.
  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const ctx = gsap.context(() => {
      if (reduced) {
        gsap.set('[data-anim], .opp-card, [data-anim="card"] > *', { opacity: 1, y: 0 })
        return
      }

      // Ekranın üst bloğu: başlık, adım rozetleri, ilerleme göstergesi
      gsap.fromTo('[data-anim="head"] > *',
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.6, stagger: 0.07, ease: 'power3.out' })

      // Paneller ve içlerindeki alan grupları
      gsap.fromTo('[data-anim="card"]',
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 0.75, delay: 0.1, stagger: 0.09, ease: 'power3.out' })

      gsap.fromTo('[data-anim="card"] > *',
        { opacity: 0, y: 12 },
        { opacity: 1, y: 0, duration: 0.5, delay: 0.28, stagger: 0.05, ease: 'power2.out' })

      // Kategori kartları sırayla "iner" — ekranın showpiece'i
      gsap.fromTo('[data-anim="showpiece"] .choice-card',
        { opacity: 0, y: 26, scale: 0.94 },
        { opacity: 1, y: 0, scale: 1, duration: 0.6, delay: 0.3, stagger: 0.06, ease: 'back.out(1.6)' })

      // Sonuç sayacı 0'dan gerçek değere saysın
      const countEl = document.querySelector('[data-count]')
      if (countEl) {
        const target = Number(countEl.textContent || '0')
        const obj = { v: 0 }
        gsap.to(obj, {
          v: target, duration: 1.0, ease: 'power2.out',
          onUpdate: () => { countEl.textContent = String(Math.round(obj.v)) },
        })
      }

      // Sonuç kartları: görünüm alanına girdikçe teker teker belirir
      ScrollTrigger.batch('.opp-card', {
        start: 'top 92%',
        onEnter: batch => gsap.fromTo(batch,
          { opacity: 0, y: 30, scale: 0.98 },
          { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.07, ease: 'power3.out', overwrite: true }),
      })
      gsap.set('.opp-card', { opacity: 0 })
      ScrollTrigger.refresh()
    })

    return () => ctx.revert()
  }, [step, results, activeCategory])

  const selectedCountry = COUNTRIES.find(c => c.code === country) ?? null
  const targetLanguage = selectedCountry?.language ?? null

  // İlerleme göstergesi: kaç anlamlı alan dolduruldu?
  const filledFlags = [
    category, country, age === '' ? null : age, highestEdu, studyLevel, field,
    languageLevel === 'none' ? null : languageLevel,
  ]
  const activeFilterCount = filledFlags.filter(Boolean).length
  const progress = Math.round((activeFilterCount / filledFlags.length) * 100)

  function handleCountryChange(newCountry: string | null) {
    setCountry(newCountry)
    setLanguageLevel(null)
  }

  async function handleSearch() {
    setLoading(true)
    setSearchError(null)
    pulseScene({ color: hexToRgb01('#2BE0C8'), strength: 1.2 })

    const baseParams: MatchParams = {
      p_host_country:  country || null,
      p_category_slug: category || null,
      p_citizenship:   citizenship || 'TR',
      p_age:           age ? parseInt(age) : null,
      p_study_level:   studyLevel || null,
      p_highest_edu:   highestEdu || null,
      p_field:         field || null,
      p_language:      languageLevel && languageLevel !== 'none' ? targetLanguage : null,
    }

    // Akıllı fallback: tam eşleşme yoksa filtreleri önem sırasına göre
    // kademeli gevşetip tekrar sorgulayalım. Ülke ve vatandaşlık hiç
    // gevşemez — kullanıcının gitmek istediği yer ve kimliği korunur.
    const fallbackOrder: { key: keyof MatchParams; label: string }[] = [
      { key: 'p_field',         label: 'Bölüm' },
      { key: 'p_language',      label: 'Dil seviyesi' },
      { key: 'p_age',           label: 'Yaş' },
      { key: 'p_highest_edu',   label: 'En yüksek eğitim' },
      { key: 'p_study_level',   label: 'Eğitim kademesi' },
      { key: 'p_category_slug', label: 'Kategori' },
    ]

    const params: MatchParams = { ...baseParams }
    const relaxed: string[] = []
    let data: Opportunity[] | null = null

    const run = async (p: MatchParams) => {
      const res = await supabase.rpc('match_opportunities', p)
      if (res.error) {
        return { ok: false as const, error: res.error.message, rows: [] as Opportunity[] }
      }
      return { ok: true as const, rows: ((res.data as Opportunity[]) ?? []) }
    }

    const first = await run(params)
    if (!first.ok) {
      setSearchError(first.error)
      setResults([])
      setRelaxedFilters([])
      setLoading(false)
      return
    }
    data = first.rows

    for (const f of fallbackOrder) {
      if (data && data.length > 0) break
      if (params[f.key] == null) continue
      ;(params as Record<string, unknown>)[f.key as string] = null
      relaxed.push(f.label)
      const next = await run(params)
      if (!next.ok) {
        setSearchError(next.error)
        setResults([])
        setRelaxedFilters(relaxed)
        setLoading(false)
        return
      }
      data = next.rows
    }

    setResults(data ?? [])
    setRelaxedFilters(relaxed)
    setActiveCategory(null)
    setSearchSnapshot({ country, category, citizenship, studyLevel, highestEdu, field, targetLanguage, languageLevel })
    setStep('results')
    setLoading(false)
  }

  const filtered = activeCategory
    ? results.filter(r => r.category_slug === activeCategory)
    : results

  const categoryCounts = CATEGORIES.reduce((acc, cat) => {
    acc[cat.slug] = results.filter(r => r.category_slug === cat.slug).length
    return acc
  }, {} as Record<string, number>)

  // ─── FORM ───────────────────────────────────────────────
  if (step === 'form') return (
    <>
    <Hero onStart={scrollToForm} />
    <main ref={formRef} style={{
      position: 'relative',
      minHeight: '100vh',
      padding: '68px 22px 72px',
      scrollMarginTop: 0,
    }}>
      <SearchScene />
      <div key="form" className="page-layer" style={{ maxWidth: 1240, margin: '0 auto' }}>

        {/* Header */}
        <div data-anim="head">
          <AppHeader />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <StepPill label="1 · Profil" active />
            <span style={{ color: 'var(--text-low)', fontSize: 12 }}>›</span>
            <StepPill label="2 · Sonuçlar" />
          </div>

          <h2 style={{
            fontSize: 'clamp(30px, 5vw, 54px)', fontWeight: 600, letterSpacing: '-0.04em',
            color: 'var(--text-hi)', margin: '10px 0 12px', lineHeight: 1.04,
            textWrap: 'balance',
          }}>
            Sana uyan fırsatı{' '}
            <span style={{
              background: 'var(--grad-brand)',
              WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
            }}>
              bulalım.
            </span>
          </h2>
          <p style={{
            fontSize: 14.5, color: 'var(--text-mid)', maxWidth: 620,
            lineHeight: 1.6, marginBottom: 24,
          }}>
            Hiçbir alan zorunlu değil — ne kadarını doldurursan eşleşme o kadar isabetli olur.
            Sonuç çıkmazsa filtreleri biz gevşetiriz.
          </p>

          <ProgressMeter progress={progress} filled={activeFilterCount} total={filledFlags.length} />
        </div>

        {searchError && (
          <div
            className="fx-fade-in-up"
            style={{
              margin: '22px 0 0',
              padding: '14px 16px',
              borderRadius: 14,
              background: 'rgba(255, 107, 107, 0.12)',
              border: '1px solid rgba(255, 107, 107, 0.4)',
              fontSize: 13,
              color: '#FFB4B4',
              lineHeight: 1.5,
            }}
          >
            <strong>Arama yapılamadı.</strong> {searchError}
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-mid)' }}>
              Veritabanında güncel SQL yoksa:{' '}
              <code style={{ fontSize: 11 }}>docs/sql/090_one_shot_after_006.sql</code> dosyasını Supabase SQL
              Editor’da bir kez çalıştırın.
            </div>
          </div>
        )}

        {/* ── 01 · NE ARIYORSUN — tam genişlik showpiece ─────────────────── */}
        <section
          data-anim="card"
          className="glass-panel"
          style={{ padding: '28px 26px', marginTop: 26 }}
        >
          <PanelTitle
            badge="01"
            title="Ne arıyorsun?"
            subtitle="Bir tür seç — ya da boş bırak, hepsini getirelim"
          />
          <div data-anim="showpiece">
            <ChoiceGrid
              label="Fırsat türü"
              hint="opsiyonel"
              options={CATEGORY_OPTIONS.map(o => ({ ...o, note: CATEGORY_BLURB[o.value] }))}
              value={category}
              onChange={setCategory}
              columns={6}
              accent="#7C5CFF"
            />
          </div>
        </section>

        {/* ── 02 · SEN | 03 · HEDEFİN ────────────────────────────────────── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(430px, 100%), 1fr))',
          gap: 22,
          alignItems: 'start',
          marginTop: 22,
        }}>

          <section data-anim="card" className="glass-panel" style={{ padding: '28px 26px' }}>
            <PanelTitle badge="02" title="Sen" subtitle="Kim olduğun" />

            <div style={{ display: 'grid', gap: 30 }}>
              <RangeSlider
                label="Yaşın"
                value={age === '' ? null : Number(age)}
                onChange={v => setAge(v === null ? '' : String(v))}
                describe={ageBlurb}
              />

              <StepSlider
                label="Halihazırdaki en yüksek eğitim seviyen"
                hint="opsiyonel — barı çek"
                stops={HIGHEST_EDU_STOPS}
                value={highestEdu}
                onChange={setHighestEdu}
                accent="#2BE0C8"
              />

              <div>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-hi)', marginBottom: 10 }}>
                  Bölümün <span style={{ fontWeight: 400, color: 'var(--text-low)' }}>· opsiyonel</span>
                </div>
                <Picker
                  placeholder="Bölüm seç"
                  value={field}
                  valueLabel={field ? fieldLabel(field) : null}
                  options={FIELDS.map(f => ({ value: f.value, label: f.label, group: f.group }))}
                  onChange={setField}
                  emptyHint="Sonuç yok"
                />
              </div>

              <div>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-hi)', marginBottom: 10 }}>
                  Vatandaşlık
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <input
                    value={citizenship}
                    onChange={e => setCitizenship(e.target.value.toUpperCase())}
                    placeholder="TR"
                    maxLength={2}
                    aria-label="Vatandaşlık kodu"
                    style={{
                      width: 96, padding: '12px 14px', borderRadius: 14,
                      border: '1px solid rgba(255,255,255,0.14)', fontSize: 16, fontWeight: 700,
                      letterSpacing: '0.1em', textAlign: 'center',
                      outline: 'none', background: 'rgba(255,255,255,0.05)', color: 'var(--text-hi)',
                    }}
                  />
                  <span style={{ fontSize: 11.5, color: 'var(--text-low)' }}>ISO kodu (TR, DE…)</span>
                </div>
              </div>
            </div>
          </section>

          <section data-anim="card" className="glass-panel" style={{ padding: '28px 26px' }}>
            <PanelTitle badge="03" title="Hedefin" subtitle="Nereye, ne için" />

            <div style={{ display: 'grid', gap: 30 }}>
              <ChoiceGrid
                label="Nereye gitmek istiyorsun?"
                hint="opsiyonel"
                options={COUNTRY_OPTIONS}
                value={country}
                onChange={handleCountryChange}
                columns={4}
                accent="#9B6BFF"
              />

              {targetLanguage && (
                <div className="fx-fade-in-up">
                  <StepSlider
                    label={`${targetLanguage} seviyen`}
                    hint="opsiyonel — bilmiyorsan boş bırak"
                    stops={CEFR_STOPS}
                    value={languageLevel}
                    onChange={setLanguageLevel}
                    accent="#FFB547"
                  />
                </div>
              )}

              <ChoiceGrid
                label="Başvurmak istediğin eğitim kademesi"
                hint="opsiyonel"
                options={STUDY_LEVEL_OPTIONS}
                value={studyLevel}
                onChange={setStudyLevel}
                columns={4}
                accent="#FF5FA2"
              />
            </div>
          </section>
        </div>

        {/* Aksiyon çubuğu — birincil aksiyon sağ altta */}
        <div data-anim="card" className="glass-panel" style={{
          marginTop: 22, padding: '20px 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 18, flexWrap: 'wrap',
        }}>
          <div style={{ fontSize: 13, color: 'var(--text-mid)', lineHeight: 1.55 }}>
            {activeFilterCount === 0
              ? 'Hiç filtre seçmedin — tüm açık fırsatları getireceğiz.'
              : `${activeFilterCount} filtre seçili · tam eşleşme çıkmazsa otomatik gevşetiriz.`}
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="btn-primary"
            style={{
              padding: '16px 36px', borderRadius: 999,
              color: '#150F35', border: 'none', fontSize: 15.5,
              fontWeight: 700, letterSpacing: '-0.01em',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.65 : 1,
              boxShadow: '0 20px 40px -18px rgba(124, 92, 255, 0.9)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 10,
              whiteSpace: 'nowrap',
            }}
          >
            {loading && <Spinner />}
            {loading ? 'Aranıyor…' : 'Fırsatları göster →'}
          </button>
        </div>
      </div>
    </main>
    </>
  )


  // ─── RESULTS ────────────────────────────────────────────
  return (
    <main style={{
      position: 'relative',
      minHeight: '100vh',
      padding: '48px 22px 64px',
    }}>
      <SearchScene density={0.7} />
      <div key="results" className="page-layer" style={{ maxWidth: 1180, margin: '0 auto' }}>

        {/* Header */}
        <div data-anim="head">
        <AppHeader
          searchSnapshot={searchSnapshot}
          rightSlot={
            <button
              onClick={() => setStep('form')}
              className="ghost-btn"
              style={{
                fontSize: 12, fontWeight: 600, color: 'var(--text-mid)',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.14)', borderRadius: 999,
                padding: '8px 16px', cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              ← Aramayı düzenle
            </button>
          }
        />

        {/* Step pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 22 }}>
          <StepPill label="1 · Profil ✓" done />
          <span style={{ color: 'var(--text-low)', fontSize: 12 }}>›</span>
          <StepPill label="2 · Sonuçlar" active />
        </div>

        {/* Result count */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
          <span
            data-count
            style={{
              fontSize: 'clamp(44px, 8vw, 76px)', fontWeight: 700, letterSpacing: '-0.05em',
              lineHeight: 1, fontVariantNumeric: 'tabular-nums',
              background: 'var(--grad-brand)',
              WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
            }}
          >
            {filtered.length}
          </span>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-hi)' }}>
            fırsat bulundu
          </span>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-low)', marginBottom: 20 }}>
          {country && `${COUNTRIES.find(c => c.code === country)?.label}`}
          {category && ` · ${CATEGORIES.find(c => c.slug === category)?.label}`}
          {(searchSnapshot.highestEdu as string | null) && ` · Mevcut: ${HIGHEST_EDU_LEVELS.find(l => l.value === searchSnapshot.highestEdu)?.label}`}
          {targetLanguage && languageLevel && languageLevel !== 'none' && ` · ${targetLanguage} ${languageLevel}`}
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 22 }}>
          <FilterChip
            label={`Tümü (${results.length})`}
            active={activeCategory === null}
            onClick={() => setActiveCategory(null)}
          />
          {CATEGORIES.filter(c => categoryCounts[c.slug] > 0).map(c => (
            <FilterChip
              key={c.slug}
              label={`${c.label} (${categoryCounts[c.slug]})`}
              iconSrc={CATEGORY_ICON_SRC[c.slug]}
              accent={CATEGORY_ACCENT[c.slug]}
              active={activeCategory === c.slug}
              onClick={() => {
                setActiveCategory(c.slug)
                pulseScene({ color: hexToRgb01(CATEGORY_ACCENT[c.slug]), strength: 0.8 })
              }}
            />
          ))}
        </div>

        </div>

        {/* Gevşetilen filtreler banner'ı */}
        {relaxedFilters.length > 0 && results.length > 0 && (
          <div className="fx-fade-in-up" style={{
            background: 'rgba(255, 181, 71, 0.10)',
            border: '1px solid rgba(255, 181, 71, 0.35)',
            borderRadius: 14, padding: '13px 16px', marginBottom: 22,
            fontSize: 12.5, color: '#FFD08A', lineHeight: 1.55,
          }}>
            <strong>Tam eşleşme bulamadık.</strong> Sana en yakın sonuçları
            getirmek için şu filtreleri otomatik gevşettik:{' '}
            <span style={{ fontWeight: 500 }}>{relaxedFilters.join(', ')}</span>.
          </div>
        )}

        {/* Cards */}
        {filtered.length === 0 ? (
          <div className="glass-panel fx-fade-in" style={{
            textAlign: 'center', padding: '70px 24px',
            color: 'var(--text-mid)', fontSize: 14.5,
          }}>
            Bu kriterlere uygun fırsat bulunamadı.
            <br />
            <button
              onClick={() => setStep('form')}
              className="ghost-btn"
              style={{
                marginTop: 16, color: '#fff', background: 'rgba(124, 92, 255, 0.22)',
                border: '1px solid rgba(124, 92, 255, 0.55)', borderRadius: 999,
                padding: '10px 20px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              }}
            >
              Filtreleri genişlet →
            </button>
          </div>
        ) : (
          // Tek sütunlu katı liste yerine ızgara — geniş ekranda iki kart yan yana
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(min(440px, 100%), 1fr))',
            gap: 18,
            marginBottom: 30,
            alignItems: 'stretch',
          }}>
            {filtered.map(opp => (
              <OpportunityCard key={opp.id} opp={opp} />
            ))}
          </div>
        )}

        {/* Email capture */}
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <EmailCapture searchSnapshot={searchSnapshot} />

          {/* Disclaimer */}
          <p style={{
            fontSize: 10.5, color: 'var(--text-low)', textAlign: 'center',
            marginTop: 20, lineHeight: 1.6,
          }}>
            Deadline ve şartlar değişebilir. Başvurmadan önce resmi sayfayı mutlaka kontrol edin.
          </p>
        </div>
      </div>
    </main>
  )
}

// ─── KÜÇÜK BİLEŞENLER ───────────────────────────────────

/**
 * Profil doluluk göstergesi. Zorunlu alan yok — ama "ne kadar doldurursan o
 * kadar isabetli" mesajını somutlaştırmak eşleşme kalitesini yükseltiyor.
 */
function ProgressMeter({ progress, filled, total }: {
  progress: number; filled: number; total: number
}) {
  const message =
    filled === 0 ? 'Başlamak için bir kart seç' :
    filled < 3   ? 'İyi gidiyor — birkaç alan daha eşleşmeyi keskinleştirir' :
    filled < 5   ? 'Güzel profil — sonuçlar isabetli olacak' :
                   'Harika, profilin neredeyse tam'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      padding: '14px 18px', borderRadius: 18,
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.09)',
      maxWidth: 560,
    }}>
      <div
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Profil doluluğu"
        style={{
          position: 'relative', width: 46, height: 46, flexShrink: 0,
          borderRadius: '50%',
          background: `conic-gradient(#7C5CFF ${progress * 3.6}deg, rgba(255,255,255,0.09) 0deg)`,
          display: 'grid', placeItems: 'center',
          transition: 'background 0.4s ease',
        }}
      >
        <div style={{
          width: 37, height: 37, borderRadius: '50%',
          background: '#0D0A26', display: 'grid', placeItems: 'center',
        }}>
          <span style={{
            fontSize: 11.5, fontWeight: 700, color: 'var(--text-hi)',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {progress}%
          </span>
        </div>
      </div>

      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-hi)', marginBottom: 2 }}>
          {message}
        </div>
        <div style={{ fontSize: 11.5, color: 'var(--text-low)' }}>
          {filled}/{total} alan dolu · hepsi opsiyonel
        </div>
      </div>
    </div>
  )
}

type PickerOption = { value: string; label: string; group?: string }

function Picker({ placeholder, value, valueLabel, options, onChange, emptyHint }: {
  placeholder: string
  value: string | null
  valueLabel: string | null
  options: PickerOption[]
  onChange: (v: string | null) => void
  emptyHint?: string
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery('')
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const normalized = query.trim().toLocaleLowerCase('tr')
  const filtered = normalized
    ? options.filter(o => o.label.toLocaleLowerCase('tr').includes(normalized))
    : options

  const hasGroups = filtered.some(o => o.group)
  const grouped: Record<string, PickerOption[]> = {}
  if (hasGroups) {
    for (const o of filtered) {
      const g = o.group ?? 'Diğer'
      if (!grouped[g]) grouped[g] = []
      grouped[g].push(o)
    }
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', padding: '13px 15px', borderRadius: 14,
          border: `1px solid ${open ? 'rgba(124, 92, 255, 0.6)' : 'rgba(255,255,255,0.14)'}`,
          background: 'rgba(255,255,255,0.05)',
          fontSize: 13.5, color: value ? 'var(--text-hi)' : 'var(--text-low)',
          cursor: 'pointer', textAlign: 'left',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {valueLabel ?? placeholder}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {value && (
            <span
              onClick={(e) => { e.stopPropagation(); onChange(null) }}
              style={{ color: 'var(--text-low)', fontSize: 15, padding: '0 4px' }}
              role="button"
              aria-label="Temizle"
            >
              ×
            </span>
          )}
          <span style={{ color: 'var(--text-low)', fontSize: 10 }}>{open ? '▲' : '▼'}</span>
        </span>
      </button>

      {open && (
        <div className="fx-scale-in" style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0,
          background: 'rgba(16, 12, 44, 0.97)',
          backdropFilter: 'blur(24px)',
          border: '1px solid rgba(255,255,255,0.14)', borderRadius: 16,
          boxShadow: '0 30px 60px -20px rgba(0,0,0,0.9)',
          maxHeight: 320, overflowY: 'auto', zIndex: 20,
          padding: 6,
          transformOrigin: 'top',
        }}>
          {options.length > 8 && (
            <input
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ara..."
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 10,
                border: '1px solid rgba(255,255,255,0.12)', fontSize: 12.5,
                outline: 'none', marginBottom: 6,
                background: 'rgba(255,255,255,0.05)', color: 'var(--text-hi)',
              }}
            />
          )}
          {filtered.length === 0 ? (
            <div style={{ padding: 14, fontSize: 12.5, color: 'var(--text-low)', textAlign: 'center' }}>
              {emptyHint ?? 'Seçenek bulunamadı'}
            </div>
          ) : hasGroups ? (
            Object.entries(grouped).map(([g, opts]) => (
              <div key={g}>
                <div style={{
                  fontSize: 10, fontWeight: 700, color: 'var(--text-low)',
                  textTransform: 'uppercase', letterSpacing: '0.08em',
                  padding: '10px 10px 5px',
                }}>
                  {g}
                </div>
                {opts.map(o => (
                  <PickerItem
                    key={o.value}
                    option={o}
                    selected={value === o.value}
                    onClick={() => { onChange(o.value); setOpen(false); setQuery('') }}
                  />
                ))}
              </div>
            ))
          ) : (
            filtered.map(o => (
              <PickerItem
                key={o.value}
                option={o}
                selected={value === o.value}
                onClick={() => { onChange(o.value); setOpen(false); setQuery('') }}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function PickerItem({ option, selected, onClick }: {
  option: PickerOption; selected: boolean; onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'block', width: '100%', textAlign: 'left',
        padding: '10px 11px', borderRadius: 10,
        background: selected ? 'rgba(124, 92, 255, 0.28)' : 'transparent',
        color: selected ? '#fff' : 'var(--text-mid)',
        fontWeight: selected ? 600 : 400,
        border: 'none', fontSize: 13, cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        if (!selected) e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
      }}
      onMouseLeave={(e) => {
        if (!selected) e.currentTarget.style.background = 'transparent'
      }}
    >
      {option.label}
    </button>
  )
}

function PanelTitle({ badge, title, subtitle }: { badge: string; title: string; subtitle: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 26 }}>
      <span style={{
        fontSize: 11.5, fontWeight: 800, letterSpacing: '0.06em',
        color: '#150F35', background: 'var(--grad-brand)',
        padding: '7px 11px', borderRadius: 12,
        boxShadow: '0 10px 22px -12px rgba(124, 92, 255, 1)',
      }}>
        {badge}
      </span>
      <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <span style={{
          fontSize: 19, fontWeight: 600, color: 'var(--text-hi)', letterSpacing: '-0.025em',
        }}>
          {title}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-low)' }}>{subtitle}</span>
      </span>
    </div>
  )
}

function StepPill({ label, active, done }: { label: string; active?: boolean; done?: boolean }) {
  return (
    <span style={{
      fontSize: 11.5, fontWeight: 600, padding: '6px 13px', borderRadius: 999,
      background: done
        ? 'rgba(43, 224, 200, 0.16)'
        : active ? 'var(--grad-brand)' : 'rgba(255,255,255,0.05)',
      border: `1px solid ${done ? 'rgba(43, 224, 200, 0.42)' : active ? 'transparent' : 'rgba(255,255,255,0.1)'}`,
      color: done ? '#7BF0DC' : active ? '#150F35' : 'var(--text-low)',
      transition: 'background 0.25s ease, color 0.25s ease',
    }}>
      {label}
    </span>
  )
}

function FilterChip({ label, active, onClick, iconSrc, accent = '#7C5CFF' }: {
  label: string; active: boolean; onClick: () => void
  iconSrc?: string; accent?: string
}) {
  return (
    <button
      onClick={onClick}
      className="pill-btn"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        fontSize: 12, fontWeight: 600, padding: '7px 14px 7px 10px', borderRadius: 999,
        background: active ? `${accent}2E` : 'rgba(255,255,255,0.04)',
        color: active ? '#fff' : 'var(--text-mid)',
        border: `1px solid ${active ? `${accent}AA` : 'rgba(255,255,255,0.1)'}`,
        boxShadow: active ? `0 10px 24px -14px ${accent}` : 'none',
        cursor: 'pointer',
      }}
    >
      {iconSrc && (
        <Image src={iconSrc} alt="" width={18} height={18} style={{ objectFit: 'contain' }} />
      )}
      {label}
    </button>
  )
}

function Spinner() {
  return (
    <span
      className="fx-spin"
      style={{
        display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
        border: '2px solid rgba(21, 15, 53, 0.35)', borderTopColor: '#150F35',
      }}
    />
  )
}
