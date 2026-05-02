'use client'
import { useState, useEffect, use } from 'react'
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

interface Submission {
  id: string
  title: string
  url: string
  category_slug: string | null
  host_countries: string[]
  deadline_text: string | null
  funding_type: string | null
  funding_notes: string | null
  eligibility_notes: string | null
  language_requirement: string | null
  age_min: number | null
  age_max: number | null
  submitter_email: string | null
  submitter_nickname: string | null
  status: string
  admin_note: string | null
  description: string | null
  created_at: string
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 8,
  border: '0.5px solid #e0e0e0', fontSize: 13,
  outline: 'none', background: '#fff', color: '#1a1a1a',
}

export default function SubmissionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const [sub, setSub] = useState<Submission | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [reviseNote, setReviseNote] = useState('')

  // Editable fields
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [categorySlug, setCategorySlug] = useState<string | null>(null)
  const [hostCountries, setHostCountries] = useState('')
  const [deadlineText, setDeadlineText] = useState('')
  const [fundingType, setFundingType] = useState<string | null>(null)
  const [fundingNotes, setFundingNotes] = useState('')
  const [eligibility, setEligibility] = useState('')
  const [languageReq, setLanguageReq] = useState('')
  const [ageMin, setAgeMin] = useState('')
  const [ageMax, setAgeMax] = useState('')

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('submissions')
        .select('*')
        .eq('id', id)
        .single()

      if (data) {
        const s = data as Submission
        setSub(s)
        setTitle(s.title)
        setUrl(s.url)
        setCategorySlug(s.category_slug)
        setHostCountries(s.host_countries?.join(', ') ?? '')
        setDeadlineText(s.deadline_text ?? '')
        setFundingType(s.funding_type)
        setFundingNotes(s.funding_notes ?? '')
        setEligibility(s.eligibility_notes ?? '')
        setLanguageReq(s.language_requirement ?? '')
        setAgeMin(s.age_min?.toString() ?? '')
        setAgeMax(s.age_max?.toString() ?? '')
      }
      setLoading(false)
    }
    load()
  }, [id])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  async function saveEdits() {
    await supabase
      .from('submissions')
      .update({
        title,
        url,
        category_slug: categorySlug,
        host_countries: hostCountries ? hostCountries.split(',').map(s => s.trim().toUpperCase()) : [],
        deadline_text: deadlineText || null,
        funding_type: fundingType,
        funding_notes: fundingNotes || null,
        eligibility_notes: eligibility || null,
        language_requirement: languageReq || null,
        age_min: ageMin ? parseInt(ageMin) : null,
        age_max: ageMax ? parseInt(ageMax) : null,
      })
      .eq('id', id)

    showToast('Kaydedildi')
  }

  async function handleApprove() {
    await saveEdits()
    setActionLoading(true)
    const { error } = await supabase.rpc('approve_submission', { p_id: id })
    setActionLoading(false)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      showToast('Onaylandı, fırsat sisteme eklendi.')
      setSub(prev => prev ? { ...prev, status: 'approved' } : null)
    }
  }

  async function handleRevise() {
    if (!reviseNote.trim()) return
    setActionLoading(true)
    const { error } = await supabase.rpc('request_revision', {
      p_id: id,
      p_note: reviseNote.trim(),
    })
    setActionLoading(false)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      showToast('Revize istendi.')
      setSub(prev => prev ? { ...prev, status: 'needs_revision' } : null)
      setReviseNote('')
    }
  }

  async function handleReject() {
    const note = prompt('Red sebebi (opsiyonel):') ?? ''
    setActionLoading(true)
    const { error } = await supabase.rpc('reject_submission', {
      p_id: id,
      p_note: note || null,
    })
    setActionLoading(false)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      showToast('Reddedildi.')
      setSub(prev => prev ? { ...prev, status: 'rejected' } : null)
    }
  }

  if (loading) {
    return (
      <main style={{ minHeight: '100vh', background: '#fafaf9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#aaa', fontSize: 13 }}>Yükleniyor...</span>
      </main>
    )
  }

  if (!sub) {
    return (
      <main style={{ minHeight: '100vh', background: '#fafaf9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#aaa', fontSize: 13 }}>Öneri bulunamadı.</span>
      </main>
    )
  }

  const isPending = sub.status === 'pending'

  return (
    <main style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
            <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Admin</span>
          </div>
          <a
            href="/admin"
            style={{
              fontSize: 12, color: '#534AB7', textDecoration: 'none',
              border: '0.5px solid #AFA9EC', borderRadius: 8,
              padding: '6px 12px',
            }}
          >
            ← Tüm öneriler
          </a>
        </div>

        {/* Submitter info */}
        <div style={{
          background: '#f5f5f5', borderRadius: 10, padding: '10px 14px',
          fontSize: 12, color: '#666', marginBottom: 16,
          display: 'flex', gap: 16, flexWrap: 'wrap',
        }}>
          <span>Gönderen: <strong>{sub.submitter_nickname ? `@${sub.submitter_nickname}` : 'Anonim'}</strong></span>
          {sub.submitter_email ? (
            <span>✉ {sub.submitter_email}</span>
          ) : (
            <span style={{ color: '#ccc' }}>✉ yok — revize maili gönderilemez</span>
          )}
          <span>{new Date(sub.created_at).toLocaleDateString('tr-TR')}</span>
        </div>

        {/* Editable form */}
        <div style={{
          background: '#fff', border: '0.5px solid #e0e0e0',
          borderRadius: 16, padding: '24px 20px',
        }}>
          <Label text="Başlık" />
          <input value={title} onChange={e => setTitle(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="URL" />
          <input value={url} onChange={e => setUrl(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="Kategori" />
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {CATEGORIES.map(c => (
              <button
                key={c.slug}
                type="button"
                onClick={() => setCategorySlug(categorySlug === c.slug ? null : c.slug)}
                style={{
                  fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
                  background: categorySlug === c.slug ? '#534AB7' : 'transparent',
                  color: categorySlug === c.slug ? '#fff' : '#534AB7',
                  border: '0.5px solid #534AB766', cursor: 'pointer',
                }}
              >
                {c.label}
              </button>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
            <div>
              <Label text="Ülkeler (virgülle)" />
              <input value={hostCountries} onChange={e => setHostCountries(e.target.value)} placeholder="DE, FR" style={inputStyle} />
            </div>
            <div>
              <Label text="Son başvuru" />
              <input value={deadlineText} onChange={e => setDeadlineText(e.target.value)} placeholder="15 Eylül 2026" style={inputStyle} />
            </div>
          </div>

          <Label text="Finansman türü" />
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {FUNDING_TYPES.map(f => (
              <button
                key={f.value}
                type="button"
                onClick={() => setFundingType(fundingType === f.value ? null : f.value)}
                style={{
                  fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
                  background: fundingType === f.value ? '#1a6b5a' : 'transparent',
                  color: fundingType === f.value ? '#fff' : '#1a6b5a',
                  border: '0.5px solid #1a6b5a66', cursor: 'pointer',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          <Label text="Finansman notları" />
          <input value={fundingNotes} onChange={e => setFundingNotes(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="Kimler başvurabilir" />
          <input value={eligibility} onChange={e => setEligibility(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="Dil şartı" />
          <input value={languageReq} onChange={e => setLanguageReq(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
            <div>
              <Label text="Min yaş" />
              <input type="number" value={ageMin} onChange={e => setAgeMin(e.target.value)} style={inputStyle} />
            </div>
            <div>
              <Label text="Max yaş" />
              <input type="number" value={ageMax} onChange={e => setAgeMax(e.target.value)} style={inputStyle} />
            </div>
          </div>

          {/* Description (readonly from user) */}
          {sub.description && (
            <>
              <Label text="Kullanıcı notu" />
              <div style={{
                background: '#fafaf9', borderRadius: 8, padding: '8px 10px',
                fontSize: 12, color: '#666', marginBottom: 12, lineHeight: 1.5,
              }}>
                {sub.description}
              </div>
            </>
          )}

          {/* Save button */}
          {isPending && (
            <button
              onClick={saveEdits}
              style={{
                width: '100%', padding: '10px', borderRadius: 8,
                background: '#f5f5f5', color: '#333', border: '0.5px solid #e0e0e0',
                fontSize: 13, fontWeight: 500, cursor: 'pointer', marginBottom: 12,
              }}
            >
              Değişiklikleri Kaydet
            </button>
          )}

          {/* Action buttons */}
          {isPending && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <button
                onClick={handleApprove}
                disabled={actionLoading}
                style={{
                  flex: 1, padding: '12px', borderRadius: 10,
                  background: '#085041', color: '#fff', border: 'none',
                  fontSize: 14, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Kaydet ve Onayla
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading}
                style={{
                  padding: '12px 16px', borderRadius: 10,
                  background: '#FDE8E8', color: '#A32D2D', border: 'none',
                  fontSize: 14, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Reddet
              </button>
            </div>
          )}

          {/* Revise */}
          {isPending && sub.submitter_email && (
            <div>
              <Label text="Revize notu (kullanıcıya gider)" />
              <div style={{ display: 'flex', gap: 8 }}>
                <textarea
                  value={reviseNote}
                  onChange={e => setReviseNote(e.target.value)}
                  placeholder="Kullanıcıya not yaz..."
                  rows={2}
                  style={{
                    flex: 1, padding: '8px 10px', borderRadius: 8,
                    border: '0.5px solid #e0e0e0', fontSize: 12,
                    outline: 'none', resize: 'vertical',
                  }}
                />
                <button
                  onClick={handleRevise}
                  disabled={!reviseNote.trim() || actionLoading}
                  style={{
                    padding: '8px 14px', borderRadius: 8,
                    background: '#534AB7', color: '#fff',
                    border: 'none', fontSize: 12, fontWeight: 500,
                    cursor: 'pointer', alignSelf: 'flex-end',
                    opacity: reviseNote.trim() ? 1 : 0.5,
                  }}
                >
                  Revize İste
                </button>
              </div>
            </div>
          )}

          {/* Status banner */}
          {!isPending && (
            <div style={{
              background: sub.status === 'approved' ? '#E1F5EE' : sub.status === 'rejected' ? '#FDE8E8' : '#EEEDFE',
              borderRadius: 10, padding: '12px 14px',
              fontSize: 13, fontWeight: 500,
              color: sub.status === 'approved' ? '#085041' : sub.status === 'rejected' ? '#A32D2D' : '#3C3489',
            }}>
              {sub.status === 'approved' && 'Bu öneri onaylanmış.'}
              {sub.status === 'rejected' && 'Bu öneri reddedilmiş.'}
              {sub.status === 'needs_revision' && 'Bu öneri revize bekliyor.'}
            </div>
          )}
        </div>

        {/* Toast */}
        {toast && (
          <div style={{
            position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
            background: '#1a1a1a', color: '#fff', padding: '10px 20px',
            borderRadius: 10, fontSize: 13, fontWeight: 500, zIndex: 200,
            boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
          }}>
            {toast}
          </div>
        )}
      </div>
    </main>
  )
}

function Label({ text }: { text: string }) {
  return (
    <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>{text}</div>
  )
}
