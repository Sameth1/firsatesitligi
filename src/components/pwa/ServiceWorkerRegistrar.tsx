'use client'

/**
 * Service worker'ı kaydeder. Görsel çıktısı yok.
 *
 * Neden bir bileşen: SW kaydı yalnız tarayıcıda ve sayfa yerleştikten sonra
 * anlamlı. Kayıt başarısız olursa (eski tarayıcı, kapalı depolama, güvensiz
 * bağlam) site normal çalışmaya devam eder — SW ilerlemeci bir iyileştirme.
 */

import { useEffect } from 'react'

export default function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    // Geliştirmede kaydetme: Next dev sunucusu HMR ile çalışıyor, araya giren
    // bir önbellek hata ayıklamayı zorlaştırır.
    if (process.env.NODE_ENV !== 'production') return

    const onLoad = () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Sessiz: kayıt olmazsa site SW'siz çalışır, kullanıcıya söylenecek
        // bir şey yok.
      })
    }

    if (document.readyState === 'complete') onLoad()
    else window.addEventListener('load', onLoad)
    return () => window.removeEventListener('load', onLoad)
  }, [])

  return null
}
