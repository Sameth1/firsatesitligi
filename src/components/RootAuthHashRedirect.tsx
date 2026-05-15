'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

/**
 * Supabase bazen hata parametrelerini yalnızca URL hash'inde döner; middleware query görmez.
 * Ana sayfada hash'te otp_expired varsa admin girişine taşır.
 */
export default function RootAuthHashRedirect() {
  const pathname = usePathname()

  useEffect(() => {
    if (pathname !== '/') return
    const h = typeof window !== 'undefined' ? window.location.hash : ''
    if (!h) return
    if (h.includes('otp_expired') || h.includes('error_code=otp_expired')) {
      window.location.replace('/admin/login?auth=otp_expired')
    }
  }, [pathname])

  return null
}
