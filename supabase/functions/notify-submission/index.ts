import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY')!
const ADMIN_NOTIFY_FROM = Deno.env.get('ADMIN_NOTIFY_FROM') || 'noreply@firsatesitligi.com'
const APP_URL = Deno.env.get('APP_URL') || 'https://firsatesitligi.com'

interface WebhookPayload {
  type: 'INSERT' | 'UPDATE'
  table: string
  record: Record<string, unknown>
  old_record: Record<string, unknown> | null
}

async function sendEmail(to: string, subject: string, html: string) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${RESEND_API_KEY}`,
    },
    body: JSON.stringify({ from: ADMIN_NOTIFY_FROM, to, subject, html }),
  })

  if (!res.ok) {
    console.error('Resend error:', await res.text())
  }
  return res.ok
}

Deno.serve(async (req) => {
  try {
    const payload: WebhookPayload = await req.json()
    const { type, record } = payload

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    if (type === 'INSERT') {
      // New submission — notify all admins
      const { data: admins } = await supabase
        .from('admins')
        .select('email')

      if (admins && admins.length > 0) {
        const title = record.title as string
        const id = record.id as string
        const nickname = (record.submitter_nickname as string) || 'Anonim'

        const subject = `Yeni fırsat önerisi: ${title}`
        const html = `
          <h2>Yeni Fırsat Önerisi</h2>
          <p><strong>Başlık:</strong> ${title}</p>
          <p><strong>URL:</strong> <a href="${record.url}">${record.url}</a></p>
          <p><strong>Kategori:</strong> ${record.category_slug || '—'}</p>
          <p><strong>Gönderen:</strong> ${nickname}${record.submitter_email ? ` (${record.submitter_email})` : ''}</p>
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
            <p>"<strong>${title}</strong>" öneriniz incelendi ve sisteme eklendi.</p>
            <p>Katkın için teşekkür ederiz!</p>
            <br/>
            <a href="${APP_URL}" style="background:#534AB7;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:500;">
              Fırsatları Gör
            </a>
          `
        )
      }

      if (status === 'needs_revision') {
        await sendEmail(
          submitterEmail,
          `Önerin hakkında geri bildirim: ${title}`,
          `
            <h2>Revize İstendi</h2>
            <p>"<strong>${title}</strong>" öneriniz incelendi, küçük bir düzeltme gerekiyor.</p>
            ${adminNote ? `<p><strong>Admin notu:</strong> ${adminNote}</p>` : ''}
            <p>E-posta ile yanıtlayarak düzeltmeyi iletebilirsin.</p>
          `
        )
      }

      if (status === 'rejected') {
        await sendEmail(
          submitterEmail,
          `Önerin hakkında bilgilendirme: ${title}`,
          `
            <h2>Değerlendirildi</h2>
            <p>"<strong>${title}</strong>" öneriniz incelendi fakat şu an sisteme eklenemedi.</p>
            ${adminNote ? `<p><strong>Sebep:</strong> ${adminNote}</p>` : ''}
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
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
})
