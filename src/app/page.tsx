'use client'
import { useState, useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { Opportunity, MatchParams } from '@/types'
import OpportunityCard from '@/components/OpportunityCard'
import EmailCapture from '@/components/EmailCapture'

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

const STUDY_LEVELS = [
  { value: 'bachelor', label: 'Lisans' },
  { value: 'master',   label: 'Yüksek Lisans' },
  { value: 'phd',      label: 'Doktora' },
  { value: 'any',      label: 'Fark etmez' },
]

const CEFR_LEVELS = [
  { value: 'A1', label: 'A1 — Başlangıç' },
  { value: 'A2', label: 'A2 — Temel' },
  { value: 'B1', label: 'B1 — Orta' },
  { value: 'B2', label: 'B2 — İyi' },
  { value: 'C1', label: 'C1 — İleri' },
  { value: 'C2', label: 'C2 — Anadil seviyesi' },
  { value: 'none', label: 'Bilmiyorum' },
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

  // Form state
  const [country, setCountry] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)
  const [citizenship, setCitizenship] = useState('TR')
  const [age, setAge] = useState('')
  const [studyLevel, setStudyLevel] = useState<string | null>(null)
  const [field, setField] = useState<string | null>(null)
  const [languageLevel, setLanguageLevel] = useState<string | null>(null)

  const selectedCountry = COUNTRIES.find(c => c.code === country) ?? null
  const targetLanguage = selectedCountry?.language ?? null

  // Ülke değişince dil seviyesini sıfırla
  useEffect(() => {
    setLanguageLevel(null)
  }, [country])

  async function handleSearch() {
    setLoading(true)

    const baseParams: MatchParams = {
      p_host_country:  country || null,
      p_category_slug: category || null,
      p_citizenship:   citizenship || 'TR',
      p_age:           age ? parseInt(age) : null,
      p_study_level:   studyLevel || null,
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
      { key: 'p_study_level',   label: 'Eğitim kademesi' },
      { key: 'p_category_slug', label: 'Kategori' },
    ]

    const params: MatchParams = { ...baseParams }
    const relaxed: string[] = []
    let data: Opportunity[] | null = null

    const run = async (p: MatchParams) => {
      const res = await supabase.rpc('match_opportunities', p)
      return (res.error ? null : (res.data as Opportunity[])) ?? []
    }

    data = await run(params)

    for (const f of fallbackOrder) {
      if (data && data.length > 0) break
      if (params[f.key] == null) continue
      ;(params as Record<string, unknown>)[f.key as string] = null
      relaxed.push(f.label)
      data = await run(params)
    }

    setResults(data ?? [])
    setRelaxedFilters(relaxed)
    setActiveCategory(null)
    setSearchSnapshot({ country, category, citizenship, studyLevel, field, targetLanguage, languageLevel })
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
    <main style={{ minHeight: '100vh', background: '#fafaf9', padding: '40px 16px' }}>
      <div style={{ maxWidth: 600, margin: '0 auto' }}>

        {/* Logo */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
          </div>
          <div style={{ fontSize: 13, color: '#888', marginTop: 4 }}>
            Burs, gönüllülük, staj — bedava yurt dışı fırsatları
          </div>
        </div>

        {/* Step pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 28 }}>
          <StepPill label="1 · Profil" active />
          <span style={{ color: '#ccc', fontSize: 12 }}>›</span>
          <StepPill label="2 · Sonuçlar" />
        </div>

        {/* Form card */}
        <div style={{
          background: '#fff', border: '0.5px solid #e0e0e0',
          borderRadius: 16, padding: '24px 20px',
        }}>

          <SectionTitle>Profilini gir</SectionTitle>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            <Field label="Vatandaşlık">
              <input
                value={citizenship}
                onChange={e => setCitizenship(e.target.value.toUpperCase())}
                placeholder="TR"
                maxLength={2}
                style={inputStyle}
              />
            </Field>
            <Field label="Yaş (opsiyonel)">
              <input
                type="number"
                value={age}
                onChange={e => setAge(e.target.value)}
                placeholder="23"
                style={inputStyle}
              />
            </Field>
          </div>

          <Field label="Eğitim kademesi" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {STUDY_LEVELS.map(l => (
                <Tag
                  key={l.value}
                  label={l.label}
                  selected={studyLevel === l.value}
                  onClick={() => setStudyLevel(studyLevel === l.value ? null : l.value)}
                  color="#534AB7"
                />
              ))}
            </div>
          </Field>

          {/* Bölüm — gruplandırılmış dropdown */}
          <Field label="Bölüm (opsiyonel — eşleşme olmazsa otomatik geçeriz)" style={{ marginBottom: 24 }}>
            <Picker
              placeholder="Bölüm seç"
              value={field}
              valueLabel={field ? fieldLabel(field) : null}
              options={FIELDS.map(f => ({ value: f.value, label: f.label, group: f.group }))}
              onChange={setField}
              emptyHint="Yükleniyor..."
            />
          </Field>

          <SectionTitle>Nereye gitmek istiyorsun?</SectionTitle>
          <p style={{ fontSize: 11, color: '#aaa', marginBottom: 10 }}>
            Önce ülke seç — sonra o ülkenin dilindeki seviyeni soracağız.
          </p>

          {/* Ülke — dropdown */}
          <Field label="Ülke" style={{ marginBottom: 16 }}>
            <Picker
              placeholder="Ülke seç"
              value={country}
              valueLabel={selectedCountry?.label ?? null}
              options={COUNTRIES.map(c => ({ value: c.code, label: c.label }))}
              onChange={setCountry}
            />
          </Field>

          {/* Dil seviyesi — sadece ülke seçildiyse, tamamen opsiyonel */}
          {targetLanguage && (
            <Field label={`${targetLanguage} seviyen (opsiyonel)`} style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {CEFR_LEVELS.map(l => (
                  <Tag
                    key={l.value}
                    label={l.label}
                    selected={languageLevel === l.value}
                    onClick={() => setLanguageLevel(languageLevel === l.value ? null : l.value)}
                    color="#0F6E56"
                  />
                ))}
              </div>
              <div style={{ fontSize: 10, color: '#aaa', marginTop: 6, lineHeight: 1.5 }}>
                Boş bırakabilirsin — dil bilmeden de başvurabileceğin bol bol fırsat var.
                Eşleşme düşük çıkarsa bu filtreyi otomatik gevşetiyoruz.
              </div>
            </Field>
          )}

          <Field label="Kategori (opsiyonel)" style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {CATEGORIES.map(c => (
                <Tag
                  key={c.slug}
                  label={c.label}
                  selected={category === c.slug}
                  onClick={() => setCategory(category === c.slug ? null : c.slug)}
                  color="#534AB7"
                />
              ))}
            </div>
          </Field>

          <button
            onClick={handleSearch}
            disabled={loading}
            style={{
              width: '100%', padding: '12px', borderRadius: 10,
              background: loading ? '#AFA9EC' : '#534AB7',
              color: '#fff', border: 'none', fontSize: 14,
              fontWeight: 500, cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Aranıyor...' : 'Fırsatları Göster →'}
          </button>
        </div>
      </div>
    </main>
  )

  // ─── RESULTS ────────────────────────────────────────────
  return (
    <main style={{ minHeight: '100vh', background: '#fafaf9', padding: '40px 16px' }}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
          </div>
          <button
            onClick={() => setStep('form')}
            style={{
              fontSize: 12, color: '#534AB7', background: 'none',
              border: '0.5px solid #AFA9EC', borderRadius: 8,
              padding: '6px 12px', cursor: 'pointer',
            }}
          >
            ← Aramayı düzenle
          </button>
        </div>

        {/* Step pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 20 }}>
          <StepPill label="1 · Profil ✓" done />
          <span style={{ color: '#ccc', fontSize: 12 }}>›</span>
          <StepPill label="2 · Sonuçlar" active />
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          <FilterChip
            label={`Tümü (${results.length})`}
            active={activeCategory === null}
            onClick={() => setActiveCategory(null)}
          />
          {CATEGORIES.filter(c => categoryCounts[c.slug] > 0).map(c => (
            <FilterChip
              key={c.slug}
              label={`${c.label} (${categoryCounts[c.slug]})`}
              active={activeCategory === c.slug}
              onClick={() => setActiveCategory(c.slug)}
            />
          ))}
        </div>

        {/* Result count */}
        <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>
          {filtered.length} fırsat bulundu
          {country && ` · ${COUNTRIES.find(c => c.code === country)?.label}`}
          {category && ` · ${CATEGORIES.find(c => c.slug === category)?.label}`}
          {targetLanguage && languageLevel && languageLevel !== 'none' && ` · ${targetLanguage} ${languageLevel}`}
        </div>

        {/* Gevşetilen filtreler banner'ı */}
        {relaxedFilters.length > 0 && results.length > 0 && (
          <div style={{
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
          <div style={{
            textAlign: 'center', padding: '60px 20px',
            color: '#aaa', fontSize: 14,
          }}>
            Bu kriterlere uygun fırsat bulunamadı.
            <br />
            <button
              onClick={() => setStep('form')}
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
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: '#fff', border: '0.5px solid #e0e0e0', borderRadius: 8,
          boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
          maxHeight: 320, overflowY: 'auto', zIndex: 20,
          padding: 4,
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

function StepPill({ label, active, done }: { label: string; active?: boolean; done?: boolean }) {
  return (
    <span style={{
      fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
      background: done ? '#E1F5EE' : active ? '#534AB7' : '#f0f0f0',
      color: done ? '#085041' : active ? '#fff' : '#aaa',
    }}>
      {label}
    </span>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 13, fontWeight: 500, color: '#333', marginBottom: 10, marginTop: 4 }}>
      {children}
    </div>
  )
}

function Field({ label, children, style }: {
  label: string; children: React.ReactNode; style?: React.CSSProperties
}) {
  return (
    <div style={style}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 5 }}>{label}</div>
      {children}
    </div>
  )
}

function Tag({ label, selected, onClick, color }: {
  label: string; selected: boolean; onClick: () => void; color: string
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
        background: selected ? color : 'transparent',
        color: selected ? '#fff' : color,
        border: `0.5px solid ${color}66`,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}

function FilterChip({ label, active, onClick }: {
  label: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
        background: active ? '#534AB7' : '#fff',
        color: active ? '#fff' : '#666',
        border: `0.5px solid ${active ? '#534AB7' : '#e0e0e0'}`,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 8,
  border: '0.5px solid #e0e0e0', fontSize: 13,
  outline: 'none', background: '#fff', color: '#1a1a1a',
}
