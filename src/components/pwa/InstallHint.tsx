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
 * KAPATMA YOK (bilinçli tercih). Şerit kalıcı; "Kapat" düğmesi ve
 * localStorage'daki kapatma işareti kaldırıldı. Tek tıkla sonsuza kadar
 * kaybolması, yanlışlıkla kapatan kullanıcının uygulamayı bir daha asla
 * kuramaması demekti.
 *
 * Yine de iki durumda görünmüyor ve bunlar "kapatma" değil, bağlam:
 *   • Uygulama olarak açılmışsa (standalone) — zaten içindesin.
 *   • Kurulum bu oturumda tamamlandıysa (`appinstalled`) — iş bitti.
 *
 * Şerit ekranın altına sabitlendiği için, göründüğü sürece <body>'ye alt
 * boşluk ekliyor; yoksa sayfanın son satırını kalıcı olarak örterdi.
 */

import { useEffect, useRef, useState } from 'react'

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
  // Hem şeridin tamamı hem içindeki düğme install()'ı çağırıyor. Tıklama
  // yukarı kabarırsa ikisi birden tetiklenir ve Chrome `prompt()` ikinci kez
  // çağrılınca hata veriyor. Bu bayrak tek çağrıyı garanti ediyor.
  const kuruluyor = useRef(false)

  useEffect(() => {
    // Zaten uygulama olarak açılmışsa ipucunun anlamı yok.
    const standalone = window.matchMedia('(display-mode: standalone)').matches
      || (window.navigator as Navigator & { standalone?: boolean }).standalone === true
    if (standalone) return

    // Eski sürümlerin bıraktığı kapatma işaretleri artık okunmuyor; tarayıcıda
    // ölü kayıt kalmasın diye siliniyor.
    try {
      localStorage.removeItem('fe-install-hint-dismissed')
      localStorage.removeItem('fe-install-hint-dismissed-v2')
    } catch { /* depolama kapalıysa geç */ }

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

  async function install() {
    const deferred = window.__feInstallPrompt
    if (!deferred || kuruluyor.current) return
    kuruluyor.current = true
    await deferred.prompt()
    const { outcome } = await deferred.userChoice
    window.__feInstallPrompt = null
    kuruluyor.current = false
    // Kullanıcı istemi reddederse şerit kalır (elle kurulum hâlâ mümkün);
    // kabul ederse `appinstalled` olayı zaten gizleyecek.
    if (outcome === 'accepted') setMode(null)
    else setMode('manual')
  }

  // Şerit kalıcı ve `position: fixed`. Alt boşluk eklenmezse sayfanın son
  // satırını (sonuç ekranındaki e-posta kutusu, formun "Fırsatları göster"
  // düğmesi) sürekli örter.
  useEffect(() => {
    if (!mode) return
    const onceki = document.body.style.paddingBottom
    document.body.style.paddingBottom = '96px'
    return () => { document.body.style.paddingBottom = onceki }
  }, [mode])

  if (!mode) return null

  const aciklama = mode === 'ios'
    ? 'Paylaş ⎋ menüsünden "Ana Ekrana Ekle" seçeneğine dokun.'
    : mode === 'manual'
      ? 'Tarayıcı menüsünden ⋮ "Uygulamayı yükle" ya da "Ana ekrana ekle" seçeneğine dokun.'
      : 'Ana ekranından tek dokunuşla aç, tarayıcı aramana gerek kalmasın.'

  const kurulabilir = mode === 'prompt'

  return (
    <div
      role={kurulabilir ? undefined : 'complementary'}
      aria-label="Uygulamayı ana ekrana ekle"
      // İstem hazırsa şeridin TAMAMI tıklanabilir: küçük ekranda 9px'lik
      // düğmeyi ıskalamak kolay, tek dokunuşla kurulum bekleniyor.
      onClick={kurulabilir ? install : undefined}
      style={{
        position: 'fixed', left: 12, right: 12, bottom: 12, zIndex: 60,
        cursor: kurulabilir ? 'pointer' : 'default',
        maxWidth: 560, margin: '0 auto',
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        padding: '12px 14px', borderRadius: 18,
        background: 'rgba(13, 10, 38, 0.92)',
        backdropFilter: 'blur(18px)',
        border: '1px solid rgba(255,255,255,0.14)',
        boxShadow: '0 24px 50px -24px rgba(0,0,0,0.9)',
      }}
    >
      {/* next/image kullanılmıyor: 34px sabit, layout hesabı gerektirmiyor. */}
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

      {mode === 'prompt' && (
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
          <button
            type="button"
            onClick={e => { e.stopPropagation(); install() }}
            style={{
              fontSize: 12.5, fontWeight: 700, padding: '9px 18px', borderRadius: 999,
              border: 'none', cursor: 'pointer', color: '#150F35',
              background: 'linear-gradient(115deg, #7C5CFF 0%, #9B6BFF 42%, #2BE0C8 100%)',
            }}
          >
            Ekle
          </button>
        </div>
      )}
    </div>
  )
}
