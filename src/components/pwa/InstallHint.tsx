'use client'

/**
 * "Ana ekrana ekle" ipucu.
 *
 * ÜÇ AYRI YOL, çünkü tarayıcılar aynı davranmıyor:
 *
 *  1. Chrome / Edge — `beforeinstallprompt` olayını verir ve kendi istemimizi
 *     açabiliriz. AMA olay hidrasyondan ÖNCE tetikleniyor: dinleyiciyi
 *     `useEffect` içinde bağlamak geç kalıyordu ve şerit hiç görünmüyordu.
 *     Olayı artık layout'taki satır içi script yakalayıp
 *     `window.__feInstallPrompt`'a koyuyor; burada ona bakıyoruz.
 *
 *  2. Safari iOS — bu olayı HİÇ vermez. Kullanıcıya Paylaş menüsünü tarif
 *     etmekten başka yol yok.
 *
 *  3. Olay hiç gelmeyen diğer durumlar — Chrome kurulabilirlik ölçütlerini
 *     kendi zamanlamasıyla değerlendiriyor ve olayı bazen hiç göndermiyor
 *     (etkileşim geçmişi yetersizse, Firefox'ta hiç yok). Bu durumda
 *     FALLBACK_MS sonra tarayıcı menüsünü tarif eden bir şerit gösteriyoruz;
 *     "Ekle" düğmesi olmadan, çünkü elimizde açacak bir istem yok.
 *
 * UX kuralı 3 ("engel koyma"): bu bir modal değil, kapatılabilir bir şerit.
 * Kapatılırsa localStorage'a yazılır ve bir daha gösterilmez; zaten uygulama
 * olarak açılmış (standalone) kullanıcıya hiç görünmez.
 */

import { useEffect, useState } from 'react'

/**
 * Anahtar SÜRÜMLÜ. Neden: şerit uzun süre Chrome'da hiç görünmüyordu
 * (beforeinstallprompt hidrasyondan önce geliyordu ve kaçırılıyordu, bkz.
 * layout.tsx). O dönemde depolanmış "kapatıldı" işaretleri artık anlamsız —
 * kullanıcı çalışan bir şeridi değil, bozuk bir şeridi kapatmış. Sürümü
 * yükseltmek herkese bir kez daha şans veriyor; yeni kapatmalar v2'ye
 * yazıldığı için kalıcı oluyor.
 *
 * ESKİ ANAHTAR TEMİZLENİYOR: bırakılırsa tarayıcıda ölü bir kayıt kalır.
 */
const DISMISS_KEY = 'fe-install-hint-dismissed-v2'
const LEGACY_DISMISS_KEY = 'fe-install-hint-dismissed'
/**
 * Olay gelmezse elle tarif eden şeridi bu kadar sonra göster.
 *
 * 12 saniyeydi ve pratikte "hiç gelmiyor" demekti: kullanıcı sayfayı açıp
 * bakıyor, şerit yok, sekmeyi kapatıyor. Chrome kurulabilirlik ölçütleri
 * karşılanıyorsa `beforeinstallprompt`'u yüklemeden sonra bir iki saniye
 * içinde gönderiyor; o süre içinde gelmediyse bu sayfa görüntülemesinde
 * gelmeyecek demektir. Olay yine de sonradan gelirse mod 'prompt'a yükselir
 * ve "Ekle" düğmesi belirir.
 */
const FALLBACK_MS = 3_500

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

declare global {
  interface Window {
    __feInstallPrompt?: InstallPromptEvent | null
  }
}

type Mode = 'prompt' | 'ios' | 'manual'

export default function InstallHint() {
  const [mode, setMode] = useState<Mode | null>(null)

  useEffect(() => {
    // Zaten uygulama olarak açılmışsa ipucunun anlamı yok.
    const standalone = window.matchMedia('(display-mode: standalone)').matches
      || (window.navigator as Navigator & { standalone?: boolean }).standalone === true
    if (standalone) return

    let dismissed = false
    try {
      dismissed = localStorage.getItem(DISMISS_KEY) === '1'
      localStorage.removeItem(LEGACY_DISMISS_KEY)
    } catch {
      // Depolama kapalıysa (gizli sekme, katı gizlilik ayarı) ipucu gösterilir;
      // kapatma kalıcı olmaz ama hiçbir şey kırılmaz.
    }
    if (dismissed) return

    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent)
      && !/crios|fxios/i.test(navigator.userAgent)

    // queueMicrotask: effect gövdesinde senkron setState zincirleme render
    // tetikliyor (react-hooks/set-state-in-effect).
    if (isIos) {
      queueMicrotask(() => setMode('ios'))
      return
    }

    // Hidrasyondan önce yakalanmış bir istem var mı?
    if (window.__feInstallPrompt) {
      queueMicrotask(() => setMode('prompt'))
      return
    }

    const onReady = () => setMode('prompt')
    const onDone = () => setMode(null)
    window.addEventListener('fe-install-ready', onReady)
    window.addEventListener('fe-install-done', onDone)
    // Satır içi script çalışmadıysa (CSP, eski deploy) doğrudan da dinle.
    window.addEventListener('beforeinstallprompt', onReady)

    // Olay hiç gelmezse elle tarif et.
    const timer = window.setTimeout(() => {
      setMode(current => current ?? 'manual')
    }, FALLBACK_MS)

    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('fe-install-ready', onReady)
      window.removeEventListener('fe-install-done', onDone)
      window.removeEventListener('beforeinstallprompt', onReady)
    }
  }, [])

  function dismiss() {
    setMode(null)
    try { localStorage.setItem(DISMISS_KEY, '1') } catch { /* depolama yoksa geç */ }
  }

  async function install() {
    const deferred = window.__feInstallPrompt
    if (!deferred) return
    await deferred.prompt()
    await deferred.userChoice
    window.__feInstallPrompt = null
    dismiss()
  }

  if (!mode) return null

  const aciklama = mode === 'ios'
    ? 'Paylaş ⎋ menüsünden "Ana Ekrana Ekle" seçeneğine dokun.'
    : mode === 'manual'
      ? 'Tarayıcı menüsünden ⋮ "Uygulamayı yükle" ya da "Ana ekrana ekle" seçeneğine dokun.'
      : 'Ana ekranından tek dokunuşla aç, tarayıcı aramana gerek kalmasın.'

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
          {aciklama}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
        {mode === 'prompt' && (
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
