import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createServerClient } from '@supabase/ssr'

/**
 * Güvenlik başlıkları — ikinci kat. next.config.ts'teki `headers()` kuralı
 * proxy'nin ürettiği yanıtlara da uygulanıyor (ölçüldü: /admin'in 307'si
 * başlıkları taşıyor), yani bu sarmalayıcı bugün gereksiz. Yine de duruyor:
 * admin yüzeyi clickjacking'e karşı korunması gereken yer ve buradaki 403
 * gibi yanıtlar proxy'nin kendi ürettiği yanıtlar. next.config.ts'teki
 * kural değişirse/daralırsa admin yine korumasız kalmasın.
 * Liste next.config.ts ile aynı tutulmalı.
 */
function withSecurityHeaders<T extends NextResponse>(res: T): T {
  res.headers.set('X-Frame-Options', 'DENY')
  res.headers.set('Content-Security-Policy', "frame-ancestors 'none'")
  res.headers.set('X-Content-Type-Options', 'nosniff')
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  res.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
  return res
}

export async function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl

  /** Supabase magic link hataları Site URL olarak köke düşerse → admin girişi */
  if (pathname === '/') {
    const error = searchParams.get('error')
    const errorCode = searchParams.get('error_code')
    if (errorCode || error === 'access_denied') {
      const url = request.nextUrl.clone()
      url.pathname = '/admin/login'
      url.search = ''
      url.searchParams.set(
        'auth',
        errorCode === 'otp_expired' ? 'otp_expired' : error ?? 'unknown'
      )
      return withSecurityHeaders(NextResponse.redirect(url))
    }
    return withSecurityHeaders(NextResponse.next({ request: { headers: request.headers } }))
  }

  // Only guard /admin routes (except login)
  const isAdminRoute = pathname.startsWith('/admin') && pathname !== '/admin/login'
  const isAuthCallback = pathname.startsWith('/auth/callback')

  const response = NextResponse.next({
    request: { headers: request.headers },
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) => {
            request.cookies.set(name, value)
            response.cookies.set(name, value, options)
          })
        },
      },
    }
  )

  // Refresh session (important for SSR)
  const { data: { user } } = await supabase.auth.getUser()

  if (isAuthCallback) {
    return withSecurityHeaders(response)
  }

  if (isAdminRoute) {
    if (!user) {
      const loginUrl = new URL('/admin/login', request.url)
      return withSecurityHeaders(NextResponse.redirect(loginUrl))
    }

    // Check admin status
    const { data: admin } = await supabase
      .from('admins')
      .select('user_id')
      .eq('user_id', user.id)
      .single()

    if (!admin) {
      return withSecurityHeaders(new NextResponse('Yetkisiz: Admin değilsiniz', { status: 403 }))
    }
  }

  return withSecurityHeaders(response)
}

export const config = {
  matcher: ['/', '/admin/:path*', '/auth/:path*'],
}
