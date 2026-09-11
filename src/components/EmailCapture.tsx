'use client'
import { useState } from 'react'
import { supabase } from '@/lib/supabase'

export default function EmailCapture({ searchSnapshot }: {
  searchSnapshot?: Record<string, unknown>
}) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')

  async function handleSubmit() {
    if (!email || !email.includes('@')) return
    setStatus('loading')

    const { error } = await supabase
      .from('subscribers')
      .insert({ email, search_snapshot: searchSnapshot ?? null })

    if (error && error.code !== '23505') { // 23505 = duplicate key, zaten kayıtlı
      setStatus('error')
    } else {
      setStatus('done')
    }
  }

  if (status === 'done') return (
    <div className="fx-fade-in-up" style={{
      background: 'rgba(43, 224, 200, 0.12)',
      border: '1px solid rgba(43, 224, 200, 0.4)',
      borderRadius: 18, padding: '18px 22px',
      fontSize: 13.5, color: '#7BF0DC', fontWeight: 500,
      display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <span style={{ fontSize: 18 }} aria-hidden="true">✓</span>
      Kaydedildi — deadline yaklaştığında seni haberdar edeceğiz.
    </div>
  )

  return (
    <div className="glass-panel" style={{ padding: '20px 22px' }}>
      <div style={{ fontSize: 14.5, fontWeight: 600, color: 'var(--text-hi)', marginBottom: 4 }}>
        Deadline yaklaştığında haber verelim mi?
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-low)', marginBottom: 14 }}>
        Hesap açılmaz. Sadece hatırlatma için.
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input
          type="email"
          placeholder="e-posta adresin"
          value={email}
          onChange={e => setEmail(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          style={{
            flex: '1 1 200px', minWidth: 0,
            padding: '12px 15px', borderRadius: 999,
            border: '1px solid rgba(255,255,255,0.14)', fontSize: 13.5,
            outline: 'none', background: 'rgba(255,255,255,0.05)',
            color: 'var(--text-hi)',
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={status === 'loading'}
          className="btn-primary"
          style={{
            padding: '12px 26px', borderRadius: 999,
            color: '#150F35', border: 'none', fontSize: 13.5, fontWeight: 700,
            cursor: status === 'loading' ? 'not-allowed' : 'pointer',
            opacity: status === 'loading' ? 0.65 : 1,
            whiteSpace: 'nowrap',
          }}
        >
          {status === 'loading' ? '...' : 'Bildir'}
        </button>
      </div>

      {status === 'error' && (
        <div style={{ fontSize: 11.5, color: '#FFB4B4', marginTop: 8 }}>
          Bir hata oluştu, tekrar dene.
        </div>
      )}
    </div>
  )
}
