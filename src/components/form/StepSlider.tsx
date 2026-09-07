'use client'

/**
 * Kademeli (snap'lenen) seviye barı — CEFR dil seviyesi için.
 * Değerler ayrık olduğu için sürükleme en yakın durağa oturur; her durağın
 * altında kısa etiketi görünür. null = "seçilmedi" (filtre uygulanmaz).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

type Stop = { value: string; short: string; label: string }

export default function StepSlider({ stops, value, onChange, label, hint }: {
  stops: Stop[]
  value: string | null
  onChange: (v: string | null) => void
  label: string
  hint?: string
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  // Render sırasında ref okunamaz; geçişleri kapatmak için ayrı bir state.
  const [dragging, setDragging] = useState(false)

  const index = value === null ? -1 : stops.findIndex(s => s.value === value)
  const ratio = index < 0 ? 0 : index / (stops.length - 1)

  const setFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const r = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
    onChange(stops[Math.round(r * (stops.length - 1))].value)
  }, [stops, onChange])

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

  const active = index >= 0

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
            style={{ fontSize: 11, color: '#7A7496', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
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
        aria-valuemin={0}
        aria-valuemax={stops.length - 1}
        aria-valuenow={index >= 0 ? index : undefined}
        aria-valuetext={active ? stops[index].label : undefined}
        onPointerDown={e => { draggingRef.current = true; setDragging(true); setFromClientX(e.clientX) }}
        onKeyDown={e => {
          if (e.key === 'ArrowRight') onChange(stops[Math.min(stops.length - 1, index + 1)].value)
          if (e.key === 'ArrowLeft' && index > 0) onChange(stops[index - 1].value)
        }}
        style={{ position: 'relative', height: 30, cursor: 'pointer', touchAction: 'none' }}
      >
        <div style={{
          position: 'absolute', top: 12, left: 0, right: 0, height: 6, borderRadius: 999,
          background: 'rgba(15, 110, 86, 0.12)',
        }} />
        <div style={{
          position: 'absolute', top: 12, left: 0, height: 6, borderRadius: 999,
          width: `${ratio * 100}%`,
          background: active ? 'linear-gradient(90deg, #0F6E56 0%, #17A79A 60%, #5BE8C8 100%)' : 'transparent',
          transition: dragging ? 'none' : 'width 0.18s ease',
        }} />
        {/* duraklar */}
        {stops.map((s, i) => (
          <span
            key={s.value}
            style={{
              position: 'absolute', top: 14, left: `calc(${(i / (stops.length - 1)) * 100}% - 2px)`,
              width: 4, height: 4, borderRadius: '50%',
              background: active && i <= index ? 'rgba(255,255,255,0.85)' : 'rgba(15, 110, 86, 0.3)',
            }}
          />
        ))}
        <div style={{
          position: 'absolute', top: 3, left: `calc(${ratio * 100}% - 12px)`,
          width: 24, height: 24, borderRadius: '50%',
          background: '#fff',
          border: `2px solid ${active ? '#0F8E76' : '#C6DED7'}`,
          boxShadow: active ? '0 6px 16px -6px rgba(15, 110, 86, 0.7)' : '0 2px 6px rgba(0,0,0,0.08)',
          opacity: active ? 1 : 0.55,
          transition: dragging ? 'none' : 'left 0.18s ease, opacity 0.2s ease',
        }} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
        {stops.map((s, i) => (
          <span key={s.value} style={{
            fontSize: 10,
            fontWeight: active && i === index ? 700 : 500,
            color: active && i === index ? '#0F6E56' : '#B4AFC9',
          }}>
            {s.short}
          </span>
        ))}
      </div>
      {active && (
        <div style={{ fontSize: 11, color: '#0F6E56', marginTop: 6, fontWeight: 500 }}>
          {stops[index].label}
        </div>
      )}
    </div>
  )
}
