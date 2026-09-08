'use client'

/**
 * Seçim kartları — ikonlu, dokunması kolay, hover'da kalkan kartlar.
 * Tek seçim; aynı karta tekrar basmak seçimi kaldırır (alanlar opsiyonel).
 *
 * İkon iki biçimde gelebilir:
 *  - `icon`      : emoji / metin (ülke bayrakları gibi)
 *  - `iconSrc`   : Higgsfield ile üretilmiş cam 3B ikon (public/icons/*.webp)
 * Seçim yapıldığında sahneye kartın vurgu rengiyle bir darbe gönderilir.
 */

import Image from 'next/image'
import { pulseScene, hexToRgb01 } from '@/components/scene/sceneBus'

type Option = {
  value: string; label: string
  icon?: string; iconSrc?: string; note?: string
  /** Kartın kendi vurgu rengi — verilmezse ızgaranın `accent`'i kullanılır. */
  accent?: string
}

export default function ChoiceGrid({
  options, value, onChange, label, hint, columns = 3, accent = '#7C5CFF',
}: {
  options: Option[]
  value: string | null
  onChange: (v: string | null) => void
  label: string
  hint?: string
  columns?: number
  accent?: string
}) {
  const minWidth = columns >= 4 ? 104 : 128

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
        marginBottom: 12, gap: 12,
      }}>
        <span style={{
          fontSize: 12.5, fontWeight: 600, color: 'var(--text-hi)',
          letterSpacing: '-0.01em',
        }}>
          {label}
        </span>
        {value ? (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="ghost-btn"
            style={{
              fontSize: 11, color: 'var(--text-low)', background: 'none',
              border: 'none', cursor: 'pointer', padding: 0, whiteSpace: 'nowrap',
            }}
          >
            temizle
          </button>
        ) : (
          hint && <span style={{ fontSize: 11, color: 'var(--text-low)', whiteSpace: 'nowrap' }}>{hint}</span>
        )}
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(auto-fit, minmax(min(${minWidth}px, 100%), 1fr))`,
        gap: 10,
      }}>
        {options.map(o => {
          const selected = value === o.value
          const tint = o.accent ?? accent
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => {
                const next = selected ? null : o.value
                onChange(next)
                if (next) pulseScene({ color: hexToRgb01(tint), strength: 0.85 })
              }}
              className="choice-card"
              data-selected={selected ? 'true' : 'false'}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8,
                padding: '14px 14px 13px',
                borderRadius: 18,
                cursor: 'pointer',
                textAlign: 'left',
                // `color` seçiliyken halka ve ikon parlamasının rengini besler
                color: selected ? tint : 'var(--text-mid)',
                background: selected
                  ? `linear-gradient(150deg, ${tint}38 0%, ${tint}14 100%)`
                  : 'rgba(255,255,255,0.035)',
                border: `1px solid ${selected ? `${tint}99` : 'rgba(255,255,255,0.09)'}`,
                boxShadow: selected
                  ? `0 18px 34px -18px ${tint}, inset 0 1px 0 rgba(255,255,255,0.14)`
                  : 'inset 0 1px 0 rgba(255,255,255,0.05)',
              }}
            >
              <span
                className="choice-icon"
                aria-hidden="true"
                style={{
                  display: 'grid', placeItems: 'center',
                  width: o.iconSrc ? 38 : 26, height: o.iconSrc ? 38 : 26,
                  fontSize: 22, lineHeight: 1,
                }}
              >
                {o.iconSrc ? (
                  <Image src={o.iconSrc} alt="" width={38} height={38} style={{ objectFit: 'contain' }} />
                ) : o.icon}
              </span>
              <span style={{
                fontSize: 13, fontWeight: 600, lineHeight: 1.25,
                color: selected ? '#fff' : 'var(--text-hi)',
              }}>
                {o.label}
              </span>
              {o.note && (
                <span style={{
                  fontSize: 11,
                  color: selected ? 'rgba(255,255,255,0.8)' : 'var(--text-mid)',
                }}>
                  {o.note}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
