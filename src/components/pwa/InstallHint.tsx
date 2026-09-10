'use client'

/**
 * "Ana ekrana ekle" ipucu.
 *
 * Neden iki ayrı yol: Chrome/Android `beforeinstallprompt` olayını verir ve
 * kendi istemini açabiliriz. Safari iOS bu olayı HİÇ vermez (Next'in PWA
 * rehberi de bunu ayrıca uyarıyor) — orada kullanıcıya Paylaş menüsünü tarif
 * etmekten başka yol yok.
 *
 * UX kuralı 3 (“engel koyma”): bu bir modal değil, kapatılabilir bir şerit.
 * Kapatılırsa localStorage'a yazılır ve bir daha gösterilmez; zaten kurulu
 * olan (standalone) kullanıcıya hiç görünmez.
 */

import { useEffect, useState } from 'react'

const DISMISS_KEY = 'fe-install-hint-dismissed'

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export default function InstallHint() {
  const [deferred, setDeferred] = useState<InstallPromptEvent | null>(null)
  const [isIos, setIsIos] = useState(false)
  const [show, setShow] = useState(false)

  useEffect(() => {
    // Zaten uygulama olarak açılmışsa ipucunun anlamı yok.
    const standalone = window.matchMedia('(display-mode: standalone)').matches
      || (window.navigator as Navigator & { standalone?: boolean }).standalone === true
    if (standalone) return

    let dismissed = false
    try {
      dismissed = localStorage.getItem(DISMISS_KEY) === '1'
    } catch {
      // Depolama kapalıysa (gizli sekme, katı gizlilik ayarı) ipucu gösterilir;
      // kapatma kalıcı olmaz ama hiçbir şey kırılmaz.
    }
    if (dismissed) return

    const ios = /iphone|ipad|ipod/i.test(navigator.userAgent)
      && !/crios|fxios/i.test(navigator.userAgent)
    if (ios) {
      // queueMicrotask: effect gövdesinde senkron setState zincirleme render
      // tetikliyor (react-hooks/set-state-in-effect). Admin ekranlarındaki
      // mevcut desenle aynı.
      queueMicrotask(() => { setIsIos(true); setShow(true) })
      return
    }

    // Olay dinleyicisinden gelen setState effect gövdesinde değil, sorun yok.
    const onPrompt = (e: Event) => {
      e.preventDefault()               // tarayıcının kendi istemini erteler
      setDeferred(e as InstallPromptEvent)
      setShow(true)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)

    const onInstalled = () => setShow(false)
    window.addEventListener('appinstalled', onInstalled)

    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  function dismiss() {
    setShow(false)
    try { localStorage.setItem(DISMISS_KEY, '1') } catch { /* depolama yoksa geç */ }
  }

  async function install() {
    if (!deferred) return
    await deferred.prompt()
    await deferred.userChoice
    setDeferred(null)
    dismiss()
  }

  if (!show) return null

  return (
    <div
      role="complementary"
      aria-label="Uygulamayı ana ekrana ekle"
      style={{
        position: 'fixed', left: 12, right: 12, bottom: 12, zIndex: 60,
        maxWidth: 560, margin: '0 auto',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        padding: '12px 14px', borderRadius: 18,
        background: 'rgba(13, 10, 38, 0.92)',
        backdropFilter: 'blur(18px)',
        border: '1px solid rgba(255,255,255,0.14)',
        boxShadow: '0 24px 50px -24px rgba(0,0,0,0.9)',
      }}
    >
      {/* next/image kullanılmıyor: 34px sabit, layout hesabı gerektirmiyor ve
          bu şerit yalnız kurulmamış kullanıcılara bir kez görünüyor. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/app-icons/icon-192.png" alt="" width={34} height={34}
           style={{ borderRadius: 9, flexShrink: 0 }} />

      <div style={{ flex: '1 1 220px', minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: '#F4F2FF', marginBottom: 2 }}>
          Uygulama olarak ekle
        </div>
        <div style={{ fontSize: 12, color: '#B3ACDE', lineHeight: 1.5 }}>
          {isIos
            ? 'Paylaş ⎋ menüsünden "Ana Ekrana Ekle" seçeneğine dokun.'
            : 'Ana ekranından tek dokunuşla aç, tarayıcı aramana gerek kalmasın.'}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
        {!isIos && deferred && (
          <button
            type="button"
            onClick={install}
            style={{
              fontSize: 12.5, fontWeight: 700, padding: '9px 18px', borderRadius: 999,
              border: 'none', cursor: 'pointer', color: '#150F35',
              background: 'linear-gradient(115deg, #7C5CFF 0%, #9B6BFF 42%, #2BE0C8 100%)',
            }}
          >
            Ekle
          </button>
        )}
        <button
          type="button"
          onClick={dismiss}
          aria-label="İpucunu kapat"
          style={{
            fontSize: 12.5, fontWeight: 600, padding: '9px 14px', borderRadius: 999,
            border: '1px solid rgba(255,255,255,0.16)', cursor: 'pointer',
            color: '#B3ACDE', background: 'transparent',
          }}
        >
          Kapat
        </button>
      </div>
    </div>
  )
}
