import { NextResponse } from 'next/server'
import { createSupabaseServer } from '@/lib/supabase-server'
import { assertPublicHttpUrl } from '@/lib/url-safety'

const UA =
  'FirsatEsitligi-LinkCheck/1.0 (+https://firsatesitligi.com)'

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

async function checkOneUrl(
  url: string
): Promise<{ status: number | null; error: string | null; finalUrl: string | null }> {
  assertPublicHttpUrl(url)
  const controller = new AbortController()
  const t = setTimeout(() => controller.abort(), 18_000)
  try {
    const res = await fetch(url, {
      method: 'GET',
      redirect: 'follow',
      signal: controller.signal,
      headers: {
        'User-Agent': UA,
        Accept: 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
      },
    })
    clearTimeout(t)
    return {
      status: res.status,
      error: null,
      finalUrl: res.url || url,
    }
  } catch (e) {
    clearTimeout(t)
    const msg = e instanceof Error ? e.message : String(e)
    return { status: null, error: msg, finalUrl: null }
  }
}

export async function POST(req: Request) {
  const supabase = await createSupabaseServer()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Oturum yok' }, { status: 401 })
  }

  const { data: admin } = await supabase
    .from('admins')
    .select('user_id')
    .eq('user_id', user.id)
    .maybeSingle()
  if (!admin) {
    return NextResponse.json({ error: 'Yetkisiz' }, { status: 403 })
  }

  let limit = 5
  try {
    const body = await req.json()
    if (typeof body?.limit === 'number' && Number.isFinite(body.limit)) {
      limit = Math.min(20, Math.max(1, Math.floor(body.limit)))
    }
  } catch {
    /* body yok */
  }

  const { data: rows, error: pickErr } = await supabase.rpc(
    'pick_opportunities_for_url_check',
    { p_limit: limit }
  )
  if (pickErr) {
    return NextResponse.json({ error: pickErr.message }, { status: 500 })
  }

  type PickRow = { id: string; official_url: string }
  const list = (rows ?? []) as PickRow[]
  const results: Array<{
    id: string
    status: number | null
    error: string | null
    finalUrl: string | null
    recorded: boolean
    recordError?: string
    skipped?: string
  }> = []

  for (const row of list) {
    try {
      assertPublicHttpUrl(row.official_url)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      const { error: recErr } = await supabase.rpc(
        'record_opportunity_url_check',
        {
          p_id: row.id,
          p_http_status: null,
          p_error: msg,
          p_final_url: null,
        }
      )
      results.push({
        id: row.id,
        status: null,
        error: msg,
        finalUrl: null,
        recorded: !recErr,
        recordError: recErr?.message,
        skipped: 'unsafe_url',
      })
      await sleep(400)
      continue
    }

    const r = await checkOneUrl(row.official_url)
    const { error: recErr } = await supabase.rpc(
      'record_opportunity_url_check',
      {
        p_id: row.id,
        p_http_status: r.status,
        p_error: r.error,
        p_final_url: r.finalUrl,
      }
    )
    results.push({
      id: row.id,
      ...r,
      recorded: !recErr,
      recordError: recErr?.message,
    })
    await sleep(750)
  }

  return NextResponse.json({ checked: results.length, results })
}
