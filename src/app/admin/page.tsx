'use client'
import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'

interface Submission {
  id: string
  title: string
  url: string
  category_slug: string | null
  host_countries: string[]
  deadline_text: string | null
  funding_type: string | null
  eligibility_notes: string | null
  submitter_email: string | null
  submitter_nickname: string | null
  status: string
  admin_note: string | null
  description: string | null
  created_at: string
}

interface Stats {
  pending_count: number
  approved_this_week: number
  total: number
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Bekliyor',
  approved: 'Onaylandı',
  needs_revision: 'Revize',
  rejected: 'Reddedildi',
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: '#FAEEDA', text: '#633806' },
  approved: { bg: '#E1F5EE', text: '#085041' },
  needs_revision: { bg: '#EEEDFE', text: '#3C3489' },
  rejected: { bg: '#FDE8E8', text: '#A32D2D' },
}

export default function AdminPage() {
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [filter, setFilter] = useState<string>('pending')
  const [loading, setLoading] = useState(true)
  const [reviseId, setReviseId] = useState<string | null>(null)
  const [reviseNote, setReviseNote] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    async function load() {
      const [{ data: subs }, { data: statsData }] = await Promise.all([
        supabase
          .from('submissions')
          .select('*')
          .eq('status', filter)
          .order('created_at', { ascending: false }),
        supabase.rpc('get_submission_stats'),
      ])
      if (!active) return
      setSubmissions((subs as Submission[]) ?? [])
      setStats(statsData as Stats | null)
      setLoading(false)
    }
    // Use queueMicrotask to avoid synchronous setState in effect body
    queueMicrotask(() => { if (active) { setLoading(true); load() } })
    const interval = setInterval(load, 30_000)
    return () => { active = false; clearInterval(interval) }
  }, [filter, refreshKey])

  function refresh() { setRefreshKey(k => k + 1) }

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  async function handleApprove(id: string) {
    setActionLoading(id)
    const { error } = await supabase.rpc('approve_submission', { p_id: id })
    setActionLoading(null)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      showToast('Onaylandı, fırsat sisteme eklendi.')
      refresh()
    }
  }

  async function handleRevise(id: string) {
    if (!reviseNote.trim()) return
    setActionLoading(id)
    const { error } = await supabase.rpc('request_revision', {
      p_id: id,
      p_note: reviseNote.trim(),
    })
    setActionLoading(null)
    setReviseId(null)
    setReviseNote('')
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      showToast('Revize istendi.')
      refresh()
    }
  }

  async function handleReject(id: string) {
    const note = prompt('Red sebebi (opsiyonel):') ?? ''
    setActionLoading(id)
    const { error } = await supabase.rpc('reject_submission', {
      p_id: id,
      p_note: note || null,
    })
    setActionLoading(null)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      showToast('Reddedildi.')
      refresh()
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut()
    window.location.href = '/admin/login'
  }

  return (
    <main style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
            <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Admin</span>
          </div>
          <button
            onClick={handleLogout}
            style={{
              fontSize: 12, color: '#999', background: 'none',
              border: '0.5px solid #e0e0e0', borderRadius: 8,
              padding: '6px 12px', cursor: 'pointer',
            }}
          >
            Çıkış
          </button>
        </div>

        {/* Stats */}
        {stats && (
          <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
            <StatPill label="Bekleyen" value={stats.pending_count} color="#FAEEDA" textColor="#633806" />
            <StatPill label="Bu hafta onay" value={stats.approved_this_week} color="#E1F5EE" textColor="#085041" />
            <StatPill label="Toplam" value={stats.total} color="#f0f0f0" textColor="#666" />
          </div>
        )}

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {['pending', 'needs_revision', 'approved', 'rejected'].map(s => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              style={{
                fontSize: 11, fontWeight: 500, padding: '4px 12px', borderRadius: 20,
                background: filter === s ? '#534AB7' : '#fff',
                color: filter === s ? '#fff' : '#666',
                border: `0.5px solid ${filter === s ? '#534AB7' : '#e0e0e0'}`,
                cursor: 'pointer',
              }}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {/* Submissions */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa', fontSize: 13 }}>
            Yükleniyor...
          </div>
        ) : submissions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa', fontSize: 13 }}>
            Bu kategoride öneri yok.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {submissions.map(sub => (
              <div
                key={sub.id}
                style={{
                  background: '#fff', border: '0.5px solid #e0e0e0',
                  borderRadius: 12, padding: '14px 16px',
                }}
              >
                {/* Top row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
                  <a
                    href={`/admin/submissions/${sub.id}`}
                    style={{ fontSize: 14, fontWeight: 500, color: '#1a1a1a', textDecoration: 'none', lineHeight: 1.4 }}
                  >
                    {sub.title}
                  </a>
                  <span style={{
                    fontSize: 10, fontWeight: 500, padding: '3px 8px', borderRadius: 20,
                    background: STATUS_COLORS[sub.status]?.bg ?? '#f0f0f0',
                    color: STATUS_COLORS[sub.status]?.text ?? '#666',
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}>
                    {STATUS_LABELS[sub.status] ?? sub.status}
                  </span>
                </div>

                {/* Meta */}
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11, color: '#888', marginBottom: 8 }}>
                  {sub.category_slug && <span>{sub.category_slug}</span>}
                  {sub.host_countries?.length > 0 && <span>{sub.host_countries.join(', ')}</span>}
                  {sub.deadline_text && <span>{sub.deadline_text}</span>}
                  <span>
                    {sub.submitter_nickname ? `@${sub.submitter_nickname}` : 'Anonim'}
                  </span>
                  {sub.submitter_email ? (
                    <span>{sub.submitter_email}</span>
                  ) : (
                    <span style={{ color: '#ccc' }} title="E-posta bırakılmamış">✉ yok</span>
                  )}
                </div>

                {/* URL */}
                <a
                  href={sub.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: 11, color: '#534AB7', wordBreak: 'break-all' }}
                >
                  {sub.url}
                </a>

                {/* Admin note (if exists) */}
                {sub.admin_note && (
                  <div style={{
                    background: '#FAEEDA', borderRadius: 6, padding: '6px 10px',
                    fontSize: 11, color: '#633806', marginTop: 8,
                  }}>
                    Admin notu: {sub.admin_note}
                  </div>
                )}

                {/* Actions — only for pending */}
                {sub.status === 'pending' && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    <ActionBtn
                      label="Onayla"
                      color="#085041"
                      bg="#E1F5EE"
                      loading={actionLoading === sub.id}
                      onClick={() => handleApprove(sub.id)}
                    />
                    {sub.submitter_email ? (
                      <ActionBtn
                        label="Revize"
                        color="#3C3489"
                        bg="#EEEDFE"
                        loading={actionLoading === sub.id}
                        onClick={() => { setReviseId(sub.id); setReviseNote('') }}
                      />
                    ) : (
                      <span
                        style={{ fontSize: 10, color: '#ccc', padding: '6px 10px' }}
                        title="E-posta yok — revize gönderilemez. Elden düzelt veya reddet."
                      >
                        Revize (✉ yok)
                      </span>
                    )}
                    <ActionBtn
                      label="Reddet"
                      color="#A32D2D"
                      bg="#FDE8E8"
                      loading={actionLoading === sub.id}
                      onClick={() => handleReject(sub.id)}
                    />
                  </div>
                )}

                {/* Revise composer */}
                {reviseId === sub.id && (
                  <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
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
                      onClick={() => handleRevise(sub.id)}
                      disabled={!reviseNote.trim()}
                      style={{
                        padding: '8px 14px', borderRadius: 8,
                        background: '#534AB7', color: '#fff',
                        border: 'none', fontSize: 12, fontWeight: 500,
                        cursor: 'pointer', alignSelf: 'flex-end',
                        opacity: reviseNote.trim() ? 1 : 0.5,
                      }}
                    >
                      Gönder
                    </button>
                  </div>
                )}
              </div>
            ))}
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

function StatPill({ label, value, color, textColor }: {
  label: string; value: number; color: string; textColor: string
}) {
  return (
    <div style={{
      background: color, borderRadius: 10, padding: '8px 14px',
      fontSize: 12, fontWeight: 500, color: textColor,
    }}>
      {label}: <strong>{value}</strong>
    </div>
  )
}

function ActionBtn({ label, color, bg, loading, onClick }: {
  label: string; color: string; bg: string; loading: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      style={{
        fontSize: 11, fontWeight: 500, padding: '6px 12px', borderRadius: 8,
        background: bg, color, border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.6 : 1,
      }}
    >
      {label}
    </button>
  )
}
