'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { supabase } from '@/lib/supabase'

/**
 * Supabase bazen hata veya başarılı oturum parametrelerini yalnızca URL hash'inde döner
 * (emailRedirectTo izin listesinde yoksa Site URL'e fallback yapar).
 * Ana sayfada hash varsa uygun şekilde yönlendir.
 */
export default function RootAuthHashRedirect() {
  const pathname = usePathname()

  useEffect(() => {
    if (pathname !== '/') return
    const h = typeof window !== 'undefined' ? window.location.hash : ''
    if (!h) return
    if (h.includes('otp_expired') || h.includes('error_code=otp_expired')) {
      window.location.replace('/admin/login?auth=otp_expired')
      return
    }
    if (h.includes('access_token=')) {
      const params = new URLSearchParams(h.replace(/^#/, ''))
      const access_token = params.get('access_token')
      const refresh_token = params.get('refresh_token')
      if (access_token && refresh_token) {
        supabase.auth.setSession({ access_token, refresh_token }).then(({ error }) => {
          window.location.replace(error ? '/admin/login?error=auth' : '/admin')
        })
      }
    }
  }, [pathname])

  return null
}
