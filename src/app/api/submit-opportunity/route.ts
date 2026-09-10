import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { assertPublicHttpUrl } from '@/lib/url-safety'

/**
 * Halka açık "Fırsat Öner" formunun sunucu ucu.
 *
 * NEDEN VAR: rate limit ancak IP bilinirse çalışır ve IP'yi yalnız sunucu
 * güvenilir biçimde bilebilir. Tarayıcı kendi genel IP'sini bilmez; bilse bile
 * istemciden gelen IP'ye güvenilemez (her istekte farklı uydurur, limit
 * anlamsızlaşır). Bu yüzden öneri artık doğrudan Supabase'e değil buraya
 * gidiyor; IP'yi burada okuyup submit_human_opportunity RPC'sine veriyoruz.
 *
 * RPC'nin EXECUTE yetkisi yalnız service_role'da — anon çağıramıyor, yani bu
 * route atlanarak sahte IP ile limit aşılamıyor.
 */

// Bu route istek başlıklarını okuyor; statik olarak önceden üretilemez.
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
    // Anahtar yoksa sessizce başarısız olmaktansa açıkça söyle: aksi hâlde
    // form çalışıyor görünüp öneriler sessizce kaybolur.
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

  const title = String(body.title ?? '').trim()
  const rawUrl = String(body.url ?? '').trim()
  if (!title || !rawUrl) {
    return NextResponse.json({ error: 'Başlık ve bağlantı zorunlu.' }, { status: 400 })
  }
  // Mevcut SSRF önlemini yeniden kullan: yerel/özel ağ adresleri engellenir.
  try {
    assertPublicHttpUrl(rawUrl)
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : 'Geçersiz bağlantı.' },
      { status: 400 },
    )
  }

  // Yalnız beklenen alanlar geçsin; istemci submission_origin/review_stage
  // gönderse bile RPC bunları zaten sabitliyor (bkz. 103/104).
  const payload = {
    title,
    url: rawUrl,
    category_slug: body.category_slug ?? null,
    submitter_nickname: body.submitter_nickname ?? null,
    submitter_email: body.submitter_email ?? null,
    host_countries: Array.isArray(body.host_countries) ? body.host_countries : [],
    deadline_text: body.deadline_text ?? null,
    funding_type: body.funding_type ?? null,
    eligibility_notes: body.eligibility_notes ?? null,
    language_requirement: body.language_requirement ?? null,
    description: body.description ?? null,
  }

  const supabase = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  })

  const { data, error } = await supabase.rpc('submit_human_opportunity', {
    p_ip: ip,
    p_payload: payload,
  })

  if (error) {
    // 53400 = configuration_limit_exceeded → RPC'nin rate limit sinyali.
    if (error.code === '53400') {
      return NextResponse.json({ error: error.message }, { status: 429 })
    }
    if (error.code === '23514') {
      return NextResponse.json({ error: error.message }, { status: 400 })
    }
    return NextResponse.json({ error: 'Öneri kaydedilemedi.' }, { status: 500 })
  }

  return NextResponse.json(data ?? { success: true }, { status: 201 })
}
