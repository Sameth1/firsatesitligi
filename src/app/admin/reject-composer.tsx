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
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const reason = REJECTION_REASONS.find(item => item.value === reasonCode)
  const detailRequired = reasonCode === 'other'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    if (!reason) {
      setErrorMsg('Lütfen listeden bir red sebebi seçin.')
      return
    }
    if (detailRequired && !detail.trim()) {
      setErrorMsg('Lütfen "Diğer" seçeneği için açıklama girin.')
      return
    }
    setErrorMsg(null)
    const suffix = detail.trim() ? ` — ${detail.trim()}` : ''
    await onSubmit(`[insan] RED:${reason.value} — ${reason.label}${suffix}`)
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        marginTop: 10, padding: 14, borderRadius: 10,
        border: '1px solid #F5B8B8', background: '#FFF7F7',
      }}
    >
      <label htmlFor={reasonId} style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#7A1F1F', marginBottom: 6 }}>
        Red nedeni <span style={{ color: '#c00' }}>*</span>
      </label>
      <select
        id={reasonId}
        value={reasonCode}
        onChange={event => {
          setReasonCode(event.target.value)
          setErrorMsg(null)
        }}
        disabled={busy}
        style={{
          width: '100%', padding: '8px 10px', borderRadius: 8,
          border: errorMsg && !reason ? '1.5px solid #dc2626' : '0.5px solid #DFAAAA',
          background: '#fff', fontSize: 12, outline: 'none',
        }}
      >
        <option value="">Bir neden seçin…</option>
        {REJECTION_REASONS.map(item => (
          <option key={item.value} value={item.value}>{item.label}</option>
        ))}
      </select>

      <label htmlFor={detailId} style={{ display: 'block', fontSize: 11, fontWeight: 500, color: '#7A1F1F', marginTop: 10, marginBottom: 5 }}>
        Açıklama {detailRequired ? '(zorunlu)' : '(opsiyonel)'}
      </label>
      <textarea
        id={detailId}
        value={detail}
        onChange={event => {
          setDetail(event.target.value)
          setErrorMsg(null)
        }}
        disabled={busy}
        rows={2}
        placeholder="Kararı açıklayan kısa not…"
        style={{
          width: '100%', padding: '8px 10px', borderRadius: 8,
          border: errorMsg && detailRequired && !detail.trim() ? '1.5px solid #dc2626' : '0.5px solid #DFAAAA',
          background: '#fff', fontSize: 12,
          resize: 'vertical', boxSizing: 'border-box', outline: 'none',
        }}
      />

      {errorMsg && (
        <div style={{ color: '#b91c1c', fontSize: 12, marginTop: 6, fontWeight: 500 }}>
          {errorMsg}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          style={{ padding: '7px 14px', borderRadius: 8, border: '0.5px solid #ddd', background: '#fff', color: '#555', cursor: 'pointer', fontSize: 12 }}
        >
          Vazgeç
        </button>
        <button
          type="submit"
          disabled={busy}
          style={{
            padding: '7px 14px', borderRadius: 8, border: 'none',
            background: '#A32D2D', color: '#fff', fontWeight: 600,
            cursor: busy ? 'not-allowed' : 'pointer',
            opacity: busy ? 0.6 : 1, fontSize: 12,
          }}
        >
          {busy ? 'Reddediliyor…' : 'Reddi Onayla'}
        </button>
      </div>
    </form>
  )
}
