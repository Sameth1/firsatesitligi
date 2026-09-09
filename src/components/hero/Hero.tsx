'use client'

/**
 * Açılış sahnesi — WebGL arka plan + GSAP ile koreografi.
 * İçerik metni DOM'da düz metin olarak durur (SEO/GEO için önemli); GSAP yalnız
 * görünürlük/dönüşüm animasyonu ekler, metni parçalayıp yeniden yazmaz.
 */

import { useEffect, useRef } from 'react'
import dynamic from 'next/dynamic'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import {
  claimFlight,
  releaseFlight,
  setFlightActive,
  setFlightProgress,
  whenFlightSceneReady,
} from './flightBus'

// WebGL yalnız istemcide — SSR'da canvas oluşturulmaz.
const HeroCanvas = dynamic(() => import('./HeroCanvas'), { ssr: false })

const HEADLINE = ['Yurt', 'dışı', 'ayrıcalık', 'değil,', 'senin', 'hakkın.']

export default function Hero({ onStart }: { onStart: () => void }) {
  const rootRef = useRef<HTMLElement>(null)

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger)

    let cancelWaitForScene: (() => void) | null = null
    let readyTimer = 0
    let intro: gsap.core.Timeline | null = null

    const ctx = gsap.context(() => {
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

      // Animasyonsuz hâl: her şey yerinde ve okunur. Uçuş hiç başlamadığı için
      // flightBus `active: false` kalır ve HeroCanvas uçağı çizmez.
      const revealAll = () => gsap.set('[data-fx]', {
        opacity: 1, y: 0, yPercent: 0, clipPath: 'inset(0% 0 0 0)',
      })

      if (reduced) {
        revealAll()
        return
      }

      // Uçuş yalnız ilk açılışta. Sonraki mount'larda içerik anında görünür.
      if (!claimFlight()) {
        revealAll()
      } else {
        /**
         * Uçak ile kelimeler TEK zaman hattından beslenir.
         *
         * Uçuş eğrisi ekranın soluna taşan bir noktadan başlar; `t` ~0.15'te
         * kadraja girer, ~0.32–0.65 arasında başlık bandını soldan sağa kat
         * eder, ~0.82'de sağdan çıkar. Kelime stagger'ı bilerek bu aralığa
         * (0.76s → 1.56s) oturtuldu: her kelime, uçak üstünden geçtikten hemen
         * sonra izin içinde yukarı doğru açılır.
         */
        const FLIGHT_DURATION = 2.4
        const flight = { t: 0 }

        intro = gsap.timeline({
          defaults: { ease: 'power3.out' },
          onComplete: () => setFlightActive(false),
        })

        intro
          .to(flight, {
            t: 1,
            duration: FLIGHT_DURATION,
            ease: 'none', // eğri yay-uzunluğuna göre örneklendiği için sabit hız
            onStart: () => { setFlightProgress(0); setFlightActive(true) },
            onUpdate: () => setFlightProgress(flight.t),
          }, 0)
          .fromTo('[data-fx="eyebrow"]',
            { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.55 }, 0)
          // uçağın izinde: 6 kelime × 0.16s = uçağın bandı kat ettiği süre
          .fromTo('[data-fx="word"]',
            { opacity: 0, yPercent: 115 },
            { opacity: 1, yPercent: 0, duration: 0.6, stagger: 0.16 }, 0.76)
          .fromTo('[data-fx="sub"]',
            { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.65 }, 1.55)
          .fromTo('[data-fx="cta"]',
            { opacity: 0, y: 18, scale: 0.96 },
            { opacity: 1, y: 0, scale: 1, duration: 0.55 }, 1.75)
          .fromTo('[data-fx="proof"] > *',
            { opacity: 0, y: 12 },
            { opacity: 1, y: 0, duration: 0.5, stagger: 0.08 }, 1.95)
          .fromTo('[data-fx="cue"]', { opacity: 0 }, { opacity: 1, duration: 0.5 }, 2.15)

        // WebGL katmanı dinamik import; hazır olmadan başlarsak uçuşun ilk
        // kareleri kaçar. Sahne gelmezse (WebGL yok) 600ms'te yine de başlar.
        intro.pause(0)
        let started = false
        const start = () => {
          if (started || !intro) return
          started = true
          intro.play(0)
        }
        cancelWaitForScene = whenFlightSceneReady(start)
        readyTimer = window.setTimeout(start, 600)
      }

      // kaydırınca içerik yukarı süzülür — hero ile form arasında derinlik
      gsap.to('[data-fx="stack"]', {
        yPercent: -14,
        opacity: 0.15,
        ease: 'none',
        scrollTrigger: {
          trigger: rootRef.current,
          start: 'top top',
          end: 'bottom top',
          scrub: 0.4,
        },
      })

      // aşağı ok sürekli nefes alsın
      gsap.to('[data-fx="cue"] span', {
        y: 7,
        repeat: -1,
        yoyo: true,
        duration: 1.1,
        ease: 'sine.inOut',
      })
    }, rootRef)

    return () => {
      cancelWaitForScene?.()
      window.clearTimeout(readyTimer)
      // Uçuş bitmeden söküldüyse (StrictMode çift-mount, hızlı route geçişi)
      // hakkı geri ver; bittiyse bir daha oynamasın.
      if (intro && intro.progress() < 1) releaseFlight()
      else setFlightActive(false)
      ctx.revert()
    }
  }, [])

  return (
    <section
      ref={rootRef}
      onClick={onStart}
      style={{
        position: 'relative',
        minHeight: '100svh',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        isolation: 'isolate',
      }}
    >
      <HeroCanvas />

      <div
        data-fx="stack"
        style={{
          position: 'relative', zIndex: 1,
          width: '100%', maxWidth: 860,
          padding: '0 24px',
          textAlign: 'center',
          color: '#fff',
        }}
      >
        <div
          data-fx="eyebrow"
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase',
            fontWeight: 600, color: 'rgba(255,255,255,0.92)',
            background: 'rgba(255,255,255,0.14)',
            border: '1px solid rgba(255,255,255,0.28)',
            backdropFilter: 'blur(8px)',
            padding: '7px 16px', borderRadius: 999, marginBottom: 26,
          }}
        >
          <span className="fx-pulse-dot" style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#5BE8C8', display: 'inline-block',
          }} />
          Ücretsiz · Hesap gerektirmez
        </div>

        <h1 style={{
          fontSize: 'clamp(34px, 7.2vw, 76px)',
          lineHeight: 1.02,
          fontWeight: 600,
          letterSpacing: '-0.035em',
          margin: '0 0 22px',
          color: '#fff',
          textWrap: 'balance',
          textShadow: '0 2px 30px rgba(24, 16, 74, 0.35)',
        }}>
          {HEADLINE.map((word, i) => (
            <span key={i} style={{ display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom' }}>
              <span data-fx="word" style={{ display: 'inline-block' }}>
                {word}
              </span>
              {i < HEADLINE.length - 1 && <span>&nbsp;</span>}
            </span>
          ))}
        </h1>

        <p
          data-fx="sub"
          style={{
            fontSize: 'clamp(15px, 2.1vw, 19px)',
            lineHeight: 1.55,
            color: 'rgba(255,255,255,0.88)',
            maxWidth: 620, margin: '0 auto 34px',
          }}
        >
          <span style={{ display: 'block' }}>
            Burs, staj, gönüllülük, yaz okulu ve değişim programları
          </span>
          <span style={{ display: 'block' }}>
            — profilini gir, sana uyanları saniyeler içinde gör.
          </span>
        </p>

        <div data-fx="cta">
          <button
            onClick={onStart}
            className="hero-cta"
            style={{
              fontSize: 15, fontWeight: 600,
              padding: '15px 34px', borderRadius: 999,
              border: 'none', cursor: 'pointer',
              color: '#2A2470',
              background: 'linear-gradient(120deg, #FFFFFF 0%, #E6E2FF 100%)',
              boxShadow: '0 18px 38px -18px rgba(10, 6, 45, 0.75)',
            }}
          >
            Fırsatları keşfet →
          </button>
        </div>

        <div
          data-fx="proof"
          style={{
            display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center',
            marginTop: 30,
          }}
        >
          {['Erasmus+ & ESC', 'DAAD bursları', 'Gönüllülük', 'Yaz okulları'].map(label => (
            <span key={label} style={{
              fontSize: 11.5, fontWeight: 500,
              color: 'rgba(255,255,255,0.9)',
              background: 'rgba(255,255,255,0.12)',
              border: '1px solid rgba(255,255,255,0.22)',
              backdropFilter: 'blur(6px)',
              padding: '6px 13px', borderRadius: 999,
            }}>
              {label}
            </span>
          ))}
        </div>
      </div>

      <button
        data-fx="cue"
        onClick={onStart}
        aria-label="Arama bölümüne in"
        className="hero-cue"
        style={{
          position: 'absolute', bottom: 30, left: '50%', transform: 'translateX(-50%)',
          zIndex: 1, cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', gap: 10,
          fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em',
          color: '#2A2470',
          background: 'rgba(255, 255, 255, 0.82)',
          border: '1px solid rgba(83, 74, 183, 0.22)',
          backdropFilter: 'blur(10px)',
          padding: '13px 26px', borderRadius: 999,
          boxShadow: '0 14px 30px -16px rgba(24, 16, 74, 0.5)',
          whiteSpace: 'nowrap',
        }}
      >
        Aşağı kaydır
        <span style={{ display: 'inline-block', fontSize: 19, lineHeight: 1 }}>↓</span>
      </button>
    </section>
  )
}
