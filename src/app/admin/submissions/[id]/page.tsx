'use client'
import { useState, useEffect, use } from 'react'
import { supabase } from '@/lib/supabase'
import RejectComposer from '../../reject-composer'

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

interface Submission {
  id: string
  title: string
  url: string
  source_url: string | null
  details_url: string | null
  application_route_status: 'verified' | 'unverified' | 'missing'
  application_method: 'online_form' | 'portal' | 'email' | 'document' | null
  category_slug: string | null
  host_countries: string[]
  eligible_citizenships: string[] | null
  target_fields: string[] | null
  study_level: string[] | null
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
  submission_origin: 'human' | 'agent'
  review_stage: string
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
  const [showReject, setShowReject] = useState(false)
  const [showRouteVerifyModal, setShowRouteVerifyModal] = useState(false)

  // Editable fields
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [detailsUrl, setDetailsUrl] = useState('')
  const [applicationMethod, setApplicationMethod] = useState<Submission['application_method']>('portal')
  const [routeVerified, setRouteVerified] = useState(false)
  const [categorySlug, setCategorySlug] = useState<string | null>(null)
  const [hostCountries, setHostCountries] = useState('')
  const [citizenships, setCitizenships] = useState('')
  const [targetFields, setTargetFields] = useState('')
  const [deadlineText, setDeadlineText] = useState('')
  const [fundingType, setFundingType] = useState<string | null>(null)
  const [fundingNotes, setFundingNotes] = useState('')
  const [studyLevel, setStudyLevel] = useState<string[]>([])
  const [eligibility, setEligibility] = useState('')
  const [languageReq, setLanguageReq] = useState('')
  const [ageMin, setAgeMin] = useState('')
  const [ageMax, setAgeMax] = useState('')

  useEffect(() => {
    async function load() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        window.location.href = '/admin/login'
        return
      }

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
        setDetailsUrl(s.details_url ?? s.source_url ?? s.url)
        setApplicationMethod(s.application_method ?? 'portal')
        setRouteVerified(s.application_route_status === 'verified')
        setCategorySlug(s.category_slug)
        setHostCountries(s.host_countries?.join(', ') ?? '')
        setCitizenships(s.eligible_citizenships?.join(', ') ?? '')
        setTargetFields(s.target_fields?.join(', ') ?? '')
        setStudyLevel(s.study_level ?? [])
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

  async function saveEdits(options?: { quietSuccess?: boolean; forceVerified?: boolean }): Promise<boolean> {
    const { quietSuccess = false, forceVerified } = options ?? {}
    const isVerified = forceVerified !== undefined ? forceVerified : routeVerified

    const { error } = await supabase
      .from('submissions')
      .update({
        title,
        url,
        details_url: detailsUrl || url,
        application_route_status: isVerified ? 'verified' : 'unverified',
        application_method: isVerified ? (applicationMethod || 'portal') : null,
        application_url_verified_at: isVerified ? new Date().toISOString() : null,
        application_url_final: isVerified ? url : null,
        application_url_evidence: isVerified ? 'İnsan admin bağlantıyı açarak doğruladı' : null,
        category_slug: categorySlug,
        host_countries: hostCountries ? hostCountries.split(',').map(s => s.trim().toUpperCase()) : [],
        // 107: onay RPC'si bu iki alanı submission'dan okuyor. Boş = kısıt yok
        // ({all} yazılır). Yanlış daraltmak, o uyruğu/bölümü seçen uygun bir
        // adayı sonuçlardan siler — emin değilsen boş bırak.
        eligible_citizenships: citizenships
          ? citizenships.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
          : null,
        target_fields: targetFields
          ? targetFields.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
          : null,
        deadline_text: deadlineText || null,
        funding_type: fundingType,
        funding_notes: fundingNotes || null,
        study_level: studyLevel.length > 0 ? studyLevel : null,
        eligibility_notes: eligibility || null,
        language_requirement: languageReq || null,
        age_min: ageMin ? parseInt(ageMin) : null,
        age_max: ageMax ? parseInt(ageMax) : null,
      })
      .eq('id', id)

    if (error) {
      showToast('Hata: ' + error.message)
      return false
    }
    if (isVerified) setRouteVerified(true)
    if (!quietSuccess) showToast('Kaydedildi')
    return true
  }

  async function handleApprove(forceVerify = false) {
    if (!routeVerified && !forceVerify) {
      setShowRouteVerifyModal(true)
      return
    }

    if (forceVerify) {
      setRouteVerified(true)
    }

    const saved = await saveEdits({ quietSuccess: true, forceVerified: forceVerify || routeVerified })
    if (!saved) return
    setActionLoading(true)
    const { error } = await supabase.rpc('approve_submission', { p_id: id })
    setActionLoading(false)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      setShowRouteVerifyModal(false)
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
      showToast('Kayıt revize için agenta gönderildi.')
      setSub(prev => prev ? {
        ...prev,
        status: 'pending',
        review_stage: 'agent_revision',
        admin_note: `[insan] REVİZE İSTENDİ: ${reviseNote.trim()}`,
      } : null)
      setReviseNote('')
    }
  }

  async function handleReject(note: string) {
    setActionLoading(true)
    const { error } = await supabase.rpc('reject_submission', {
      p_id: id,
      p_note: note,
    })
    setActionLoading(false)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      setShowReject(false)
      showToast('Reddedildi.')
      setSub(prev => prev ? { ...prev, status: 'rejected', admin_note: note } : null)
    }
  }

  if (loading) {
    return (
      <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#aaa', fontSize: 13 }}>Yükleniyor...</span>
      </main>
    )
  }

  if (!sub) {
    return (
      <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#aaa', fontSize: 13 }}>Öneri bulunamadı.</span>
      </main>
    )
  }

  const isPending = sub.status === 'pending'
  const isHuman = sub.submission_origin === 'human'
  const isAgentRevision = isPending && sub.review_stage === 'agent_revision'
  const canReview = isPending && !isAgentRevision

  return (
    <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
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
          <span><strong>{isHuman ? 'Kullanıcı kaydı' : 'Agent kaydı'}</strong></span>
          {sub.submitter_email ? (
            <span>✉ {sub.submitter_email}</span>
          ) : isHuman ? (
            <span style={{ color: '#ccc' }}>✉ yok — revize maili gönderilemez</span>
          ) : null}
          <span>{new Date(sub.created_at).toLocaleDateString('tr-TR')}</span>
        </div>

        {/* Editable form */}
        <div style={{
          background: '#fff', border: '0.5px solid #e0e0e0',
          borderRadius: 16, padding: '24px 20px',
        }}>
          <Label text="Başlık" />
          <input value={title} onChange={e => setTitle(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="Doğrudan başvuru URL'si" />
          <input value={url} onChange={e => setUrl(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="Resmî bilgi / koşullar URL'si" />
          <input value={detailsUrl} onChange={e => setDetailsUrl(e.target.value)} style={{ ...inputStyle, marginBottom: 12 }} />

          <Label text="Başvuru yöntemi" />
          <select
            value={applicationMethod ?? 'portal'}
            onChange={e => setApplicationMethod(e.target.value as Submission['application_method'])}
            style={{ ...inputStyle, marginBottom: 10 }}
          >
            <option value="portal">Başvuru portalı</option>
            <option value="online_form">Online form</option>
            <option value="email">E-posta</option>
            <option value="document">İndirilebilir form</option>
          </select>
          <div style={{
            background: routeVerified ? '#E1F5EE' : '#FFF9E6',
            border: `1px solid ${routeVerified ? '#9FE1CB' : '#FDE68A'}`,
            borderRadius: 8, padding: '10px 12px', marginBottom: 14,
          }}>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12, color: '#333', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={routeVerified}
                onChange={e => setRouteVerified(e.target.checked)}
                style={{ marginTop: 2, accentColor: '#085041' }}
              />
              <span>
                <strong>Doğrudan başvuru adımı doğrulandı:</strong> Bu bağlantıyı açtım; kullanıcı buradan doğrudan başvuruyu başlatabiliyor. (Yayına almak için zorunludur)
              </span>
            </label>
          </div>

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

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
            <div>
              <Label text="Uyruk şartı (ISO, virgülle)" />
              <input
                value={citizenships}
                onChange={e => setCitizenships(e.target.value)}
                placeholder="CN, PS · boş = şart yok"
                style={inputStyle}
              />
            </div>
            <div>
              <Label text="Bölüm kısıtı (slug, virgülle)" />
              <input
                value={targetFields}
                onChange={e => setTargetFields(e.target.value)}
                placeholder="medicine, nursing · boş = kısıt yok"
                style={inputStyle}
              />
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

          <Label text="Öğrenim Seviyesi / Kimler İçin?" />
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {STUDY_LEVELS.map(s => {
              const active = studyLevel.includes(s.value)
              return (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => {
                    setStudyLevel(prev =>
                      prev.includes(s.value) ? prev.filter(x => x !== s.value) : [...prev, s.value]
                    )
                  }}
                  style={{
                    fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 20,
                    background: active ? '#1a6b5a' : 'transparent',
                    color: active ? '#fff' : '#1a6b5a',
                    border: '0.5px solid #1a6b5a66', cursor: 'pointer',
                  }}
                >
                  {s.label}
                </button>
              )
            })}
          </div>

          <Label text="Kimler başvurabilir (Notlar)" />
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

          {sub.admin_note && (
            <div style={{
              background: sub.status === 'rejected' ? '#FDE8E8' : '#FAEEDA',
              borderRadius: 8, padding: '9px 11px', marginBottom: 12,
              fontSize: 12, color: sub.status === 'rejected' ? '#7A1F1F' : '#633806',
              lineHeight: 1.5, wordBreak: 'break-word',
            }}>
              <strong>Karar / inceleme notu:</strong> {sub.admin_note}
            </div>
          )}

          {/* Save button */}
          {canReview && (
            <button
              onClick={() => { void saveEdits() }}
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
          {canReview && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <button
                onClick={() => handleApprove()}
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
                onClick={() => setShowReject(true)}
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

          {canReview && showReject && (
            <RejectComposer
              busy={actionLoading}
              onCancel={() => setShowReject(false)}
              onSubmit={handleReject}
            />
          )}

          {/* Revise */}
          {canReview && isHuman && (
            <div>
              <Label text="Revize görevi (agenta gider)" />
              <div style={{ display: 'flex', gap: 8 }}>
                <textarea
                  value={reviseNote}
                  onChange={e => setReviseNote(e.target.value)}
                  placeholder="Agenta neyi kontrol edip tamamlayacağını yaz..."
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
                  Ajana Yolla
                </button>
              </div>
            </div>
          )}

          {/* Status banner */}
          {(!isPending || isAgentRevision) && (
            <div style={{
              background: sub.status === 'approved' ? '#E1F5EE' : sub.status === 'rejected' ? '#FDE8E8' : '#EEEDFE',
              borderRadius: 10, padding: '12px 14px',
              fontSize: 13, fontWeight: 500,
              color: sub.status === 'approved' ? '#085041' : sub.status === 'rejected' ? '#A32D2D' : '#3C3489',
            }}>
              {sub.status === 'approved' && 'Bu öneri onaylanmış.'}
              {sub.status === 'rejected' && 'Bu öneri reddedilmiş.'}
              {sub.status === 'needs_revision' && 'Bu öneri revize bekliyor.'}
              {isAgentRevision && 'Bu öneriyi agent revize ediyor; bitince yeniden insan onayına dönecek.'}
            </div>
          )}
        </div>

        {/* Route verification confirmation modal */}
        {showRouteVerifyModal && (
          <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 300, padding: 16,
          }}>
            <div style={{
              background: '#fff', borderRadius: 14, padding: 24,
              maxWidth: 480, width: '100%', boxShadow: '0 8px 30px rgba(0,0,0,0.2)',
            }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#1a1a1a', marginBottom: 12 }}>
                Başvuru Bağlantısını Doğrula ve Onayla
              </div>
              <p style={{ fontSize: 13, color: '#555', lineHeight: 1.5, marginBottom: 16 }}>
                &quot;Doğrudan başvuru adımı doğrulandı&quot; kutusu işaretlenmemiş. Fırsatın yayına alınabilmesi için doğrudan başvuru adresi gereklidir.
              </p>
              <div style={{
                background: '#f8f8f8', border: '1px solid #e5e5e5', borderRadius: 8,
                padding: '10px 12px', fontSize: 12, marginBottom: 16, wordBreak: 'break-all',
              }}>
                <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>Başvuru URL&apos;si:</div>
                <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: '#534AB7', textDecoration: 'underline' }}>
                  {url}
                </a>
              </div>
              <p style={{ fontSize: 12, color: '#777', marginBottom: 20 }}>
                Bu bağlantıyı kontrol ettiyseniz, &quot;Doğrula ve Onayla&quot; butonuna basarak doğrudan sisteme ekleyebilirsiniz.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setShowRouteVerifyModal(false)}
                  disabled={actionLoading}
                  style={{ padding: '8px 14px', borderRadius: 8, border: '0.5px solid #ccc', background: '#fff', fontSize: 13, cursor: 'pointer' }}
                >
                  Vazgeç
                </button>
                <button
                  type="button"
                  onClick={() => handleApprove(true)}
                  disabled={actionLoading}
                  style={{
                    padding: '8px 16px', borderRadius: 8, border: 'none',
                    background: '#085041', color: '#fff', fontSize: 13, fontWeight: 500,
                    cursor: actionLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {actionLoading ? 'Onaylanıyor…' : 'Doğrula ve Onayla'}
                </button>
              </div>
            </div>
          </div>
        )}

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
