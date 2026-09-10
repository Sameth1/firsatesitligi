'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import RejectComposer from './reject-composer'

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
  submission_origin: 'human' | 'agent'
  review_stage: string
}

interface Stats {
  pending_count: number
  approved_this_week: number
  submissions_total: number
  opportunities_total: number
  subscribers_total: number
  never_url_checked: number
  never_verified: number
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

// admin_note önekleri — 105 akışında notu kimin yazdığını buradan ayırıyoruz.
const AGENT_REPORT_PREFIX = '[ajan] REVİZE SONUCU'
const HUMAN_REVISION_PREFIX = '[insan] REVİZE İSTENDİ'

/**
 * Rozet metni status'tan değil, status + review_stage'den çıkar.
 * Revize istendiğinde kayıt 'pending' KALIR (ajan yalnız pending kayıtları
 * çeker); onu ajanın elinde tutan review_stage'dir. Yalnız status'a bakan bir
 * rozet bu kayıtları "Bekliyor" diye gösterip admin'i yanıltırdı.
 */
function stageBadge(sub: Submission): { label: string; bg: string; text: string } {
  if (sub.status === 'pending' && sub.review_stage === 'agent_revision') {
    return { label: 'Ajanda · revize', bg: '#E6F1FB', text: '#0C447C' }
  }
  if (sub.status === 'pending' && sub.review_stage === 'agent_uncertain') {
    return { label: 'Ajan: belirsiz', bg: '#FAEEDA', text: '#633806' }
  }
  const color = STATUS_COLORS[sub.status]
  return {
    label: STATUS_LABELS[sub.status] ?? sub.status,
    bg: color?.bg ?? '#f0f0f0',
    text: color?.text ?? '#666',
  }
}

const FILTERS = [
  { key: 'human_pending', label: 'Kullanıcı Kayıtları' },
  { key: 'agent_revision', label: 'Ajanda (Revize)' },
  { key: 'agent_uncertain', label: 'Agent Belirsizleri' },
  { key: 'needs_revision', label: 'Revize Bekleyen' },
  { key: 'approved', label: 'Onaylandı' },
  { key: 'rejected', label: 'Reddedildi' },
] as const

export default function AdminPage() {
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [filter, setFilter] = useState<string>('human_pending')
  const [loading, setLoading] = useState(true)
  const [reviseId, setReviseId] = useState<string | null>(null)
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [reviseNote, setReviseNote] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true
    async function load() {
      let submissionsQuery = supabase.from('submissions').select('*')
      if (filter === 'human_pending') {
        submissionsQuery = submissionsQuery
          .eq('status', 'pending')
          .eq('submission_origin', 'human')
          // Ajana gönderilmiş kayıt bu listede durmasın: sıra admin'de değil.
          // Ajan işini bitirince review_stage human_review olur ve geri gelir.
          .neq('review_stage', 'agent_revision')
      } else if (filter === 'agent_revision') {
        submissionsQuery = submissionsQuery
          .eq('status', 'pending')
          .eq('submission_origin', 'human')
          .eq('review_stage', 'agent_revision')
      } else if (filter === 'agent_uncertain') {
        submissionsQuery = submissionsQuery
          .eq('status', 'pending')
          .eq('submission_origin', 'agent')
          .eq('review_stage', 'agent_uncertain')
      } else {
        submissionsQuery = submissionsQuery.eq('status', filter)
      }
      const [{ data: subs }, statsRes] = await Promise.all([
        submissionsQuery.order('created_at', { ascending: false }),
        // Yeni RPC: 090 sonrası genişletilmiş istatistikler.
        // Eski deploylar için fallback: yoksa get_submission_stats'e düş.
        supabase.rpc('get_admin_stats'),
      ])
      let statsData = statsRes.data as Stats | null
      if (statsRes.error) {
        const legacy = await supabase.rpc('get_submission_stats')
        const legacyData = legacy.data as { pending_count: number; approved_this_week: number; total: number } | null
        if (legacyData) {
          statsData = {
            pending_count: legacyData.pending_count ?? 0,
            approved_this_week: legacyData.approved_this_week ?? 0,
            submissions_total: legacyData.total ?? 0,
            opportunities_total: 0,
            subscribers_total: 0,
            never_url_checked: 0,
            never_verified: 0,
          }
        }
      }
      if (!active) return
      setSubmissions((subs as Submission[]) ?? [])
      setStats(statsData)
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
      showToast('Ajana gönderildi — inceleyip notunu bırakacak.')
      refresh()
    }
  }

  async function handleReject(id: string, note: string) {
    setActionLoading(id)
    const { error } = await supabase.rpc('reject_submission', {
      p_id: id,
      p_note: note,
    })
    setActionLoading(null)
    if (error) {
      showToast('Hata: ' + error.message)
    } else {
      setRejectId(null)
      showToast('Reddedildi.')
      refresh()
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut()
    window.location.href = '/admin/login'
  }

  return (
    <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
            <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Admin</span>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Link
              href="/admin/grid"
              style={{
                fontSize: 12,
                color: '#534AB7',
                textDecoration: 'none',
                padding: '6px 12px',
                border: '0.5px solid #e0e0e0',
                borderRadius: 8,
                background: '#fff',
              }}
            >
              Tablo görünümü (beta)
            </Link>
            <Link
              href="/admin/link-audit"
              style={{
                fontSize: 12,
                color: '#534AB7',
                textDecoration: 'none',
                padding: '6px 12px',
                border: '0.5px solid #e0e0e0',
                borderRadius: 8,
                background: '#fff',
              }}
            >
              Bağlantı denetimi
            </Link>
            <Link
              href="/admin/review"
              style={{
                fontSize: 12,
                color: '#534AB7',
                textDecoration: 'none',
                padding: '6px 12px',
                border: '0.5px solid #e0e0e0',
                borderRadius: 8,
                background: '#fff',
              }}
            >
              Belirsizler
            </Link>
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
        </div>

        {/* Stats */}
        {stats && (
          <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
            <StatPill label="Bekleyen" value={stats.pending_count} color="#FAEEDA" textColor="#633806" />
            <StatPill label="Bu hafta onay" value={stats.approved_this_week} color="#E1F5EE" textColor="#085041" />
            <StatPill label="Aktif fırsat" value={stats.opportunities_total} color="#EEEDFE" textColor="#3C3489" />
            <StatPill label="Aboneler" value={stats.subscribers_total} color="#E6F1FB" textColor="#0C447C" />
            <StatPill label="Tüm öneri" value={stats.submissions_total} color="#f0f0f0" textColor="#666" />
            {stats.never_verified > 0 && (
              <StatPill label="Manuel doğrulanmamış" value={stats.never_verified} color="#FAEEDA" textColor="#633806" />
            )}
          </div>
        )}

        {/* Visitor analytics hint */}
        {!process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && (
          <div style={{
            background: '#fff', border: '0.5px solid #e0e0e0', borderRadius: 10,
            padding: '10px 14px', fontSize: 11, color: '#888', marginBottom: 16, lineHeight: 1.5,
          }}>
            Ziyaretçi/sayfa görüntüleme sayısı için <strong>Plausible Analytics</strong> entegre değil.
            <br />
            <code>.env.local</code> içine <code>NEXT_PUBLIC_PLAUSIBLE_DOMAIN=firsatesitligi.com</code>
            ekleyip yeniden başlat — script otomatik yüklenir, sayım dashboard.plausible.io üzerinden takip edilir.
          </div>
        )}

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {FILTERS.map(item => (
            <button
              key={item.key}
              onClick={() => setFilter(item.key)}
              style={{
                fontSize: 11, fontWeight: 500, padding: '4px 12px', borderRadius: 20,
                background: filter === item.key ? '#534AB7' : '#fff',
                color: filter === item.key ? '#fff' : '#666',
                border: `0.5px solid ${filter === item.key ? '#534AB7' : '#e0e0e0'}`,
                cursor: 'pointer',
              }}
            >
              {item.label}
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
            {submissions.map(sub => {
              const badge = stageBadge(sub)
              const note = sub.admin_note ?? ''
              const isAgentReport = note.startsWith(AGENT_REPORT_PREFIX)
              const isRevisionRequest = note.startsWith(HUMAN_REVISION_PREFIX)
              return (
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
                    background: badge.bg,
                    color: badge.text,
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}>
                    {badge.label}
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
                  <span>{sub.submission_origin === 'agent' ? 'Agent kaydı' : 'Kullanıcı kaydı'}</span>
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

                {/* Not kutusu — ajan raporu mavi, admin isteği/karar notu sarı */}
                {sub.admin_note && (
                  <div style={{
                    background: isAgentReport ? '#E6F1FB' : '#FAEEDA',
                    borderRadius: 6, padding: '6px 10px',
                    fontSize: 11, color: isAgentReport ? '#0C447C' : '#633806',
                    marginTop: 8, lineHeight: 1.5, wordBreak: 'break-word',
                  }}>
                    <strong>
                      {isAgentReport ? 'Ajan raporu: '
                        : isRevisionRequest ? 'Revize isteğin: '
                        : 'Admin notu: '}
                    </strong>
                    {isAgentReport ? sub.admin_note.slice(AGENT_REPORT_PREFIX.length).replace(/^[\s—-]+/, '')
                      : isRevisionRequest ? sub.admin_note.slice(HUMAN_REVISION_PREFIX.length).replace(/^[\s:]+/, '')
                      : sub.admin_note}
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
                    {/* Revize notu artık kullanıcıya değil AJANA gider; e-posta
                        şartı 105 ile kalktı (mail gönderen kod hiç olmadı). */}
                    {sub.submission_origin === 'human' && (
                      <ActionBtn
                        label={sub.review_stage === 'agent_revision' ? 'Ajanda' : 'Ajana yolla'}
                        color="#0C447C"
                        bg="#E6F1FB"
                        loading={actionLoading === sub.id || sub.review_stage === 'agent_revision'}
                        onClick={() => { setReviseId(sub.id); setRejectId(null); setReviseNote('') }}
                      />
                    )}
                    <ActionBtn
                      label="Reddet"
                      color="#A32D2D"
                      bg="#FDE8E8"
                      loading={actionLoading === sub.id}
                      onClick={() => { setRejectId(sub.id); setReviseId(null) }}
                    />
                  </div>
                )}

                {/* Revise composer */}
                {reviseId === sub.id && sub.submission_origin === 'human' && (
                  <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                    <textarea
                      value={reviseNote}
                      onChange={e => setReviseNote(e.target.value)}
                      placeholder="Ajan neyi araştırsın / neyi düzeltsin? Ör: 'Son başvuru tarihi sayfada doğru mu, ülke ve finansman bilgisini doldur.'"
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
                      Ajana gönder
                    </button>
                  </div>
                )}

                {rejectId === sub.id && (
                  <RejectComposer
                    busy={actionLoading === sub.id}
                    onCancel={() => setRejectId(null)}
                    onSubmit={note => handleReject(sub.id, note)}
                  />
                )}
              </div>
              )
            })}
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
