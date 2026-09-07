'use client'

/**
 * Seçim kartları — küçük "tag" düğmeleri yerine ikonlu, dokunması kolay,
 * hover'da kalkan kartlar. Tek seçim; aynı karta tekrar basmak seçimi kaldırır
 * (alanlar opsiyonel kalmalı).
 */

type Option = { value: string; label: string; icon: string; note?: string }

export default function ChoiceGrid({ options, value, onChange, label, hint, columns = 3, accent = '#534AB7' }: {
  options: Option[]
  value: string | null
  onChange: (v: string | null) => void
  label: string
  hint?: string
  columns?: number
  accent?: string
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#4A4468', letterSpacing: '-0.01em' }}>{label}</span>
        {value ? (
          <button
            type="button"
            onClick={() => onChange(null)}
            style={{ fontSize: 11, color: '#7A7496', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            temizle
          </button>
        ) : (
          hint && <span style={{ fontSize: 11, color: '#A9A4BF' }}>{hint}</span>
        )}
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(auto-fit, minmax(min(${columns >= 4 ? 92 : 112}px, 100%), 1fr))`,
        gap: 8,
      }}>
        {options.map(o => {
          const selected = value === o.value
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(selected ? null : o.value)}
              className="choice-card"
              data-selected={selected ? 'true' : 'false'}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6,
                padding: '12px 12px 11px',
                borderRadius: 14,
                cursor: 'pointer',
                textAlign: 'left',
                background: selected ? `linear-gradient(140deg, ${accent} 0%, ${accent}D9 100%)` : 'rgba(255,255,255,0.72)',
                border: `1px solid ${selected ? 'transparent' : 'rgba(83, 74, 183, 0.16)'}`,
                color: selected ? '#fff' : '#3A3556',
                boxShadow: selected
                  ? `0 14px 26px -14px ${accent}CC`
                  : '0 2px 6px -4px rgba(35, 28, 82, 0.25)',
              }}
            >
              <span style={{ fontSize: 19, lineHeight: 1 }} aria-hidden="true">{o.icon}</span>
              <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.25 }}>{o.label}</span>
              {o.note && (
                <span style={{ fontSize: 10, opacity: selected ? 0.85 : 0.6 }}>{o.note}</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
