'use client'
import { useState, useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { Opportunity, MatchParams } from '@/types'
import OpportunityCard from '@/components/OpportunityCard'
import EmailCapture from '@/components/EmailCapture'
import AppHeader from '@/components/AppHeader'
import Hero from '@/components/hero/Hero'
import AmbientCanvas from '@/components/hero/AmbientCanvas'
import ThemeGlyphs from '@/components/hero/ThemeGlyphs'
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

// ChoiceGrid / StepSlider için ikonlu görünüm listeleri. Değerler (value)
// yukarıdaki listelerle birebir aynı — yalnız sunum katmanı zenginleşiyor,
// match_opportunities'e giden parametreler değişmiyor.
const COUNTRY_OPTIONS = COUNTRIES.map(c => ({
  value: c.code,
  label: c.label.replace(/^\S+\s/, ''),
  icon: c.label.split(' ')[0],
  note: c.language ?? undefined,
}))

const CATEGORY_ICON_BY_SLUG: Record<string, string> = {
  scholarship: '🎓', volunteering: '🤝', youth_project: '🚀',
  internship: '💼', summer_school: '☀️', exchange: '🔁',
}

const CATEGORY_OPTIONS = [
  { value: 'scholarship',   label: 'Burs',            icon: '🎓' },
  { value: 'volunteering',  label: 'Gönüllülük',      icon: '🤝' },
  { value: 'youth_project', label: 'Gençlik Projesi', icon: '🚀' },
  { value: 'internship',    label: 'Staj',            icon: '💼' },
  { value: 'summer_school', label: 'Yaz Okulu',       icon: '☀️' },
  { value: 'exchange',      label: 'Değişim',         icon: '🔁' },
]

const STUDY_LEVEL_OPTIONS = [
  { value: 'bachelor', label: 'Lisans',        icon: '📘' },
  { value: 'master',   label: 'Yüksek Lisans', icon: '📗' },
  { value: 'phd',      label: 'Doktora',       icon: '🔬' },
  { value: 'any',      label: 'Fark etmez',    icon: '✨' },
]

const HIGHEST_EDU_OPTIONS = [
  { value: 'lise',          label: 'Lise',          icon: '🏫' },
  { value: 'on_lisans',     label: 'Ön Lisans',     icon: '📒' },
  { value: 'lisans',        label: 'Lisans',        icon: '📘' },
  { value: 'yuksek_lisans', label: 'Yüksek Lisans', icon: '📗' },
  { value: 'doktora',       label: 'Doktora',       icon: '🎓' },
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
        gsap.set('[data-anim], .opp-card', { opacity: 1, y: 0 })
        return
      }

      // Ekranın üst bloğu: başlık, adım rozetleri, filtreler
      gsap.fromTo('[data-anim="head"] > *',
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.6, stagger: 0.07, ease: 'power3.out' })

      // Form kartı ve içindeki alan grupları
      gsap.fromTo('[data-anim="card"]',
        { opacity: 0, y: 26 },
        { opacity: 1, y: 0, duration: 0.7, delay: 0.12, ease: 'power3.out' })

      gsap.fromTo('[data-anim="card"] > *',
        { opacity: 0, y: 12 },
        { opacity: 1, y: 0, duration: 0.5, delay: 0.25, stagger: 0.045, ease: 'power2.out' })

      // Sonuç sayacı 0'dan gerçek değere saysın
      const countEl = document.querySelector('[data-count]')
      if (countEl) {
        const target = Number(countEl.textContent || '0')
        const obj = { v: 0 }
        gsap.to(obj, {
          v: target, duration: 0.9, ease: 'power2.out',
          onUpdate: () => { countEl.textContent = String(Math.round(obj.v)) },
        })
      }

      // Sonuç kartları: görünüm alanına girdikçe teker teker belirir
      ScrollTrigger.batch('.opp-card', {
        start: 'top 92%',
        onEnter: batch => gsap.fromTo(batch,
          { opacity: 0, y: 28 },
          { opacity: 1, y: 0, duration: 0.6, stagger: 0.08, ease: 'power3.out', overwrite: true }),
      })
      gsap.set('.opp-card', { opacity: 0 })
      ScrollTrigger.refresh()
    })

    return () => ctx.revert()
  }, [step, results, activeCategory])

  const selectedCountry = COUNTRIES.find(c => c.code === country) ?? null
  const activeFilterCount = [country, category, studyLevel, highestEdu, field,
    age === '' ? null : age, languageLevel === 'none' ? null : languageLevel]
    .filter(Boolean).length
  const targetLanguage = selectedCountry?.language ?? null

  function handleCountryChange(newCountry: string | null) {
    setCountry(newCountry)
    setLanguageLevel(null)
  }

  async function handleSearch() {
    setLoading(true)
    setSearchError(null)

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
      padding: '64px 20px 56px',
      scrollMarginTop: 0,
    }}>
      <AmbientCanvas />
      <ThemeGlyphs />
      <div key="form" className="page-layer" style={{ maxWidth: 1080, margin: '0 auto' }}>

        {/* Header */}
        <div data-anim="head">
          <AppHeader />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <StepPill label="1 · Profil" active />
            <span style={{ color: '#C7C3DC', fontSize: 12 }}>›</span>
            <StepPill label="2 · Sonuçlar" />
          </div>
          <h2 style={{
            fontSize: 'clamp(26px, 4vw, 40px)', fontWeight: 600, letterSpacing: '-0.035em',
            color: '#231C52', margin: '10px 0 8px', lineHeight: 1.1,
          }}>
            Sana uyan fırsatı bulalım.
          </h2>
          <p style={{ fontSize: 14, color: '#6F6990', maxWidth: 560, lineHeight: 1.55, marginBottom: 26 }}>
            Hiçbir alan zorunlu değil — ne kadarını doldurursan eşleşme o kadar isabetli olur.
            Sonuç çıkmazsa filtreleri biz gevşetiriz.
          </p>
        </div>

        {searchError && (
          <div
            style={{
              marginBottom: 16,
              padding: '12px 14px',
              borderRadius: 12,
              background: '#FDE8E8',
              border: '0.5px solid #E8A8A8',
              fontSize: 13,
              color: '#A32D2D',
              lineHeight: 1.45,
            }}
          >
            <strong>Arama yapılamadı.</strong> {searchError}
            <div style={{ marginTop: 8, fontSize: 12, color: '#633806' }}>
              Veritabanında güncel SQL yoksa:{' '}
              <code style={{ fontSize: 11 }}>docs/sql/090_one_shot_after_006.sql</code> dosyasını Supabase SQL
              Editor’da bir kez çalıştırın.
            </div>
          </div>
        )}

        {/* İki sütun: SEN | HEDEFİN */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(420px, 100%), 1fr))',
          gap: 20,
          alignItems: 'start',
        }}>

          {/* ── SEN ─────────────────────────────────────────── */}
          <section data-anim="card" className="glass-panel" style={{ padding: '26px 24px' }}>
            <PanelTitle badge="01" title="Sen" subtitle="Kim olduğun" />

            <div style={{ display: 'grid', gap: 26 }}>
              <ChoiceGrid
                label="Halihazırdaki en yüksek eğitim seviyen"
                hint="opsiyonel"
                options={HIGHEST_EDU_OPTIONS}
                value={highestEdu}
                onChange={setHighestEdu}
                accent="#0F6E56"
              />

              <RangeSlider
                label="Yaşın"
                value={age === '' ? null : Number(age)}
                onChange={v => setAge(v === null ? '' : String(v))}
              />

              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#4A4468', marginBottom: 10 }}>
                  Vatandaşlık
                </div>
                <input
                  value={citizenship}
                  onChange={e => setCitizenship(e.target.value.toUpperCase())}
                  placeholder="TR"
                  maxLength={2}
                  aria-label="Vatandaşlık kodu"
                  style={{
                    width: 96, padding: '11px 14px', borderRadius: 12,
                    border: '1px solid rgba(83, 74, 183, 0.2)', fontSize: 15, fontWeight: 600,
                    letterSpacing: '0.08em', textAlign: 'center',
                    outline: 'none', background: 'rgba(255,255,255,0.85)', color: '#231C52',
                  }}
                />
                <span style={{ fontSize: 11, color: '#A9A4BF', marginLeft: 10 }}>ISO kodu (TR, DE…)</span>
              </div>

              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#4A4468', marginBottom: 10 }}>
                  Bölümün <span style={{ fontWeight: 400, color: '#A9A4BF' }}>· opsiyonel</span>
                </div>
                <Picker
                  placeholder="Bölüm seç"
                  value={field}
                  valueLabel={field ? fieldLabel(field) : null}
                  options={FIELDS.map(f => ({ value: f.value, label: f.label, group: f.group }))}
                  onChange={setField}
                  emptyHint="Yükleniyor..."
                />
              </div>
            </div>
          </section>

          {/* ── HEDEFİN ─────────────────────────────────────── */}
          <section data-anim="card" className="glass-panel" style={{ padding: '26px 24px' }}>
            <PanelTitle badge="02" title="Hedefin" subtitle="Nereye, ne için" />

            <div style={{ display: 'grid', gap: 26 }}>
              <ChoiceGrid
                label="Nereye gitmek istiyorsun?"
                hint="opsiyonel"
                options={COUNTRY_OPTIONS}
                value={country}
                onChange={handleCountryChange}
                columns={4}
                accent="#4B41B5"
              />

              {targetLanguage && (
                <StepSlider
                  label={`${targetLanguage} seviyen`}
                  hint="opsiyonel — bilmiyorsan boş bırak"
                  stops={CEFR_STOPS}
                  value={languageLevel}
                  onChange={setLanguageLevel}
                />
              )}

              <ChoiceGrid
                label="Ne arıyorsun?"
                hint="opsiyonel"
                options={CATEGORY_OPTIONS}
                value={category}
                onChange={setCategory}
                columns={3}
                accent="#C9539C"
              />

              <ChoiceGrid
                label="Başvurmak istediğin eğitim kademesi"
                hint="opsiyonel"
                options={STUDY_LEVEL_OPTIONS}
                value={studyLevel}
                onChange={setStudyLevel}
                columns={4}
                accent="#534AB7"
              />
            </div>
          </section>
        </div>

        {/* Aksiyon çubuğu — birincil aksiyon sağ altta */}
        <div data-anim="card" className="glass-panel action-bar" style={{
          marginTop: 20, padding: '18px 22px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 16, flexWrap: 'wrap',
        }}>
          <div style={{ fontSize: 12.5, color: '#6F6990', lineHeight: 1.5 }}>
            {activeFilterCount === 0
              ? 'Hiç filtre seçmedin — tüm açık fırsatları getireceğiz.'
              : `${activeFilterCount} filtre seçili · tam eşleşme çıkmazsa otomatik gevşetiriz.`}
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="btn-primary"
            style={{
              padding: '15px 34px', borderRadius: 999,
              background: loading
                ? 'linear-gradient(115deg, #AFA9EC 0%, #9FD9D2 100%)'
                : 'linear-gradient(115deg, #4B41B5 0%, #6C4FD0 55%, #17A79A 100%)',
              boxShadow: loading ? 'none' : '0 18px 32px -16px rgba(76, 65, 181, 0.85)',
              color: '#fff', border: 'none', fontSize: 15,
              fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
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
      padding: '40px 16px',
    }}>
      <AmbientCanvas />
      <ThemeGlyphs />
      <div key="results" className="page-layer" style={{ maxWidth: 680, margin: '0 auto' }}>

        {/* Header */}
        <div data-anim="head">
        <AppHeader
          searchSnapshot={searchSnapshot}
          rightSlot={
            <button
              onClick={() => setStep('form')}
              className="ghost-btn"
              style={{
                fontSize: 12, color: '#534AB7', background: 'none',
                border: '0.5px solid #AFA9EC', borderRadius: 8,
                padding: '6px 12px', cursor: 'pointer',
              }}
            >
              ← Aramayı düzenle
            </button>
          }
        />

        {/* Step pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 20 }}>
          <StepPill label="1 · Profil ✓" done />
          <span style={{ color: '#ccc', fontSize: 12 }}>›</span>
          <StepPill label="2 · Sonuçlar" active />
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          <FilterChip
            label={`✨ Tümü (${results.length})`}
            active={activeCategory === null}
            onClick={() => setActiveCategory(null)}
          />
          {CATEGORIES.filter(c => categoryCounts[c.slug] > 0).map(c => (
            <FilterChip
              key={c.slug}
              label={`${CATEGORY_ICON_BY_SLUG[c.slug] ?? ''} ${c.label} (${categoryCounts[c.slug]})`}
              active={activeCategory === c.slug}
              onClick={() => setActiveCategory(c.slug)}
            />
          ))}
        </div>

        </div>

        {/* Result count */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '4px 0 14px' }}>
          <span
            data-count
            style={{
              fontSize: 'clamp(30px, 5vw, 46px)', fontWeight: 700, letterSpacing: '-0.04em',
              lineHeight: 1,
              background: 'linear-gradient(115deg, #4B41B5 0%, #6C4FD0 45%, #17A79A 100%)',
              WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
            }}
          >
            {filtered.length}
          </span>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#4A4468' }}>fırsat bulundu</span>
        </div>
        <div style={{ fontSize: 12, color: '#8B85A8', marginBottom: 18 }}>
          {country && ` · ${COUNTRIES.find(c => c.code === country)?.label}`}
          {category && ` · ${CATEGORIES.find(c => c.slug === category)?.label}`}
          {(searchSnapshot.highestEdu as string | null) && ` · Mevcut: ${HIGHEST_EDU_LEVELS.find(l => l.value === searchSnapshot.highestEdu)?.label}`}
          {targetLanguage && languageLevel && languageLevel !== 'none' && ` · ${targetLanguage} ${languageLevel}`}
        </div>

        {/* Gevşetilen filtreler banner'ı */}
        {relaxedFilters.length > 0 && results.length > 0 && (
          <div className="fx-fade-in-up" style={{
            background: '#FAEEDA', border: '0.5px solid #E6C79A',
            borderRadius: 10, padding: '10px 14px', marginBottom: 16,
            fontSize: 12, color: '#633806', lineHeight: 1.5,
          }}>
            <strong>Tam eşleşme bulamadık.</strong> Sana en yakın sonuçları
            getirmek için şu filtreleri otomatik gevşettik:{' '}
            <span style={{ fontWeight: 500 }}>{relaxedFilters.join(', ')}</span>.
          </div>
        )}

        {/* Cards */}
        {filtered.length === 0 ? (
          <div className="fx-fade-in" style={{
            textAlign: 'center', padding: '60px 20px',
            color: '#aaa', fontSize: 14,
          }}>
            Bu kriterlere uygun fırsat bulunamadı.
            <br />
            <button
              onClick={() => setStep('form')}
              className="ghost-btn"
              style={{ marginTop: 12, color: '#534AB7', background: 'none', border: 'none', cursor: 'pointer', fontSize: 13 }}
            >
              Filtreleri genişlet →
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
            {filtered.map(opp => (
              <OpportunityCard key={opp.id} opp={opp} />
            ))}
          </div>
        )}

        {/* Email capture */}
        <EmailCapture searchSnapshot={searchSnapshot} />

        {/* Disclaimer */}
        <p style={{ fontSize: 10, color: '#bbb', textAlign: 'center', marginTop: 16, lineHeight: 1.6 }}>
          Deadline ve şartlar değişebilir. Başvurmadan önce resmi sayfayı mutlaka kontrol edin.
        </p>
      </div>
    </main>
  )
}

// ─── KÜÇÜK BİLEŞENLER ───────────────────────────────────

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
          width: '100%', padding: '10px 12px', borderRadius: 8,
          border: '0.5px solid #e0e0e0', background: '#fff',
          fontSize: 13, color: value ? '#1a1a1a' : '#999',
          cursor: 'pointer', textAlign: 'left',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <span>{valueLabel ?? placeholder}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {value && (
            <span
              onClick={(e) => { e.stopPropagation(); onChange(null) }}
              style={{ color: '#aaa', fontSize: 14, padding: '0 4px' }}
              role="button"
              aria-label="Temizle"
            >
              ×
            </span>
          )}
          <span style={{ color: '#aaa', fontSize: 10 }}>{open ? '▲' : '▼'}</span>
        </span>
      </button>

      {open && (
        <div className="fx-scale-in" style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: '#fff', border: '0.5px solid #e0e0e0', borderRadius: 8,
          boxShadow: '0 12px 28px -8px rgba(0,0,0,0.14)',
          maxHeight: 320, overflowY: 'auto', zIndex: 20,
          padding: 4,
          transformOrigin: 'top',
        }}>
          {options.length > 8 && (
            <input
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ara..."
              style={{
                width: '100%', padding: '8px 10px', borderRadius: 6,
                border: '0.5px solid #e0e0e0', fontSize: 12,
                outline: 'none', marginBottom: 4, background: '#fafaf9',
              }}
            />
          )}
          {filtered.length === 0 ? (
            <div style={{ padding: 12, fontSize: 12, color: '#aaa', textAlign: 'center' }}>
              {emptyHint ?? 'Seçenek bulunamadı'}
            </div>
          ) : hasGroups ? (
            Object.entries(grouped).map(([g, opts]) => (
              <div key={g}>
                <div style={{
                  fontSize: 10, fontWeight: 600, color: '#999',
                  textTransform: 'uppercase', letterSpacing: 0.5,
                  padding: '8px 10px 4px',
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
        padding: '8px 10px', borderRadius: 6,
        background: selected ? '#EEEDFE' : 'transparent',
        color: selected ? '#3C3489' : '#1a1a1a',
        fontWeight: selected ? 500 : 400,
        border: 'none', fontSize: 13, cursor: 'pointer',
      }}
      onMouseEnter={(e) => {
        if (!selected) (e.target as HTMLButtonElement).style.background = '#fafaf9'
      }}
      onMouseLeave={(e) => {
        if (!selected) (e.target as HTMLButtonElement).style.background = 'transparent'
      }}
    >
      {option.label}
    </button>
  )
}

function PanelTitle({ badge, title, subtitle }: { badge: string; title: string; subtitle: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
      <span style={{
        fontSize: 11, fontWeight: 700, letterSpacing: '0.08em',
        color: '#fff', background: 'linear-gradient(135deg, #4B41B5, #17A79A)',
        padding: '6px 10px', borderRadius: 10,
      }}>
        {badge}
      </span>
      <span style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontSize: 17, fontWeight: 600, color: '#231C52', letterSpacing: '-0.02em' }}>
          {title}
        </span>
        <span style={{ fontSize: 11.5, color: '#8B85A8' }}>{subtitle}</span>
      </span>
    </div>
  )
}

function StepPill({ label, active, done }: { label: string; active?: boolean; done?: boolean }) {
  return (
    <span style={{
      fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
      background: done
        ? '#E1F5EE'
        : active ? 'linear-gradient(115deg, #4B41B5 0%, #17A79A 140%)' : '#f0f0f0',
      color: done ? '#085041' : active ? '#fff' : '#aaa',
      transition: 'background 0.25s ease, color 0.25s ease',
    }}>
      {label}
    </span>
  )
}

function FilterChip({ label, active, onClick }: {
  label: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="pill-btn"
      style={{
        fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
        background: active ? 'linear-gradient(115deg, #4B41B5 0%, #17A79A 130%)' : '#fff',
        color: active ? '#fff' : '#666',
        border: `0.5px solid ${active ? 'transparent' : '#e0e0e0'}`,
        boxShadow: active ? '0 8px 16px -10px rgba(76, 65, 181, 0.8)' : 'none',
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}

function Spinner() {
  return (
    <span
      className="fx-spin"
      style={{
        display: 'inline-block', width: 13, height: 13, borderRadius: '50%',
        border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff',
      }}
    />
  )
}

