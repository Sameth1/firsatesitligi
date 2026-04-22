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
    <div style={{
      background: '#E1F5EE', border: '0.5px solid #9FE1CB',
      borderRadius: 12, padding: '14px 18px',
      fontSize: 13, color: '#085041', fontWeight: 500,
    }}>
      Kaydedildi — deadline yaklaştığında seni haberdar edeceğiz.
    </div>
  )

  return (
    <div style={{
      background: '#EEEDFE', border: '0.5px solid #AFA9EC',
      borderRadius: 12, padding: '14px 18px',
    }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: '#3C3489', marginBottom: 8 }}>
        Deadline yaklaştığında haber verelim mi?
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="email"
          placeholder="e-posta adresin"
          value={email}
          onChange={e => setEmail(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          style={{
            flex: 1, padding: '8px 12px', borderRadius: 8,
            border: '0.5px solid #AFA9EC', fontSize: 13,
            outline: 'none', background: '#fff',
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={status === 'loading'}
          style={{
            padding: '8px 16px', borderRadius: 8,
            background: '#534AB7', color: '#fff',
            border: 'none', fontSize: 13, fontWeight: 500,
            cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          {status === 'loading' ? '...' : 'Bildir'}
        </button>
      </div>
      {status === 'error' && (
        <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 6 }}>
          Bir hata oluştu, tekrar dene.
        </div>
      )}
      <div style={{ fontSize: 10, color: '#7F77DD', marginTop: 6 }}>
        Hesap açılmaz. Sadece hatırlatma için.
      </div>
    </div>
  )
}
