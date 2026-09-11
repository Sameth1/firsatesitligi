'use client'

/**
 * Belirsizler — otomatik karar verilemeyen fırsat kayıtları.
 *
 * Scraper'lar ve backfill'ler bir alanı güvenle dolduramadığında kaydı silmek
 * ya da tahmin etmek yerine buraya işaretliyor: `review_flag` + Türkçe
 * `review_note`. Kayıt yayında kalmaya devam eder (gizlenmez) — amaç bilgiyi
 * kaybetmeden insana sormak.
 *
 * Veriyi doğrudan tablodan okuyamıyoruz: opportunities'te RLS yalnız
 * "is_active = true" public SELECT'e izin veriyor. Bağlantı denetimi ekranıyla
 * aynı desen: SECURITY DEFINER RPC + admins tablosu kontrolü.
 */

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'

type ReviewRow = {
  id: string
  title: string
  official_url: string
  is_active: boolean
  review_flag: string
  review_note: string | null
  review_flagged_at: string | null
  age_min: number | null
  age_max: number | null
  host_countries: string[] | null
  eligible_citizenships: string[] | null
  eligibility_notes: string | null
}

const FLAG_LABELS: Record<string, { text: string; bg: string; color: string }> = {
  age_belirsiz:    { text: 'Yaş şartı belirsiz',    bg: '#FAEEDA', color: '#633806' },
  uyruk_belirsiz:  { text: 'Uyruk şartı belirsiz',  bg: '#E4F0FC', color: '#0C447C' },
}

function flagLabel(flag: string) {
  return FLAG_LABELS[flag] ?? { text: flag, bg: '#f0f0f0', color: '#666' }
}

export default function ReviewQueuePage() {
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [resolvingId, setResolvingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    const { data, error } = await supabase.rpc('get_opportunity_review_queue')
    setLoading(false)
    if (error) {
      setErr(error.message)
      setRows([])
      return
    }
    setRows((data as ReviewRow[]) ?? [])
  }, [])

  useEffect(() => {
    queueMicrotask(() => { void load() })
  }, [load])

  async function handleLogout() {
    await supabase.auth.signOut()
    window.location.href = '/admin/login'
  }

  async function resolve(id: string) {
    setResolvingId(id)
    setErr(null)
    setMsg(null)
    const { error } = await supabase.rpc('resolve_opportunity_review', { p_id: id })
    setResolvingId(null)
    if (error) {
      setErr('İşaret kaldırılamadı: ' + error.message)
      return
    }
    setMsg('İncelendi olarak işaretlendi.')
    await load()
  }

  return (
    <main className="light-surface" style={{ minHeight: '100vh', background: '#fafaf9', padding: '32px 16px' }}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>

        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 20, flexWrap: 'wrap', gap: 12,
        }}>
          <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a' }}>
            <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
            <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Belirsizler</span>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Link href="/admin" style={{
              fontSize: 12, color: '#534AB7', textDecoration: 'none',
              padding: '6px 12px', border: '0.5px solid #e0e0e0',
              borderRadius: 8, background: '#fff',
            }}>
              ← Öneriler
            </Link>
            <Link href="/admin/link-audit" style={{
              fontSize: 12, color: '#534AB7', textDecoration: 'none',
              padding: '6px 12px', border: '0.5px solid #e0e0e0',
              borderRadius: 8, background: '#fff',
            }}>
              Bağlantı denetimi
            </Link>
            <button type="button" onClick={handleLogout} style={{
              fontSize: 12, color: '#999', background: 'none',
              border: '0.5px solid #e0e0e0', borderRadius: 8,
              padding: '6px 12px', cursor: 'pointer',
            }}>
              Çıkış
            </button>
          </div>
        </div>

        <p style={{ fontSize: 13, color: '#666', lineHeight: 1.6, marginBottom: 18 }}>
          Otomatik olarak güvenle karar verilemeyen kayıtlar. Bunlar <strong>yayından
          kaldırılmadı</strong> — kullanıcılar görmeye devam ediyor; şart, kartın metninde
          zaten yazıyor. Karar verdikten sonra kaydı Supabase&apos;den düzeltip aşağıdaki
          düğmeyle işareti kaldır.
        </p>

        {err && (
          <div style={{
            background: '#FDE8E8', border: '0.5px solid #E8A8A8', color: '#A32D2D',
            borderRadius: 10, padding: '10px 14px', fontSize: 13, marginBottom: 14,
          }}>
            {err}
          </div>
        )}
        {msg && (
          <div style={{
            background: '#E1F5EE', border: '0.5px solid #9FE1CB', color: '#085041',
            borderRadius: 10, padding: '10px 14px', fontSize: 13, marginBottom: 14,
          }}>
            {msg}
          </div>
        )}

        {loading ? (
          <div style={{ fontSize: 13, color: '#999', padding: '40px 0', textAlign: 'center' }}>
            Yükleniyor…
          </div>
        ) : rows.length === 0 ? (
          <div style={{
            background: '#fff', border: '0.5px solid #e5e5e5', borderRadius: 12,
            padding: '48px 20px', textAlign: 'center', fontSize: 14, color: '#666',
          }}>
            İncelenecek belirsiz kayıt yok.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {rows.map(row => {
              const flag = flagLabel(row.review_flag)
              return (
                <article key={row.id} style={{
                  background: '#fff', border: '0.5px solid #e5e5e5',
                  borderRadius: 12, padding: '16px 18px',
                }}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'flex-start', gap: 12, flexWrap: 'wrap', marginBottom: 10,
                  }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: 15, fontWeight: 500, color: '#1a1a1a', marginBottom: 6 }}>
                        {row.title}
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        <span style={{
                          fontSize: 11, fontWeight: 600, padding: '3px 9px', borderRadius: 20,
                          background: flag.bg, color: flag.color,
                        }}>
                          {flag.text}
                        </span>
                        {!row.is_active && (
                          <span style={{
                            fontSize: 11, padding: '3px 9px', borderRadius: 20,
                            background: '#f0f0f0', color: '#666',
                          }}>
                            Pasif
                          </span>
                        )}
                        <span style={{ fontSize: 11, color: '#999' }}>
                          Yaş: {row.age_min ?? '—'}–{row.age_max ?? '—'}
                          {' · '}
                          Uyruk: {(row.eligible_citizenships ?? []).join(', ') || '—'}
                        </span>
                      </div>
                    </div>
                    <a
                      href={row.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 12, color: '#534AB7', textDecoration: 'none',
                        padding: '6px 12px', border: '0.5px solid #e0e0e0',
                        borderRadius: 8, whiteSpace: 'nowrap',
                      }}
                    >
                      Kaynak ↗
                    </a>
                  </div>

                  {row.review_note && (
                    <div style={{
                      background: '#fafaf9', border: '0.5px solid #eee', borderRadius: 8,
                      padding: '10px 12px', fontSize: 12.5, color: '#444',
                      lineHeight: 1.65, marginBottom: 10,
                    }}>
                      {row.review_note}
                    </div>
                  )}

                  {row.eligibility_notes && (
                    <details style={{ marginBottom: 10 }}>
                      <summary style={{ fontSize: 12, color: '#666', cursor: 'pointer' }}>
                        Kaynak uygunluk metni
                      </summary>
                      <div style={{
                        fontSize: 12, color: '#666', lineHeight: 1.6,
                        marginTop: 6, whiteSpace: 'pre-wrap',
                      }}>
                        {row.eligibility_notes}
                      </div>
                    </details>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      type="button"
                      onClick={() => resolve(row.id)}
                      disabled={resolvingId === row.id}
                      style={{
                        fontSize: 12, fontWeight: 500,
                        color: '#fff', background: '#534AB7',
                        border: 'none', borderRadius: 8, padding: '8px 16px',
                        cursor: resolvingId === row.id ? 'not-allowed' : 'pointer',
                        opacity: resolvingId === row.id ? 0.6 : 1,
                      }}
                    >
                      {resolvingId === row.id ? 'Kaydediliyor…' : 'İncelendi, işareti kaldır'}
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </main>
  )
}
