'use client'

import { useId, useState, type FormEvent } from 'react'

const REJECTION_REASONS = [
  { value: 'expired', label: 'Son başvuru tarihi geçmiş' },
  { value: 'duplicate', label: 'Aynı fırsat zaten mevcut' },
  { value: 'dead_link', label: 'Bağlantı çalışmıyor' },
  { value: 'not_opportunity', label: 'Gerçek bir fırsat ilanı değil' },
  { value: 'category_mismatch', label: 'Kategoriyle uyumlu değil' },
  { value: 'paid_commercial', label: 'Ücretli veya ticari program' },
  { value: 'collection_page', label: 'Tek fırsat değil, liste/derleme sayfası' },
  { value: 'not_eligible', label: 'Hedef kitle için uygun değil' },
  { value: 'insufficient_info', label: 'Bilgi eksik veya güncel değil' },
  { value: 'other', label: 'Diğer' },
] as const

interface RejectComposerProps {
  busy: boolean
  onCancel: () => void
  onSubmit: (note: string) => void | Promise<void>
}

export default function RejectComposer({ busy, onCancel, onSubmit }: RejectComposerProps) {
  const reasonId = useId()
  const detailId = useId()
  const [reasonCode, setReasonCode] = useState('')
  const [detail, setDetail] = useState('')

  const reason = REJECTION_REASONS.find(item => item.value === reasonCode)
  const detailRequired = reasonCode === 'other'
  const canSubmit = Boolean(reason && (!detailRequired || detail.trim()))

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!reason || !canSubmit || busy) return
    const suffix = detail.trim() ? ` — ${detail.trim()}` : ''
    await onSubmit(`[insan] RED:${reason.value} — ${reason.label}${suffix}`)
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        marginTop: 10, padding: 12, borderRadius: 10,
        border: '1px solid #F5B8B8', background: '#FFF7F7',
      }}
    >
      <label htmlFor={reasonId} style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#7A1F1F', marginBottom: 5 }}>
        Red nedeni
      </label>
      <select
        id={reasonId}
        value={reasonCode}
        onChange={event => setReasonCode(event.target.value)}
        disabled={busy}
        required
        style={{
          width: '100%', padding: '8px 10px', borderRadius: 8,
          border: '0.5px solid #DFAAAA', background: '#fff', fontSize: 12,
        }}
      >
        <option value="">Bir neden seç…</option>
        {REJECTION_REASONS.map(item => (
          <option key={item.value} value={item.value}>{item.label}</option>
        ))}
      </select>

      <label htmlFor={detailId} style={{ display: 'block', fontSize: 11, fontWeight: 500, color: '#7A1F1F', marginTop: 9, marginBottom: 5 }}>
        Açıklama {detailRequired ? '(zorunlu)' : '(opsiyonel)'}
      </label>
      <textarea
        id={detailId}
        value={detail}
        onChange={event => setDetail(event.target.value)}
        disabled={busy}
        required={detailRequired}
        rows={2}
        placeholder="Kararı açıklayan kısa not…"
        style={{
          width: '100%', padding: '8px 10px', borderRadius: 8,
          border: '0.5px solid #DFAAAA', background: '#fff', fontSize: 12,
          resize: 'vertical', boxSizing: 'border-box',
        }}
      />

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 9 }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          style={{ padding: '7px 12px', borderRadius: 8, border: '0.5px solid #ddd', background: '#fff', color: '#555', cursor: 'pointer' }}
        >
          Vazgeç
        </button>
        <button
          type="submit"
          disabled={!canSubmit || busy}
          style={{
            padding: '7px 12px', borderRadius: 8, border: 'none',
            background: '#A32D2D', color: '#fff', fontWeight: 600,
            cursor: canSubmit && !busy ? 'pointer' : 'not-allowed',
            opacity: canSubmit && !busy ? 1 : 0.5,
          }}
        >
          {busy ? 'Reddediliyor…' : 'Reddi Onayla'}
        </button>
      </div>
    </form>
  )
}
