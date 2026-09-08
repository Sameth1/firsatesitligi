'use client'

/**
 * Kademeli (snap'lenen) seviye barı — eğitim kademesi ve CEFR dil seviyesi için.
 *
 * Değerler ayrık olduğu için sürükleme en yakın durağa oturur. Duraklar aynı
 * zamanda tıklanabilir (bar sürüklemek istemeyen kullanıcı doğrudan seçebilsin);
 * seçili durağın tam adı barın altında büyük olarak yazılır.
 * null = "seçilmedi", filtre uygulanmaz.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { pulseScene, hexToRgb01 } from '@/components/scene/sceneBus'

export type Stop = { value: string; short: string; label: string; icon?: string }

export default function StepSlider({
  stops, value, onChange, label, hint, accent = '#2BE0C8',
}: {
  stops: Stop[]
  value: string | null
  onChange: (v: string | null) => void
  label: string
  hint?: string
  accent?: string
}) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)
  const [dragging, setDragging] = useState(false)

  const index = value === null ? -1 : stops.findIndex(s => s.value === value)
  const active = index >= 0
  const ratio = index < 0 ? 0 : index / (stops.length - 1)

  const commit = useCallback((next: string) => {
    onChange(next)
    if (!draggingRef.current) pulseScene({ color: hexToRgb01(accent), strength: 0.8 })
  }, [onChange, accent])

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
    function up() {
      if (!draggingRef.current) return
      draggingRef.current = false
      setDragging(false)
      pulseScene({ color: hexToRgb01(accent), strength: 0.7 })
    }
    window.addEventListener('pointermove', move, { passive: false })
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
  }, [setFromClientX, accent])

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
        marginBottom: 6, gap: 12,
      }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-hi)' }}>{label}</span>
        {active ? (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="ghost-btn"
            style={{
              fontSize: 11, color: 'var(--text-low)', background: 'none',
              border: 'none', cursor: 'pointer', padding: 0,
            }}
          >
            temizle
          </button>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-low)' }}>{hint ?? 'opsiyonel'}</span>
        )}
      </div>

      {/* Seçili durağın tam adı — barın kendisi kısa etiket gösteriyor */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 9,
        minHeight: 30, marginBottom: 10,
      }}>
        {active && stops[index].icon && (
          <span style={{ fontSize: 20, lineHeight: 1 }} aria-hidden="true">{stops[index].icon}</span>
        )}
        <span style={{
          fontSize: active ? 19 : 15, fontWeight: 600, letterSpacing: '-0.02em',
          color: active ? accent : 'var(--text-low)',
          transition: 'color 0.2s ease, font-size 0.2s ease',
        }}>
          {active ? stops[index].label : 'Seçilmedi — filtrelenmez'}
        </span>
      </div>

      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={stops.length - 1}
        aria-valuenow={index >= 0 ? index : undefined}
        aria-valuetext={active ? stops[index].label : 'belirtilmedi'}
        onPointerDown={e => {
          draggingRef.current = true
          setDragging(true)
          setFromClientX(e.clientX)
        }}
        onKeyDown={e => {
          if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault()
            commit(stops[Math.min(stops.length - 1, index + 1)].value)
          }
          if ((e.key === 'ArrowLeft' || e.key === 'ArrowDown') && index > 0) {
            e.preventDefault()
            commit(stops[index - 1].value)
          }
          if (e.key === 'Home') { e.preventDefault(); commit(stops[0].value) }
          if (e.key === 'End')  { e.preventDefault(); commit(stops[stops.length - 1].value) }
        }}
        className="range-track"
        style={{ position: 'relative', height: 34, cursor: 'grab', touchAction: 'none' }}
      >
        <div style={{
          position: 'absolute', top: 13, left: 0, right: 0, height: 8, borderRadius: 999,
          background: 'rgba(255,255,255,0.09)',
          border: '1px solid rgba(255,255,255,0.06)',
        }} />
        <div style={{
          position: 'absolute', top: 13, left: 0, height: 8, borderRadius: 999,
          width: `${ratio * 100}%`,
          background: active
            ? `linear-gradient(90deg, ${accent}55 0%, ${accent} 100%)`
            : 'transparent',
          boxShadow: active ? `0 0 20px ${accent}88` : 'none',
          transition: dragging ? 'none' : 'width 0.22s cubic-bezier(0.16,1,0.3,1)',
        }} />

        {/* Duraklar tıklanabilir — sürüklemek zorunda değilsin */}
        {stops.map((s, i) => {
          const passed = active && i <= index
          return (
            <button
              key={s.value}
              type="button"
              tabIndex={-1}
              aria-label={s.label}
              onClick={e => { e.stopPropagation(); commit(s.value) }}
              onPointerDown={e => e.stopPropagation()}
              style={{
                position: 'absolute', top: 8, left: `${(i / (stops.length - 1)) * 100}%`,
                width: 18, height: 18, marginLeft: -9, padding: 0,
                borderRadius: '50%', cursor: 'pointer',
                background: 'transparent', border: 'none',
                display: 'grid', placeItems: 'center',
              }}
            >
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: passed ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.28)',
                transition: 'background 0.2s ease',
              }} />
            </button>
          )
        })}

        <div
          className="range-thumb"
          data-active={active ? 'true' : 'false'}
          style={{
            position: 'absolute', top: 3, left: `calc(${ratio * 100}% - 14px)`,
            width: 28, height: 28, borderRadius: '50%',
            background: active
              ? 'linear-gradient(150deg, #FFFFFF 0%, #CFF6EE 100%)'
              : 'rgba(255,255,255,0.16)',
            border: `2px solid ${active ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.26)'}`,
            boxShadow: active ? `0 8px 22px -6px ${accent}` : '0 2px 8px rgba(0,0,0,0.5)',
            opacity: active ? 1 : 0.65,
            pointerEvents: 'none',
            transform: dragging ? 'scale(1.14)' : 'scale(1)',
            transition: dragging
              ? 'transform 0.12s ease'
              : 'left 0.22s cubic-bezier(0.16,1,0.3,1), transform 0.18s ease, opacity 0.2s ease',
          }}
        />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, gap: 4 }}>
        {stops.map((s, i) => (
          <span
            key={s.value}
            style={{
              fontSize: 10.5,
              fontWeight: active && i === index ? 700 : 500,
              color: active && i === index ? accent : 'var(--text-low)',
              transition: 'color 0.2s ease',
              textAlign: 'center',
            }}
          >
            {s.short}
          </span>
        ))}
      </div>
    </div>
  )
}
