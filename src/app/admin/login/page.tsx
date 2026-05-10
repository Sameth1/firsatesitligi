'use client'
import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'
import { getPublicSiteOrigin } from '@/lib/site-origin'

type Status = 'idle' | 'loading' | 'sent' | 'error'

const OTP_EXPIRED_HINT =
  'Magic link süresi doldu veya zaten kullanıldı. Bazı e-posta uygulamaları (Outlook, Gmail güvenli tarama vb.) linki önizleyerek kodu tek kullanımlık hale getirir — mümkünse web postadan tıkla veya yeni link iste.'

export default function AdminLogin() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const q = new URLSearchParams(window.location.search)
    if (q.get('auth') === 'otp_expired') {
      setErrorDetail(OTP_EXPIRED_HINT)
      setStatus('error')
      window.history.replaceState(null, '', '/admin/login')
      return
    }
    if (q.get('error') === 'auth') {
      setErrorDetail('Oturum doğrulanamadı. Yeni magic link iste.')
      setStatus('error')
      window.history.replaceState(null, '', '/admin/login')
      return
    }
    const h = window.location.hash
    if (h.includes('otp_expired') || h.includes('error_code=otp_expired')) {
      setErrorDetail(OTP_EXPIRED_HINT)
      setStatus('error')
      window.history.replaceState(null, '', '/admin/login')
    }
  }, [])

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!email.includes('@')) return

    setStatus('loading')
    setErrorDetail(null)
    const origin = getPublicSiteOrigin()
    if (!origin) {
      setStatus('error')
      setErrorDetail(
        'Site adresi (origin) alınamadı. Sayfayı yenileyin. Vercel’de eski deploy kullanıyorsan yeni sürümü bekleyin.'
      )
      return
    }
    const redirectTo = `${origin}/auth/callback?next=${encodeURIComponent('/admin')}`
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: redirectTo,
      },
    })

    if (error) {
      setStatus('error')
      setErrorDetail(
        error.message +
          (error.message.toLowerCase().includes('redirect') || error.message.includes('URI')
            ? ' — Supabase Dashboard → Authentication → URL Configuration içinde Redirect URLs listesine şunu ekleyin: ' +
                redirectTo
            : '')
      )
    } else {
      setStatus('sent')
    }
  }

  return (
    <main style={{ minHeight: '100vh', background: '#fafaf9', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ maxWidth: 400, width: '100%' }}>
        <div style={{ fontSize: 22, fontWeight: 500, color: '#1a1a1a', marginBottom: 24 }}>
          <span style={{ color: '#534AB7' }}>fırsat</span>eşitliği
          <span style={{ fontSize: 12, color: '#999', marginLeft: 8 }}>Admin</span>
        </div>

        {status === 'sent' ? (
          <div style={{
            background: '#E1F5EE', border: '0.5px solid #9FE1CB',
            borderRadius: 12, padding: '20px 18px',
            fontSize: 14, color: '#085041', lineHeight: 1.6,
          }}>
            <strong>Magic link gönderildi.</strong><br />
            E-posta kutunu kontrol et ve linke <strong>bir kez</strong> tıkla. Uygulama önizlemesi linki önce açarsa kod geçersiz olabilir; o zaman buradan yeni link iste.
          </div>
        ) : (
          <form onSubmit={handleLogin} style={{
            background: '#fff', border: '0.5px solid #e0e0e0',
            borderRadius: 16, padding: '24px 20px',
          }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#333', marginBottom: 12 }}>
              Admin girişi
            </div>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 5 }}>E-posta</div>
            <input
              type="email"
              value={email}
              onChange={e => {
                setEmail(e.target.value)
                if (errorDetail) setErrorDetail(null)
              }}
              placeholder="admin@example.com"
              required
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 8,
                border: '0.5px solid #e0e0e0', fontSize: 13,
                outline: 'none', background: '#fff', color: '#1a1a1a',
                marginBottom: 16,
              }}
            />
            <button
              type="submit"
              disabled={status === 'loading'}
              style={{
                width: '100%', padding: '12px', borderRadius: 10,
                background: status === 'loading' ? '#AFA9EC' : '#534AB7',
                color: '#fff', border: 'none', fontSize: 14,
                fontWeight: 500, cursor: status === 'loading' ? 'not-allowed' : 'pointer',
              }}
            >
              {status === 'loading' ? 'Gönderiliyor...' : 'Magic Link Gönder'}
            </button>
            {status === 'error' && (
              <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 8, lineHeight: 1.45 }}>
                <strong>Giriş başarısız.</strong> {errorDetail ?? 'Tekrar dene.'}
              </div>
            )}
          </form>
        )}
      </div>
    </main>
  )
}
