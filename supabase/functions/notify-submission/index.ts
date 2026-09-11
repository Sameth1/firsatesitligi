import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY')
const SUBMISSION_WEBHOOK_SECRET = Deno.env.get('SUBMISSION_WEBHOOK_SECRET')
const ADMIN_NOTIFY_FROM = Deno.env.get('ADMIN_NOTIFY_FROM') || 'noreply@firsatesitligi.com'
const APP_URL = Deno.env.get('APP_URL') || 'https://firsatesitligi.vercel.app'

interface WebhookPayload {
  type: 'INSERT' | 'UPDATE'
  table: string
  record: Record<string, unknown>
  old_record: Record<string, unknown> | null
}

async function sendEmail(to: string, subject: string, html: string) {
  if (!RESEND_API_KEY) throw new Error('RESEND_API_KEY eksik')
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${RESEND_API_KEY}`,
    },
    body: JSON.stringify({ from: ADMIN_NOTIFY_FROM, to, subject, html }),
  })

  if (!res.ok) {
    const detail = await res.text()
    console.error('Resend error:', detail)
    throw new Error(`E-posta gönderilemedi (${res.status})`)
  }
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function safeHttpUrl(value: unknown) {
  try {
    const url = new URL(String(value ?? ''))
    return url.protocol === 'http:' || url.protocol === 'https:'
      ? escapeHtml(url.toString())
      : '#'
  } catch {
    return '#'
  }
}

function secretsEqual(left: string, right: string) {
  const a = new TextEncoder().encode(left)
  const b = new TextEncoder().encode(right)
  if (a.length !== b.length) return false
  let difference = 0
  for (let index = 0; index < a.length; index += 1) {
    difference |= a[index] ^ b[index]
  }
  return difference === 0
}

function makeToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  return btoa(String.fromCharCode(...bytes))
    .replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  return Array.from(new Uint8Array(digest))
    .map(byte => byte.toString(16).padStart(2, '0')).join('')
}

Deno.serve(async (req) => {
  try {
    if (!SUBMISSION_WEBHOOK_SECRET) {
      return new Response(JSON.stringify({ error: 'Webhook yapılandırması eksik' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    const providedSecret = req.headers.get('x-webhook-secret') || ''
    if (!secretsEqual(providedSecret, SUBMISSION_WEBHOOK_SECRET)) {
      return new Response(JSON.stringify({ error: 'Yetkisiz' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const payload: WebhookPayload = await req.json()
    const { type, old_record: oldRecord } = payload
    if (payload.table !== 'submissions' || !['INSERT', 'UPDATE'].includes(type)) {
      return new Response(JSON.stringify({ error: 'Geçersiz webhook olayı' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )
    const recordId = String(payload.record?.id ?? '')
    const { data: storedRecord, error: recordError } = await supabase
      .from('submissions')
      .select('*')
      .eq('id', recordId)
      .single()
    if (recordError || !storedRecord) throw recordError || new Error('Submission bulunamadı')
    const record = storedRecord as Record<string, unknown>

    if (type === 'INSERT') {
      // New submission — notify all admins
      const { data: admins } = await supabase
        .from('admins')
        .select('email')

      if (admins && admins.length > 0) {
        const title = String(record.title ?? '')
        const id = record.id as string
        const nickname = String(record.submitter_nickname || 'Anonim')
        const safeTitle = escapeHtml(title)
        const safeRecordUrl = safeHttpUrl(record.url)
        const safeNickname = escapeHtml(nickname)
        const safeEmail = escapeHtml(record.submitter_email)

        const subject = `Yeni fırsat önerisi: ${title}`
        const html = `
          <h2>Yeni Fırsat Önerisi</h2>
          <p><strong>Başlık:</strong> ${safeTitle}</p>
          <p><strong>URL:</strong> <a href="${safeRecordUrl}">${safeRecordUrl}</a></p>
          <p><strong>Kategori:</strong> ${escapeHtml(record.category_slug || '—')}</p>
          <p><strong>Gönderen:</strong> ${safeNickname}${record.submitter_email ? ` (${safeEmail})` : ''}</p>
          <br/>
          <a href="${APP_URL}/admin/submissions/${id}" style="background:#534AB7;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:500;">
            İncele ve Onayla
          </a>
        `

        for (const admin of admins) {
          await sendEmail(admin.email, subject, html)
        }
      }
    }

    if (type === 'UPDATE') {
      const status = record.status as string
      const submitterEmail = record.submitter_email as string | null
      const title = record.title as string
      const adminNote = record.admin_note as string | null

      // Aynı statüdeki alan güncellemeleri yeni e-posta/token üretmesin.
      if (oldRecord?.status === status) {
        return new Response(JSON.stringify({ ok: true, skipped: 'status_unchanged' }), {
          headers: { 'Content-Type': 'application/json' },
        })
      }

      // No email provided — skip silently
      if (!submitterEmail) {
        return new Response(JSON.stringify({ ok: true, skipped: 'no_email' }), {
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (status === 'approved') {
        await sendEmail(
          submitterEmail,
          `Önerin onaylandı: ${title}`,
          `
            <h2>Tebrikler!</h2>
            <p>"<strong>${escapeHtml(title)}</strong>" öneriniz incelendi ve sisteme eklendi.</p>
            <p>Katkın için teşekkür ederiz!</p>
            <br/>
            <a href="${APP_URL}" style="background:#534AB7;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:500;">
              Fırsatları Gör
            </a>
          `
        )
      }

      if (status === 'needs_revision') {
        const rawToken = makeToken()
        const tokenHash = await sha256(rawToken)
        const submissionId = record.id as string

        await supabase
          .from('submission_revision_tokens')
          .update({ used_at: new Date().toISOString() })
          .eq('submission_id', submissionId)
          .is('used_at', null)

        const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
        const { error: tokenError } = await supabase
          .from('submission_revision_tokens')
          .insert({ submission_id: submissionId, token_hash: tokenHash, expires_at: expiresAt })
        if (tokenError) throw tokenError

        const revisionUrl = `${APP_URL}/revise/${encodeURIComponent(rawToken)}`
        await sendEmail(
          submitterEmail,
          `Önerin hakkında geri bildirim: ${title}`,
          `
            <h2>Revize İstendi</h2>
            <p>"<strong>${escapeHtml(title)}</strong>" öneriniz incelendi, küçük bir düzeltme gerekiyor.</p>
            ${adminNote ? `<p><strong>Admin notu:</strong> ${escapeHtml(adminNote)}</p>` : ''}
            <p><a href="${revisionUrl}" style="background:#534AB7;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:500;">Öneriyi Düzenle</a></p>
            <p>Bu güvenli bağlantı 7 gün geçerlidir ve bir kez kullanılabilir.</p>
          `
        )
      }

      if (status === 'rejected') {
        await sendEmail(
          submitterEmail,
          `Önerin hakkında bilgilendirme: ${title}`,
          `
            <h2>Değerlendirildi</h2>
            <p>"<strong>${escapeHtml(title)}</strong>" öneriniz incelendi fakat şu an sisteme eklenemedi.</p>
            ${adminNote ? `<p><strong>Sebep:</strong> ${escapeHtml(adminNote)}</p>` : ''}
            <p>Yeni öneriler için her zaman bekleriz. Katkın için teşekkürler!</p>
          `
        )
      }
    }

    return new Response(JSON.stringify({ ok: true }), {
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (err) {
    console.error('notify-submission error:', err)
    return new Response(JSON.stringify({ error: 'Bildirim işlenemedi' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
})
