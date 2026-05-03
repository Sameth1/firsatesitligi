'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'

type AuditRow = {
  id: string
  title: string
  official_url: string
  is_active: boolean
  deadline: string | null
  last_url_check_at: string | null
  last_url_check_status: number | null
  last_url_check_error: string | null
  last_url_check_final_url: string | null
  last_verified_at?: string | null
}

function statusLabel(row: AuditRow): { text: string; bg: string; color: string } {
  if (row.last_url_check_error) {
    return { text: 'Hata', bg: '#FDE8E8', color: '#A32D2D' }
  }
  const s = row.last_url_check_status
  if (s == null) {
    return { text: '—', bg: '#f0f0f0', color: '#666' }
  }
  if (s >= 200 && s < 400) {
    return { text: String(s), bg: '#E1F5EE', color: '#085041' }
  }
  return { text: String(s), bg: '#FAEEDA', color: '#633806' }
}

export default function LinkAuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [verifyingId, setVerifyingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    const { data, error } = await supabase.rpc('get_opportunity_link_audit')
    setLoading(false)
    if (error) {
      setErr(error.message)
      setRows([])
      return
    }
    setRows((data as AuditRow[]) ?? [])
  }, [])

  useEffect(() => {
    queueMicrotask(() => { void load() })
  }, [load])

  async function runBatch(limit: number) {
    setRunning(true)
    setMsg(null)
    setErr(null)
    try {
      const res = await fetch('/api/admin/check-opportunity-links', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit }),
      })
      const j = await res.json().catch(() => ({}))
      if (!res.ok) {
        setErr(j.error ?? `HTTP ${res.status}`)
        return
      }
      setMsg(`${j.checked ?? 0} kayıt kontrol edildi.`)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut()
    window.location.href = '/admin/login'
  }

  async function markVerified(id: string) {
    setVerifyingId(id)
    setErr(null)
    setMsg(null)
    const { error } = await supabase.rpc('mark_opportunity_verified', { p_id: id })
    setVerifyingId(null)
    if (error) {
      setErr('Doğrulama kaydedilemedi: ' + error.message)
      return
    }
    setMsg('Manuel doğrulama kaydedildi.')
    await load()
  }

  return (
    <main style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 20,
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
            <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Bağlantı denetimi</span>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Link
              href="/admin"
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
              ← Öneriler
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              style={{
                fontSize: 12,
                color: '#999',
                background: 'none',
                border: '0.5px solid #e0e0e0',
                borderRadius: 8,
                padding: '6px 12px',
                cursor: 'pointer',
              }}
            >
              Çıkış
            </button>
          </div>
        </div>

        <p style={{ fontSize: 13, color: '#666', marginBottom: 16, lineHeight: 1.5 }}>
          Her kayıt için resmi <code>official_url</code> adresine sunucudan GET isteği atılır (yönlendirmeler
          izlenir). Sonuç HTTP kodu ve hata metni veritabanına yazılır; bu otomatik içerik analizi değil,
          &quot;link hâlâ yanıt veriyor mu&quot; kontrolüdür.
        </p>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
          {[3, 5, 10].map((n) => (
            <button
              key={n}
              type="button"
              disabled={running}
              onClick={() => void runBatch(n)}
              style={{
                fontSize: 12,
                fontWeight: 500,
                padding: '8px 14px',
                borderRadius: 8,
                border: 'none',
                cursor: running ? 'not-allowed' : 'pointer',
                background: '#534AB7',
                color: '#fff',
                opacity: running ? 0.6 : 1,
              }}
            >
              {running ? 'Kontrol…' : `Sıradaki ${n} kaydı kontrol et`}
            </button>
          ))}
          <button
            type="button"
            disabled={loading}
            onClick={() => void load()}
            style={{
              fontSize: 12,
              padding: '8px 14px',
              borderRadius: 8,
              border: '0.5px solid #e0e0e0',
              background: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            Listeyi yenile
          </button>
        </div>

        {msg && (
          <div
            style={{
              marginBottom: 12,
              padding: '10px 14px',
              borderRadius: 8,
              background: '#E1F5EE',
              color: '#085041',
              fontSize: 13,
            }}
          >
            {msg}
          </div>
        )}
        {err && (
          <div
            style={{
              marginBottom: 12,
              padding: '10px 14px',
              borderRadius: 8,
              background: '#FDE8E8',
              color: '#A32D2D',
              fontSize: 13,
            }}
          >
            {err}
            {err.includes('Yetkisiz') || err.includes('function') ? (
              <span style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                <code>docs/sql/007_opportunity_url_health.sql</code> dosyasını Supabase SQL Editor’da
                çalıştırdığınızdan emin olun.
              </span>
            ) : null}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>Yükleniyor…</div>
        ) : (
          <div style={{ overflowX: 'auto', border: '0.5px solid #e0e0e0', borderRadius: 12, background: '#fff' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: '#fafafa', textAlign: 'left' }}>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Durum</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>HTTP</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Başlık</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Son kontrol</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Manuel</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const pill = statusLabel(row)
                  return (
                    <tr key={row.id} style={{ borderTop: '0.5px solid #eee' }}>
                      <td style={{ padding: '10px 12px', verticalAlign: 'top' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: 6,
                            fontSize: 10,
                            fontWeight: 600,
                            background: row.is_active ? '#E1F5EE' : '#f0f0f0',
                            color: row.is_active ? '#085041' : '#666',
                          }}
                        >
                          {row.is_active ? 'aktif' : 'pasif'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px', verticalAlign: 'top' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 600,
                            background: pill.bg,
                            color: pill.color,
                          }}
                        >
                          {pill.text}
                        </span>
                        {row.last_url_check_error && (
                          <div style={{ marginTop: 6, color: '#A32D2D', fontSize: 11, maxWidth: 220 }}>
                            {row.last_url_check_error}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '10px 12px', verticalAlign: 'top' }}>
                        <div style={{ fontWeight: 500, marginBottom: 6 }}>{row.title}</div>
                        <a
                          href={row.official_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: '#534AB7', wordBreak: 'break-all' }}
                        >
                          {row.official_url}
                        </a>
                        {row.last_url_check_final_url &&
                          row.last_url_check_final_url !== row.official_url && (
                            <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>
                              Son URL: {row.last_url_check_final_url}
                            </div>
                          )}
                      </td>
                      <td style={{ padding: '10px 12px', verticalAlign: 'top', color: '#888', whiteSpace: 'nowrap' }}>
                        {row.last_url_check_at
                          ? new Date(row.last_url_check_at).toLocaleString('tr-TR')
                          : '—'}
                      </td>
                      <td style={{ padding: '10px 12px', verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                        {row.last_verified_at && (
                          <div style={{ fontSize: 10, color: '#085041', marginBottom: 4 }}>
                            ✓ {new Date(row.last_verified_at).toLocaleDateString('tr-TR')}
                          </div>
                        )}
                        <button
                          type="button"
                          disabled={verifyingId === row.id}
                          onClick={() => void markVerified(row.id)}
                          style={{
                            fontSize: 11,
                            padding: '4px 10px',
                            borderRadius: 6,
                            border: '0.5px solid #1a6b5a66',
                            background: verifyingId === row.id ? '#f0f0f0' : '#fff',
                            color: '#1a6b5a',
                            cursor: verifyingId === row.id ? 'not-allowed' : 'pointer',
                          }}
                          title="Linki açıp manuel kontrol ettiysen tıkla — admin panelinde 'doğrulanmış' işaretlenir."
                        >
                          {verifyingId === row.id ? '…' : 'Doğruladım'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  )
}
