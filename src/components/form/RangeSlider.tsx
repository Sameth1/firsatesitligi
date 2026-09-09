'use client'

/**
 * Elle çekilen yaş barı. Native <input type=range> yerine kendi kontrolümüz:
 * büyük değer göstergesi, dolgu gradyanı, tutamağın etrafında nefes alan hale
 * ve "belirtme" durumu (null) gerekiyor — yaş opsiyonel bir alan.
 *
 * Erişilebilirlik: gerçek slider rolü, ok tuşları + Home/End, PageUp/PageDown.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { pulseScene, hexToRgb01 } from '@/components/scene/sceneBus'
import ResetButton from './ResetButton'

type Props = {
  value: number | null
  onChange: (v: number | null) => void
  min?: number
  max?: number
  label: string
  hint?: string
  /** Barın altında görünen kısa açıklama, örn. "18 yaş — çoğu program açık" */
  describe?: (v: number) => string
}

const ACCENT = '#7C5CFF'

export default function RangeSlider({
  value, onChange, min = 15, max = 45, label, hint, describe,
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  // Render sırasında ref okunamaz; geçişleri kapatmak için ayrı bir state.
  const [dragging, setDragging] = useState(false)

  const active = value !== null
  const ratio = value === null ? 0.5 : (value - min) / (max - min)

  const commit = useCallback((next: number) => {
    onChange(next)
    // Sürükleme sırasında her piksel için darbe göndermeyelim — sahne titrer.
    if (!draggingRef.current) pulseScene({ color: hexToRgb01(ACCENT), strength: 0.5 })
  }, [onChange])

  const setFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const r = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
    onChange(Math.round(min + r * (max - min)))
  }, [min, max, onChange])

  useEffect(() => {
    function move(e: PointerEvent) {
      if (!draggingRef.current) return
      e.preventDefault()
      setFromClientX(e.clientX)
    }
    function up() {
      if (!draggingRef.current) return
      draggingRef.current = false
      setDragging(false)
      pulseScene({ color: hexToRgb01(ACCENT), strength: 0.6 })
    }
    window.addEventListener('pointermove', move, { passive: false })
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
  }, [setFromClientX])

  // Bar boyunca 5'er yaşta işaretler
  const ticks: number[] = []
  for (let v = min; v <= max; v += 5) ticks.push(v)

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
        marginBottom: 6, gap: 12,
      }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-hi)' }}>
          {label}
        </span>
        {active ? (
          <ResetButton onClick={() => onChange(null)} label={`${label} seçimini sıfırla`} />
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-low)' }}>{hint ?? 'opsiyonel'}</span>
        )}
      </div>

      {/* Büyük değer göstergesi — sürüklerken gözün takip ettiği yer */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 12, minHeight: 44 }}>
        <span style={{
          fontSize: 40, fontWeight: 700, lineHeight: 1, letterSpacing: '-0.04em',
          fontVariantNumeric: 'tabular-nums',
          background: active ? 'var(--grad-brand)' : 'none',
          WebkitBackgroundClip: active ? 'text' : undefined,
          backgroundClip: active ? 'text' : undefined,
          color: active ? 'transparent' : 'var(--text-low)',
          transition: 'color 0.2s ease',
        }}>
          {active ? value : '—'}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-mid)' }}>
          {active ? 'yaşındasın' : 'fark etmez'}
        </span>
      </div>

      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value ?? undefined}
        aria-valuetext={active ? `${value} yaş` : 'belirtilmedi'}
        onPointerDown={e => {
          draggingRef.current = true
          setDragging(true)
          setFromClientX(e.clientX)
        }}
        onKeyDown={e => {
          const current = value ?? Math.round((min + max) / 2)
          if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); commit(Math.min(max, current + 1)) }
          if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { e.preventDefault(); commit(Math.max(min, current - 1)) }
          if (e.key === 'PageUp')   { e.preventDefault(); commit(Math.min(max, current + 5)) }
          if (e.key === 'PageDown') { e.preventDefault(); commit(Math.max(min, current - 5)) }
          if (e.key === 'Home')     { e.preventDefault(); commit(min) }
          if (e.key === 'End')      { e.preventDefault(); commit(max) }
        }}
        className="range-track"
        style={{ position: 'relative', height: 38, cursor: 'grab', touchAction: 'none' }}
      >
        {/* ray */}
        <div style={{
          position: 'absolute', top: 16, left: 0, right: 0, height: 8, borderRadius: 999,
          background: 'rgba(255,255,255,0.09)',
          border: '1px solid rgba(255,255,255,0.06)',
        }} />

        {/* işaretler */}
        {ticks.map(v => (
          <span
            key={v}
            aria-hidden="true"
            style={{
              position: 'absolute', top: 28, left: `${((v - min) / (max - min)) * 100}%`,
              width: 1, height: 5, marginLeft: -0.5,
              background: 'rgba(255,255,255,0.16)',
            }}
          />
        ))}

        {/* dolgu */}
        <div style={{
          position: 'absolute', top: 16, left: 0, height: 8, borderRadius: 999,
          width: `${ratio * 100}%`,
          background: active ? 'var(--grad-brand)' : 'rgba(255,255,255,0.14)',
          boxShadow: active ? '0 0 20px rgba(124, 92, 255, 0.65)' : 'none',
          transition: dragging ? 'none' : 'width 0.22s cubic-bezier(0.16,1,0.3,1), background 0.2s ease',
        }} />

        {/* tutamak */}
        <div
          className="range-thumb"
          data-active={active ? 'true' : 'false'}
          style={{
            position: 'absolute', top: 6, left: `calc(${ratio * 100}% - 14px)`,
            width: 28, height: 28, borderRadius: '50%',
            background: active
              ? 'linear-gradient(150deg, #FFFFFF 0%, #D9CEFF 100%)'
              : 'rgba(255,255,255,0.18)',
            border: `2px solid ${active ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.28)'}`,
            boxShadow: active
              ? '0 8px 22px -6px rgba(124, 92, 255, 0.95)'
              : '0 2px 8px rgba(0,0,0,0.5)',
            transform: dragging ? 'scale(1.14)' : 'scale(1)',
            transition: dragging
              ? 'transform 0.12s ease'
              : 'left 0.22s cubic-bezier(0.16,1,0.3,1), transform 0.18s ease, background 0.2s ease',
          }}
        />
      </div>

      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 10.5, color: 'var(--text-low)', marginTop: 4,
      }}>
        <span>{min}</span>
        <span>{max}+</span>
      </div>

      {active && describe && (
        <div style={{ fontSize: 11.5, color: 'var(--teal)', marginTop: 8, fontWeight: 500 }}>
          {describe(value)}
        </div>
      )}
    </div>
  )
}
