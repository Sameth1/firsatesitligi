'use client'

/**
 * Form ve sonuç ekranlarının arkasında süzülen eğitim/burs motifleri.
 *
 * Neden SVG: tema hissini taşımak için ikinci bir WebGL sahnesi açmak pahalı;
 * bunlar birkaç yüz baytlık vektör, GSAP ile hareket ediyor ve içerik sütununun
 * dışında, düşük opaklıkta durduğu için okunabilirliği bozmuyor. Dar ekranlarda
 * (içerik sütunu tüm genişliği kapladığında) gizlenir.
 */

import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

const CAP = (
  <path d="M32 6 2 20l30 14 30-14L32 6Zm0 32L14 30v12c0 4 8 8 18 8s18-4 18-8V30L32 38Z" />
)
const BOOK = (
  <path d="M8 8h18c4 0 6 2 6 5v42c0-3-2-5-6-5H8V8Zm48 0H38c-4 0-6 2-6 5v42c0-3 2-5 6-5h18V8Z" />
)
const GLOBE = (
  <path d="M32 4a28 28 0 1 0 0 56 28 28 0 0 0 0-56Zm0 4c4 0 9 8 9 20s-5 20-9 20-9-8-9-20 5-20 9-20ZM9 32c0-3 .5-6 1.5-9h43c1 3 1.5 6 1.5 9s-.5 6-1.5 9h-43C9.5 38 9 35 9 32Z" />
)
const COMPASS = (
  <path d="M32 4a28 28 0 1 0 0 56 28 28 0 0 0 0-56Zm0 6a22 22 0 1 1 0 44 22 22 0 0 1 0-44Zm10 12L26 28l-4 16 16-6 4-16Zm-10 8a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z" />
)
const STAMP = (
  <path d="M32 6c-6 0-10 4-10 9 0 4 2 6 2 9H16c-4 0-6 2-6 6v8h44v-8c0-4-2-6-6-6H40c0-3 2-5 2-9 0-5-4-9-10-9ZM10 44v6c0 3 2 5 5 5h34c3 0 5-2 5-5v-6H10Z" />
)

type Glyph = {
  path: React.ReactNode
  top: string
  left?: string
  right?: string
  size: number
  color: string
  rotate: number
  depth: number   // parallax katsayısı
}

const GLYPHS: Glyph[] = [
  { path: CAP,     top: '8%',  left: '4%',  size: 96,  color: '#534AB7', rotate: -12, depth: 0.22 },
  { path: GLOBE,   top: '26%', right: '5%', size: 118, color: '#17A79A', rotate: 8,   depth: 0.34 },
  { path: BOOK,    top: '52%', left: '6%',  size: 84,  color: '#C9539C', rotate: 10,  depth: 0.28 },
  { path: COMPASS, top: '70%', right: '7%', size: 92,  color: '#534AB7', rotate: -6,  depth: 0.4 },
  { path: STAMP,   top: '88%', left: '8%',  size: 76,  color: '#0F6E56', rotate: 14,  depth: 0.24 },
]

export default function ThemeGlyphs() {
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    gsap.registerPlugin(ScrollTrigger)

    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>('[data-glyph]').forEach(el => {
        const depth = Number(el.dataset.depth ?? 0.25)

        // kaydırmaya bağlı parallax
        gsap.to(el, {
          yPercent: -depth * 100,
          ease: 'none',
          scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: 0.6 },
        })

        // yerinde yavaş salınım
        gsap.to(el, {
          rotation: `+=${depth > 0.3 ? 10 : -8}`,
          y: depth > 0.3 ? 14 : -12,
          duration: 6 + depth * 6,
          repeat: -1,
          yoyo: true,
          ease: 'sine.inOut',
        })
      })
    }, rootRef)

    return () => ctx.revert()
  }, [])

  return (
    <div
      ref={rootRef}
      aria-hidden="true"
      className="theme-glyphs"
      style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}
    >
      {GLYPHS.map((g, i) => (
        <svg
          key={i}
          data-glyph
          data-depth={g.depth}
          viewBox="0 0 64 64"
          width={g.size}
          height={g.size}
          fill={g.color}
          style={{
            position: 'absolute',
            top: g.top,
            left: g.left,
            right: g.right,
            opacity: 0.085,
            transform: `rotate(${g.rotate}deg)`,
          }}
        >
          {g.path}
        </svg>
      ))}
    </div>
  )
}
