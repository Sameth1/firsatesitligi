'use client'
import { useState, useEffect, useRef } from 'react'
import { supabase } from '@/lib/supabase'

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

  // Opsiyonel kimlik
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')

  // Expand — opsiyonel detaylar
  const [expanded, setExpanded] = useState(false)
  const [hostCountry, setHostCountry] = useState(
    (searchSnapshot?.country as string) ?? ''
  )
  const [deadlineText, setDeadlineText] = useState('')
  const [fundingType, setFundingType] = useState<string | null>(null)
  const [eligibility, setEligibility] = useState('')
  const [languageReq, setLanguageReq] = useState('')
  const [description, setDescription] = useState('')

  // Honeypot
  const [honeypot, setHoneypot] = useState('')

  // State
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')

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

    const { error } = await supabase.from('submissions').insert({
      title: title.trim(),
      url: url.trim(),
      category_slug: categorySlug,
      submitter_nickname: nickname.trim() || null,
      submitter_email: email.trim() || null,
      host_countries: hostCountry ? [hostCountry.toUpperCase()] : [],
      deadline_text: deadlineText || null,
      funding_type: fundingType,
      eligibility_notes: eligibility || null,
      language_requirement: languageReq || null,
      description: description || null,
      submission_origin: 'human',
      review_stage: 'human_review',
    })

    setStatus(error ? 'error' : 'done')
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
              {email
                ? 'Teşekkürler, ekibimiz inceleyecek. Durum email\'ine düşecek.'
                : 'Teşekkürler, ekibimiz inceleyecek.'}
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

            {/* Opsiyonel kimlik bloğu */}
            <div style={{
              borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 14, marginBottom: 14,
            }}>
              <div style={{ fontSize: 11, color: 'var(--text-low)', marginBottom: 10 }}>
                İsteğe bağlı
              </div>

              <Label text="Takma ad" />
              <input
                value={nickname}
                onChange={e => setNickname(e.target.value)}
                placeholder="@ayse (fırsatın altında görünür)"
                style={{ ...inputStyle, marginBottom: 10 }}
              />

              <Label text="E-posta" />
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="Geri dönüş istersen e-postanı bırak"
                type="email"
                style={{ ...inputStyle, marginBottom: 2 }}
              />
              <div style={{ fontSize: 10.5, color: 'var(--text-low)', marginBottom: 12, lineHeight: 1.5 }}>
                Revize veya onay durumunda haber vereceğiz. Boş bırakırsan rahatsız etmeyiz.
              </div>
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
                    <Label text="Ülke kodu" />
                    <input
                      value={hostCountry}
                      onChange={e => setHostCountry(e.target.value)}
                      placeholder="DE, FR, ES..."
                      maxLength={2}
                      style={inputStyle}
                    />
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

                <Label text="Kimler başvurabilir" />
                <input
                  value={eligibility}
                  onChange={e => setEligibility(e.target.value)}
                  placeholder="18-30 yaş, tüm vatandaşlıklar"
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
                Bir hata oluştu, tekrar dene.
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
