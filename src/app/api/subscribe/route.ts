import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

/**
 * Abone (deadline hatırlatma) kaydının sunucu ucu.
 *
 * NEDEN VAR: rate limit ancak IP bilinirse çalışır ve IP'yi yalnız sunucu
 * güvenilir biçimde bilebilir. Önceden tarayıcı doğrudan `subscribers`
 * tablosuna yazıyordu ve politika `with check (true)` idi — tek bir script
 * saniyede yüzlerce adres ekleyebilirdi.
 *
 * subscribe_email RPC'sinin EXECUTE yetkisi yalnız service_role'da; bu route
 * atlanarak sahte IP ile limit aşılamaz (bkz. 114).
 */

// İstek başlıklarını okuyor; statik üretilemez.
export const dynamic = 'force-dynamic'

/** Vercel x-forwarded-for'u kendisi yazar; ilk değer gerçek istemcidir. */
function clientIp(req: Request): string | null {
  const xff = req.headers.get('x-forwarded-for')
  if (xff) {
    const first = xff.split(',')[0]?.trim()
    if (first) return first
  }
  return req.headers.get('x-real-ip')?.trim() || null
}

export async function POST(req: Request) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !serviceKey) {
    return NextResponse.json(
      { error: 'Sunucu yapılandırması eksik (SUPABASE_SERVICE_ROLE_KEY).' },
      { status: 503 },
    )
  }

  const ip = clientIp(req)
  if (!ip) {
    return NextResponse.json({ error: 'İstek kaynağı belirlenemedi.' }, { status: 400 })
  }

  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Geçersiz istek gövdesi.' }, { status: 400 })
  }

  const email = String(body.email ?? '').trim()
  if (!email || !email.includes('@')) {
    return NextResponse.json({ error: 'Geçerli bir e-posta gir.' }, { status: 400 })
  }

  const supabase = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  })

  const { error } = await supabase.rpc('subscribe_email', {
    p_ip: ip,
    p_email: email,
    p_snapshot: body.search_snapshot ?? null,
  })

  if (error) {
    // 53400 = configuration_limit_exceeded → RPC'nin rate limit sinyali.
    if (error.code === '53400') {
      return NextResponse.json({ error: error.message }, { status: 429 })
    }
    if (error.code === '23514' || error.code === '23502') {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }
    return NextResponse.json({ error: 'Kayıt tamamlanamadı.' }, { status: 500 })
  }

  return NextResponse.json({ success: true }, { status: 201 })
}
