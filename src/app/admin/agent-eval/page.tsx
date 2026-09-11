'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import RejectComposer from '../reject-composer'

type Snapshot = {
  title: string
  url: string
  source_url: string | null
  category_slug: string | null
  host_countries: string[] | null
  eligibility_notes: string | null
  deadline_text: string | null
  funding_type: string | null
  study_level: string[] | string | null
  language_requirement: string | null
  description: string | null
}

type EvalCase = {
  id: string
  snapshot: Snapshot
  source_nickname: string
  category_slug: string
  human_decision: 'approve' | 'reject' | null
  human_reason_code: string | null
  human_note: string | null
  labeled_at: string | null
  agent_decision: 'approve' | 'reject' | 'uncertain' | 'retry' | null
  agent_reason: string | null
  agent_outcome: string | null
  is_match: boolean | null
}

type EvalPayload = {
  batch: { id: string; name: string; status: string; model: string; created_at: string } | null
  cases: EvalCase[]
  summary: {
    total: number
    labeled: number
    auto_decided: number
    comparable: number
    correct: number
    false_approvals: number
    coverage_percent: number | null
    accuracy_percent: number | null
    approval_precision_percent: number | null
  } | null
}

const AGENT_LABELS: Record<string, string> = {
  approve: 'ONAY',
  reject: 'RED',
  uncertain: 'BELİRSİZ',
  retry: 'TEKRAR',
}

function metric(value: number | null) {
  return value == null ? '—' : `%${value}`
}

export default function AgentEvaluationPage() {
  const [payload, setPayload] = useState<EvalPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [showCompleted, setShowCompleted] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const { data, error: rpcError } = await supabase.rpc('get_agent_evaluation_queue')
    setLoading(false)
    if (rpcError) {
      setError(rpcError.message)
      return
    }
    setPayload(data as unknown as EvalPayload)
  }, [])

  useEffect(() => {
    queueMicrotask(() => { void load() })
  }, [load])

  const visibleCases = useMemo(() => {
    const rows = payload?.cases ?? []
    return showCompleted ? rows : rows.filter(item => item.human_decision == null)
  }, [payload, showCompleted])

  async function label(id: string, decision: 'approve' | 'reject', note?: string) {
    setBusyId(id)
    setError(null)
    const { error: rpcError } = await supabase.rpc('label_agent_evaluation_case', {
      p_id: id,
      p_decision: decision,
      p_note: note ?? null,
    })
    setBusyId(null)
    if (rpcError) {
      setError(rpcError.message)
      return
    }
    setRejectId(null)
    await load()
  }

  const summary = payload?.summary

  return (
    <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 980, margin: '0 auto' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 18 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 600, color: '#1a1a1a' }}>Agent doğruluk testi</div>
            <div style={{ fontSize: 12, color: '#888', marginTop: 3 }}>{payload?.batch?.name ?? 'Aktif test yok'}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Link href="/admin" style={navStyle}>← Öneriler</Link>
            <Link href="/admin/review" style={navStyle}>Belirsizler</Link>
          </div>
        </header>

        <div style={{ background: '#EEEDFE', color: '#3C3489', borderRadius: 10, padding: '11px 14px', fontSize: 12.5, lineHeight: 1.6, marginBottom: 16 }}>
          Kaydı ilk kez gelmiş gibi değerlendir. Sitede zaten bulunmasını dikkate alma.
          Ajanın kararı, sen Onay veya Red etiketi verene kadar özellikle gizlidir.
        </div>

        {summary && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            <Stat label="Etiketlenen" value={`${summary.labeled}/${summary.total}`} />
            <Stat label="Otomatik karar kapsamı" value={metric(summary.coverage_percent)} />
            <Stat label="Doğruluk" value={metric(summary.accuracy_percent)} />
            <Stat label="Onay isabeti" value={metric(summary.approval_precision_percent)} />
            <Stat label="Yanlış onay" value={String(summary.false_approvals)} danger={summary.false_approvals > 0} />
          </div>
        )}

        <label style={{ display: 'inline-flex', gap: 7, alignItems: 'center', fontSize: 12, color: '#666', marginBottom: 14 }}>
          <input type="checkbox" checked={showCompleted} onChange={event => setShowCompleted(event.target.checked)} />
          Etiketlenen kayıtları da göster
        </label>

        {error && <div style={{ background: '#FDE8E8', color: '#A32D2D', borderRadius: 9, padding: '10px 13px', fontSize: 12, marginBottom: 14 }}>{error}</div>}

        {loading ? (
          <div style={emptyStyle}>Yükleniyor…</div>
        ) : !payload?.batch ? (
          <div style={emptyStyle}>Henüz hazırlanmış doğruluk testi yok.</div>
        ) : visibleCases.length === 0 ? (
          <div style={emptyStyle}>Bu görünümde kayıt yok. Test tamamlandıysa sonuçları görmek için yukarıdaki kutuyu işaretle.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {visibleCases.map((item, index) => {
              const snap = item.snapshot
              const finished = item.human_decision != null
              const falseApproval = item.agent_decision === 'approve' && item.human_decision === 'reject'
              return (
                <article key={item.id} style={{ background: '#fff', border: `1px solid ${falseApproval ? '#E8A8A8' : '#e5e5e5'}`, borderRadius: 12, padding: '16px 18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 240 }}>
                      <div style={{ fontSize: 11, color: '#999', marginBottom: 5 }}>#{index + 1} · {item.source_nickname}</div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', lineHeight: 1.4 }}>{snap.title}</div>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 11, color: '#777', marginTop: 7 }}>
                        <span>{snap.category_slug || 'kategori yok'}</span>
                        <span>{(snap.host_countries ?? []).join(', ') || 'ülke yok'}</span>
                        <span>{snap.deadline_text || 'tarih yok'}</span>
                        <span>{snap.funding_type || 'finansman yok'}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
                      <a href={snap.url} target="_blank" rel="noopener noreferrer" style={navStyle}>Hedef ↗</a>
                      {snap.source_url && snap.source_url !== snap.url && (
                        <a href={snap.source_url} target="_blank" rel="noopener noreferrer" style={navStyle}>Kaynak ↗</a>
                      )}
                    </div>
                  </div>

                  {snap.eligibility_notes && <Info label="Uygunluk" text={snap.eligibility_notes} />}
                  {snap.description && <Info label="Açıklama" text={snap.description} />}

                  {!finished ? (
                    <>
                      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                        <button type="button" disabled={busyId === item.id} onClick={() => void label(item.id, 'approve')} style={{ ...buttonStyle, background: '#E1F5EE', color: '#085041' }}>
                          İnsan: Onay
                        </button>
                        <button type="button" disabled={busyId === item.id} onClick={() => setRejectId(item.id)} style={{ ...buttonStyle, background: '#FDE8E8', color: '#A32D2D' }}>
                          İnsan: Red
                        </button>
                      </div>
                      {rejectId === item.id && (
                        <RejectComposer busy={busyId === item.id} onCancel={() => setRejectId(null)} onSubmit={note => label(item.id, 'reject', note)} />
                      )}
                    </>
                  ) : (
                    <div style={{ marginTop: 12, borderRadius: 9, padding: '10px 12px', background: falseApproval ? '#FFF1F1' : item.is_match ? '#E1F5EE' : '#FAEEDA', fontSize: 12, color: '#333', lineHeight: 1.55 }}>
                      <strong>İnsan:</strong> {item.human_decision === 'approve' ? 'ONAY' : 'RED'}
                      {' · '}
                      <strong>Ajan:</strong> {AGENT_LABELS[item.agent_decision ?? ''] ?? '—'}
                      {' · '}
                      {item.is_match === true ? 'Eşleşti' : item.is_match === false ? 'Eşleşmedi' : 'Ajan otomatik karar vermedi'}
                      {item.agent_reason && <div style={{ marginTop: 5, color: '#666' }}>Ajan gerekçesi: {item.agent_reason}</div>}
                      {item.human_note && <div style={{ marginTop: 3, color: '#666' }}>İnsan notu: {item.human_note}</div>}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </div>
    </main>
  )
}

function Stat({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return (
    <div style={{ background: danger ? '#FDE8E8' : '#fff', border: '1px solid #e5e5e5', borderRadius: 9, padding: '8px 12px' }}>
      <div style={{ fontSize: 10, color: '#888' }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 650, color: danger ? '#A32D2D' : '#222', marginTop: 2 }}>{value}</div>
    </div>
  )
}

function Info({ label, text }: { label: string; text: string }) {
  return (
    <div style={{ marginTop: 10, background: '#fafaf9', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#555', lineHeight: 1.55 }}>
      <strong>{label}:</strong> {text}
    </div>
  )
}

const navStyle = {
  fontSize: 12,
  color: '#534AB7',
  textDecoration: 'none',
  padding: '6px 10px',
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  background: '#fff',
}

const buttonStyle = {
  border: 'none',
  borderRadius: 8,
  padding: '8px 13px',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
}

const emptyStyle = {
  background: '#fff',
  border: '1px solid #e5e5e5',
  borderRadius: 12,
  padding: '44px 18px',
  textAlign: 'center' as const,
  color: '#777',
  fontSize: 13,
}
