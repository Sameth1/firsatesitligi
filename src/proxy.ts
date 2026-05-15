import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createServerClient } from '@supabase/ssr'

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
      return NextResponse.redirect(url)
    }
    return NextResponse.next({ request: { headers: request.headers } })
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
    return response
  }

  if (isAdminRoute) {
    if (!user) {
      const loginUrl = new URL('/admin/login', request.url)
      return NextResponse.redirect(loginUrl)
    }

    // Check admin status
    const { data: admin } = await supabase
      .from('admins')
      .select('user_id')
      .eq('user_id', user.id)
      .single()

    if (!admin) {
      return new NextResponse('Yetkisiz: Admin değilsiniz', { status: 403 })
    }
  }

  return response
}

export const config = {
  matcher: ['/', '/admin/:path*', '/auth/:path*'],
}
