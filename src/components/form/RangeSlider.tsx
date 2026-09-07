'use client'

/**
 * Elle çekilen yaş barı. Native <input type=range> yerine kendi kontrolümüz:
 * dolgu gradyanı, tutamağın üstünde canlı değer balonu ve "belirtme" durumu
 * (null) gerekiyor — yaş opsiyonel bir alan, boş bırakılabilmeli.
 *
 * Erişilebilirlik: gerçek bir slider rolü, ok tuşlarıyla da değiştirilebilir.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

type Props = {
  value: number | null
  onChange: (v: number | null) => void
  min?: number
  max?: number
  label: string
  hint?: string
}

export default function RangeSlider({ value, onChange, min = 15, max = 45, label, hint }: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  // Render sırasında ref okunamaz; geçişleri kapatmak için ayrı bir state.
  const [dragging, setDragging] = useState(false)

  const ratio = value === null ? 0.5 : (value - min) / (max - min)

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
    function up() { draggingRef.current = false; setDragging(false) }
    window.addEventListener('pointermove', move, { passive: false })
    window.addEventListener('pointerup', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [setFromClientX])

  const active = value !== null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#4A4468', letterSpacing: '-0.01em' }}>
          {label}
        </span>
        {active ? (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="ghost-btn"
            style={{
              fontSize: 11, color: '#7A7496', background: 'none',
              border: 'none', cursor: 'pointer', padding: 0,
            }}
          >
            temizle
          </button>
        ) : (
          <span style={{ fontSize: 11, color: '#A9A4BF' }}>{hint ?? 'opsiyonel'}</span>
        )}
      </div>

      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value ?? undefined}
        onPointerDown={e => { draggingRef.current = true; setDragging(true); setFromClientX(e.clientX) }}
        onKeyDown={e => {
          if (e.key === 'ArrowRight' || e.key === 'ArrowUp') onChange(Math.min(max, (value ?? min) + 1))
          if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') onChange(Math.max(min, (value ?? min) - 1))
        }}
        className="range-track"
        style={{ position: 'relative', height: 34, cursor: 'pointer', touchAction: 'none' }}
      >
        {/* ray */}
        <div style={{
          position: 'absolute', top: 14, left: 0, right: 0, height: 6, borderRadius: 999,
          background: 'rgba(83, 74, 183, 0.13)',
        }} />
        {/* dolgu */}
        <div style={{
          position: 'absolute', top: 14, left: 0, height: 6, borderRadius: 999,
          width: `${ratio * 100}%`,
          background: active
            ? 'linear-gradient(90deg, #4B41B5 0%, #6C4FD0 55%, #17A79A 100%)'
            : 'rgba(83, 74, 183, 0.22)',
          transition: dragging ? 'none' : 'width 0.18s ease, background 0.2s ease',
        }} />
        {/* tutamak + değer balonu */}
        <div
          className="range-thumb"
          style={{
            position: 'absolute', top: 5, left: `calc(${ratio * 100}% - 12px)`,
            width: 24, height: 24, borderRadius: '50%',
            background: '#fff',
            border: `2px solid ${active ? '#5B4FC4' : '#C9C5E4'}`,
            boxShadow: active
              ? '0 6px 16px -6px rgba(76, 65, 181, 0.8)'
              : '0 2px 6px rgba(0,0,0,0.08)',
            transition: dragging ? 'none' : 'left 0.18s ease, border-color 0.2s ease',
          }}
        >
          <span style={{
            position: 'absolute', bottom: 30, left: '50%', transform: 'translateX(-50%)',
            fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap',
            color: active ? '#3C3489' : '#A9A4BF',
          }}>
            {active ? `${value} yaş` : 'fark etmez'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#B4AFC9', marginTop: 2 }}>
        <span>{min}</span>
        <span>{max}+</span>
      </div>
    </div>
  )
}
