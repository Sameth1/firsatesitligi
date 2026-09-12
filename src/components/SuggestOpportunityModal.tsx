'use client'
import { useState, useEffect, useRef } from 'react'
import { COUNTRIES } from '@/lib/countries'

const CATEGORIES = [
  { slug: 'scholarship',   label: 'Burs' },
  { slug: 'volunteering',  label: 'Gönüllülük' },
  { slug: 'youth_project', label: 'Gençlik Projesi' },
  { slug: 'internship',    label: 'Staj' },
  { slug: 'summer_school', label: 'Yaz Okulu' },
  { slug: 'exchange',      label: 'Değişim' },
]

const FUNDING_TYPES = [
  { value: 'full',    label: 'Tam Burs' },
  { value: 'partial', label: 'Kısmi Burs' },
  { value: 'free',    label: 'Ücretsiz' },
  { value: 'stipend', label: 'Harçlık' },
]

const STUDY_LEVELS = [
  { value: 'high_school', label: 'Lise' },
  { value: 'bachelor',    label: 'Lisans' },
  { value: 'master',      label: 'Yüksek Lisans' },
  { value: 'phd',         label: 'Doktora' },
  { value: 'graduate',    label: 'Mezun / Genç Profesyonel' },
]

interface Props {
  searchSnapshot?: Record<string, unknown>
  onClose: () => void
}

export default function SuggestOpportunityModal({ searchSnapshot, onClose }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null)

  // Zorunlu alanlar
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [categorySlug, setCategorySlug] = useState<string | null>(
    (searchSnapshot?.category as string) ?? null
  )

  // Expand — opsiyonel detaylar
  const [expanded, setExpanded] = useState(false)
  const [hostCountry, setHostCountry] = useState(
    (searchSnapshot?.country as string) ?? ''
  )
  const [deadlineText, setDeadlineText] = useState('')
  const [fundingType, setFundingType] = useState<string | null>(null)
  const [ageMin, setAgeMin] = useState('')
  const [ageMax, setAgeMax] = useState('')
  const [selectedStudyLevels, setSelectedStudyLevels] = useState<string[]>([])
  const [citizenshipOnlyTR, setCitizenshipOnlyTR] = useState(false)
  const [eligibility, setEligibility] = useState('')
  const [languageReq, setLanguageReq] = useState('')
  const [description, setDescription] = useState('')

  // Honeypot
  const [honeypot, setHoneypot] = useState('')

  // State
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || !url.trim() || !categorySlug) return
    if (honeypot) return // bot

    setStatus('loading')
    setErrorMessage('')

    try {
      const response = await fetch('/api/submit-opportunity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          url: url.trim(),
          category_slug: categorySlug,
          // Takma ad ve e-posta artık sorulmuyor: UX kuralı 3 — işlevsel
          // olarak şart olmayan kişisel veri istenmez. Sunucu tarafı bu
          // alanları hâlâ kabul ediyor, biz göndermiyoruz.
          host_countries: hostCountry ? [hostCountry] : [],
          deadline_text: deadlineText || null,
          funding_type: fundingType,
          age_min: ageMin ? parseInt(ageMin, 10) : null,
          age_max: ageMax ? parseInt(ageMax, 10) : null,
          study_level: selectedStudyLevels.length > 0 ? selectedStudyLevels : null,
          eligible_citizenships: citizenshipOnlyTR ? ['TR'] : null,
          eligibility_notes: eligibility || null,
          language_requirement: languageReq || null,
          description: description || null,
        }),
      })
      const result = await response.json().catch(() => null) as { error?: string } | null
      if (!response.ok) {
        throw new Error(result?.error || `Öneri gönderilemedi (HTTP ${response.status}).`)
      }
      setStatus('done')
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : 'Öneri gönderilemedi. Tekrar dene.',
      )
      setStatus('error')
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 10px', borderRadius: 8,
    border: '1px solid rgba(255,255,255,0.14)', fontSize: 13,
    outline: 'none', background: 'rgba(255,255,255,0.05)', color: 'var(--text-hi)',
  }

  return (
    <div
      ref={overlayRef}
      onClick={e => { if (e.target === overlayRef.current) onClose() }}
      className="fx-fade-in"
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(4, 3, 14, 0.72)',
        backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}
    >
      <div className="fx-scale-in" style={{
        background: 'rgba(16, 12, 44, 0.97)',
        border: '1px solid rgba(255,255,255,0.12)',
        boxShadow: '0 40px 90px -30px rgba(0,0,0,0.95)',
        borderRadius: 22,
        maxWidth: 520, width: '100%', maxHeight: '90vh',
        overflowY: 'auto', padding: '26px 22px',
      }}>
        {status === 'done' ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{
              fontSize: 14, fontWeight: 500, color: '#7BF0DC', marginBottom: 8,
            }}>
              Teşekkürler, ekibimiz inceleyecek.
            </div>
            <button
              onClick={onClose}
              style={{
                marginTop: 8, padding: '8px 20px', borderRadius: 8,
                background: 'var(--grad-brand)', color: '#150F35', border: 'none',
                fontSize: 13, fontWeight: 700, cursor: 'pointer',
              }}
            >
              Kapat
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginBottom: 16,
            }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-hi)' }}>
                Fırsat Öner
              </div>
              <button
                type="button"
                onClick={onClose}
                style={{
                  background: 'none', border: 'none', fontSize: 18,
                  color: 'var(--text-low)', cursor: 'pointer', padding: '0 4px',
                }}
              >
                ×
              </button>
            </div>

            {/* Zorunlu: Başlık */}
            <Label text="Başlık *" />
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Erasmus+ Gençlik Değişimi — Portekiz"
              required
              style={{ ...inputStyle, marginBottom: 12 }}
            />

            {/* Zorunlu: URL */}
            <Label text="Resmi başvuru linki *" />
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://..."
              type="url"
              required
              style={{ ...inputStyle, marginBottom: 12 }}
            />

            {/* Zorunlu: Kategori */}
            <Label text="Kategori *" />
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
              {CATEGORIES.map(c => (
                <button
                  key={c.slug}
                  type="button"
                  onClick={() => setCategorySlug(categorySlug === c.slug ? null : c.slug)}
                  style={{
                    fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
                    background: categorySlug === c.slug ? 'rgba(124, 92, 255, 0.35)' : 'rgba(255,255,255,0.04)',
                    color: categorySlug === c.slug ? '#fff' : 'var(--text-mid)',
                    border: `1px solid ${categorySlug === c.slug ? 'rgba(124, 92, 255, 0.8)' : 'rgba(255,255,255,0.12)'}`, cursor: 'pointer',
                  }}
                >
                  {c.label}
                </button>
              ))}
            </div>

            {/* Expand — opsiyonel detaylar */}
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              style={{
                background: 'none', border: 'none', color: 'var(--violet)',
                fontSize: 12, fontWeight: 500, cursor: 'pointer',
                padding: 0, marginBottom: expanded ? 12 : 0,
              }}
            >
              {expanded ? '▲ Daha az detay' : '▼ Daha fazla detay ekle (opsiyonel)'}
            </button>

            {expanded && (
              <div style={{ marginTop: 8 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                  <div>
                    <Label text="Ülke" />
                    {/* Eskiden iki harfli kod isteniyordu ("DE, FR, ES...").
                        Kullanıcı ISO kodu bilmek zorunda değil; yanlış kod
                        girilirse kayıt o ülkeyi seçenlere hiç görünmüyordu.
                        Artık ad seçiliyor, koda biz çeviriyoruz. */}
                    <select
                      value={hostCountry}
                      onChange={e => setHostCountry(e.target.value)}
                      style={{ ...inputStyle, appearance: 'none', cursor: 'pointer',
                               colorScheme: 'dark' }}
                    >
                      <option value="">Ülke seç…</option>
                      <option value="*">Küresel / çevrim içi</option>
                      {COUNTRIES.map(c => (
                        <option key={c.code} value={c.code}>{c.nameTr}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label text="Son başvuru tarihi" />
                    <input
                      value={deadlineText}
                      onChange={e => setDeadlineText(e.target.value)}
                      placeholder="15 Eylül 2026"
                      style={inputStyle}
                    />
                  </div>
                </div>

                <Label text="Finansman türü" />
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  {FUNDING_TYPES.map(f => (
                    <button
                      key={f.value}
                      type="button"
                      onClick={() => setFundingType(fundingType === f.value ? null : f.value)}
                      style={{
                        fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
                        background: fundingType === f.value ? 'rgba(43, 224, 200, 0.28)' : 'rgba(255,255,255,0.04)',
                        color: fundingType === f.value ? '#fff' : '#7BF0DC',
                        border: `1px solid ${fundingType === f.value ? 'rgba(43, 224, 200, 0.75)' : 'rgba(255,255,255,0.12)'}`, cursor: 'pointer',
                      }}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>

                {/* Yaş Aralığı */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                  <div>
                    <Label text="Min. Yaş" />
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={ageMin}
                      onChange={e => setAgeMin(e.target.value)}
                      placeholder="Örn: 18"
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <Label text="Maks. Yaş" />
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={ageMax}
                      onChange={e => setAgeMax(e.target.value)}
                      placeholder="Örn: 30"
                      style={inputStyle}
                    />
                  </div>
                </div>

                {/* Öğrenim Seviyesi */}
                <Label text="Kimler için? (Öğrenim Seviyesi)" />
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  {STUDY_LEVELS.map(s => {
                    const active = selectedStudyLevels.includes(s.value)
                    return (
                      <button
                        key={s.value}
                        type="button"
                        onClick={() => {
                          setSelectedStudyLevels(prev =>
                            prev.includes(s.value) ? prev.filter(x => x !== s.value) : [...prev, s.value]
                          )
                        }}
                        style={{
                          fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
                          background: active ? 'rgba(175, 137, 255, 0.28)' : 'rgba(255,255,255,0.04)',
                          color: active ? '#fff' : '#C4A8FF',
                          border: `1px solid ${active ? 'rgba(175, 137, 255, 0.75)' : 'rgba(255,255,255,0.12)'}`,
                          cursor: 'pointer',
                        }}
                      >
                        {s.label}
                      </button>
                    )
                  })}
                </div>

                {/* Vatandaşlık Filtresi */}
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, cursor: 'pointer', fontSize: 12, color: 'var(--text-mid)' }}>
                  <input
                    type="checkbox"
                    checked={citizenshipOnlyTR}
                    onChange={e => setCitizenshipOnlyTR(e.target.checked)}
                    style={{ accentColor: '#2BE0C8', cursor: 'pointer', width: 14, height: 14 }}
                  />
                  <span>Yalnızca T.C. Vatandaşlarına açık</span>
                </label>

                {/* Diğer Başvuru Şartları */}
                <Label text="Diğer başvuru koşulları (Not ortalaması, bölüm vb.)" />
                <input
                  value={eligibility}
                  onChange={e => setEligibility(e.target.value)}
                  placeholder="Örn: 2.50+ GANO, Mühendislik öğrencisi vb."
                  style={{ ...inputStyle, marginBottom: 10 }}
                />

                <Label text="Dil şartı" />
                <input
                  value={languageReq}
                  onChange={e => setLanguageReq(e.target.value)}
                  placeholder="B2 İngilizce veya yok"
                  style={{ ...inputStyle, marginBottom: 10 }}
                />

                <Label text="Açıklama / notlar" />
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="Ek bilgi varsa yaz..."
                  rows={3}
                  style={{
                    ...inputStyle,
                    resize: 'vertical',
                    marginBottom: 10,
                  }}
                />
              </div>
            )}

            {/* Honeypot */}
            <div style={{ position: 'absolute', left: -9999, top: -9999 }} aria-hidden="true">
              <input
                name="website"
                tabIndex={-1}
                autoComplete="off"
                value={honeypot}
                onChange={e => setHoneypot(e.target.value)}
              />
            </div>

            <button
              type="submit"
              disabled={status === 'loading' || !title.trim() || !url.trim() || !categorySlug}
              style={{
                width: '100%', padding: '12px', borderRadius: 10, marginTop: 16,
                background: 'var(--grad-brand)',
                color: '#150F35', border: 'none', fontSize: 14, fontWeight: 700,
                cursor: status === 'loading' ? 'not-allowed' : 'pointer',
                opacity: (status === 'loading' || !title.trim() || !url.trim() || !categorySlug)
                  ? 0.5 : 1,
              }}
            >
              {status === 'loading' ? 'Gönderiliyor...' : 'Gönder'}
            </button>

            {status === 'error' && (
              <div style={{ fontSize: 11, color: '#FFB4B4', marginTop: 8, textAlign: 'center' }}>
                {errorMessage}
              </div>
            )}
          </form>
        )}
      </div>
    </div>
  )
}

function Label({ text }: { text: string }) {
  return (
    <div style={{ fontSize: 11.5, color: 'var(--text-mid)', marginBottom: 4 }}>{text}</div>
  )
}
