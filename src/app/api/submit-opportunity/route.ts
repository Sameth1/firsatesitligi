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

const VALID_CATEGORIES = new Set([
  'scholarship', 'volunteering', 'youth_project',
  'internship', 'summer_school', 'exchange',
])
const VALID_FUNDING_TYPES = new Set(['full', 'partial', 'free', 'stipend'])

function optionalText(value: unknown): string | null {
  if (typeof value !== 'string') return null
  return value.trim() || null
}

/** Vercel x-forwarded-for'u kendisi yazar; ilk değer gerçek istemcidir. */
function clientIp(req: Request): string | null {
  const xff = req.headers.get('x-vercel-forwarded-for')
    || req.headers.get('x-forwarded-for')
  if (xff) {
    const first = xff.split(',')[0]?.trim()
    if (first) return first
  }
  return req.headers.get('x-real-ip')?.trim() || null
}

export async function POST(req: Request) {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !serviceKey) {
    console.error('submit-opportunity: Supabase sunucu değişkenleri eksik')
    return NextResponse.json(
      { error: 'Öneri sistemi geçici olarak kullanılamıyor.' },
      { status: 503 },
    )
  }

  const ip = clientIp(req)
  if (!ip) {
    return NextResponse.json({ error: 'İstek kaynağı belirlenemedi.' }, { status: 400 })
  }

  let rawBody: string
  try {
    rawBody = await req.text()
  } catch {
    return NextResponse.json({ error: 'Geçersiz istek gövdesi.' }, { status: 400 })
  }
  if (rawBody.length > 32_000) {
    return NextResponse.json({ error: 'İstek gövdesi çok büyük.' }, { status: 413 })
  }

  let body: Record<string, unknown>
  try {
    const parsed: unknown = JSON.parse(rawBody)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error()
    body = parsed as Record<string, unknown>
  } catch {
    return NextResponse.json({ error: 'Geçersiz istek gövdesi.' }, { status: 400 })
  }

  const title = String(body.title ?? '').trim()
  const rawUrl = String(body.url ?? '').trim()
  const categorySlug = String(body.category_slug ?? '').trim()
  if (!title || !rawUrl || !categorySlug) {
    return NextResponse.json(
      { error: 'Başlık, bağlantı ve kategori zorunlu.' },
      { status: 400 },
    )
  }
  if (title.length > 240 || rawUrl.length > 2_048) {
    return NextResponse.json({ error: 'Başlık veya bağlantı çok uzun.' }, { status: 400 })
  }
  if (!VALID_CATEGORIES.has(categorySlug)) {
    return NextResponse.json({ error: 'Geçersiz kategori.' }, { status: 400 })
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
  const fundingType = body.funding_type == null
    ? null
    : String(body.funding_type).trim() || null
  if (fundingType && !VALID_FUNDING_TYPES.has(fundingType)) {
    return NextResponse.json({ error: 'Geçersiz finansman türü.' }, { status: 400 })
  }

  const hostCountries = Array.isArray(body.host_countries)
    ? body.host_countries.map(value => String(value).trim().toUpperCase())
    : []
  if (hostCountries.length > 10 || hostCountries.some(code => !/^[A-Z]{2}$|^\*$/.test(code))) {
    return NextResponse.json({ error: 'Geçersiz ülke kodu.' }, { status: 400 })
  }

  const nickname = optionalText(body.submitter_nickname)
  const email = optionalText(body.submitter_email)
  const deadlineText = optionalText(body.deadline_text)
  const eligibilityNotes = optionalText(body.eligibility_notes)
  const languageRequirement = optionalText(body.language_requirement)
  const description = optionalText(body.description)
  if ((nickname?.length ?? 0) > 100
      || (email?.length ?? 0) > 320
      || (deadlineText?.length ?? 0) > 240
      || (eligibilityNotes?.length ?? 0) > 5_000
      || (languageRequirement?.length ?? 0) > 1_000
      || (description?.length ?? 0) > 10_000) {
    return NextResponse.json({ error: 'Gönderilen alanlardan biri çok uzun.' }, { status: 400 })
  }
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: 'Geçersiz e-posta adresi.' }, { status: 400 })
  }

  let ageMin: number | null = null
  let ageMax: number | null = null
  if (body.age_min !== undefined && body.age_min !== null && body.age_min !== '') {
    const parsed = Number(body.age_min)
    if (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 120) {
      ageMin = Math.floor(parsed)
    }
  }
  if (body.age_max !== undefined && body.age_max !== null && body.age_max !== '') {
    const parsed = Number(body.age_max)
    if (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 120) {
      ageMax = Math.floor(parsed)
    }
  }
  if (ageMin !== null && ageMax !== null && ageMin > ageMax) {
    return NextResponse.json({ error: 'Minimum yaş, maksimum yaştan büyük olamaz.' }, { status: 400 })
  }

  const VALID_STUDY_LEVELS = new Set(['high_school', 'bachelor', 'master', 'phd', 'graduate'])
  const studyLevel = Array.isArray(body.study_level)
    ? body.study_level
        .map(value => String(value).trim().toLowerCase())
        .filter(value => VALID_STUDY_LEVELS.has(value))
    : []

  const eligibleCitizenships = Array.isArray(body.eligible_citizenships)
    ? body.eligible_citizenships
        .map(value => String(value).trim().toUpperCase())
        .filter(code => /^[A-Z]{2}$|^\*$/.test(code))
    : []

  const payload = {
    title,
    url: rawUrl,
    category_slug: categorySlug,
    submitter_nickname: nickname,
    submitter_email: email,
    host_countries: hostCountries,
    deadline_text: deadlineText,
    funding_type: fundingType,
    age_min: ageMin,
    age_max: ageMax,
    study_level: studyLevel.length > 0 ? studyLevel : null,
    eligible_citizenships: eligibleCitizenships.length > 0 ? eligibleCitizenships : null,
    eligibility_notes: eligibilityNotes,
    language_requirement: languageRequirement,
    description,
  }

  const supabase = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  })

  try {
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
  } catch {
    return NextResponse.json({ error: 'Öneri kaydedilemedi.' }, { status: 500 })
  }
}
