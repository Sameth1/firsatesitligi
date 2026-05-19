'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

/**
 * Supabase magic link parametreleri /auth/callback yerine ana sayfaya (Site URL) düşebilir:
 *  - PKCE başarı: ?code=... query'si köke gelir → /auth/callback'e taşı (oturum değişimi orada).
 *  - Hata: yalnızca URL hash'inde döner (middleware query göremez) → admin girişine taşı.
 */
export default function RootAuthHashRedirect() {
  const pathname = usePathname()

  useEffect(() => {
    if (pathname !== '/') return
    if (typeof window === 'undefined') return

    // PKCE auth kodu köke düşmüşse callback rotasına taşı; exchangeCodeForSession orada çalışır.
    const search = window.location.search
    if (new URLSearchParams(search).has('code')) {
      window.location.replace(`/auth/callback${search}`)
      return
    }

    // Hata yalnızca hash'te dönmüşse: admin girişine taşı.
    const h = window.location.hash
    if (!h) return
    if (h.includes('otp_expired') || h.includes('error_code=otp_expired')) {
      window.location.replace('/admin/login?auth=otp_expired')
    }
  }, [pathname])

  return null
}
